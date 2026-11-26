"""A realtime token request's timeout also bounds its wait for signing capacity.

The realtime connection and subscription tokens are fetched with one signed
GET, which draws its timestamp from the API key's shared allocator, as the
ConnectRPC requests do. When a burst used the lead the allocator allows, the
wait for the clock is part of the request: it ends at the request's deadline
with the same error the GET's own timeout raises, sends nothing and takes no
timestamp, and a cancelled request is never signed or sent.

The signing clock is frozen, so capacity never recovers unless a test moves
it; the allocator's own ten-second cap is the only other end to the wait.
"""

from __future__ import annotations

import asyncio
import threading
import types
import uuid

import httpx
import pytest

import polyester.auth as auth_module
from polyester.auth import ApiKeyCredentials, sign_request_async
from polyester.errors import PolyesterRateLimitError, PolyesterRealtimeError
from polyester.realtime.auth import fetch_connection_token
from tests.hardening_support import HttpScript, MockHttpServer, make_test_credentials

FROZEN_MS = 1_800_000_000_000
# The deadline of the token request, as in a client built with timeout=0.1.
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
    return make_test_credentials(f"ak_rt_deadline_{uuid.uuid4().hex}")


def _occupy_signing_capacity(creds: ApiKeyCredentials) -> int:
    """Take every timestamp the frozen clock allows; return the last one."""
    while True:
        try:
            last = creds._timestamp_allocator.next()
        except PolyesterRateLimitError:
            return last


async def _next_timestamp(creds: ApiKeyCredentials) -> int:
    headers = await sign_request_async(
        creds, method="POST", url="https://api.example.test/next", body=b""
    )
    return int(headers["X-API-TIMESTAMP"])


async def test_token_deadline_bounds_the_signing_wait(clock: _FrozenSigningClock) -> None:
    http = await MockHttpServer.spawn(lambda _req: HttpScript.never_respond())
    creds = _credentials()
    client = httpx.AsyncClient(timeout=TIMEOUT)
    try:
        # With capacity free the server never answers: the GET's own timeout.
        with pytest.raises(PolyesterRealtimeError) as transport_timeout:
            await fetch_connection_token(client, creds, api_url=http.base_url)
        sent = http.request_count
        assert sent == 1

        last = _occupy_signing_capacity(creds)
        loop = asyncio.get_running_loop()
        started = loop.time()
        async with asyncio.timeout(GUARD):
            with pytest.raises(PolyesterRealtimeError) as signing_timeout:
                await fetch_connection_token(client, creds, api_url=http.base_url)
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


async def test_a_token_request_out_of_time_after_signing_is_not_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http = await MockHttpServer.spawn(lambda _req: HttpScript.json(200, {"token": "t"}))
    creds = _credentials()
    allocator = creds._timestamp_allocator
    take = allocator.next_async

    async def slow_signing(*args: object, **kwargs: object) -> int:
        timestamp = await take(*args, **kwargs)  # type: ignore[arg-type]
        # The timestamp came after the whole deadline had passed.
        await asyncio.sleep(TIMEOUT * 2)
        return timestamp

    monkeypatch.setattr(allocator, "next_async", slow_signing)
    client = httpx.AsyncClient(timeout=TIMEOUT)
    try:
        async with asyncio.timeout(GUARD):
            with pytest.raises(PolyesterRealtimeError, match="timed out"):
                await fetch_connection_token(client, creds, api_url=http.base_url)
    finally:
        await client.aclose()
        await http.aclose()
    assert http.request_count == 0


async def test_a_cancelled_token_request_is_never_signed_or_sent(
    clock: _FrozenSigningClock,
) -> None:
    http = await MockHttpServer.spawn(lambda _req: HttpScript.json(200, {"token": "t"}))
    creds = _credentials()
    client = httpx.AsyncClient(timeout=30.0)
    try:
        last = _occupy_signing_capacity(creds)
        task = asyncio.create_task(fetch_connection_token(client, creds, api_url=http.base_url))
        await asyncio.sleep(0.05)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Capacity returns on the turn the request was cancelled: still nothing.
        clock.advance(1)
        await asyncio.sleep(0.05)
    finally:
        await client.aclose()
        await http.aclose()
    assert http.request_count == 0
    assert not creds._timestamp_allocator._async_gates
    assert await _next_timestamp(creds) == last + 1
