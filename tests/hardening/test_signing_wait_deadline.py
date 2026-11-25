"""A request's ``timeout`` also bounds its wait for signing capacity.

Every credentials object for one API key draws signing timestamps from one
allocator, which refuses to run more than ``MAX_SIGNING_FUTURE_SKEW_MS`` ahead
of the clock. A burst of requests can use all of that lead, and a request then
waits for the clock to catch up. That wait is part of the request: it ends at
the request's deadline with the same ``PolyesterTimeoutError`` the transport
raises, sends nothing, takes no timestamp, and the transport and server get
only the time that is left.

The signing clock is frozen, so capacity never recovers unless a test moves
it; the allocator's own ten-second cap is the only other end to the wait.
"""

from __future__ import annotations

import asyncio
import threading
import time
import types
import uuid
from collections.abc import Iterator

import connectrpc.request
import pytest

import polyester.auth as auth_module
from polyester import AsyncPolyester, Polyester
from polyester.auth import ApiKeyCredentials, sign_request_async
from polyester.errors import PolyesterRateLimitError, PolyesterTimeoutError
from tests.hardening_support import HttpScript, MockHttpServer, ParsedRequest, make_test_credentials

FROZEN_MS = 1_800_000_000_000
ME_PATH = "/auth.v1.AuthService/Me"
# The deadline of the urgent request, as in a client built with timeout=0.1.
TIMEOUT = 0.1
# Room for scheduling on a busy host; far below the ten-second cap.
MARGIN = 0.5
# Ends a test that regresses to the cap instead of waiting it out.
GUARD = 5.0


class _FrozenSigningClock:
    def __init__(self) -> None:
        self._now_ms = FROZEN_MS
        self._lock = threading.Lock()

    def time_ns(self) -> int:
        with self._lock:
            return self._now_ms * 1_000_000

    def advance(self, ms: int) -> None:
        with self._lock:
            self._now_ms += ms


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FrozenSigningClock:
    fake = _FrozenSigningClock()
    monkeypatch.setattr(auth_module, "time", types.SimpleNamespace(time_ns=fake.time_ns))
    return fake


def _credentials() -> ApiKeyCredentials:
    return make_test_credentials(f"ak_deadline_{uuid.uuid4().hex}")


def _occupy_signing_capacity(creds: ApiKeyCredentials) -> int:
    """Take every timestamp the frozen clock allows; return the last one."""
    while True:
        try:
            last = creds._timestamp_allocator.next()
        except PolyesterRateLimitError:
            return last


def _async_client(api_url: str, creds: ApiKeyCredentials, timeout: float) -> AsyncPolyester:
    return AsyncPolyester(
        api_url=api_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        timeout=timeout,
    )


async def _next_timestamp(creds: ApiKeyCredentials) -> int:
    headers = await sign_request_async(
        creds, method="POST", url="https://api.example.test/next", body=b""
    )
    return int(headers["X-API-TIMESTAMP"])


async def test_async_request_deadline_bounds_the_signing_wait(
    clock: _FrozenSigningClock,
) -> None:
    http = await MockHttpServer.spawn(lambda _req: HttpScript.never_respond())
    creds = _credentials()
    client = _async_client(http.base_url, creds, TIMEOUT)
    try:
        # With capacity free the server never answers: the transport's timeout.
        with pytest.raises(PolyesterTimeoutError) as transport_timeout:
            await client.auth.me()
        sent = http.request_count
        assert sent == 1

        last = _occupy_signing_capacity(creds)
        loop = asyncio.get_running_loop()
        started = loop.time()
        async with asyncio.timeout(GUARD):
            with pytest.raises(PolyesterTimeoutError) as signing_timeout:
                await client.auth.me()
        elapsed = loop.time() - started
    finally:
        await client.aclose()
        await http.aclose()

    assert elapsed < TIMEOUT + MARGIN
    assert type(signing_timeout.value) is type(transport_timeout.value)
    assert str(signing_timeout.value) == str(transport_timeout.value)
    # The expired request was never sent, left the queue and took no timestamp.
    assert http.request_count == sent
    assert not creds._timestamp_allocator._async_gates
    clock.advance(1)
    assert await _next_timestamp(creds) == last + 1


