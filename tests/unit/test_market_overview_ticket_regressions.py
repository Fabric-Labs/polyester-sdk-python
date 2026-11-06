from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import websockets

from polyester.errors import PolyesterRealtimeOverflowError
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.models.market import MarketOverviewEntry, MarketOverviewList
from polyester.realtime.client import AsyncRealtimeClient, _TerminalRealtimeError
from polyester.services.market_overview import AsyncMarketOverviewService
from polyester.types.money import Price


def publication(price: int) -> bytes:
    data = marketoverview_pb2.MarketOverviewBatch(
        markets=[marketoverview_pb2.MarketOverview(symbol_id=1, last_price_ticks=price)]
    ).SerializeToString()
    assert len(data) < 120
    return bytes([len(data) + 6, 34, len(data) + 4, 34, len(data) + 2, 34, len(data)]) + data


@pytest.mark.parametrize("mode", ["bad_frame", "overflow", "close"])
async def test_market_overview_terminal_lifecycle(mode):
    # Frame delivery and every healthy emit are barriers; no sleeps select the scenario.
    frames = asyncio.Queue()
    socket_released = asyncio.Event()
    connections = 0

    async def handler(ws):
        nonlocal connections
        connections += 1
        await ws.recv()
        await ws.send(bytes.fromhex("020801"))
        await ws.recv()
        await ws.send(bytes.fromhex("020802"))
        try:
            while True:
                get_frame = asyncio.create_task(frames.get())
                closed = asyncio.create_task(ws.wait_closed())
                done, pending = await asyncio.wait(
                    [get_frame, closed], return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if closed in done:
                    return
                data, sent = get_frame.result()
                await ws.send(data)
                sent.set_result(None)
        finally:
            socket_released.set()

    async with websockets.serve(
        handler, "127.0.0.1", 0, subprotocols=["centrifuge-protobuf"]
    ) as server:
        port = server.sockets[0].getsockname()[1]
        rt = AsyncRealtimeClient(f"ws://127.0.0.1:{port}")
        service = AsyncMarketOverviewService(MagicMock(), realtime=rt)
        service.list = AsyncMock(
            return_value=MarketOverviewList(
                markets=[
                    MarketOverviewEntry(symbol_id=1, last_price=Price.from_ticks(1)),
                ],
                total=1,
            )
        )
        events = asyncio.Queue()
        errors = []
        failed = asyncio.Event()

        def report(error):
            errors.append(error)
            failed.set()

        sub = await service.create_subscription(
            on_event=events.put_nowait,
            on_error=report,
        )

        def expect_price(rows, price):
            assert len(rows) == 1
            assert rows[0].last_price.ticks == price

        async def send(data):
            sent = asyncio.get_running_loop().create_future()
            await frames.put((data, sent))
            await asyncio.wait_for(sent, 10)

        try:
            expect_price(await asyncio.wait_for(events.get(), 10), 1)
            if mode != "overflow":
                expect_price(await asyncio.wait_for(anext(sub), 10), 1)
            last = 51 if mode == "overflow" else 3
            for price in range(2, last + 1):
                await send(publication(price))
                expect_price(await asyncio.wait_for(events.get(), 10), price)
            if mode == "bad_frame":
                await send(b"\xff")
            if mode != "close":
                await asyncio.wait_for(failed.wait(), 10)
                assert errors == [sub.last_error]
                if mode == "bad_frame":
                    assert isinstance(sub.last_error, _TerminalRealtimeError)
                    assert "invalid realtime protobuf frame" in str(sub.last_error)
                else:
                    assert isinstance(sub.last_error, PolyesterRealtimeOverflowError)
                    assert str(sub.last_error) == (
                        "market overview subscription queue full; consumer too slow"
                    )
                await asyncio.wait_for(socket_released.wait(), 10)
            else:
                await asyncio.wait_for(sub.aclose(), 10)
                assert sub.last_error is None and not errors
            # Full-queue close must also return after overflow.
            if mode == "overflow":
                await asyncio.wait_for(sub.aclose(), 10)
            received = []
            while True:
                try:
                    rows = await asyncio.wait_for(anext(sub), 10)
                except StopAsyncIteration:
                    break
                received.append(rows[0].last_price.ticks)
            assert received == (list(range(1, 51)) if mode == "overflow" else [2, 3])
            assert connections == 1
            await asyncio.wait_for(sub.aclose(), 10)
            await asyncio.wait_for(socket_released.wait(), 10)
            service.list.assert_awaited_once()
        finally:
            # Bounded cleanup also makes the red full-queue-close failure observable.
            await asyncio.wait_for(sub.aclose(), 10)
