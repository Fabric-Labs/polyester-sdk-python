"""POLY-3746: wait_for_order_trades_complete polls until trade qtys match cum_qty."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from polyester.errors import PolyesterTransportError
from polyester.models.trading import GetOrderResult, Order, UserTrade
from polyester.services.orders import wait_for_order_trades_complete
from polyester.types.money import Quantity


@pytest.mark.asyncio
async def test_wait_for_order_trades_complete_resolves_when_sum_matches() -> None:
    calls = {"n": 0}

    async def fake_get(**kwargs):
        calls["n"] += 1
        order = Order(
            order_id="1",
            symbol_id=1,
            cum_qty=Quantity.from_scaled(100, scale=6),
        )
        if calls["n"] == 1:
            return GetOrderResult(order=order, trades=[])
        return GetOrderResult(
            order=order,
            trades=[
                UserTrade(symbol_id=1, qty=Quantity.from_scaled(40, scale=6)),
                UserTrade(symbol_id=1, qty=Quantity.from_scaled(60, scale=6)),
            ],
        )

    orders = AsyncMock()
    orders.get = AsyncMock(side_effect=fake_get)
    result = await wait_for_order_trades_complete(
        orders,
        order_id=1,
        timeout=2.0,
        poll_interval=0.01,
    )
    assert calls["n"] == 2
    assert sum(t.qty.scaled for t in result.trades if t.qty) == 100


@pytest.mark.asyncio
async def test_wait_for_order_trades_complete_times_out() -> None:
    order = Order(
        order_id="1",
        symbol_id=1,
        cum_qty=Quantity.from_scaled(100, scale=6),
    )
    orders = AsyncMock()
    orders.get = AsyncMock(return_value=GetOrderResult(order=order, trades=[]))
    with pytest.raises(PolyesterTransportError, match="timed out"):
        await wait_for_order_trades_complete(
            orders,
            order_id=1,
            timeout=0.05,
            poll_interval=0.01,
        )
