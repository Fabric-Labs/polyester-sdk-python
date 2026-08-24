"""Live create → get(include_attached_risk) → cancel for attached TP/SL."""

from __future__ import annotations

import pytest

from polyester.models import ClientOrderId
from polyester.types.money import resolve_price_ticks
from tests.e2e.helpers import (
    unique_client_order_id,
    usdt_funded_buy_limit_params,
    wait_for_open_order,
)
from tests.helpers import (
    DevnetOrderNotIndexedError,
    devnet_order_read_index_skip_message,
    devnet_order_skip_message,
    is_devnet_order_internal_error,
    pair_for_symbol,
    pair_tick_size,
    resolve_far_above_buy_stop_price,
)


async def _bracket_prices(client, symbol: str) -> tuple[str, str, str, str]:
    """Parent far-below buy plus TP/SL that should not fire while resting."""
    from polyester.codecs.scalars import align_price_ticks, format_price_ticks, parse_price_ticks

    price, qty = await usdt_funded_buy_limit_params(client, symbol)
    spot = await client.market_data.get_spot_config()
    pair = pair_for_symbol(spot.raw, symbol) or {}
    take_profit = await resolve_far_above_buy_stop_price(client, symbol, pair)
    tick_size = pair_tick_size(pair)
    parent_ticks = parse_price_ticks(price, "price")
    stop_ticks = align_price_ticks(max(parent_ticks // 2, 1), tick_size)
    stop_loss = format_price_ticks(stop_ticks)
    return price, qty, take_profit, stop_loss


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_create_attached_tp_sl_round_trips(
    live_client,
    trade_symbol,
    funded_enabled,
    mutation_enabled,
    require_trade_trading_balance,
):
    """Friendly attached_risk must survive create and come back on get."""
    price, qty, take_profit, stop_loss = await _bracket_prices(live_client, trade_symbol)
    client_order_id = unique_client_order_id("tp-sl")
    attached_risk = {
        "take_profit": {"trigger_price": take_profit, "order_type": "market"},
        "stop_loss": {"trigger_price": stop_loss, "order_type": "market"},
        "oco": True,
    }

    try:
        created = await live_client.orders.create(
            symbol=trade_symbol,
            side="buy",
            order_type="limit",
            tif="gtc",
            qty=qty,
            price=price,
            post_only=True,
            client_order_id=client_order_id,
            attached_risk=attached_risk,
        )
    except Exception as exc:
        if is_devnet_order_internal_error(exc):
            pytest.skip(devnet_order_skip_message())
        raise
    assert created.status
    assert created.client_order_id == client_order_id
    assert created.order_id

    try:
        try:
            await wait_for_open_order(live_client, client_order_id)
        except DevnetOrderNotIndexedError:
            pytest.skip(devnet_order_read_index_skip_message())

        detail = await live_client.orders.get(
            key=ClientOrderId(client_order_id),
            include_attached_risk=True,
        )
        assert detail.order is not None
        risk = detail.order.attached_risk
        assert risk is not None
        assert risk.oco is True
        assert risk.take_profit is not None
        assert risk.take_profit.order_type == "market"
        assert risk.take_profit.trigger_price is not None
        assert risk.take_profit.trigger_price.ticks == resolve_price_ticks(
            take_profit, "take_profit"
        )
        assert risk.stop_loss is not None
        assert risk.stop_loss.order_type == "market"
        assert risk.stop_loss.trigger_price is not None
        assert risk.stop_loss.trigger_price.ticks == resolve_price_ticks(
            stop_loss, "stop_loss"
        )
        assert risk.trailing_stop is None
    finally:
        await live_client.orders.cancel(
            key=ClientOrderId(client_order_id),
            symbol=trade_symbol,
        )
