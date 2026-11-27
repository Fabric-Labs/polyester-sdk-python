"""``on_event`` and the iterator see an order book's views in one order.

A ``set_bucket()`` called from ``on_event`` adds its view after the one being
delivered, on both surfaces: the callback and the iterator see the same
sequence, and the last view is grouped by the latest bucket requested.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest

from polyester import AsyncPolyester, Polyester
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.polyester.type.v1 import depth_tier_pb2
from polyester.models.common import OrderbookData
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)
from tests.unit.test_server_unsubscribe import CentrifugoServer

BID = 71_600_000
# A bid of 71_600_000 ticks read by bucket: raw, "0.01" and "0.001".
RAW, CENT, MILLI = BID, 70_000_000, 71_000_000


async def _snapshot(_request: ParsedRequest) -> HttpScript:
    response = orderbook_pb2.GetOrderBookResponse(
        symbol_id=1, book_seq=1, available=True, depth=depth_tier_pb2.DEPTH_20
    )
    response.bids.add(price_ticks=BID, qty_scaled=1)
    response.asks.add(price_ticks=71_700_000, qty_scaled=4)
    return connect_proto_response(response.SerializeToString())


def _bid(view: OrderbookData) -> int:
    return view.bids[0].price.ticks


@asynccontextmanager
async def _servers() -> AsyncIterator[tuple[str, str]]:
    async with CentrifugoServer() as ws:
        http = await MockHttpServer.spawn(_snapshot)
        try:
            yield http.base_url, ws.url
        finally:
            await http.aclose()


def _catalog(client: AsyncPolyester | Polyester) -> None:
    client.catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "DOGE-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )


async def _deliveries(
    on_view: Callable[[Any, OrderbookData], None], changes: int
) -> tuple[list[int], list[int]]:
    """The bids the callback and the iterator saw: the snapshot's view, then
    ``changes`` more, with ``on_view(sub, view)`` run from ``on_event``."""
    called: list[int] = []
    holder: dict[str, Any] = {}

    def on_event(view: OrderbookData) -> None:
        called.append(_bid(view))
        # The snapshot view arrives during create_subscription, before sub is set.
        on_view(holder.get("sub"), view)

    async with _servers() as (api_url, ws_url):
        client = AsyncPolyester(api_url=api_url, ws_url=ws_url, hydrate_catalogs=False)
        _catalog(client)
        try:
            sub = await client.orderbook.create_subscription(
                symbol="DOGE-USDT", depth=20, on_event=on_event
            )
            holder["sub"] = sub
            iterated = [_bid(await anext(sub))]
            sub.set_bucket("0.01")
            async with asyncio.timeout(5):
                for _ in range(changes):
                    iterated.append(_bid(await anext(sub)))
            await sub.aclose()
        finally:
            await client.aclose()
    return called, iterated


async def test_a_set_bucket_from_on_event_comes_after_the_view_being_delivered() -> None:
    def ungroup_once_grouped(sub: Any, view: OrderbookData) -> None:
        if _bid(view) == CENT:
            sub.set_bucket(None)

    called, iterated = await _deliveries(ungroup_once_grouped, changes=2)
    assert called == [RAW, CENT, RAW]
    assert iterated == called


async def test_nested_set_buckets_keep_their_order_and_the_latest_bucket_last() -> None:
    def regroup(sub: Any, view: OrderbookData) -> None:
        if _bid(view) == CENT:
            sub.set_bucket("0.001")
            sub.set_bucket(None)

    called, iterated = await _deliveries(regroup, changes=3)
    assert called == [RAW, CENT, MILLI, RAW]
    assert iterated == called


async def test_a_set_bucket_after_on_event_returns_stays_in_order() -> None:
    called, iterated = await _deliveries(lambda _sub, _view: None, changes=1)
    assert called == iterated == [RAW, CENT]


async def test_the_sync_client_delivers_a_nested_set_bucket_after_the_current_view() -> None:
    # The sync client feeds on_event from the iterator, and schedules its
    # set_bucket on the client loop: one surface, in publication order.
    async with _servers() as (api_url, ws_url):

        def run() -> list[int]:
            seen: list[int] = []
            third = threading.Event()
            with Polyester(api_url=api_url, ws_url=ws_url, hydrate_catalogs=False) as client:
                _catalog(client)
                holder: dict[str, Any] = {}

                def on_event(view: OrderbookData) -> None:
                    seen.append(_bid(view))
                    if _bid(view) == CENT:
                        holder["sub"].set_bucket(None)
                    if len(seen) == 3:
                        third.set()

                holder["sub"] = client.orderbook.subscribe_sync(
                    symbol="DOGE-USDT", depth=20, on_event=on_event
                )
                holder["sub"].set_bucket("0.01")
                assert third.wait(5), seen
                holder["sub"].close()
            return seen

        assert await asyncio.to_thread(run) == [RAW, CENT, RAW]


async def test_views_are_delivered_again_after_on_event_raises() -> None:
    called: list[int] = []

    def on_event(view: OrderbookData) -> None:
        called.append(_bid(view))
        if _bid(view) == CENT:
            sub.set_bucket(None)
            raise RuntimeError("callback failed")

    async with _servers() as (api_url, ws_url):
        client = AsyncPolyester(api_url=api_url, ws_url=ws_url, hydrate_catalogs=False)
        _catalog(client)
        try:
            sub = await client.orderbook.create_subscription(
                symbol="DOGE-USDT", depth=20, on_event=on_event
            )
            assert _bid(await anext(sub)) == RAW
            with pytest.raises(RuntimeError, match="callback failed"):
                sub.set_bucket("0.01")
            # The failed view and the one queued behind it are not delivered;
            # the next change is, on both surfaces.
            sub.set_bucket("0.001")
            async with asyncio.timeout(5):
                assert _bid(await anext(sub)) == MILLI
            assert called == [RAW, CENT, MILLI]
            await sub.aclose()
        finally:
            await client.aclose()
