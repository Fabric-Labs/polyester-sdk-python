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
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.services._symbols import resolve_symbol_id
from polyester.services._validation import validate_limit
from polyester.services.market_overview import AsyncMarketOverviewService
from polyester.services.orders import AsyncOrdersService
from polyester.services.trades import AsyncTradesService
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
    pair = catalogs.spot_config["pairs"][0]
    assert pair["tick_size"] == "0.01"
    assert pair["step_size"] == "0.001"
    assert "min_qty_base" not in pair
    assert "min_notional_quote" not in pair
    assert catalogs.symbol_id_for_symbol("BTC-USDT") == 1
    assert catalogs.base_quantity_scale_for_symbol("BTC-USDT") == 4


def test_unknown_symbol_id_resolution_still_fails_locally() -> None:
    with pytest.raises(PolyesterValidationError, match="Unknown symbol"):
        resolve_symbol_id(_catalogs(), symbol="NOPE-USDT", symbol_id=None, label="create")


@pytest.mark.asyncio
async def test_market_overview_resolves_known_symbols_and_rejects_unknown() -> None:
    capture = CaptureUnary(marketoverview_pb2.ListMarketOverviewResponse())
    service = AsyncMarketOverviewService(MagicMock(), catalogs=_catalogs())
    with patch("polyester.services.market_overview.unary_public_decoded", capture):
        await service.list(symbols=["  BTC-USDT  ", ""], limit=5)
    assert list(capture.request.symbol_id) == [1]
    with pytest.raises(PolyesterValidationError, match="Unknown symbol"):
        await service.list(symbols=["NOPE-USDT"])


@pytest.mark.asyncio
async def test_trigger_list_rejects_unknown_raw_symbol() -> None:
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    with pytest.raises(PolyesterValidationError, match="Unknown symbol"):
        await service.list(symbol="NOPE-USDT")


@pytest.mark.asyncio
async def test_cancel_all_rejects_unknown_raw_symbol() -> None:
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with pytest.raises(PolyesterValidationError, match="Unknown symbol"):
        await service.cancel_all(symbol="NOPE-USDT", dry_run=True)


@pytest.mark.asyncio
async def test_cancel_all_after_rejects_unknown_raw_symbol() -> None:
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with pytest.raises(PolyesterValidationError, match="Unknown symbol"):
        await service.cancel_all_after(timeout_sec=30, symbol="NOPE-USDT")


@pytest.mark.asyncio
async def test_create_order_does_not_preflight_pair_constraints() -> None:
    """Off-tick / below-min inputs must reach encode/transport (backend admits)."""
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.001",  # below min_qty_base 0.002 and off step if checked
            price="1.001",  # off tick_size 0.01
        )
    assert capture.calls == 1
    assert capture.request.order.symbol_id == 1
    assert capture.request.order.limit_gtc.price_ticks == 1_001_000


@pytest.mark.parametrize("limit", [True, 1.5, "10"])
def test_list_limit_rejects_non_integers(limit: object) -> None:
    with pytest.raises(PolyesterValidationError, match="limit"):
        validate_limit(limit)  # type: ignore[arg-type]


def test_list_limit_allows_values_outside_former_1000_cap() -> None:
    assert validate_limit(1001) == 1001
    assert validate_limit(0) == 0
    assert validate_limit(None, allow_none=True) is None


def test_trigger_label_decoders_use_sdk_validation_error() -> None:
    with pytest.raises(PolyesterValidationError):
        trigger_status_from_label("unknown")
    with pytest.raises(PolyesterValidationError):
        trigger_event_type_from_label("unknown")


def test_ts_ns_decodes_millisecond_shaped_values() -> None:
    ms_shaped = 1_700_000_000_000
    ns_shaped = 1_700_000_000_000_000_000
    assert ts_ns_from_response(ms_shaped, context="test") == ms_shaped
    assert ts_ns_from_response(ns_shaped, context="test") == ns_shaped

    trade = market_trade_from_proto(
        marketdata_pb2.MarketTrade(
            symbol_id=1,
            match_id=1,
            price_ticks=1,
            qty_scaled=1,
            ts_ns=1_700_000_000_000,
        ),
        quantity_scale=4,
    )
    assert trade.ts_ns == "1700000000000"


@pytest.mark.asyncio
async def test_trades_list_after_match_id_requires_symbol() -> None:
    service = AsyncTradesService(MagicMock(), _catalogs(), None)
    with pytest.raises(PolyesterValidationError, match="Unknown symbol|symbol"):
        await service.list(after_match_id=12)


@pytest.mark.asyncio
async def test_trades_list_after_match_id_wires_symbol_and_cursor() -> None:
    capture = CaptureUnary(orders_read_pb2.GetUserTradesResponse())
    service = AsyncTradesService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.trades.unary_auth_decoded", capture):
        await service.list(symbol="BTC-USDT", after_match_id=12, limit=5)
    assert capture.request.symbol_id == 1
    assert capture.request.after_match_id == 12
    assert capture.request.limit == 5


@pytest.mark.asyncio
async def test_trades_list_rejects_non_positive_after_match_id() -> None:
    service = AsyncTradesService(MagicMock(), _catalogs(), None)
    with pytest.raises(PolyesterValidationError, match="after_match_id"):
        await service.list(symbol="BTC-USDT", after_match_id=0)
