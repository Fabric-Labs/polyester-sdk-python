"""Closing a subscription ends every reader iterating it.

Readers of one subscription share its updates: each update goes to one of
them. When the subscription closes or ends, every reader waiting for an update
stops, however many there are, and so does every reader that starts later:
with ``StopAsyncIteration``, or with a realtime subscription's terminal error
when it failed. Updates queued before the close are still delivered first.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterRealtimeError
from polyester.market_overview.subscription import MarketOverviewSubscription
from polyester.orderbook.subscription import OrderbookSubscription
from polyester.realtime.client import AsyncSubscription
from tests.unit.test_server_unsubscribe import CentrifugoServer

READERS = [1, 2, 3, 10]


class _Stream:
    async def aclose(self) -> None:
        return None


def _realtime() -> AsyncSubscription[Any]:
    return AsyncSubscription(queue=asyncio.Queue(maxsize=8), close=asyncio.Event())


def _orderbook() -> OrderbookSubscription:
    return OrderbookSubscription(
        queue=asyncio.Queue(maxsize=8),
        close=asyncio.Event(),
        stream=_Stream(),
        set_bucket=lambda _bucket: None,
    )


def _market_overview() -> MarketOverviewSubscription:
    return MarketOverviewSubscription(
        queue=asyncio.Queue(maxsize=8), close=asyncio.Event(), stream=_Stream()
    )


SUBSCRIPTIONS: list[Any] = [
    pytest.param(_realtime, id="realtime"),
    pytest.param(_orderbook, id="orderbook"),
    pytest.param(_market_overview, id="market_overview"),
]


async def _read_all(sub: Any, seen: list[Any]) -> str:
    try:
        async for item in sub:
            seen.append(item)
    except Exception as exc:
        return f"raised {exc}"
    return "ended"


async def _waiting(sub: Any, readers: int) -> tuple[list[asyncio.Task[str]], list[Any]]:
    """``readers`` tasks iterating ``sub``, all waiting for an update."""
    seen: list[Any] = []
    tasks = [asyncio.create_task(_read_all(sub, seen)) for _ in range(readers)]
    for _ in range(5):
        await asyncio.sleep(0)
    assert not any(task.done() for task in tasks)
    return tasks, seen


async def _outcomes(tasks: list[asyncio.Task[str]]) -> list[str]:
    done, pending = await asyncio.wait(tasks, timeout=1.0)
    for task in pending:
        task.cancel()
    assert not pending, f"{len(pending)} of {len(tasks)} readers still waiting after close"
    return [task.result() for task in tasks]


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
@pytest.mark.parametrize("readers", READERS)
async def test_close_ends_every_waiting_reader(make: Callable[[], Any], readers: int) -> None:
    sub = make()
    tasks, _ = await _waiting(sub, readers)
    await sub.aclose()
    assert await _outcomes(tasks) == ["ended"] * readers


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_updates_queued_before_close_are_delivered_first(make: Callable[[], Any]) -> None:
    sub = make()
    sub._queue.put_nowait("a")
    sub._queue.put_nowait("b")
    await sub.aclose()
    seen: list[Any] = []
    assert await _read_all(sub, seen) == "ended"
    assert seen == ["a", "b"]


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_a_reader_that_starts_after_close_ends_at_once(make: Callable[[], Any]) -> None:
    sub = make()
    tasks, _ = await _waiting(sub, 3)
    await sub.aclose()
    await _outcomes(tasks)
    for _ in range(3):
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(sub.__anext__(), timeout=0.5)


@pytest.mark.parametrize("readers", READERS)
async def test_a_stream_that_ends_ends_every_reader(readers: int) -> None:
    # The stream ending queues one end marker, as the worker does when it stops.
    sub = _realtime()
    tasks, _ = await _waiting(sub, readers)
    sub._queue.put_nowait(None)
    assert await _outcomes(tasks) == ["ended"] * readers


@pytest.mark.parametrize("readers", READERS)
async def test_a_failed_subscription_gives_every_reader_its_error(readers: int) -> None:
    sub = _realtime()
    tasks, _ = await _waiting(sub, readers)
    sub._set_error(PolyesterRealtimeError("stream failed"))
    sub._queue.put_nowait(None)
    assert await _outcomes(tasks) == ["raised stream failed"] * readers
    with pytest.raises(PolyesterRealtimeError, match="stream failed"):
        await asyncio.wait_for(sub.__anext__(), timeout=0.5)


async def test_every_subscribe_trades_reader_ends_on_close() -> None:
    async with CentrifugoServer() as server:
        client = AsyncPolyester(
            api_url="http://127.0.0.1:9", ws_url=server.url, hydrate_catalogs=False
        )
        client.catalogs.hydrate_spot_config(
            {"pairs": [{"symbol": "DOGE-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
        )
        try:
            sub = await client.market_data.subscribe_trades(symbol="DOGE-USDT")
            tasks, _ = await _waiting(sub, 3)
            await sub.aclose()
            assert await _outcomes(tasks) == ["ended"] * 3
        finally:
            await client.aclose()
