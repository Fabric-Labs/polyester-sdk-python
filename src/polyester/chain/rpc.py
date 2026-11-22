"""Minimal JSON-RPC helpers for chain RPC / bundler / paymaster."""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import httpx

from polyester._answer import retry_after_from_headers
from polyester.user_agent import USER_AGENT, USER_AGENT_HEADER

# Reject oversized JSON-RPC bodies before decode (DoS / memory).
MAX_JSONRPC_RESPONSE_BYTES = 1 * 1024 * 1024
_HTTP_HEADERS = {USER_AGENT_HEADER: USER_AGENT}


class JsonRpcError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class JsonRpcHttpError(JsonRpcError, httpx.HTTPStatusError):
    """A JSON-RPC endpoint's failed HTTP answer. It is the ``httpx.HTTPStatusError``
    httpx raises for it, and keeps the answer's ``status_code`` and the delay it
    asked for with ``Retry-After`` (``retry_after``, seconds, ``None`` without
    one)."""

    def __init__(self, error: httpx.HTTPStatusError) -> None:
        httpx.HTTPStatusError.__init__(
            self, str(error), request=error.request, response=error.response
        )
        self.code = None
        self.data = None
        self.status_code = error.response.status_code
        self.retry_after = retry_after_from_headers(error.response.headers)


def _raise_for_status(response: httpx.Response) -> None:
    """``response.raise_for_status()``, with the answer's metadata on its error.

    It runs as a response hook, when the answer's headers arrive: before its
    body is read and before httpx reads a redirect's ``Location``, so a body
    cut short or a malformed ``Location`` cannot hide the answer. A redirect is
    never followed.
    """
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise JsonRpcHttpError(exc) from exc


async def _araise_for_status(response: httpx.Response) -> None:
    _raise_for_status(response)


class JsonRpcClient:
    def __init__(self, url: str, *, timeout: float = 60.0) -> None:
        self._url = url
        self._timeout = timeout
        # itertools.count next() is atomic under the CPython GIL (thread-safe enough
        # for concurrent request()/arequest() callers sharing one client).
        self._ids = itertools.count(1)

    def request(
        self, method: str, params: list[Any] | None = None, *, timeout: float | None = None
    ) -> Any:
        """Call ``method`` and return its result.

        The call ends within the client's timeout, or within ``timeout``
        seconds when that is shorter; past it, it raises ``JsonRpcError``.
        """
        req_id = next(self._ids)
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or [],
        }
        budget = self._timeout if timeout is None else min(timeout, self._timeout)
        deadline = time.monotonic() + budget
        # httpx Timeout is per-phase, not a total wall clock. Enforce an absolute
        # deadline via a guard that, at ``deadline``, shuts down the connection's
        # socket and closes the client, plus between-chunk checks. The socket is
        # taken from httpcore's trace as soon as the connection is made, so the
        # guard cuts a stall in any phase after connecting: sending the request,
        # partial or complete headers, the body, or a slow drip. Connecting is
        # bounded by the connect timeout, which is the budget.
        with (
            httpx.Client(
                timeout=httpx.Timeout(max(budget, 0.0)),
                headers=_HTTP_HEADERS,
                event_hooks={"response": [_raise_for_status]},
            ) as client,
            _deadline_guard(client, deadline) as guard,
        ):
            try:
                with client.stream(
                    "POST", self._url, json=payload, extensions={"trace": guard.trace}
                ) as response:
                    raw = _read_limited_sync(
                        response,
                        MAX_JSONRPC_RESPONSE_BYTES,
                        deadline=deadline,
                    )
            except httpx.TimeoutException as exc:
                raise JsonRpcError("json-rpc timed out") from exc
            except (httpx.HTTPError, OSError) as exc:
                if time.monotonic() >= deadline:
                    raise JsonRpcError("json-rpc timed out") from exc
                raise
        return _decode_jsonrpc_envelope(raw, expected_id=req_id)

    async def arequest(self, method: str, params: list[Any] | None = None) -> Any:
        req_id = next(self._ids)
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or [],
        }
        try:
            async with asyncio.timeout(self._timeout):
                async with (
                    httpx.AsyncClient(
                        timeout=self._timeout,
                        headers=_HTTP_HEADERS,
                        event_hooks={"response": [_araise_for_status]},
                    ) as client,
                    client.stream("POST", self._url, json=payload) as response,
                ):
                    raw = await _read_limited(response, MAX_JSONRPC_RESPONSE_BYTES)
        except TimeoutError as exc:
            raise JsonRpcError("json-rpc timed out") from exc
        except httpx.TimeoutException as exc:
            raise JsonRpcError("json-rpc timed out") from exc
        return _decode_jsonrpc_envelope(raw, expected_id=req_id)


