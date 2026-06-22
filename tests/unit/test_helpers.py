from decimal import Decimal

from tests.helpers import (
    FAR_ABOVE_BUY_STOP_PRICE_HINTS,
    FAR_BELOW_BUY_PRICE_HINTS,
    base_asset_id_for_symbol,
    ledger_id_for_asset_symbol,
    min_base_qty_for_pair,
    pick_smoke_symbol,
    quote_asset_id_for_symbol,
)


def test_pick_smoke_symbol_prefers_eth_usdt():
    spot = {
        "pairs": [
            {"symbol": "BNB-USDT"},
            {"symbol": "ETH-USDT"},
        ]
    }
    assert pick_smoke_symbol(spot) == "ETH-USDT"


def test_quote_asset_id_resolves_via_zipper_catalog():
    spot = {
        "pairs": [
            {
                "symbol": "ETH-USDT",
                "quoteAsset": "USDT",
                "baseAsset": "ETH",
            }
        ]
    }
    zipper = {
        "assets": [
            {"asset": "USDT", "ledgerId": 1},
            {"asset": "ETH", "ledgerId": 2},
        ]
    }
    assert quote_asset_id_for_symbol(spot, "ETH-USDT", zipper_raw=zipper) == 1
    assert base_asset_id_for_symbol(spot, "ETH-USDT", zipper_raw=zipper) == 2


def test_ledger_id_for_asset_symbol():
    zipper = {"assets": [{"asset": "USDT", "ledgerId": 1}]}
    assert ledger_id_for_asset_symbol(zipper, "USDT") == 1
    assert ledger_id_for_asset_symbol(zipper, "ETH") is None


def test_min_base_qty_for_pair_uses_quote_notional():
    pair = {
        "stepSize": "0.0001",
        "minQtyBase": "0.0001",
        "minNotionalQuote": "1",
    }
    qty = min_base_qty_for_pair(pair, "100")
    assert Decimal(qty) == Decimal("0.01")


def test_eth_usdt_price_hints_present():
    assert FAR_BELOW_BUY_PRICE_HINTS["ETH-USDT"] == "100"
    assert FAR_ABOVE_BUY_STOP_PRICE_HINTS["ETH-USDT"] == "50000"
