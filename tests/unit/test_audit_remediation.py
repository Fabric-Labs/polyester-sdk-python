from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.invariants import ts_ns_from_response
from polyester.codecs.decode.market_data import market_trade_from_proto
from polyester.codecs.decode.triggers import (
    trigger_event_type_from_label,
    trigger_status_from_label,
)
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.services._pair_constraints import preflight_pair_constraints
from polyester.services.market_overview import AsyncMarketOverviewService
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 4,
                    "quote_quantity_scale": 2,
                    "tick_size": "0.01",
                    "step_size": "0.001",
                    "min_qty_base": "0.002",
                    "min_notional_quote": "10",
                }
            ]
        }
    )
    return catalogs


def test_catalog_exposes_pair_constraints() -> None:
    constraints = _catalogs().pair_constraints_for_symbol("BTC-USDT")
    assert constraints is not None
    assert constraints.symbol_id == 1
    assert constraints.tick_size == "0.01"
    assert constraints.step_size == "0.001"
    assert constraints.min_qty_base == "0.002"
    assert constraints.min_notional_quote == "10"


def test_catalog_treats_zero_optional_constraints_as_unset() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 4,
                    "tick_size": "0.01",
                    "step_size": "0.001",
                    "min_qty_base": "0",
                    "min_notional_quote": "0",
                }
            ]
        }
    )
    constraints = catalogs.pair_constraints_for_symbol("BTC-USDT")
    assert constraints is not None
    assert constraints.tick_size == "0.01"
    assert constraints.step_size == "0.001"
    assert constraints.min_qty_base is None
    assert constraints.min_notional_quote is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"qty": "0.0025"}, "step_size"),
        ({"qty": "0.001"}, "at least"),
        ({"prices": {"price": "1.001"}}, "tick_size"),
        ({"qty": "0.002", "notional_price": "100"}, "notional"),
    ],
)
def test_pair_constraint_preflight_rejects_deterministic_violations(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(PolyesterValidationError, match=message):
        preflight_pair_constraints(_catalogs(), symbol="BTC-USDT", **kwargs)


@pytest.mark.asyncio
async def test_market_overview_filters_are_catalog_backed() -> None:
    capture = CaptureUnary(marketoverview_pb2.ListMarketOverviewResponse())
    service = AsyncMarketOverviewService(MagicMock(), _catalogs())
    with patch("polyester.services.market_overview.unary_public_decoded", capture):
        await service.list(symbols=["BTC-USDT"], limit=5)
    assert list(capture.request.symbols) == ["BTC-USDT"]

    with pytest.raises(PolyesterValidationError, match="Unknown symbol filter"):
        await service.list(symbols=["NOPE-USDT"])


@pytest.mark.asyncio
async def test_trigger_raw_symbol_filter_fails_closed() -> None:
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    with pytest.raises(PolyesterValidationError, match="Unknown symbol filter"):
        await service.list(symbol="NOPE-USDT")


@pytest.mark.parametrize("limit", [0, -1, 1001, True])
@pytest.mark.asyncio
async def test_list_limit_is_validated_before_encoding(limit: object) -> None:
    service = AsyncMarketOverviewService(MagicMock(), _catalogs())
    with pytest.raises(PolyesterValidationError, match="limit"):
        await service.list(limit=limit)  # type: ignore[arg-type]


def test_trigger_label_decoders_use_sdk_validation_error() -> None:
    with pytest.raises(PolyesterValidationError):
        trigger_status_from_label("unknown")
    with pytest.raises(PolyesterValidationError):
        trigger_event_type_from_label("unknown")


def test_ts_ns_invariant_rejects_millisecond_shaped_values() -> None:
    with pytest.raises(PolyesterResponseContractError, match="millisecond-shaped"):
        ts_ns_from_response(1_700_000_000_000, context="test")
    assert ts_ns_from_response(1_700_000_000_000_000_000, context="test")

    with pytest.raises(PolyesterResponseContractError):
        market_trade_from_proto(
            marketdata_pb2.MarketTrade(
                symbol_id=1,
                match_id=1,
                price_ticks=1,
                qty_scaled=1,
                ts_ns=1_700_000_000_000,
            ),
            quantity_scale=4,
        )
