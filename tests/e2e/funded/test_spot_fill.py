import asyncio
import os
from decimal import Decimal

import pytest

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_price_ticks
from polyester.errors import PolyesterApiError
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


def _maker_credentials() -> tuple[str, str] | None:
    key_id = os.getenv("POLYESTER_TEST_MAKER_API_KEY_ID")
    private_key = os.getenv("POLYESTER_TEST_MAKER_API_PRIVATE_KEY")
    if not key_id or not private_key:
        return None
    return key_id, private_key


async def _hydrate_test_catalogs(client) -> tuple[dict, dict]:
    spot = await client.market_data.get_spot_config()
    client.catalogs.hydrate_spot_config(spot.raw)
    if not client.catalogs.zipper:
        zipper = await client.zipper.get_deposit_withdraw_config()
        client.catalogs.hydrate_zipper_config(zipper)
    return spot.raw, client.catalogs.zipper_config


async def _wait_for_filled_order(client, client_order_id: str, *, timeout: float = 20):
    attempts = max(1, int(timeout / 0.5))
    last_detail = None
    for _ in range(attempts):
        detail = await client.orders.get(client_order_id=client_order_id)
        last_detail = detail
        if detail.order is not None and detail.order.status == "filled" and detail.trades:
            return detail
        await asyncio.sleep(0.5)
    raise AssertionError(f"Order {client_order_id} did not fill within {timeout}s: {last_detail}")


async def _wait_for_trade_match(client, symbol: str, match_id: str, *, timeout: float = 20):
    attempts = max(1, int(timeout / 0.5))
    for _ in range(attempts):
        trades = await client.trades.list(symbol=symbol, limit=25)
        for trade in trades.trades:
            if trade.match_id == match_id:
                return trade
        await asyncio.sleep(0.5)
    raise AssertionError(f"User trade {match_id} was not visible within {timeout}s")


def _base_qty_from_scaled(qty_scaled: str, quantity_scale: int) -> Decimal:
    return Decimal(qty_scaled) / (Decimal(10) ** quantity_scale)


def _decimal_string(value: Decimal) -> str:
    return format(value.normalize(), "f")


async def _best_ask_params(client, symbol: str, pair: dict) -> tuple[str, str]:
    try:
        book = await client.orderbook.get(symbol=symbol, depth=5)
    except PolyesterApiError as exc:
        if str(exc.code or "").lower() in {"not_found", "route_not_found", "unimplemented"}:
            pytest.skip(f"Orderbook unavailable for {symbol}: {exc}")
        raise
    if not book.asks:
        pytest.skip(f"No visible asks on {symbol}; cannot passive-fill a buy")

    ask = min(book.asks, key=lambda level: int(level.price_ticks))
    price = format_price_ticks(int(ask.price_ticks))
    quantity_scale = client.catalogs.base_quantity_scale_for_symbol(symbol)
    available_qty = _base_qty_from_scaled(ask.qty_scaled, quantity_scale)
    requested_qty = os.getenv("POLYESTER_TEST_TRADE_QTY")
    qty = Decimal(requested_qty) if requested_qty else Decimal(min_base_qty_for_pair(pair, price))
    if available_qty < qty:
        pytest.skip(
            f"Best ask quantity {available_qty} below requested fill quantity {qty} on {symbol}"
        )
    return price, _decimal_string(qty)


@pytest.mark.integration
@pytest.mark.funded
async def test_spot_fill(
    live_client, trade_symbol, funded_enabled, require_trade_trading_balance
):
    if not _trade_e2e_enabled():
        pytest.skip("Set POLYESTER_TEST_TRADE_E2E=1 to run spot fill e2e")

    maker_credentials = _maker_credentials()
    maker = None
    if maker_credentials is not None:
        maker_key_id, maker_private_key = maker_credentials
        maker = AsyncPolyester(
            api_key_id=maker_key_id,
            api_private_key=maker_private_key,
            api_url=live_client.api_url,
            hydrate_catalogs=True,
        )
    maker_cid = unique_client_order_id("maker-fill")
    taker_cid = unique_client_order_id("taker-fill")
    maker_order_created = False
    taker_order_created = False

    try:
        spot_raw, zipper_raw = await _hydrate_test_catalogs(live_client)
        if maker is not None:
            await _hydrate_test_catalogs(maker)
        pair = next(
            (p for p in spot_raw.get("pairs") or [] if p.get("symbol") == trade_symbol), {}
        )
        if not pair:
            pytest.skip(f"Trade symbol {trade_symbol} is not in spot config")

        if maker is None:
            price, qty = await _best_ask_params(live_client, trade_symbol, pair)
        else:
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

        maker_quote_before = Decimal(0)
        maker_base_before = Decimal(0)
        if maker is not None:
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
                order_type="limit",
                tif="gtc",
                qty=qty,
                price=price,
                post_only=False,
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
        taker_match_ids = {trade.match_id for trade in taker_detail.trades}
        assert taker_match_ids

        if maker is not None:
            maker_detail = await _wait_for_filled_order(maker, maker_cid)
            maker_match_ids = {trade.match_id for trade in maker_detail.trades}
            assert taker_match_ids & maker_match_ids
            match_id = next(iter(taker_match_ids & maker_match_ids))
        else:
            match_id = next(iter(taker_match_ids))
        taker_trade = await _wait_for_trade_match(live_client, trade_symbol, match_id)
        assert taker_trade.side == "buy"
        if maker is not None:
            maker_trade = await _wait_for_trade_match(maker, trade_symbol, match_id)
            assert maker_trade.side == "sell"

        taker_after = await live_client.balances.list()
        assert trading_balance_decimal(taker_after, base_asset_id) > taker_base_before
        assert trading_balance_decimal(taker_after, quote_asset_id) < taker_quote_before
        if maker is not None:
            maker_after = await maker.balances.list()
            assert trading_balance_decimal(maker_after, base_asset_id) < maker_base_before
            assert trading_balance_decimal(maker_after, quote_asset_id) > maker_quote_before
    finally:
        if taker_order_created:
            await live_client.orders.cancel_all(symbol=trade_symbol, dry_run=False)
        if maker is not None and maker_order_created:
            await maker.orders.cancel_all(symbol=trade_symbol, dry_run=False)
        if maker is not None:
            await maker.aclose()
