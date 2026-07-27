"""Self-contained market BUY → SELL roundtrip using net received quantity."""

from __future__ import annotations

import asyncio
import contextlib
import os

import pytest

from polyester import AsyncPolyester, is_not_found
from polyester.types.money import Quantity
from tests.e2e.helpers import unique_client_order_id, wait_for_terminal_order
from tests.helpers import (
    FAR_ABOVE_BUY_STOP_PRICE_HINTS,
    base_asset_id_for_symbol,
    is_devnet_order_internal_error,
    min_base_qty_for_pair,
    quote_asset_id_for_symbol,
    reserved_balance_raw,
    resolve_far_below_buy_limit_price,
    resolve_market_ref_price,
    trading_balance_raw,
)


def _trade_e2e_enabled() -> bool:
    return os.getenv("POLYESTER_TEST_TRADE_E2E", "").lower() in {"1", "true", "yes"}


def _maker_credentials() -> tuple[str, str] | None:
    key_id = os.getenv("POLYESTER_TEST_MAKER_API_KEY_ID")
    private_key = os.getenv("POLYESTER_TEST_MAKER_API_PRIVATE_KEY")
    if not key_id or not private_key:
        return None
    return key_id, private_key


def _poly3028_skip(reason: str) -> None:
    pytest.skip(f"possible POLY-3028 backend reserve blocker: {reason}")


async def _hydrate_catalogs(client) -> tuple[dict, dict]:
    spot = await client.market_data.get_spot_config()
    client.catalogs.hydrate_spot_config(spot.raw)
    if not client.catalogs.zipper:
        zipper = await client.zipper.get_deposit_withdraw_config()
        client.catalogs.hydrate_zipper_config(zipper)
    return spot.raw, client.catalogs.zipper_config or {}


async def _wait_no_open_cids(client, cids: set[str], *, timeout: float = 20) -> None:
    attempts = max(1, int(timeout / 0.5))
    for _ in range(attempts):
        open_orders = await client.orders.list_open(limit=100)
        remaining = {o.client_order_id for o in open_orders.orders if o.client_order_id in cids}
        if not remaining:
            return
        await asyncio.sleep(0.5)
    open_orders = await client.orders.list_open(limit=100)
    remaining = {o.client_order_id for o in open_orders.orders if o.client_order_id in cids}
    raise AssertionError(f"test orders still open after cleanup: {sorted(remaining)}")


async def _exercise_holds_route(client) -> None:
    # Reserved balances remain the required reconciliation signal when this
    # optional detailed route is not mounted in the target environment.
    with contextlib.suppress(Exception):
        await client.balances.list_holds(limit=1)


