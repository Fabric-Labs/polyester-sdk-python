from __future__ import annotations

import asyncio
import hashlib
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, NoReturn
from urllib.parse import parse_qsl, quote_from_bytes, unquote_to_bytes, urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.errors import (
    PolyesterAuthError,
    PolyesterRateLimitError,
    PolyesterTransportError,
    PolyesterValidationError,
)

API_KEY_ID_ENV = "POLYESTER_API_KEY_ID"
API_PRIVATE_KEY_ENV = "POLYESTER_API_PRIVATE_KEY"
ACCOUNT_ID_ENV = "POLYESTER_ACCOUNT_ID"
MAX_SIGNING_FUTURE_SKEW_MS = 5_000
_MAX_SIGNING_BACKPRESSURE_SECONDS = 10.0


_NOT_SERIALIZABLE = (
    "ApiKeyCredentials holds an API private key and cannot be pickled, deep-copied, "
    "or converted with dataclasses.asdict or astuple"
)


def _refuse_serialization() -> NoReturn:
    raise TypeError(_NOT_SERIALIZABLE)


class _LoopGate:
    """FIFO queue for one event loop's async signers, counted by its users."""

    __slots__ = ("lock", "users")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.users = 0


class _SigningTimestampAllocator:
    """Allocate distinct millisecond timestamps without exceeding clock skew.

    One allocator serves every credentials object for an API key ID in this
    process, because the server rejects a repeated (API key, signature) pair.
    """

    def __init__(self) -> None:
        self._last_timestamp_ms = 0
        self._lock = threading.Lock()
        # An asyncio lock belongs to one event loop, and every sync client runs
        # its own, so async waiters queue on a gate per loop; ``_lock`` orders
        # all loops. A gate exists only while a coroutine on its loop waits:
        # its lock references the loop, and this allocator lives as long as
        # the process, so a kept gate would keep a closed loop alive.
        self._async_gates: dict[asyncio.AbstractEventLoop, _LoopGate] = {}

    def __reduce_ex__(self, protocol: Any) -> NoReturn:
        _refuse_serialization()

    def __deepcopy__(self, memo: Any) -> NoReturn:
        _refuse_serialization()

    def _enter_async_gate(self, loop: asyncio.AbstractEventLoop) -> _LoopGate:
        with self._lock:
            gate = self._async_gates.get(loop)
            if gate is None:
                gate = self._async_gates[loop] = _LoopGate()
            gate.users += 1
            return gate

    def _leave_async_gate(self, loop: asyncio.AbstractEventLoop, gate: _LoopGate) -> None:
        with self._lock:
            gate.users -= 1
            if gate.users == 0:
                del self._async_gates[loop]

    def next(self) -> int:
        """Allocate immediately or fail with retryable capacity backpressure.

        Synchronous callers must never sleep an async executor thread. Async
        SDK transports use :meth:`next_async`, which waits cooperatively.
        """
        return self._try_next()

    async def next_async(self) -> int:
        """Allocate with bounded, cooperative backpressure."""

        async def allocate() -> int:
            loop = asyncio.get_running_loop()
            gate = self._enter_async_gate(loop)
            try:
                async with gate.lock:
                    while True:
                        try:
                            return self._try_next()
                        except PolyesterRateLimitError as exc:
                            await asyncio.sleep(exc.retry_after or 0.001)
            finally:
                self._leave_async_gate(loop, gate)

        try:
            return await asyncio.wait_for(
                allocate(),
                timeout=_MAX_SIGNING_BACKPRESSURE_SECONDS,
            )
        except TimeoutError as exc:
            raise PolyesterRateLimitError(
                "signing timestamp capacity exhausted; retry after clock advances",
                retry_after=0.001,
            ) from exc

    def _try_next(self) -> int:
        now = time.time_ns() // 1_000_000
        if now < 0:
            raise PolyesterTransportError("system clock is before UNIX_EPOCH")
        with self._lock:
            candidate = max(now, self._last_timestamp_ms + 1)
            if candidate <= now + MAX_SIGNING_FUTURE_SKEW_MS:
                self._last_timestamp_ms = candidate
                return candidate
            wait_seconds = max(0.001, (candidate - (now + MAX_SIGNING_FUTURE_SKEW_MS)) / 1_000)
        raise PolyesterRateLimitError(
            "signing timestamp capacity exhausted; retry after clock advances",
            retry_after=wait_seconds,
        )


