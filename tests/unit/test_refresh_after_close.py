"""A closed subscription's snapshot refresh sends no request.

``refresh_snapshot()`` on a closed market overview or order book subscription
returns ``False`` without fetching a snapshot, whether it is called after the
close or was queued behind a refresh in flight when the subscription closed.
A refresh in flight at the close still ends ``False`` once its request answers.
Neither delivers a view or calls ``on_error``. An open subscription's refresh
fetches and delivers its snapshot and returns ``True``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.polyester.type.v1 import depth_tier_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    wait_until,
)
from tests.unit.test_server_unsubscribe import CentrifugoServer


def _overview_snapshot() -> bytes:
    response = marketoverview_pb2.ListMarketOverviewResponse()
    response.markets.add(symbol_id=1, last_price_ticks=61_000)
    return response.SerializeToString()


def _book_snapshot() -> bytes:
    response = orderbook_pb2.GetOrderBookResponse(
        symbol_id=1, book_seq=1, available=True, depth=depth_tier_pb2.DEPTH_50
    )
    response.bids.add(price_ticks=71_600_000, qty_scaled=1)
    response.asks.add(price_ticks=71_700_000, qty_scaled=4)
    return response.SerializeToString()


@dataclass
class _Snapshots:
    """Answers each snapshot request; holds the ones made while ``hold`` is set."""

    body: bytes
    path: str
    requests: int = 0
    hold: bool = False
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def handler(self, request: ParsedRequest) -> HttpScript:
        assert request.path.endswith(self.path), request.path
        self.requests += 1
        if self.hold:
            await self.release.wait()
        return connect_proto_response(self.body)


@dataclass
class _Callbacks:
    events: list[Any] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)


Open = Callable[[AsyncPolyester, _Callbacks], Awaitable[Any]]


async def _open_overview(client: AsyncPolyester, callbacks: _Callbacks) -> Any:
    return await client.market_overview.create_subscription(
        on_event=callbacks.events.append, on_error=callbacks.errors.append
    )


async def _open_book(client: AsyncPolyester, callbacks: _Callbacks) -> Any:
    return await client.orderbook.create_subscription(
        symbol="DOGE-USDT",
        depth=50,
        on_event=callbacks.events.append,
        on_error=callbacks.errors.append,
        on_snapshot_refresh=lambda: callbacks.events.append("snapshot_refresh"),
    )


SUBSCRIPTIONS = [
    pytest.param(_open_overview, _overview_snapshot(), "/ListMarketOverview", id="market_overview"),
    pytest.param(_open_book, _book_snapshot(), "/GetOrderBook", id="orderbook"),
]


async def _with_subscription(
    open_subscription: Open,
    snapshots: _Snapshots,
    body: Callable[[Any, _Callbacks], Awaitable[None]],
) -> None:
    async with CentrifugoServer() as server:
        http = await MockHttpServer.spawn(snapshots.handler)
        client = AsyncPolyester(api_url=http.base_url, ws_url=server.url, hydrate_catalogs=False)
        client.catalogs.hydrate_spot_config(
            {"pairs": [{"symbol": "DOGE-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
        )
        callbacks = _Callbacks()
        try:
            sub = await open_subscription(client, callbacks)
            assert snapshots.requests == 1
            await body(sub, callbacks)
        finally:
            snapshots.release.set()
            await client.aclose()
            await http.aclose()


@pytest.mark.parametrize(("open_subscription", "body", "path"), SUBSCRIPTIONS)
async def test_a_refresh_queued_behind_one_in_flight_at_close_sends_nothing(
    open_subscription: Open, body: bytes, path: str
) -> None:
    snapshots = _Snapshots(body, path)

    async def scenario(sub: Any, callbacks: _Callbacks) -> None:
        snapshots.hold = True
        in_flight = asyncio.create_task(sub.refresh_snapshot())
        await wait_until(lambda: snapshots.requests == 2, timeout=5)
        queued = asyncio.create_task(sub.refresh_snapshot())
        await asyncio.sleep(0)
        assert not queued.done()
        delivered = len(callbacks.events)

        await sub.aclose()
        snapshots.release.set()
        assert await in_flight is False
        assert await queued is False
        assert snapshots.requests == 2
        assert len(callbacks.events) == delivered
        assert callbacks.errors == []

    await _with_subscription(open_subscription, snapshots, scenario)


@pytest.mark.parametrize(("open_subscription", "body", "path"), SUBSCRIPTIONS)
async def test_a_refresh_after_close_sends_nothing(
    open_subscription: Open, body: bytes, path: str
) -> None:
    snapshots = _Snapshots(body, path)

    async def scenario(sub: Any, callbacks: _Callbacks) -> None:
        delivered = len(callbacks.events)
        await sub.aclose()
        assert await sub.refresh_snapshot() is False
        assert snapshots.requests == 1
        assert len(callbacks.events) == delivered
        assert callbacks.errors == []

    await _with_subscription(open_subscription, snapshots, scenario)


@pytest.mark.parametrize(("open_subscription", "body", "path"), SUBSCRIPTIONS)
async def test_an_open_subscription_refresh_delivers_its_snapshot(
    open_subscription: Open, body: bytes, path: str
) -> None:
    snapshots = _Snapshots(body, path)

    async def scenario(sub: Any, callbacks: _Callbacks) -> None:
        delivered = len(callbacks.events)
        assert await sub.refresh_snapshot() is True
        assert snapshots.requests == 2
        assert len(callbacks.events) > delivered
        assert callbacks.errors == []
        await sub.aclose()

    await _with_subscription(open_subscription, snapshots, scenario)
