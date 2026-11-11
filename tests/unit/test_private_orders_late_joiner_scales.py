"""A consumer that joins a running order stream gets the cached view at the
scales the catalogs know when it joins.

The stream caches the live view for consumers that join later. When that view
was decoded before the catalogs loaded, replaying the cached orders as they
were would hand the late consumer quantities without a scale although the
catalogs now know it. The cached view is decoded again with the current
scales: a pair the catalogs list gets its scale (zero included), a pair they
don't list stays unscaled.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models import PrivateOrdersConnected, PrivateOrdersSnapshot, PrivateOrdersUnit
from polyester.realtime.private_orders import PrivateOrderStream
from polyester.services.orders import AsyncOrdersService
from tests.unit.test_private_orders_stream import (
    ACCOUNT_B58,
    FakePrivateWsServer,
    fast_backoff,  # noqa: F401  (autouse fixture)
    next_event,
    open_stream,
    server,  # noqa: F401  (fixture)
    stream,  # noqa: F401  (fixture)
    tokens,  # noqa: F401  (fixture)
)

PAIRS = [
    {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8, "quote_quantity_scale": 6},
    {"symbol": "ZERO-USDT", "symbol_id": 2, "base_quantity_scale": 0, "quote_quantity_scale": 0},
]


def _order(order_id: int, symbol_id: int, version: int = 1) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(
        order_id=order_id,
        symbol_id=symbol_id,
        side=orders_pb2.BUY,
        version=version,
        orig_qty_scaled=231_500,
        cum_qty_scaled=100_000,
    )


def _scales(order) -> tuple[int | None, int | None]:
    assert order.cum_qty is not None and order.orig_qty is not None
    assert order.cum_qty.scale == order.orig_qty.scale
    return order.cum_qty.scale, order.quote_quantity_scale


@pytest.mark.asyncio
async def test_late_consumer_gets_the_cached_view_at_the_scales_known_when_it_joins(
    server: FakePrivateWsServer,  # noqa: F811
    stream: PrivateOrderStream,  # noqa: F811
) -> None:
    catalogs = CatalogManager()
    stream.order_scales = AsyncOrdersService(MagicMock(), catalogs, None)._order_scales

    first, conn = await open_stream(server, stream)
    # The snapshot arrives before the catalogs load: no scale is known yet.
    await conn.snapshot("s1", "c1", [_order(1, 1), _order(2, 2), _order(3, 99)])
    early = await next_event(first)
    assert isinstance(early, PrivateOrdersSnapshot)
    assert [_scales(o) for o in early.orders] == [(None, None)] * 3

    catalogs.hydrate_spot_config({"pairs": PAIRS})

    # A second consumer joins without any further server update.
    late = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(late), PrivateOrdersConnected)
    cached = await next_event(late)
    assert isinstance(cached, PrivateOrdersSnapshot)
    by_id = {o.order_id: o for o in cached.orders}
    assert [o.order_id for o in cached.orders] == [o.order_id for o in early.orders]
    btc, zero, unknown = (by_id[o.order_id] for o in early.orders)
    assert _scales(btc) == (8, 6)
    assert btc.cum_qty is not None and btc.cum_qty.as_decimal() == Decimal("0.001")
    assert _scales(zero) == (0, 0)
    assert zero.cum_qty is not None and zero.cum_qty.as_decimal() == Decimal(100_000)
    assert _scales(unknown) == (None, None)

    # A unit applied after the join keeps the cache current, at the known scales.
    await conn.send(
        "s1", 4, unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[_order(1, 1, 2)])
    )
    for consumer in (first, late):
        unit = await next_event(consumer)
        assert isinstance(unit, PrivateOrdersUnit)
        assert _scales(unit.orders[0]) == (8, 6)
    third = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(third), PrivateOrdersConnected)
    replay = await next_event(third)
    assert isinstance(replay, PrivateOrdersSnapshot)
    assert [(o.order_id, o.version, _scales(o)) for o in replay.orders] == [
        (btc.order_id, 2, (8, 6)),
        (zero.order_id, 1, (0, 0)),
        (unknown.order_id, 1, (None, None)),
    ]


@pytest.mark.asyncio
async def test_without_scales_the_cached_view_replays_unscaled(
    server: FakePrivateWsServer,  # noqa: F811
    stream: PrivateOrderStream,  # noqa: F811
) -> None:
    first, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [_order(1, 1)])
    assert isinstance(await next_event(first), PrivateOrdersSnapshot)
    late = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(late), PrivateOrdersConnected)
    cached = await next_event(late)
    assert isinstance(cached, PrivateOrdersSnapshot)
    assert _scales(cached.orders[0]) == (None, None)
