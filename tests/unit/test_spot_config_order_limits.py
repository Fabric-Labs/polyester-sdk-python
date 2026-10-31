"""Spot config exposes typed order-size and open-order limits like the TS SDK."""

from __future__ import annotations

from typing import Any

import pytest

from polyester._wire import protobuf_to_public_dict
from polyester.catalogs import CatalogManager
from polyester.codecs.spot_config import spot_config_from_dict
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models import PairOrderLimits

PAIR: dict[str, Any] = {
    "symbolId": 101,
    "symbol": "BTC-USDT",
    "baseAsset": "BTC",
    "quoteAsset": "USDT",
    "tickSize": "0.000001",
    "stepSize": "0.00000001",
    "baseQuantityScale": 8,
    "quoteQuantityScale": 6,
}


def _wire_config(**top: Any) -> dict[str, Any]:
    """GetSpotConfig as proto JSON, the shape the transport hands to the decoder."""
    response = marketdata_pb2.GetSpotConfigResponse(
        pairs=[
            marketdata_pb2.PairConfig(
                symbol_id=101,
                symbol="BTC-USDT",
                base_quantity_scale=8,
                quote_quantity_scale=6,
                max_limit_qty_base="100",
                max_market_qty_base="25.5",
                max_order_notional_quote="1000000",
                max_market_notional_quote="250000.5",
                max_open_orders_per_pair=200,
            ),
            marketdata_pb2.PairConfig(
                symbol_id=102, symbol="ETH-USDT", base_quantity_scale=8, quote_quantity_scale=6
            ),
        ],
        **top,
    )
    return protobuf_to_public_dict(response)


def test_spot_config_decodes_limits_and_omits_unlimited_maxima() -> None:
    config = spot_config_from_dict(_wire_config(max_open_orders_total=1000))

    assert config.max_open_orders_total == 1000
    assert config.pair_order_limits == [
        PairOrderLimits(
            symbol="BTC-USDT",
            symbol_id=101,
            max_limit_qty_base="100",
            max_market_qty_base="25.5",
            max_order_notional_quote="1000000",
            max_market_notional_quote="250000.5",
            max_open_orders_per_pair=200,
        ),
        PairOrderLimits(symbol="ETH-USDT", symbol_id=102),
    ]
    unlimited = config.pair_order_limits[1]
    assert unlimited.max_limit_qty_base is None
    assert unlimited.max_market_qty_base is None
    assert unlimited.max_order_notional_quote is None
    assert unlimited.max_market_notional_quote is None
    assert unlimited.max_open_orders_per_pair == 0
    assert config.raw["pairs"][0]["maxLimitQtyBase"] == "100"
    assert config.raw["pairs"][0]["maxMarketNotionalQuote"] == "250000.5"
    assert "maxMarketNotionalQuote" not in config.raw["pairs"][1]


def test_market_notional_cap_decodes_from_snake_case_and_empty_means_no_cap() -> None:
    config = spot_config_from_dict(
        {
            "pairs": [
                {**PAIR, "max_market_notional_quote": "5000000"},
                {**PAIR, "symbolId": 102, "symbol": "ETH-USDT", "maxMarketNotionalQuote": ""},
            ]
        }
    )

    assert config.pair_order_limits[0].max_market_notional_quote == "5000000"
    assert config.pair_order_limits[1].max_market_notional_quote is None


def test_older_spot_config_without_limits_still_decodes() -> None:
    config = spot_config_from_dict({"pairs": [dict(PAIR)]})

    assert config.max_open_orders_total == 0
    assert config.pair_order_limits == [PairOrderLimits(symbol="BTC-USDT", symbol_id=101)]


@pytest.mark.parametrize(
    ("pair_overrides", "top"),
    [
        ({"maxLimitQtyBase": "-1"}, {}),
        ({"maxOrderNotionalQuote": "1e6"}, {}),
        ({"maxMarketQtyBase": "1."}, {}),
        ({"maxMarketQtyBase": 5}, {}),
        ({"maxMarketNotionalQuote": "-1"}, {}),
        ({"maxMarketNotionalQuote": "1e6"}, {}),
        ({"maxMarketNotionalQuote": "0.5."}, {}),
        ({"maxMarketNotionalQuote": 250000}, {}),
        ({"max_market_notional_quote": " 1"}, {}),
        ({"maxOpenOrdersPerPair": -1}, {}),
        ({"maxOpenOrdersPerPair": 2**32}, {}),
        ({}, {"maxOpenOrdersTotal": 1.5}),
    ],
)
def test_malformed_limits_are_rejected(pair_overrides: dict[str, Any], top: dict[str, Any]) -> None:
    raw = {"pairs": [{**PAIR, **pair_overrides}], **top}

    with pytest.raises(PolyesterValidationError):
        spot_config_from_dict(raw)
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError):
        catalogs.hydrate_spot_config(raw)


def test_catalog_exposes_limits_per_symbol_and_total() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(_wire_config(max_open_orders_total=1000))

    by_symbol = catalogs.order_limits_for_symbol("BTC-USDT")
    assert by_symbol is not None
    assert by_symbol.max_limit_qty_base == "100"
    assert by_symbol.max_market_notional_quote == "250000.5"
    assert by_symbol.max_open_orders_per_pair == 200
    assert catalogs.order_limits_for_symbol_id(102) == PairOrderLimits(
        symbol="ETH-USDT", symbol_id=102
    )
    assert catalogs.order_limits_for_symbol("DOGE-USDT") is None
    assert catalogs.max_open_orders_total == 1000


def test_unusable_catalog_reports_no_limits() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(_wire_config(max_open_orders_total=1000))
    catalogs.mark_unusable("test")

    assert catalogs.order_limits_for_symbol("BTC-USDT") is None
    assert catalogs.max_open_orders_total == 0


@pytest.mark.asyncio
async def test_get_spot_config_returns_typed_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    from polyester.services import market_data

    async def fake_unary_public(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return _wire_config(max_open_orders_total=7)

    monkeypatch.setattr(market_data, "unary_public", fake_unary_public)
    service = market_data.AsyncMarketDataService(transport=None)

    config = await service.get_spot_config()

    assert config.max_open_orders_total == 7
    assert config.pair_order_limits[0].max_market_qty_base == "25.5"
    assert config.pair_order_limits[0].max_market_notional_quote == "250000.5"
    assert config.pair_order_limits[1].max_market_notional_quote is None
