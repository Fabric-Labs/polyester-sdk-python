import pytest

from polyester.models import ClientOrderId
from tests.e2e.helpers import (
    unique_client_order_id,
    usdt_funded_buy_limit_params,
    wait_for_open_order,
)
from tests.helpers import (
    devnet_order_skip_message,
    is_devnet_order_internal_error,
    quote_asset_id_for_symbol,
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
    capabilities,
):
    if not capabilities["list_holds"]:
        pytest.skip("list_holds unavailable on devnet")

    price, qty = await usdt_funded_buy_limit_params(live_client, trade_symbol)
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
    except Exception as exc:
        if is_devnet_order_internal_error(exc):
            pytest.skip(devnet_order_skip_message())
        raise
    assert created.status
    assert created.client_order_id == client_order_id
    assert created.order_id

    try:
        open_order = await wait_for_open_order(live_client, client_order_id)
        assert open_order.order_id == created.order_id

        spot = await live_client.market_data.get_spot_config()
        quote_asset_id = quote_asset_id_for_symbol(
            spot.raw,
            trade_symbol,
            zipper_raw=live_client.catalogs.zipper_config,
        )
        assert quote_asset_id is not None
        holds = await live_client.balances.list_holds(limit=20)
        assert any(
            hold.asset_id == quote_asset_id and int(hold.amount_reserved) > 0
            for hold in holds.holds
        )
    finally:
        await live_client.orders.cancel(
            key=ClientOrderId(client_order_id),
            symbol=trade_symbol,
        )
