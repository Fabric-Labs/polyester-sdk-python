from decimal import Decimal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester import POLYESTER_DEVNET_ENVIRONMENT, POLYESTER_TESTNET_ENVIRONMENT
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV
from tests.helpers import (
    FAR_ABOVE_BUY_STOP_PRICE_HINTS,
    FAR_BELOW_BUY_PRICE_HINTS,
    base_asset_id_for_symbol,
    far_below_price_from_last_ticks,
    ledger_id_for_asset_symbol,
    live_client_kwargs_from_env,
    min_base_qty_for_pair,
    pick_smoke_symbol,
    pick_trade_symbol,
    quote_asset_id_for_symbol,
)


def _private_key_hex() -> str:
    return Ed25519PrivateKey.generate().private_bytes_raw().hex()


def test_live_client_kwargs_honors_polyester_env(monkeypatch) -> None:
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_live")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, _private_key_hex())
    monkeypatch.setenv("POLYESTER_ENV", "testnet")
    monkeypatch.delenv("POLYESTER_API_URL", raising=False)
    kwargs = live_client_kwargs_from_env()
    assert kwargs is not None
    assert kwargs["environment"] is POLYESTER_TESTNET_ENVIRONMENT


def test_live_client_kwargs_default_omits_environment(monkeypatch) -> None:
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_live")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, _private_key_hex())
    monkeypatch.delenv("POLYESTER_ENV", raising=False)
    monkeypatch.delenv("POLYESTER_ENVIRONMENT", raising=False)
    kwargs = live_client_kwargs_from_env()
    assert kwargs is not None
    assert "environment" not in kwargs


def test_live_client_kwargs_explicit_environment_wins(monkeypatch) -> None:
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_live")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, _private_key_hex())
    monkeypatch.setenv("POLYESTER_ENV", "testnet")
    kwargs = live_client_kwargs_from_env(environment=POLYESTER_DEVNET_ENVIRONMENT)
    assert kwargs is not None
    assert kwargs["environment"] is POLYESTER_DEVNET_ENVIRONMENT


def test_live_client_kwargs_reads_ws_url(monkeypatch) -> None:
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_live")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, _private_key_hex())
    monkeypatch.setenv("POLYESTER_WS_URL", "wss://mm.internal.example")
    kwargs = live_client_kwargs_from_env()
    assert kwargs is not None
    assert kwargs["ws_url"] == "wss://mm.internal.example"


def test_pick_smoke_symbol_uses_canonical_trade_selection(monkeypatch):
    monkeypatch.delenv("POLYESTER_TEST_TRADE_SYMBOL", raising=False)
    spot = {
        "pairs": [
            {"symbol": "BNB-USDT"},
            {"symbol": "BTC-USDT"},
            {"symbol": "ETH-USDT"},
        ]
    }
    assert pick_smoke_symbol(spot) == "BTC-USDT"


def test_pick_trade_symbol_prefers_trade_env_override(monkeypatch):
    spot = {
        "pairs": [
            {"symbol": "ETH-USDT"},
            {"symbol": "BTC-USDT"},
        ]
    }
    monkeypatch.setenv("POLYESTER_TEST_TRADE_SYMBOL", "BTC-USDT")
    assert pick_trade_symbol(spot) == "BTC-USDT"


def test_pick_trade_symbol_ignores_smoke_override_and_prefers_btc(monkeypatch):
    monkeypatch.delenv("POLYESTER_TEST_TRADE_SYMBOL", raising=False)
    monkeypatch.setenv("POLYESTER_TEST_SMOKE_SYMBOL", "ETH-USDT")
    monkeypatch.setenv("POLYESTER_SMOKE_SYMBOL", "ETH-USDT")
    spot = {"pairs": [{"symbol": "ETH-USDT"}, {"symbol": "BTC-USDT"}]}
    assert pick_trade_symbol(spot) == "BTC-USDT"


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


def test_post_only_buy_price_from_last_ticks_uses_fraction_of_spot():
    price = far_below_price_from_last_ticks(
        50_000_000_000,  # 50k USDT with 6 decimal ticks
        tick_size="0.01",
        symbol="BTC-USDT",
    )
    assert price == "49750"


def test_far_below_price_from_last_ticks_falls_back_without_market():
    price = far_below_price_from_last_ticks(
        0,
        tick_size="0.01",
        symbol="BTC-USDT",
    )
    assert price == "1000"
