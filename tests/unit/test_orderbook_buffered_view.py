"""POLY-9098: a snapshot applied with the deltas buffered behind it adds one view.

The snapshot answer is held back, so the deltas the server publishes right after the
subscribe are buffered. Applying them is one book state. A view for the snapshot, plus
one per buffered delta (including a delta the snapshot already covers), queued copies
of states the consumer never needed, and a stale copy of an older one.
"""

from __future__ import annotations

import asyncio

import pytest

from polyester import AsyncPolyester
from polyester.gen.orderbook.v1 import orderbook_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)
from tests.unit.test_server_unsubscribe import CentrifugoServer, publication

BID = 71_600_000


def _delta(seq: int, qty: int) -> bytes:
    delta = orderbook_pb2.OrderBookDelta(symbol_id=1, book_seq_start=seq - 1, book_seq_end=seq)
    delta.bids.add(price_ticks=BID, qty_scaled=qty)
    return publication(delta.SerializeToString())


@pytest.mark.parametrize(
    "buffered",
    [
        [(2, 2)],
        [(1, 9), (2, 2)],  # The first is already in the snapshot (sequence 1).
        [(2, 2), (3, 3), (4, 4)],
    ],
)
async def test_snapshot_with_buffered_deltas_adds_one_view(buffered) -> None:
    async def snapshot(request: ParsedRequest) -> HttpScript:
        await asyncio.sleep(0.3)
        response = orderbook_pb2.GetOrderBookResponse(symbol_id=1, book_seq=1, available=True)
        response.bids.add(price_ticks=BID, qty_scaled=1)
        response.asks.add(price_ticks=71_700_000, qty_scaled=4)
        return connect_proto_response(response.SerializeToString())

    async with CentrifugoServer() as server:

        async def publish(channel, ws) -> None:
            for seq, qty in buffered:
                await ws.send(_delta(seq, qty))

        server.on_subscribed = publish
        http = await MockHttpServer.spawn(snapshot)
        client = AsyncPolyester(api_url=http.base_url, ws_url=server.url, hydrate_catalogs=False)
        client.catalogs.hydrate_spot_config(
            {"pairs": [{"symbol": "DOGE-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
        )
        try:
            sub = await client.orderbook.create_subscription(
                symbol="DOGE-USDT", depth=50, bucket="0.1"
            )
            last_seq, last_qty = buffered[-1]
            async with asyncio.timeout(5):
                first = await anext(sub)
            assert (first.book_seq, first.bids[0].qty.scaled) == (str(last_seq), last_qty)
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.3):
                    extra = await anext(sub)
                    pytest.fail(f"one book state added a second view: {extra}")

            # The next bucket change reads its own view, not a stale one.
            sub.set_bucket("0.001")
            async with asyncio.timeout(5):
                fine = await anext(sub)
            assert fine.bids[0].price.ticks == 71_000_000, "bid bucket price"
            await sub.aclose()
        finally:
            await client.aclose()
            await http.aclose()
