import os
from decimal import Decimal

import pytest

from polyester import AsyncPolyester
from tests.e2e.funded.test_spot_fill import (
    _hydrate_test_catalogs,
    _maker_credentials,
    _wait_for_filled_order,
    _wait_for_trade_match,
)
from tests.e2e.helpers import unique_client_order_id
from tests.helpers import (
    FAR_ABOVE_BUY_STOP_PRICE_HINTS,
    base_asset_id_for_symbol,
    devnet_order_skip_message,
    is_devnet_order_internal_error,
    min_base_qty_for_pair,
    quote_asset_id_for_symbol,
    trading_balance_decimal,
)


def _trade_e2e_enabled() -> bool:
    return os.getenv("POLYESTER_TEST_TRADE_E2E", "").lower() in {"1", "true", "yes"}


@pytest.mark.integration
@pytest.mark.funded
async def test_market_order_fill(
    live_client, trade_symbol, funded_enabled, require_trade_trading_balance
):
    if not _trade_e2e_enabled():
        pytest.skip("Set POLYESTER_TEST_TRADE_E2E=1 to run market order fill e2e")

    maker_credentials = _maker_credentials()
    if maker_credentials is None:
        pytest.skip(
            "Set POLYESTER_TEST_MAKER_API_KEY_ID and "
            "POLYESTER_TEST_MAKER_API_PRIVATE_KEY for market order fill e2e"
        )

    maker_key_id, maker_private_key = maker_credentials
    maker = AsyncPolyester(
        api_key_id=maker_key_id,
        api_private_key=maker_private_key,
        api_url=live_client.api_url,
        hydrate_catalogs=True,
    )
    maker_cid = unique_client_order_id("maker-mkt")
    taker_cid = unique_client_order_id("taker-mkt")
    maker_order_created = False
    taker_order_created = False

    try:
        spot_raw, zipper_raw = await _hydrate_test_catalogs(live_client)
        await _hydrate_test_catalogs(maker)
        pair = next(
            (p for p in spot_raw.get("pairs") or [] if p.get("symbol") == trade_symbol), {}
        )
        if not pair:
            pytest.skip(f"Trade symbol {trade_symbol} is not in spot config")

        price = (
            os.getenv("POLYESTER_TEST_TRADE_PRICE")
            or FAR_ABOVE_BUY_STOP_PRICE_HINTS.get(trade_symbol)
            or "50000"
        )
        qty = os.getenv("POLYESTER_TEST_TRADE_QTY") or min_base_qty_for_pair(pair, price)
        qty_decimal = Decimal(qty)

        quote_asset_id = quote_asset_id_for_symbol(
            spot_raw, trade_symbol, zipper_raw=zipper_raw
        )
        base_asset_id = base_asset_id_for_symbol(spot_raw, trade_symbol, zipper_raw=zipper_raw)
        assert quote_asset_id is not None
        assert base_asset_id is not None

        taker_before = await live_client.balances.list()
        taker_quote_before = trading_balance_decimal(taker_before, quote_asset_id)
        taker_base_before = trading_balance_decimal(taker_before, base_asset_id)
        required_quote = Decimal(price) * qty_decimal
        if taker_quote_before < required_quote:
            pytest.skip(
                f"Taker quote balance {taker_quote_before} below required {required_quote} "
                f"for {qty} {trade_symbol} at {price}"
            )

        maker_before = await maker.balances.list()
        maker_quote_before = trading_balance_decimal(maker_before, quote_asset_id)
        maker_base_before = trading_balance_decimal(maker_before, base_asset_id)
        if maker_base_before < qty_decimal:
            pytest.skip(
                f"Maker base balance {maker_base_before} below fill quantity {qty_decimal}"
            )

        try:
            maker_created = await maker.orders.create(
                symbol=trade_symbol,
                side="sell",
                order_type="limit",
                tif="gtc",
                qty=qty,
                price=price,
                post_only=True,
                client_order_id=maker_cid,
            )
        except Exception as exc:
            if is_devnet_order_internal_error(exc):
                pytest.skip(devnet_order_skip_message())
            raise
        assert maker_created.client_order_id == maker_cid
        assert maker_created.order_id
        maker_order_created = True

        try:
            taker_created = await live_client.orders.create(
                symbol=trade_symbol,
                side="buy",
                order_type="market",
                tif="ioc",
                qty=qty,
                client_order_id=taker_cid,
            )
        except Exception as exc:
            if is_devnet_order_internal_error(exc):
                pytest.skip(devnet_order_skip_message())
            raise
        assert taker_created.client_order_id == taker_cid
        assert taker_created.order_id
        taker_order_created = True

        taker_detail = await _wait_for_filled_order(live_client, taker_cid)
        if taker_detail.order is not None and taker_detail.order.order_type:
            assert taker_detail.order.order_type == "market"

        taker_match_ids = {trade.match_id for trade in taker_detail.trades}
        assert taker_match_ids

        maker_detail = await _wait_for_filled_order(maker, maker_cid)
        maker_match_ids = {trade.match_id for trade in maker_detail.trades}
        assert taker_match_ids & maker_match_ids
        match_id = next(iter(taker_match_ids & maker_match_ids))

        taker_trade = await _wait_for_trade_match(live_client, trade_symbol, match_id)
        assert taker_trade.side == "buy"
        maker_trade = await _wait_for_trade_match(maker, trade_symbol, match_id)
        assert maker_trade.side == "sell"

        taker_after = await live_client.balances.list()
        assert trading_balance_decimal(taker_after, base_asset_id) > taker_base_before
        assert trading_balance_decimal(taker_after, quote_asset_id) < taker_quote_before

        maker_after = await maker.balances.list()
        assert trading_balance_decimal(maker_after, base_asset_id) < maker_base_before
        assert trading_balance_decimal(maker_after, quote_asset_id) > maker_quote_before
    finally:
        if taker_order_created:
            await live_client.orders.cancel_all(symbol=trade_symbol, dry_run=False)
        if maker_order_created:
            await maker.orders.cancel_all(symbol=trade_symbol, dry_run=False)
        await maker.aclose()