_ALLOCATORS: dict[str, _SigningTimestampAllocator] = {}
_ALLOCATORS_LOCK = threading.Lock()


def _allocator_for_key(key_id: str) -> _SigningTimestampAllocator:
    with _ALLOCATORS_LOCK:
        allocator = _ALLOCATORS.get(key_id)
        if allocator is None:
            allocator = _ALLOCATORS[key_id] = _SigningTimestampAllocator()
        return allocator


@dataclass(frozen=True, slots=True)
class ApiKeyCredentials:
    """API-key authentication material.

    Credentials with the same ``key_id`` share timestamp allocation within this
    process, so identical requests never share a signature. The signing
    protocol has no cross-process nonce; use one API key per process.

    ``repr`` and ``str`` redact the private key. Pickling, deep-copying and
    ``dataclasses.asdict``/``astuple`` raise ``TypeError``; read
    ``private_key`` explicitly when you need it.
    """

    key_id: str
    private_key: bytes = field(repr=False)
    _timestamp_allocator: _SigningTimestampAllocator = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "_timestamp_allocator", _allocator_for_key(self.key_id))

    def __repr__(self) -> str:
        return f"ApiKeyCredentials(key_id={self.key_id!r}, private_key='[REDACTED]')"

    def __copy__(self) -> ApiKeyCredentials:
        return self

    def __deepcopy__(self, memo: Any) -> NoReturn:
        _refuse_serialization()

    def __reduce_ex__(self, protocol: Any) -> NoReturn:
        _refuse_serialization()

    def sign_payload(self, payload: bytes) -> bytes:
        """Sign exact protocol-defined business-payload bytes with Ed25519."""
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        key = Ed25519PrivateKey.from_private_bytes(self.private_key)
        return key.sign(payload)


def load_api_key_credentials(
    *,
    api_key_id: str | None = None,
    api_private_key: str | bytes | None = None,
    from_env: bool = True,
) -> ApiKeyCredentials | None:
    key_id = api_key_id
    private = api_private_key
    if from_env:
        key_id = key_id or os.getenv(API_KEY_ID_ENV)
        private = private if private is not None else os.getenv(API_PRIVATE_KEY_ENV)
    if not key_id and not private:
        return None
    if not key_id or private is None:
        if from_env:
            message = "Both POLYESTER_API_KEY_ID and POLYESTER_API_PRIVATE_KEY are required"
        else:
            message = "Both api_key_id and api_private_key are required"
        raise PolyesterAuthError(message)
    return ApiKeyCredentials(key_id=key_id, private_key=normalize_private_key(private))