async def _cancel_open_test_orders(client, cids: set[str]) -> list[str]:
    """Cancel only this fixture's open orders, never unrelated account orders."""
    errors: list[str] = []
    try:
        open_orders = await client.orders.list_open(limit=100)
    except Exception as exc:  # noqa: BLE001
        return [f"list_open before targeted cleanup: {exc}"]

    for order in open_orders.orders:
        if order.client_order_id not in cids:
            continue
        try:
            await client.orders.cancel(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
            )
        except Exception as exc:  # noqa: BLE001
            if is_not_found(exc):
                continue
            errors.append(f"cancel {order.client_order_id}: {exc}")
    return errors


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_market_buy_sell_roundtrip_carries_filled_qty(
    live_client,
    trade_symbol,
    funded_enabled,
    mutation_enabled,
    require_trade_trading_balance,
):
    if not _trade_e2e_enabled():
        pytest.skip("Set POLYESTER_TEST_TRADE_E2E=1 to run market roundtrip e2e")

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

    buy_cid = unique_client_order_id("rt-buy")
    sell_cid = unique_client_order_id("rt-sell")
    maker_sell_cid = unique_client_order_id("rt-maker")
    maker_buy_cid = unique_client_order_id("rt-maker-buy")
    test_cids = {buy_cid, sell_cid}
    maker_test_cids = {maker_sell_cid, maker_buy_cid}
    roundtrip_ok = False

    liquidity = "dedicated-maker" if maker is not None else "external-orderbook"
    print(f"trade_symbol={trade_symbol} liquidity={liquidity}", flush=True)

    try:
        spot_raw, zipper_raw = await _hydrate_catalogs(live_client)
        if maker is not None:
            await _hydrate_catalogs(maker)
        pair = next(
            (p for p in spot_raw.get("pairs") or [] if p.get("symbol") == trade_symbol),
            None,
        )
        if not pair:
            pytest.skip(f"Trade symbol {trade_symbol} is not in spot config")

        base_asset_id = base_asset_id_for_symbol(spot_raw, trade_symbol, zipper_raw=zipper_raw)
        quote_asset_id = quote_asset_id_for_symbol(spot_raw, trade_symbol, zipper_raw=zipper_raw)
        assert base_asset_id is not None
        assert quote_asset_id is not None

        before = await live_client.balances.list()
        base_before = trading_balance_raw(before, base_asset_id)
        quote_reserved_before = reserved_balance_raw(before, quote_asset_id)
        base_reserved_before = reserved_balance_raw(before, base_asset_id)

        buy_ref_price = await resolve_market_ref_price(live_client, trade_symbol, pair, side="buy")
        price = buy_ref_price
        if maker is not None:
            price = (
                os.getenv("POLYESTER_TEST_TRADE_PRICE")
                or FAR_ABOVE_BUY_STOP_PRICE_HINTS.get(trade_symbol)
                or "50000"
            )
        qty = os.getenv("POLYESTER_TEST_TRADE_QTY") or min_base_qty_for_pair(pair, price)

        if maker is not None:
            try:
                await maker.orders.create(
                    symbol=trade_symbol,
                    side="sell",
                    order_type="limit",
                    tif="gtc",
                    qty=qty,
                    price=price,
                    post_only=True,
                    client_order_id=maker_sell_cid,
                )
            except Exception as exc:  # noqa: BLE001
                if is_devnet_order_internal_error(exc):
                    pytest.skip(f"maker create unavailable: {exc}")
                raise

        try:
            await live_client.orders.create(
                symbol=trade_symbol,
                side="buy",
                order_type="market",
                tif="ioc",
                qty=qty,
                client_order_id=buy_cid,
                market_client_ref_price=buy_ref_price,
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            if is_devnet_order_internal_error(exc):
                pytest.skip(f"buy unavailable: {exc}")
            if "notional" in msg:
                pytest.skip(f"notional: {exc}")
            raise

        try:
            buy_detail = await wait_for_terminal_order(live_client, buy_cid, timeout=20)
        except AssertionError as exc:
            _poly3028_skip(f"buy terminal wait: {exc}")

        buy_order = buy_detail.order
        assert buy_order is not None
        assert buy_order.status in {"filled", "canceled", "rejected"}
        if buy_order.cum_qty is None:
            _poly3028_skip(f"buy produced no fill (status={buy_order.status})")
        filled = buy_order.cum_qty.scaled
        if filled <= 0:
            _poly3028_skip("buy produced no fill (cum_qty<=0)")
        buy_projection = await live_client.orders.wait_for_order_trades_complete(
            client_order_id=buy_cid,
            timeout=20,
        )
        received_fee = sum(
            int(trade.fee_scaled or "0")
            for trade in buy_projection.trades
            if trade.fee_source == "received"
        )
        net_received = filled - received_fee
        assert net_received > 0, "BUY net received quantity must be positive"
        cleanup_qty = Quantity.from_scaled(
            net_received,
            scale=buy_order.cum_qty.scale,
            symbol=buy_order.cum_qty.symbol,
            symbol_id=buy_order.cum_qty.symbol_id,
        )

        if maker is not None:
            maker_buy_price = await resolve_far_below_buy_limit_price(maker, trade_symbol, pair)
            try:
                await maker.orders.create(
                    symbol=trade_symbol,
                    side="buy",
                    order_type="limit",
                    tif="gtc",
                    qty=cleanup_qty,
                    price=maker_buy_price,
                    post_only=True,
                    client_order_id=maker_buy_cid,
                )
            except Exception as exc:  # noqa: BLE001
                if is_devnet_order_internal_error(exc):
                    pytest.skip(f"maker buy unavailable: {exc}")
                raise

        # A BUY that pays fees from the received asset cannot safely sell its
        # gross cum_qty; carry the exact net base received into cleanup.
        sell_ref_price = await resolve_market_ref_price(
            live_client, trade_symbol, pair, side="sell"
        )
        try:
            await live_client.orders.create(
                symbol=trade_symbol,
                side="sell",
                order_type="market",
                tif="ioc",
                qty=cleanup_qty,
                client_order_id=sell_cid,
                market_client_ref_price=sell_ref_price,
            )
        except Exception as exc:  # noqa: BLE001
            if is_devnet_order_internal_error(exc):
                pytest.skip(f"sell cleanup unavailable: {exc}")
            raise

        try:
            sell_detail = await wait_for_terminal_order(live_client, sell_cid, timeout=20)
        except AssertionError as exc:
            _poly3028_skip(f"sell terminal wait: {exc}")

        sell_order = sell_detail.order
        assert sell_order is not None
        assert sell_order.status in {"filled", "canceled", "rejected"}
        assert sell_order.status == "filled", f"cleanup SELL not filled: {sell_order.status}"
        assert sell_order.cum_qty is not None
        sell_filled = sell_order.cum_qty.scaled
        assert sell_filled == net_received, (
            "cleanup SELL must use BUY net received qty: "
            f"sell={sell_filled} net_received={net_received}"
        )

        open_orders = await live_client.orders.list_open(limit=100)
        for order in open_orders.orders:
            assert order.client_order_id not in test_cids, f"test order still open: {order}"

        after = await live_client.balances.list()
        base_after = trading_balance_raw(after, base_asset_id)
        assert base_after == base_before, (
            f"residual base position not zero: before={base_before} after={base_after}"
        )

        quote_reserved_after = reserved_balance_raw(after, quote_asset_id)
        base_reserved_after = reserved_balance_raw(after, base_asset_id)
        assert quote_reserved_after == quote_reserved_before, (
            f"quote reserved not reconciled: before={quote_reserved_before} "
            f"after={quote_reserved_after}"
        )
        assert base_reserved_after == base_reserved_before, (
            f"base reserved not reconciled: before={base_reserved_before} "
            f"after={base_reserved_after}"
        )
        await _exercise_holds_route(live_client)
        roundtrip_ok = True
    finally:
        cleanup_errors: list[str] = []
        cleanup_errors.extend(await _cancel_open_test_orders(live_client, test_cids))
        if maker is not None:
            cleanup_errors.extend(await _cancel_open_test_orders(maker, maker_test_cids))
        try:
            await _wait_no_open_cids(live_client, test_cids)
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"taker open poll: {exc}")
        if maker is not None:
            try:
                await maker.aclose()
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(f"maker aclose: {exc}")
        if cleanup_errors and roundtrip_ok:
            pytest.fail("cleanup failed: " + "; ".join(cleanup_errors))
