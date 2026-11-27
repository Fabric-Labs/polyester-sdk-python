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
from unittest.mock import patch

import pytest
from websockets.exceptions import ConnectionClosedError

from polyester import AsyncPolyester
from polyester.errors import PolyesterRealtimeError
from polyester.market_overview.subscription import MarketOverviewSubscription
from polyester.orderbook.subscription import OrderbookSubscription
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from tests.unit.test_realtime_batch_publications import (
    ACK_CONNECT,
    ACK_SUBSCRIBE,
    publication_frame,
)
from tests.unit.test_server_unsubscribe import CentrifugoServer

READERS = [1, 2, 3, 10]


class _Stream:
    async def aclose(self) -> None:
        return None


def _realtime(maxsize: int = 8) -> AsyncSubscription[Any]:
    return AsyncSubscription(queue=asyncio.Queue(maxsize=maxsize), close=asyncio.Event())


def _orderbook(maxsize: int = 8) -> OrderbookSubscription:
    return OrderbookSubscription(
        queue=asyncio.Queue(maxsize=maxsize),
        close=asyncio.Event(),
        stream=_Stream(),
        set_bucket=lambda _bucket: None,
    )


def _market_overview(maxsize: int = 8) -> MarketOverviewSubscription:
    return MarketOverviewSubscription(
        queue=asyncio.Queue(maxsize=maxsize), close=asyncio.Event(), stream=_Stream()
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


async def _settle(*tasks: asyncio.Task[Any]) -> None:
    await asyncio.wait(tasks, timeout=1.0)
    for task in tasks:
        task.cancel()


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_an_update_is_not_lost_when_its_reader_is_cancelled(
    make: Callable[[], Any],
) -> None:
    # The update wakes the first reader, which is cancelled before it resumes.
    sub = make()
    first = asyncio.create_task(sub.__anext__())
    second = asyncio.create_task(sub.__anext__())
    for _ in range(5):
        await asyncio.sleep(0)
    sub._queue.put_nowait("tail")
    asyncio.get_running_loop().call_soon(first.cancel)
    await asyncio.wait((first, second), timeout=0.2)
    got = [t.result() for t in (first, second) if t.done() and not t.cancelled()]
    assert got == ["tail"], "the update reached no reader"
    await sub.aclose()
    await _settle(first, second)


async def test_an_end_marker_reaches_every_reader_when_its_reader_is_cancelled() -> None:
    # The end marker wakes the first reader, which is cancelled before it resumes.
    sub = _realtime()
    readers = [asyncio.create_task(sub.__anext__()) for _ in range(3)]
    for _ in range(5):
        await asyncio.sleep(0)
    sub._set_error(PolyesterRealtimeError("stream failed"))
    sub._queue.put_nowait(None)
    asyncio.get_running_loop().call_soon(readers[0].cancel)
    done, pending = await asyncio.wait(readers, timeout=1.0)
    for task in pending:
        task.cancel()
    assert not pending, f"{len(pending)} readers still waiting after the stream ended"
    for task in readers[1:]:
        with pytest.raises(PolyesterRealtimeError, match="stream failed"):
            task.result()
    assert sub._close.is_set()
    with pytest.raises(PolyesterRealtimeError, match="stream failed"):
        await asyncio.wait_for(sub.__anext__(), timeout=0.5)


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_an_update_queued_before_close_is_delivered_before_any_reader_ends(
    make: Callable[[], Any],
) -> None:
    sub = make()
    earlier = asyncio.create_task(sub.__anext__())
    for _ in range(5):
        await asyncio.sleep(0)
    sub._queue.put_nowait("tail")
    await sub.aclose()
    later = asyncio.create_task(sub.__anext__())
    await asyncio.wait((earlier, later), timeout=1.0)
    outcomes = sorted(
        "tail" if t.exception() is None and t.result() == "tail" else type(t.exception()).__name__
        for t in (earlier, later)
    )
    assert outcomes == ["StopAsyncIteration", "tail"]


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_a_close_on_a_full_queue_ends_readers_once_it_is_drained(
    make: Callable[[], Any],
) -> None:
    # The end marker finds no room; the queued updates still come first.
    sub = make()
    for index in range(sub._queue.maxsize):
        sub._queue.put_nowait(index)
    await sub.aclose()
    seen: list[Any] = []
    outcomes = await asyncio.gather(_read_all(sub, seen), _read_all(sub, seen))
    assert outcomes == ["ended", "ended"]
    assert sorted(seen) == list(range(sub._queue.maxsize))


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_a_parked_reader_ends_after_another_drains_a_queue_closed_full(
    make: Callable[[], Any],
) -> None:
    # A waits; the queue fills and closes full before A runs; B drains it all.
    sub = make()
    waiting = asyncio.create_task(sub.__anext__())
    for _ in range(5):
        await asyncio.sleep(0)
    for index in range(sub._queue.maxsize):
        sub._queue.put_nowait(index)
    await sub.aclose()
    drained: list[Any] = []
    with pytest.raises(StopAsyncIteration):
        while True:
            drained.append(await sub.__anext__())
    assert drained == list(range(sub._queue.maxsize))
    await asyncio.wait((waiting,), timeout=1.0)
    waiting.cancel()
    assert waiting.done() and not waiting.cancelled(), "the parked reader is still waiting"
    assert isinstance(waiting.exception(), StopAsyncIteration)


@pytest.mark.parametrize("make", SUBSCRIPTIONS)
async def test_two_parked_readers_of_a_queue_of_one_both_end(make: Callable[..., Any]) -> None:
    sub = make(maxsize=1)
    readers = [asyncio.create_task(sub.__anext__()) for _ in range(2)]
    for _ in range(5):
        await asyncio.sleep(0)
    sub._queue.put_nowait("last")
    await sub.aclose()
    done, pending = await asyncio.wait(readers, timeout=1.0)
    for task in pending:
        task.cancel()
    assert not pending, "a parked reader was never woken"
    outcomes = sorted(
        "last" if t.exception() is None else type(t.exception()).__name__ for t in readers
    )
    assert outcomes == ["StopAsyncIteration", "last"]


class _EndingWS:
    """Acks the handshake; once released, serves one publication and then
    fails at once, without yielding, so the worker ends before any reader runs."""

    subprotocol = "centrifuge-protobuf"

    def __init__(self) -> None:
        self.handshake = [ACK_CONNECT, ACK_SUBSCRIBE]
        self.release = asyncio.Event()
        self.served = False

    async def __aenter__(self) -> _EndingWS:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def send(self, payload: bytes) -> None:
        return None

    async def recv(self) -> bytes:
        if self.handshake:
            return self.handshake.pop(0)
        if not self.served:
            await self.release.wait()
            self.served = True
            return publication_frame(b"last")
        raise ConnectionClosedError(None, None)


async def test_a_stream_that_ends_with_its_queue_full_ends_every_reader() -> None:
    # Two readers wait; the stream queues its last update into a queue of one
    # and ends before either runs, so its end marker finds no room.
    realtime = AsyncRealtimeClient("wss://api.devnet.polyester.com", max_queue_size=1)
    ws = _EndingWS()
    with patch("polyester.realtime.client.websockets.connect", return_value=ws):
        sub = await realtime.subscribe_proto(
            "public:test", decode=lambda payload: payload, auto_reconnect=False
        )
        readers = [asyncio.create_task(sub.__anext__()) for _ in range(2)]
        for _ in range(5):
            await asyncio.sleep(0)
        ws.release.set()
        done, pending = await asyncio.wait(readers, timeout=1.0)
        for task in pending:
            task.cancel()
        try:
            assert not pending, "a reader still waits after the stream ended"
            results = [t.result() if t.exception() is None else t.exception() for t in readers]
            assert b"last" in results
            assert sub.error is not None
            assert [r for r in results if r != b"last"] == [sub.error]
            assert sub._close.is_set()
        finally:
            await sub.aclose()