async def test_many_waiters_each_end_at_their_own_deadline(
    clock: _FrozenSigningClock,
) -> None:
    http = await MockHttpServer.spawn(lambda _req: HttpScript.never_respond())
    creds = _credentials()
    patient = _async_client(http.base_url, creds, 30.0)
    urgent = _async_client(http.base_url, creds, TIMEOUT)
    try:
        last = _occupy_signing_capacity(creds)
        background = [asyncio.create_task(patient.auth.me()) for _ in range(50)]
        await asyncio.sleep(0)
        loop = asyncio.get_running_loop()
        started = loop.time()
        async with asyncio.timeout(GUARD):
            with pytest.raises(PolyesterTimeoutError):
                await urgent.auth.me()
        elapsed = loop.time() - started
        # The urgent request did not wait behind the queue ahead of it, which
        # still waits.
        assert not any(task.done() for task in background)
        for task in background:
            task.cancel()
        results = await asyncio.gather(*background, return_exceptions=True)
    finally:
        await patient.aclose()
        await urgent.aclose()
        await http.aclose()

    assert elapsed < TIMEOUT + MARGIN
    assert all(isinstance(result, asyncio.CancelledError) for result in results)
    assert http.request_count == 0
    assert not creds._timestamp_allocator._async_gates
    clock.advance(1)
    assert await _next_timestamp(creds) == last + 1


class _ContextClock:
    """The clock connectrpc keeps a request's deadline by, held by the test."""

    def __init__(self) -> None:
        self.now = 1024.0

    def monotonic(self) -> float:
        return self.now


async def test_server_deadline_is_what_remains_after_signing(
    clock: _FrozenSigningClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    context_clock = _ContextClock()
    monkeypatch.setattr(
        connectrpc.request, "time", types.SimpleNamespace(monotonic=context_clock.monotonic)
    )
    timeouts: list[str] = []

    def handle(req: ParsedRequest) -> HttpScript:
        if req.path == ME_PATH:
            timeouts.append(req.headers.get("connect-timeout-ms", ""))
        return HttpScript.not_found()

    http = await MockHttpServer.spawn(handle)
    creds = _credentials()
    client = _async_client(http.base_url, creds, 2.0)
    try:
        _occupy_signing_capacity(creds)

        def release() -> None:
            # 1.25 s of the request's 2 s pass while it waits; then a
            # timestamp is free.
            context_clock.now += 1.25
            clock.advance(1)

        asyncio.get_running_loop().call_later(0.05, release)
        async with asyncio.timeout(GUARD):
            with pytest.raises(Exception):  # noqa: B017 - the answer is a 404
                await client.auth.me()
    finally:
        await client.aclose()
        await http.aclose()

    assert timeouts == ["750"]


class _ThreadedApi:
    """A local API on its own loop and thread, for the sync client."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self.server = asyncio.run_coroutine_threadsafe(
            MockHttpServer.spawn(lambda _req: HttpScript.never_respond()), self._loop
        ).result(timeout=5)

    def close(self) -> None:
        asyncio.run_coroutine_threadsafe(self.server.aclose(), self._loop).result(timeout=5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()


@pytest.fixture
def threaded_api() -> Iterator[_ThreadedApi]:
    api = _ThreadedApi()
    try:
        yield api
    finally:
        api.close()


def test_sync_request_deadline_bounds_the_signing_wait(
    clock: _FrozenSigningClock, threaded_api: _ThreadedApi
) -> None:
    creds = _credentials()
    client = Polyester(
        api_url=threaded_api.server.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        timeout=TIMEOUT,
    )
    try:
        with pytest.raises(PolyesterTimeoutError) as transport_timeout:
            client.auth.me()
        sent = threaded_api.server.request_count

        last = _occupy_signing_capacity(creds)
        started = time.monotonic()
        with pytest.raises(PolyesterTimeoutError) as signing_timeout:
            client.auth.me()
        elapsed = time.monotonic() - started
    finally:
        client.close()

    assert elapsed < TIMEOUT + MARGIN
    assert str(signing_timeout.value) == str(transport_timeout.value)
    assert threaded_api.server.request_count == sent
    assert not creds._timestamp_allocator._async_gates
    clock.advance(1)
    assert asyncio.run(_next_timestamp(creds)) == last + 1