class _DeadlineGuard:
    """Aborts a sync request at its deadline.

    It shuts down the connection's socket, which httpcore's ``trace`` request
    extension hands it once the TCP connection (and TLS, for HTTPS) is made: a
    send or read blocked on the socket, in any phase of the request, returns at
    once, which closing the client does not ensure. It then closes the client.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self._lock = threading.Lock()
        self._socket: socket.socket | None = None
        self._expired = False

    def trace(self, event: str, info: dict[str, Any]) -> None:
        """httpcore trace callback: take the socket of each connection made."""
        if event not in _CONNECTED_EVENTS:
            return
        stream = info.get("return_value")
        sock = stream.get_extra_info("socket") if stream is not None else None
        if not isinstance(sock, socket.socket):
            return
        with self._lock:
            self._socket = sock
            expired = self._expired
        if expired:
            _shutdown(sock)

    def expire(self) -> None:
        with self._lock:
            self._expired = True
            sock = self._socket
        # The socket first: closing the client can wait on the read it ends.
        if sock is not None:
            _shutdown(sock)
        self._client.close()


# httpcore trace events that carry a new network stream: the TCP connection,
# then, for HTTPS, the TLS stream that replaces it.
_CONNECTED_EVENTS = frozenset({"connection.connect_tcp.complete", "connection.start_tls.complete"})


def _shutdown(sock: socket.socket) -> None:
    with contextlib.suppress(OSError):
        sock.shutdown(socket.SHUT_RDWR)


@contextlib.contextmanager
def _deadline_guard(client: httpx.Client, deadline: float) -> Iterator[_DeadlineGuard]:
    """A :class:`_DeadlineGuard` for ``client`` that expires at ``deadline``.

    The timer is cancelled on exit, so successful calls leave no worker threads.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise JsonRpcError("json-rpc timed out")
    guard = _DeadlineGuard(client)
    timer = threading.Timer(remaining, guard.expire)
    timer.daemon = True
    timer.start()
    try:
        yield guard
    finally:
        timer.cancel()


def _content_length_exceeds(response: httpx.Response, max_bytes: int) -> bool:
    raw = response.headers.get("content-length")
    if raw is None:
        return False
    try:
        return int(raw) > max_bytes
    except ValueError:
        return False


def _read_limited_sync(
    response: httpx.Response,
    max_bytes: int,
    *,
    deadline: float,
) -> bytes:
    if _content_length_exceeds(response, max_bytes):
        raise JsonRpcError(f"json-rpc response exceeds {max_bytes} bytes")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        if time.monotonic() >= deadline:
            response.close()
            raise JsonRpcError("json-rpc timed out")
        total += len(chunk)
        if total > max_bytes:
            raise JsonRpcError(f"json-rpc response exceeds {max_bytes} bytes")
        chunks.append(chunk)
    if time.monotonic() >= deadline:
        raise JsonRpcError("json-rpc timed out")
    return b"".join(chunks)


async def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    if _content_length_exceeds(response, max_bytes):
        raise JsonRpcError(f"json-rpc response exceeds {max_bytes} bytes")
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise JsonRpcError(f"json-rpc response exceeds {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_jsonrpc_envelope(raw: bytes, *, expected_id: int) -> Any:
    try:
        body = json.loads(raw)
    except ValueError as exc:
        # Not JSON, not UTF-8, or an integer too long to convert.
        raise JsonRpcError("json-rpc response is not valid JSON") from exc
    if not isinstance(body, dict):
        raise JsonRpcError("json-rpc response must be a JSON object")
    if body.get("jsonrpc") != "2.0":
        raise JsonRpcError('json-rpc response must have jsonrpc="2.0"')
    if "id" not in body or body["id"] != expected_id:
        raise JsonRpcError(
            f"json-rpc response id mismatch: expected {expected_id}, got {body.get('id')!r}"
        )
    has_result = "result" in body
    has_error = "error" in body and body["error"] is not None
    if has_result == has_error:
        raise JsonRpcError("json-rpc response must contain exactly one of result|error")
    if has_error:
        err = body["error"]
        if not isinstance(err, dict):
            raise JsonRpcError("json-rpc error must be an object")
        message = err.get("message")
        code = err.get("code")
        if not isinstance(message, str) or type(code) is not int:
            # Not a JSON-RPC error object: its code, if any, proves nothing.
            raise JsonRpcError(
                "json-rpc malformed error object: want an integer code and a string message",
                data=err.get("data"),
            )
        raise JsonRpcError(message, code=code, data=err.get("data"))
    # ``result: null`` is a valid JSON-RPC success (has_result True).
    return body["result"]