def normalize_private_key(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        private = value
    else:
        try:
            private = bytes.fromhex(value.strip())
        except ValueError as exc:
            raise PolyesterAuthError(
                "API private key must be a valid hex string or raw bytes"
            ) from exc
    if len(private) != 32:
        raise PolyesterAuthError("Ed25519 API private key must be exactly 32 bytes")
    return private


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    """Generate a new Ed25519 keypair (public, secret), each 32 bytes."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return public_key.public_bytes_raw(), private_key.private_bytes_raw()


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_query(url: str) -> str:
    """Sort decoded key/value bytes before RFC 3986 encoding, as the server does."""
    _validated_url(url)
    # Preserve percent-escaped bytes that are not UTF-8 instead of replacing
    # them. Sort bytes, since surrogate character order is not byte order.
    pairs = sorted(
        (key.encode("utf-8", "surrogateescape"), value.encode("utf-8", "surrogateescape"))
        for key, value in parse_qsl(
            urlsplit(url).query, keep_blank_values=True, errors="surrogateescape"
        )
    )
    return "&".join(
        f"{quote_from_bytes(key, safe='')}={quote_from_bytes(value, safe='')}"
        for key, value in pairs
    )


# Bounds of an API-key request's receive window (``X-API-RECV-WINDOW``), in
# milliseconds. Without the header the server applies 10000.
MIN_RECV_WINDOW_MS = 1
MAX_RECV_WINDOW_MS = 60_000


def validate_recv_window_ms(recv_window_ms: int | None) -> int | None:
    """Check a receive window before anything is signed.

    ``None`` means no window header; any other value must be an ``int`` from
    :data:`MIN_RECV_WINDOW_MS` to :data:`MAX_RECV_WINDOW_MS`. The server refuses
    a header outside that range as ``AUTH_RECV_WINDOW_INVALID``.
    """
    if recv_window_ms is None:
        return None
    if (
        isinstance(recv_window_ms, bool)
        or not isinstance(recv_window_ms, int)
        or not MIN_RECV_WINDOW_MS <= recv_window_ms <= MAX_RECV_WINDOW_MS
    ):
        raise PolyesterValidationError(
            "recv_window_ms must be a whole number of milliseconds from 1 to 60000, or None"
        )
    return recv_window_ms


def canonical_signing_string(
    *,
    timestamp_ms: str,
    method: str,
    url: str,
    body: bytes,
    recv_window_ms: int | None = None,
) -> str:
    """Build the API-key signing payload.

    With ``recv_window_ms``, for a request that sends ``X-API-RECV-WINDOW``, the
    window's decimal string is its own line right after the timestamp.
    """
    window = validate_recv_window_ms(recv_window_ms)
    # The server verifies the decoded path. Keep percent-escaped bytes that are
    # not UTF-8 as surrogates, so signing turns them back into the same bytes.
    pathname = unquote_to_bytes(_validated_url(url).path or "/").decode("utf-8", "surrogateescape")
    lines = [timestamp_ms]
    if window is not None:
        lines.append(str(window))
    lines += [method.upper(), pathname, canonical_query(url), sha256_hex(body)]
    return "\n".join(lines)


def sign_request(
    credentials: ApiKeyCredentials,
    *,
    method: str,
    url: str,
    body: bytes = b"",
    timestamp_ms: str | None = None,
    recv_window_ms: int | None = None,
) -> dict[str, str]:
    """Return API-key headers for a request.

    With ``recv_window_ms`` the server processes the request only until its
    timestamp plus that many milliseconds; the headers then include the signed
    ``X-API-RECV-WINDOW``. A value outside 1 to 60000 raises
    :class:`PolyesterValidationError` before anything is signed.
    """
    validate_recv_window_ms(recv_window_ms)
    timestamp = timestamp_ms or str(credentials._timestamp_allocator.next())
    return _sign_request_at_timestamp(
        credentials,
        method=method,
        url=url,
        body=body,
        timestamp=timestamp,
        recv_window_ms=recv_window_ms,
    )


async def sign_request_async(
    credentials: ApiKeyCredentials,
    *,
    method: str,
    url: str,
    body: bytes = b"",
    timestamp_ms: str | None = None,
    recv_window_ms: int | None = None,
) -> dict[str, str]:
    """Sign without blocking an async runtime while timestamp capacity recovers.

    ``recv_window_ms`` works as for :func:`sign_request`.
    """
    validate_recv_window_ms(recv_window_ms)
    timestamp = timestamp_ms or str(await credentials._timestamp_allocator.next_async())
    return _sign_request_at_timestamp(
        credentials,
        method=method,
        url=url,
        body=body,
        timestamp=timestamp,
        recv_window_ms=recv_window_ms,
    )


def _sign_request_at_timestamp(
    credentials: ApiKeyCredentials,
    *,
    method: str,
    url: str,
    body: bytes,
    timestamp: str,
    recv_window_ms: int | None = None,
) -> dict[str, str]:
    canonical = canonical_signing_string(
        timestamp_ms=timestamp,
        method=method,
        url=url,
        body=body,
        recv_window_ms=recv_window_ms,
    )
    key = Ed25519PrivateKey.from_private_bytes(credentials.private_key)
    signature = key.sign(canonical.encode("utf-8", "surrogateescape")).hex()
    headers = {
        "X-API-KEY-ID": credentials.key_id,
        "X-API-TIMESTAMP": timestamp,
        "X-API-SIGNATURE": signature,
    }
    if recv_window_ms is not None:
        headers["X-API-RECV-WINDOW"] = str(recv_window_ms)
    return headers


def _validated_url(url: str):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        # Never quote the URL: it can carry a password in its userinfo.
        raise PolyesterAuthError("Cannot sign malformed absolute HTTP URL")
    return parsed
