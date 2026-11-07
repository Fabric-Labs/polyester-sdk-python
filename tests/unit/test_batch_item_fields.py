"""Batch item dictionaries apply every supported field and refuse the rest by name."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import batch_cancel_orders_to_proto, batch_replace_orders_to_proto
from polyester.codecs.scalars import parse_price_ticks
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import AttachedRisk, BatchReplaceItem, OrderId, RiskLeg
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary

STOP_LOSS = {"stop_loss": {"trigger_price": "30000", "order_type": "market"}}


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    return catalogs


def _replace(items: list) -> orders_pb2.BatchReplaceOrdersRequest:
    return batch_replace_orders_to_proto(
        items=items, symbol_id=1, symbol="BTC-USDT", quantity_scale=8
    )


def test_batch_replace_dict_applies_new_attached_risk() -> None:
    proto = _replace([{"key": OrderId(42), "new_price": "100", "new_attached_risk": STOP_LOSS}])
    item = proto.items[0]
    assert item.new_price_ticks == parse_price_ticks("100", "price")
    assert item.HasField("new_attached_risk")
    assert item.new_attached_risk.stop_loss.trigger_price_ticks == parse_price_ticks(
        "30000", "price"
    )
    assert item.new_attached_risk.stop_loss.child.HasField("market_ioc")


def test_batch_replace_dict_applies_attached_risk_alone() -> None:
    proto = _replace([{"key": OrderId(42), "new_attached_risk": STOP_LOSS}])
    assert proto.items[0].HasField("new_attached_risk")
    assert not proto.items[0].new_price_ticks
    assert not proto.items[0].new_qty_scaled


def test_batch_replace_model_applies_new_attached_risk() -> None:
    risk = AttachedRisk(stop_loss=RiskLeg(trigger_price="30000", order_type="market"))
    proto = _replace([BatchReplaceItem(key=OrderId(42), new_qty="1", new_attached_risk=risk)])
    assert proto.items[0].new_qty_scaled == 100_000_000
    assert proto.items[0].new_attached_risk.stop_loss.trigger_price_ticks == parse_price_ticks(
        "30000", "price"
    )


@pytest.mark.parametrize(
    "unknown",
    ["new_stop_loss", "new_atached_risk", "attached_risk", "symbol", "symbol_id", "newPrice"],
)
def test_batch_replace_dict_refuses_unknown_field_by_name(unknown: str) -> None:
    item = {"key": OrderId(42), "new_price": "100", unknown: STOP_LOSS}
    with pytest.raises(PolyesterValidationError, match=unknown):
        _replace([item])


def test_batch_replace_dict_refuses_misspelt_risk_inside_attached_risk() -> None:
    item = {"key": OrderId(42), "new_attached_risk": {"stop_los": STOP_LOSS["stop_loss"]}}
    with pytest.raises(PolyesterValidationError, match="stop_los"):
        _replace([item])


def test_batch_replace_still_requires_a_change() -> None:
    with pytest.raises(PolyesterValidationError, match="new_attached_risk"):
        _replace([{"key": OrderId(42)}])


def test_batch_cancel_dict_keeps_supported_symbol_id() -> None:
    proto = batch_cancel_orders_to_proto(items=[{"key": OrderId(42), "symbol_id": 7}])
    assert proto.items[0].symbol_id == 7


@pytest.mark.parametrize("unknown", ["symbol", "symbolId", "side", "new_price"])
def test_batch_cancel_dict_refuses_unknown_field_by_name(unknown: str) -> None:
    item = {"key": OrderId(42), unknown: "BTC-USDT"}
    with pytest.raises(PolyesterValidationError, match=unknown):
        batch_cancel_orders_to_proto(items=[item])


@pytest.mark.asyncio
async def test_batch_replace_service_sends_attached_risk_and_refuses_unknown() -> None:
    capture = CaptureUnary(orders_pb2.BatchReplaceOrdersResponse(batch_request_id=9, status=1))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.batch_replace(
            symbol="BTC-USDT",
            items=[{"key": OrderId(42), "new_price": "100", "new_attached_risk": STOP_LOSS}],
        )
        assert capture.calls == 1
        assert capture.request.items[0].HasField("new_attached_risk")
        with pytest.raises(PolyesterValidationError, match="new_stop_loss"):
            await service.batch_replace(
                symbol="BTC-USDT",
                items=[{"key": OrderId(42), "new_price": "100", "new_stop_loss": STOP_LOSS}],
            )
    assert capture.calls == 1


@pytest.mark.asyncio
async def test_batch_cancel_service_refuses_symbol_before_sending() -> None:
    capture = CaptureUnary(orders_pb2.BatchCancelOrdersResponse())
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch("polyester.services.orders.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match="symbol"),
    ):
        await service.batch_cancel(items=[{"key": OrderId(42), "symbol": "BTC-USDT"}])
    assert capture.calls == 0
