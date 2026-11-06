from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import websockets

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterRealtimeError, PolyesterValidationError
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription, _TerminalRealtimeError
from polyester.services.orderbook import AsyncOrderbookService

ACK = bytes.fromhex("020802")
FIRST = bytes.fromhex("0b2209220722056669727374")


def publication(data: bytes) -> bytes:
    return bytes([len(data) + 6, 34, len(data) + 4, 34, len(data) + 2, 34, len(data)]) + data


@pytest.mark.parametrize(
    "frames",
    [
        [ACK + FIRST],
        [FIRST + ACK],
        [FIRST, ACK],
        [ACK, FIRST],
        [FIRST + ACK + publication(b"second")],
    ],
)
async def test_setup_preserves_publications(frames: list[bytes]) -> None:
    async def handler(ws):
        await ws.recv()
        await ws.send(bytes.fromhex("020801"))
        await ws.recv()
        for frame in frames:
            await ws.send(frame)
        await ws.send(publication(b"control"))
        await ws.wait_closed()

    async with websockets.serve(
        handler, "127.0.0.1", 0, subprotocols=["centrifuge-protobuf"]
    ) as server:
        port = server.sockets[0].getsockname()[1]
        rt = AsyncRealtimeClient(f"ws://127.0.0.1:{port}")
        sub = await rt.subscribe_proto("public:test:proto", decode=lambda data: data)
        received = []
        try:
            while True:
                item = await asyncio.wait_for(anext(sub), 10)
                received.append(item)
                if item == b"control":
                    break
            expected = [b"first"] + ([b"second"] if len(frames[0]) > len(FIRST + ACK) else [])
            assert received == expected + [b"control"]
        finally:
            await sub.aclose()


class BookHarness:
    def __init__(self, monkeypatch, seq=1, available=True):
        catalogs = CatalogManager()
        catalogs.hydrate_spot_config(
            {
                "pairs": [
                    {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8},
                    {"symbol": "ETH-USDT", "symbol_id": 2, "base_quantity_scale": 6},
                ]
            }
        )
        self.queue = asyncio.Queue()
        self.transport_sub = AsyncSubscription(queue=self.queue, close=asyncio.Event())
        self.rt = MagicMock()
        self.rt.subscribe_proto = AsyncMock(return_value=self.transport_sub)
        self.fetch = AsyncMock(
            return_value=orderbook_pb2.GetOrderBookResponse(
                book_seq=seq,
                available=available,
            )
        )
        monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", self.fetch)
        self.service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=self.rt)


async def test_conflicting_selectors_rejected_before_subscription(monkeypatch):
    harness = BookHarness(monkeypatch)
    with pytest.raises(PolyesterValidationError, match="symbol.*symbol_id"):
        sub = await harness.service.create_subscription(symbol="BTC-USDT", symbol_id=2)
        await sub.aclose()
    harness.rt.subscribe_proto.assert_not_called()
    harness.fetch.assert_not_called()


@pytest.mark.parametrize(
    ("symbol", "symbol_id", "scale"),
    [
        ("BTC-USDT", None, 8),
        ("ETH-USDT", None, 6),
        ("ETH-USDT", 2, 6),
    ],
)
async def test_selector_controls_keep_reset_identity_and_scale(
    monkeypatch, symbol, symbol_id, scale
):
    harness = BookHarness(monkeypatch)
    sub = await harness.service.create_subscription(symbol=symbol, symbol_id=symbol_id)
    try:
        initial = await asyncio.wait_for(anext(sub), 10)
        assert initial.symbol == symbol
        request = harness.fetch.call_args.args[3]
        expected_id = 1 if symbol == "BTC-USDT" else 2
        assert request.symbol_id == expected_id
        assert harness.rt.subscribe_proto.call_args.args[0].endswith(f":{expected_id}:proto")
        await harness.queue.put(
            OrderBookDeltaUpdate(
                symbol_id=expected_id,
                book_seq_start="0",
                book_seq_end="2",
                reset=True,
                bids=[["1000000000", "1000000"]],
            )
        )
        reset = await asyncio.wait_for(anext(sub), 10)
        assert reset.symbol == symbol
        assert reset.bids[0].qty.scale == scale
        assert reset.bids[0].qty.format() == ("0.01" if scale == 8 else "1")
    finally:
        await sub.aclose()


@pytest.mark.parametrize("seq", [0, 1])
@pytest.mark.parametrize("available", [False, True])
async def test_sequence_zero_and_availability_are_independent(monkeypatch, seq, available):
    harness = BookHarness(monkeypatch, seq, available)
    sub = await harness.service.create_subscription(symbol="BTC-USDT")
    try:
        view = await asyncio.wait_for(anext(sub), 10)
        assert view.book_seq == str(seq)
        assert view.available is available
        assert sub.last_error is None
    finally:
        await sub.aclose()


@pytest.mark.parametrize("mode", ["refresh", "transport", "close", "recover"])
async def test_managed_book_terminal_receiver_lifecycle(monkeypatch, mode):
    harness = BookHarness(monkeypatch)
    errors = []
    sub = await harness.service.create_subscription(symbol="BTC-USDT", on_error=errors.append)
    assert (await asyncio.wait_for(anext(sub), 10)).book_seq == "1"
    pending = asyncio.create_task(anext(sub))
    try:
        if mode in ("refresh", "recover"):
            harness.fetch.side_effect = PolyesterRealtimeError("snapshot unavailable")
            # A real gap requests bounded refreshes through the managed book.
            await harness.queue.put(OrderBookDeltaUpdate(book_seq_start="3", book_seq_end="3"))
            if mode == "recover":
                # Explicit failed refresh provides a deterministic barrier; recover via public API.
                await sub.refresh_snapshot()
                harness.fetch.side_effect = None
                await sub.refresh_snapshot()
                assert (await asyncio.wait_for(pending, 10)).book_seq == "1"
                assert sub.last_error is None
                assert errors
                return
        elif mode == "transport":
            harness.transport_sub._set_error(_TerminalRealtimeError("invalid frame"))
            await harness.queue.put(None)
        else:
            await sub.aclose()
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(pending, 10)
        if mode != "close":
            assert isinstance(sub.last_error, PolyesterRealtimeError)
            assert errors and errors[-1] is sub.last_error
            if mode == "refresh":
                assert harness.fetch.call_count >= 5
        else:
            assert sub.last_error is None
            assert not errors
    finally:
        pending.cancel()
        await sub.aclose()


async def test_terminal_transport_error_during_start_releases_handshake(monkeypatch):
    harness = BookHarness(monkeypatch)
    error = _TerminalRealtimeError("invalid setup frame")
    harness.rt.subscribe_proto.side_effect = error
    with pytest.raises(_TerminalRealtimeError, match="invalid setup frame"):
        await asyncio.wait_for(harness.service.create_subscription(symbol="BTC-USDT"), 10)
    harness.fetch.assert_not_called()
