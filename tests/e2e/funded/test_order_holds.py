import asyncio
from decimal import ROUND_FLOOR, Decimal

import pytest

from polyester.models import ClientOrderId
from tests.e2e.helpers import (
    unique_client_order_id,
    wait_for_open_order,
)
from tests.helpers import (
    min_base_qty_for_pair,
    pair_tick_size,
    quote_asset_id_for_symbol,
    reserved_balance_raw,
)


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_order_hold_visible_while_open(
    live_client,
    trade_symbol,
    funded_enabled,
    mutation_enabled,
    require_trade_trading_balance,
):
    spot = await live_client.market_data.get_spot_config()
    quote_asset_id = quote_asset_id_for_symbol(
        spot.raw,
        trade_symbol,
        zipper_raw=live_client.catalogs.zipper_config,
    )
    assert quote_asset_id is not None
    before = reserved_balance_raw(await live_client.balances.list(), quote_asset_id)
    pair = next(p for p in spot.raw["pairs"] if p["symbol"] == trade_symbol)
    book = await live_client.orderbook.get(symbol=trade_symbol, depth=5)
    assert book.bids, "a live bid is required to choose a far-from-market price"
    tick = Decimal(pair_tick_size(pair))
    price = str(
        (Decimal(book.bids[0].price.format()) / 2 / tick).to_integral_value(rounding=ROUND_FLOOR)
        * tick
    )
    qty = min_base_qty_for_pair(pair, price)
    client_order_id = unique_client_order_id("hold")

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
        )
        assert created.client_order_id == client_order_id
        assert created.order_id
        open_order = await wait_for_open_order(live_client, client_order_id)
        assert open_order.order_id == created.order_id

        for _ in range(40):
            reserved = reserved_balance_raw(await live_client.balances.list(), quote_asset_id)
            if reserved > before:
                break
            await asyncio.sleep(0.25)
        print(f"reserved quote balance: before={before} resting={reserved}")
        assert reserved > before, "resting post-only order never increased reserved balance"
    finally:
        await live_client.orders.cancel(
            key=ClientOrderId(client_order_id),
            symbol=trade_symbol,
        )

    for _ in range(40):
        reserved = reserved_balance_raw(await live_client.balances.list(), quote_asset_id)
        if reserved == before:
            break
        await asyncio.sleep(0.25)
    print(f"reserved quote balance after cancel={reserved}")
    assert reserved == before, "cancel did not release reserved balance"
    orders = await live_client.orders.list_open(limit=100)
    assert all(order.client_order_id != client_order_id for order in orders.orders)
