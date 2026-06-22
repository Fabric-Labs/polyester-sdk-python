from __future__ import annotations

import os
from decimal import ROUND_UP, Decimal

from polyester import format_ledger_u128
from polyester.errors import PolyesterApiError, PolyesterServerError
from polyester.models import BalancesList

# USDT-quoted pairs; ETH-USDT first (devnet funding uses USDT on Ethereum).
SMOKE_SYMBOL_CANDIDATES = ("ETH-USDT", "BTC-USDT", "SOL-USDT", "BNB-USDT")
DEFAULT_SMOKE_SYMBOL = "ETH-USDT"

# Limit prices safely below typical devnet spot when market overview is unavailable.
FAR_BELOW_BUY_PRICE_HINTS: dict[str, str] = {
    "ETH-USDT": "100",
    "BTC-USDT": "1000",
    "SOL-USDT": "10",
    "BNB-USDT": "10",
}

# Buy-stop trigger/limit prices safely above typical devnet spot (USDT-funded entry).
FAR_ABOVE_BUY_STOP_PRICE_HINTS: dict[str, str] = {
    "ETH-USDT": "50000",
    "BTC-USDT": "500000",
    "SOL-USDT": "5000",
    "BNB-USDT": "5000",
}


def env_smoke_symbol() -> str | None:
    return os.getenv("POLYESTER_TEST_SMOKE_SYMBOL") or os.getenv("POLYESTER_SMOKE_SYMBOL")


def pick_smoke_symbol(spot_raw: dict) -> str:
    override = env_smoke_symbol()
    if override:
        return override
    symbols = {p.get("symbol") for p in spot_raw.get("pairs") or []}
    for candidate in SMOKE_SYMBOL_CANDIDATES:
        if candidate in symbols:
            return candidate
    pairs = spot_raw.get("pairs") or []
    if pairs:
        return str(pairs[0].get("symbol") or DEFAULT_SMOKE_SYMBOL)
    return DEFAULT_SMOKE_SYMBOL


def pair_for_symbol(spot_raw: dict, symbol: str) -> dict | None:
    for pair in spot_raw.get("pairs") or []:
        if pair.get("symbol") == symbol:
            return pair
    return None


def _asset_symbol_from_zipper_row(row: dict) -> str | None:
    value = row.get("asset") or row.get("code")
    return str(value) if value else None


def ledger_id_for_asset_symbol(zipper_raw: dict, asset_symbol: str) -> int | None:
    for row in zipper_raw.get("assets") or []:
        if _asset_symbol_from_zipper_row(row) == asset_symbol:
            value = row.get("ledgerId") or row.get("ledger_id")
            return int(value) if value is not None else None
    return None


def quantity_scale_for_asset_symbol(zipper_raw: dict, asset_symbol: str) -> int | None:
    for row in zipper_raw.get("assets") or []:
        if _asset_symbol_from_zipper_row(row) == asset_symbol:
            value = row.get("quantityScale") or row.get("quantity_scale")
            return int(value) if value is not None else None
    return None


def quote_asset_symbol_for_pair(pair: dict) -> str | None:
    value = pair.get("quoteAsset") or pair.get("quote_asset")
    return str(value) if value else None


def base_asset_symbol_for_pair(pair: dict) -> str | None:
    value = pair.get("baseAsset") or pair.get("base_asset")
    return str(value) if value else None


def quote_asset_id_for_symbol(
    spot_raw: dict,
    symbol: str,
    *,
    zipper_raw: dict | None = None,
) -> int | None:
    pair = pair_for_symbol(spot_raw, symbol)
    if pair is None:
        return None

    direct = pair.get("quote_asset_id") or pair.get("quoteAssetId")
    if direct is not None:
        return int(direct)

    quote_symbol = quote_asset_symbol_for_pair(pair)
    if quote_symbol is None or not zipper_raw:
        return None
    return ledger_id_for_asset_symbol(zipper_raw, quote_symbol)


def base_asset_id_for_symbol(
    spot_raw: dict,
    symbol: str,
    *,
    zipper_raw: dict | None = None,
) -> int | None:
    pair = pair_for_symbol(spot_raw, symbol)
    if pair is None:
        return None

    direct = pair.get("base_asset_id") or pair.get("baseAssetId")
    if direct is not None:
        return int(direct)

    base_symbol = base_asset_symbol_for_pair(pair)
    if base_symbol is None or not zipper_raw:
        return None
    return ledger_id_for_asset_symbol(zipper_raw, base_symbol)


def trading_balance_decimal(balances: BalancesList, asset_id: int) -> Decimal:
    for row in balances.balances:
        if row.asset_id == asset_id:
            return Decimal(format_ledger_u128(row.trading))
    return Decimal(0)


def min_trading_quote_required() -> Decimal:
    raw = os.getenv("POLYESTER_TEST_MIN_TRADING_QUOTE", "10")
    return Decimal(raw)


def skip_funding_check() -> bool:
    return os.getenv("POLYESTER_TEST_SKIP_FUNDING_CHECK", "").lower() in ("1", "true", "yes")


def _min_base_qty_for_notional(
    *,
    min_notional: Decimal,
    price: Decimal,
    step_size: Decimal,
    min_qty_base: Decimal,
) -> str:
    if price <= 0 or step_size <= 0:
        qty_units = Decimal(1)
    else:
        qty_units = (min_notional / price / step_size).to_integral_value(rounding=ROUND_UP)
    min_qty_units = (min_qty_base / step_size).to_integral_value(rounding=ROUND_UP)
    qty_units = max(qty_units, min_qty_units, Decimal(1))
    return format(qty_units * step_size, "f")


def min_base_qty_for_pair(pair: dict, price: str) -> str:
    step_size = Decimal(pair.get("stepSize") or pair.get("step_size") or "0.001")
    min_qty_base = Decimal(pair.get("minQtyBase") or pair.get("min_qty_base") or step_size)
    min_notional = Decimal(pair.get("minNotionalQuote") or pair.get("min_notional_quote") or "10")
    return _min_base_qty_for_notional(
        min_notional=min_notional,
        price=Decimal(price),
        step_size=step_size,
        min_qty_base=min_qty_base,
    )


def is_devnet_order_internal_error(exc: BaseException) -> bool:
    if isinstance(exc, PolyesterServerError):
        return "internal error" in str(exc).lower()
    if isinstance(exc, PolyesterApiError):
        code = getattr(exc, "code", None) or ""
        return str(code).upper() == "INTERNAL_ERROR" or "internal error" in str(exc).lower()
    return False


def batch_results_are_all_internal_error(results) -> bool:
    if not results:
        return False
    codes = {getattr(item, "code", None) or "" for item in results}
    return codes == {"INTERNAL_ERROR"}


def devnet_order_skip_message() -> str:
    return (
        "Devnet order placement returned INTERNAL_ERROR for ETH-USDT USDT-funded buys; "
        "check OMS on devnet"
    )
