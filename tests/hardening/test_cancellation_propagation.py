"""A caller's cancellation or timeout leaves an SDK call as itself.

Cancelling the task that awaits an SDK call raises ``asyncio.CancelledError``
and ``asyncio.timeout`` raises ``TimeoutError``, for unary calls, server
realtime streams, retried reads and realtime setup. The SDK never reports the caller's
own cancellation as a server error.

The interleaving tests draw cancellation and server timing from one seed. Set
``POLYESTER_INTERLEAVING_SEED`` to replay a failing run.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterServerError
from polyester.gen.chain.analytics.v1 import analytics_read_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    MockWsServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
    wait_until,
)

SUPPLY_PATH = "/chain.analytics.v1.ChainAnalyticsService/GetZippedAssetSupply"
TRIGGER_PATH = "/triggers.v1.TriggersService/GetTrigger"
UNAVAILABLE = HttpScript.json(503, {"code": "unavailable", "message": "catching up"})
INTERLEAVINGS = 150


def _seed() -> int:
    raw = os.environ.get("POLYESTER_INTERLEAVING_SEED")
    return int(raw) if raw else random.SystemRandom().randrange(2**32)


class _HangingApi:
    """Local API that holds every Connect read open and counts arrivals."""

    def __init__(self, before_hang: list[HttpScript] | None = None) -> None:
        self.arrived = asyncio.Event()
        self.paths: list[str] = []
        self._before_hang = list(before_hang or [])

    async def handle(self, req: ParsedRequest) -> HttpScript:
        if req.path.startswith("/v1/rt/"):
            return HttpScript.json(200, b'{"token":"rt-ok"}')
        self.paths.append(req.path)
        if self._before_hang:
            return self._before_hang.pop(0)
        self.arrived.set()
        return HttpScript.never_respond()


@asynccontextmanager
async def _client(handler: Any, *, ws_url: str | None = None) -> AsyncIterator[AsyncPolyester]:
    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        ws_url=ws_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        timeout=30.0,
    )
    try:
        yield client
    finally:
        await client.aclose()
        await http.aclose()


async def _cancel_once_arrived(
    call: Callable[[], Awaitable[object]], arrived: asyncio.Event
) -> asyncio.Task[object]:
    task: asyncio.Task[object] = asyncio.create_task(call())  # type: ignore[arg-type]
    await asyncio.wait_for(arrived.wait(), 5.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    return task


def _supply(client: AsyncPolyester) -> Callable[[], Awaitable[object]]:
    return lambda: client.chain_analytics.get_zipped_asset_supply(zipped_asset_id=1, range="1d")


# ---------------------------------------------------------------------------
# Unary
# ---------------------------------------------------------------------------


async def test_cancelled_public_unary_raises_cancelled_error() -> None:
    api = _HangingApi()
    async with _client(api.handle) as client:
        task = await _cancel_once_arrived(_supply(client), api.arrived)
    assert task.cancelled()


async def test_cancelled_signed_unary_raises_cancelled_error() -> None:
    api = _HangingApi()
    async with _client(api.handle) as client:
        task = await _cancel_once_arrived(client.balances.list, api.arrived)
    assert task.cancelled()


async def test_unary_under_asyncio_timeout_raises_timeout_error() -> None:
    api = _HangingApi()
    async with _client(api.handle) as client:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.2):
                await _supply(client)()
        # The timed-out task is not left cancelling: it can await again.
        task = asyncio.current_task()
        assert task is not None and task.cancelling() == 0
        await asyncio.sleep(0)


async def test_task_group_stops_an_sdk_call_when_a_sibling_fails() -> None:
    api = _HangingApi()

    async def fail_once_arrived() -> None:
        await asyncio.wait_for(api.arrived.wait(), 5.0)
        raise ValueError("sibling failed")

    async with _client(api.handle) as client:
        with pytest.raises(ExceptionGroup) as raised:
            async with asyncio.TaskGroup() as group:
                group.create_task(_supply(client)())  # type: ignore[arg-type]
                group.create_task(fail_once_arrived())
    # The cancelled SDK call adds nothing: only the sibling's error remains.
    assert [type(exc) for exc in raised.value.exceptions] == [ValueError]


async def test_server_canceled_answer_stays_an_sdk_error() -> None:
    async def handler(_req: ParsedRequest) -> HttpScript:
        return HttpScript.json(499, {"code": "canceled", "message": "server gave up"})

    async with _client(handler) as client:
        with pytest.raises(PolyesterServerError, match="server gave up"):
            await _supply(client)()


# ---------------------------------------------------------------------------
# Retried reads
# ---------------------------------------------------------------------------


async def test_cancel_during_a_retried_read_raises_and_stops_retrying() -> None:
    api = _HangingApi(before_hang=[UNAVAILABLE, UNAVAILABLE])
    async with _client(api.handle) as client:
        task = await _cancel_once_arrived(lambda: client.triggers.get(trigger_id=1), api.arrived)
        await asyncio.sleep(0.2)
    assert task.cancelled()
    assert api.paths == [TRIGGER_PATH] * 3


async def test_retried_read_under_asyncio_timeout_raises_timeout_error() -> None:
    api = _HangingApi(before_hang=[UNAVAILABLE])
    async with _client(api.handle) as client:
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.3):
                await client.triggers.get(trigger_id=1)
        await asyncio.sleep(0.2)
    assert api.paths == [TRIGGER_PATH] * 2


# ---------------------------------------------------------------------------
# Server streams (realtime subscriptions)
# ---------------------------------------------------------------------------


async def test_cancelled_realtime_stream_read_raises_cancelled_error() -> None:
    ws = await MockWsServer.spawn_centrifugo_public()
    try:
        async with _client(_HangingApi().handle, ws_url=ws.ws_url()) as client:
            sub = await client.market_overview.subscribe()
            waiting = asyncio.Event()

            async def consume() -> None:
                waiting.set()
                async for _ in sub:
                    pass

            task = await _cancel_once_arrived(consume, waiting)
            assert task.cancelled()
            await sub.aclose()
    finally:
        await ws.aclose()


async def test_realtime_stream_read_under_asyncio_timeout_raises_timeout_error() -> None:
    ws = await MockWsServer.spawn_centrifugo_public()
    try:
        async with _client(_HangingApi().handle, ws_url=ws.ws_url()) as client:
            sub = await client.market_overview.subscribe()
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.2):
                    async for _ in sub:
                        pass
            await sub.aclose()
    finally:
        await ws.aclose()


# ---------------------------------------------------------------------------
# Realtime setup
# ---------------------------------------------------------------------------


async def test_realtime_snapshot_setup_under_asyncio_timeout_raises_timeout_error() -> None:
    api = _HangingApi()
    errors: list[Exception] = []
    ws = await MockWsServer.spawn_centrifugo_public()
    try:
        async with _client(api.handle, ws_url=ws.ws_url()) as client:
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.5):
                    await client.market_overview.create_subscription(on_error=errors.append)
            assert api.arrived.is_set(), "the snapshot read never started"
            await wait_until(lambda: ws.active == 0, 2.0)
            await asyncio.sleep(0.2)
            assert len(api.paths) == 1, "a cancelled snapshot read was retried"
    finally:
        await ws.aclose()
    assert errors == []


# ---------------------------------------------------------------------------
# Randomized interleavings
# ---------------------------------------------------------------------------


async def test_cancel_racing_a_unary_answer_is_an_answer_or_a_cancellation() -> None:
    seed = _seed()
    rng = random.Random(seed)
    body = analytics_read_pb2.GetZippedAssetSupplyResponse().SerializeToString()

    async def handler(_req: ParsedRequest) -> HttpScript:
        await asyncio.sleep(rng.uniform(0, 0.004))
        return connect_proto_response(body)

    async with _client(handler) as client:
        for i in range(INTERLEAVINGS):
            task = asyncio.create_task(_supply(client)())
            await asyncio.sleep(rng.uniform(0, 0.006))
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                assert task.cancelled(), f"seed={seed} run={i}"
            except BaseException as exc:
                raise AssertionError(f"seed={seed} run={i}: {exc!r}") from exc


async def test_timeout_racing_a_retried_read_is_always_a_timeout() -> None:
    seed = _seed()
    rng = random.Random(seed)
    calls = 0

    async def handler(req: ParsedRequest) -> HttpScript:
        nonlocal calls
        calls += 1
        await asyncio.sleep(rng.uniform(0, 0.03))
        return UNAVAILABLE

    async with _client(handler) as client:
        for i in range(INTERLEAVINGS // 5):
            try:
                async with asyncio.timeout(rng.uniform(0, 0.12)):
                    await client.triggers.get(trigger_id=1)
            except TimeoutError:
                pass
            except BaseException as exc:
                raise AssertionError(f"seed={seed} run={i}: {exc!r}") from exc
            else:
                raise AssertionError(f"seed={seed} run={i}: read answered")
            # A request already written when the deadline fired may still be
            # counted; after that, a stopped read sends nothing more. The next
            # backoff step after a 0.12 s deadline is at most 0.1 s.
            await asyncio.sleep(0.05)
            settled = calls
            await asyncio.sleep(0.15)
            assert calls == settled, f"seed={seed} run={i}: retried after the timeout"
