"""POLY-3746: wait_for_order_trades_complete polls until trade qtys match cum_qty."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from polyester.errors import PolyesterTransportError
from polyester.models import OrderId
from polyester.models.trading import GetOrderResult, Order, UserTrade
from polyester.services.orders import wait_for_order_trades_complete
from polyester.types.money import Quantity


def _qty(scaled: int) -> Quantity:
    return Quantity.from_scaled(scaled, scale=6)


@pytest.mark.asyncio
async def test_wait_for_order_trades_complete_resolves_when_sum_matches() -> None:
    calls = {"n": 0}

    async def fake_get(**kwargs):
        calls["n"] += 1
        order = Order(
            order_id="1",
            symbol_id=1,
            cum_qty=_qty(100),
        )
        if calls["n"] == 1:
            return GetOrderResult(order=order, trades=[])
        return GetOrderResult(
            order=order,
            trades=[
                UserTrade(symbol_id=1, qty=_qty(40)),
                UserTrade(symbol_id=1, qty=_qty(60)),
            ],
        )

    orders = AsyncMock()
    orders.get = AsyncMock(side_effect=fake_get)
    result = await wait_for_order_trades_complete(
        orders,
        key=OrderId(1),
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
        cum_qty=_qty(100),
    )
    orders = AsyncMock()
    orders.get = AsyncMock(return_value=GetOrderResult(order=order, trades=[]))
    with pytest.raises(PolyesterTransportError, match="timed out"):
        await wait_for_order_trades_complete(
            orders,
            key=OrderId(1),
            timeout=0.05,
            poll_interval=0.01,
        )


@pytest.mark.asyncio
async def test_wait_for_order_trades_complete_pages_execution_history() -> None:
    calls: list[dict] = []
    order = Order(order_id="11", symbol_id=1, cum_qty=_qty(100))

    async def fake_get(**kwargs):
        calls.append(kwargs)
        if kwargs.get("page_token") == "page-2":
            return GetOrderResult(
                order=order,
                trades=[UserTrade(symbol_id=1, qty=_qty(60))],
            )
        return GetOrderResult(
            order=order,
            trades=[UserTrade(symbol_id=1, qty=_qty(40))],
            next_page_token="page-2",
        )

    orders = AsyncMock()
    orders.get = AsyncMock(side_effect=fake_get)
    result = await wait_for_order_trades_complete(
        orders,
        key=OrderId(11),
        timeout=2.0,
        poll_interval=0.01,
    )
    assert [call.get("page_token") for call in calls] == [None, "page-2"]
    assert all(call.get("include_execution_history") is True for call in calls)
    assert sum(t.qty.scaled for t in result.trades if t.qty) == 100
    assert result.next_page_token == ""
