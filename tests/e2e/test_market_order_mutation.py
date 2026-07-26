import pytest

from tests.e2e.helpers import (
    btc_usdt_market_qty,
    unique_client_order_id,
    wait_for_terminal_order,
)
from tests.helpers import (
    base_asset_id_for_symbol,
    devnet_order_skip_message,
    is_devnet_order_internal_error,
    resolve_market_ref_price,
    trading_balance_decimal,
)

pytestmark = [
    pytest.mark.account_wide_cleanup,
    pytest.mark.usefixtures("account_wide_cleanup_enabled"),
]


async def _require_trading_base_balance(live_client, symbol: str, qty: str) -> None:
    from tests.helpers import skip_funding_check

    if skip_funding_check():
        return
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    if not live_client.catalogs.zipper:
        zipper = await live_client.zipper.get_deposit_withdraw_config()
        live_client.catalogs.hydrate_zipper_config(zipper)
    base_asset_id = base_asset_id_for_symbol(
        spot.raw,
        symbol,
        zipper_raw=live_client.catalogs.zipper_config,
    )
    assert base_asset_id is not None
    balances = await live_client.balances.list()
    balance = trading_balance_decimal(balances, base_asset_id)
    from decimal import Decimal

    if balance < Decimal(qty):
        pytest.skip(
            f"Trading base balance {balance} below required {qty} for asset {base_asset_id}; "
            "fund BTC in trading or set POLYESTER_TEST_SKIP_FUNDING_CHECK=1"
        )


@pytest.mark.integration
@pytest.mark.mutation
async def test_market_buy_mutation(live_client, mutation_enabled, require_trade_trading_balance):
    symbol = "BTC-USDT"
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == symbol), {})
    assert pair
    qty = await btc_usdt_market_qty(live_client, symbol)
    ref_price = await resolve_market_ref_price(live_client, symbol, pair, side="buy")
    client_order_id = unique_client_order_id("mkt-buy")

    try:
        created = await live_client.orders.create(
            symbol=symbol,
            side="buy",
            order_type="market",
            tif="ioc",
            qty=qty,
            market_client_ref_price=ref_price,
            client_order_id=client_order_id,
        )
    except Exception as exc:
        if is_devnet_order_internal_error(exc):
            pytest.skip(devnet_order_skip_message())
        raise

    assert created.client_order_id == client_order_id
    assert created.order_id
    assert created.status

    if created.status in {"canceled", "rejected", "filled"}:
        return

    try:
        detail = await wait_for_terminal_order(live_client, client_order_id)
        assert detail.order is not None
        if detail.order.order_type:
            assert detail.order.order_type == "market"
        assert detail.order.status in {"canceled", "rejected", "filled"}
    finally:
        await live_client.orders.cancel_all(symbol=symbol, dry_run=False)


@pytest.mark.integration
@pytest.mark.mutation
async def test_market_sell_mutation(live_client, mutation_enabled):
    symbol = "BTC-USDT"
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == symbol), {})
    assert pair
    qty = await btc_usdt_market_qty(live_client, symbol)
    await _require_trading_base_balance(live_client, symbol, qty)
    client_order_id = unique_client_order_id("mkt-sell")
    ref_price = await resolve_market_ref_price(live_client, symbol, pair, side="sell")

    try:
        created = await live_client.orders.create(
            symbol=symbol,
            side="sell",
            order_type="market",
            tif="ioc",
            qty=qty,
            market_client_ref_price=ref_price,
            client_order_id=client_order_id,
        )
    except Exception as exc:
        if is_devnet_order_internal_error(exc):
            pytest.skip(devnet_order_skip_message())
        raise

    assert created.client_order_id == client_order_id
    assert created.order_id
    assert created.status

    if created.status in {"canceled", "rejected", "filled"}:
        return

    try:
        detail = await wait_for_terminal_order(live_client, client_order_id)
        assert detail.order is not None
        if detail.order.order_type:
            assert detail.order.order_type == "market"
        assert detail.order.status in {"canceled", "rejected", "filled"}
    finally:
        await live_client.orders.cancel_all(symbol=symbol, dry_run=False)
