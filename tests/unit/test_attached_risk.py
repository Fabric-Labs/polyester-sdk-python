"""Attached TP/SL encode: friendly keys, typed models, proto-JSON, fail-closed."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import (
    modify_order_to_proto,
    order_intent_from_request,
    risk_policy_from_dict,
)
from polyester.codecs.scalars import parse_price_ticks
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import AttachedRisk, ClientOrderId, CreateOrderRequest, RiskLeg
from polyester.models.trading import TrailingStop
from polyester.services.orders import AsyncOrdersService
from polyester.types.money import Price
from tests.unit.support import CaptureUnary


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
                    "tick_size": "0.01",
                }
            ]
        }
    )
    return catalogs


def test_friendly_take_profit_market_encodes_child_not_dropped() -> None:
    """Regression: trigger_price/order_type used to be ignored by ParseDict."""
    risk = risk_policy_from_dict(
        {"take_profit": {"trigger_price": "35000", "order_type": "market"}}
    )
    assert risk is not None
    assert risk.take_profit.trigger_price_ticks == parse_price_ticks("35000", "price")
    assert risk.take_profit.HasField("child")
    assert risk.take_profit.child.HasField("market_ioc")
    assert not risk.take_profit.child.HasField("limit_gtc")


def test_friendly_stop_loss_limit_encodes_limit_gtc() -> None:
    risk = risk_policy_from_dict(
        {
            "stop_loss": {
                "trigger_price": "30000",
                "order_type": "limit",
                "limit_price": "29900",
            }
        }
    )
    assert risk is not None
    assert risk.WhichOneof("stop_leg") == "stop_loss"
    assert risk.stop_loss.trigger_price_ticks == parse_price_ticks("30000", "price")
    assert risk.stop_loss.child.HasField("limit_gtc")
    assert risk.stop_loss.child.limit_gtc.price_ticks == parse_price_ticks("29900", "price")


def test_friendly_bracket_oco_and_defaults_market_child() -> None:
    risk = risk_policy_from_dict(
        {
            "take_profit": {"trigger_price": "140"},
            "stop_loss": {"trigger_price": "80"},
            "oco": True,
        }
    )
    assert risk is not None
    assert risk.oco is True
    assert risk.take_profit.child.HasField("market_ioc")
    assert risk.stop_loss.child.HasField("market_ioc")


def test_typed_attached_risk_round_trips_to_wire() -> None:
    risk = risk_policy_from_dict(
        AttachedRisk(
            take_profit=RiskLeg(
                trigger_price=Price.from_ticks(140_000_000),
                order_type="market",
            ),
            stop_loss=RiskLeg(
                trigger_price=Price.from_ticks(80_000_000),
                order_type="limit",
                limit_price=Price.from_ticks(79_000_000),
            ),
            oco=True,
        ),
        symbol="BTC-USDT",
    )
    assert risk is not None
    assert risk.oco is True
    assert risk.take_profit.trigger_price_ticks == 140_000_000
    assert risk.take_profit.child.HasField("market_ioc")
    assert risk.stop_loss.trigger_price_ticks == 80_000_000
    assert risk.stop_loss.child.limit_gtc.price_ticks == 79_000_000


def test_proto_json_take_profit_still_encodes() -> None:
    risk = risk_policy_from_dict(
        {
            "take_profit": {
                "trigger_price_ticks": 35_000_000_000,
                "child": {"market_ioc": {}},
            }
        }
    )
    assert risk is not None
    assert risk.take_profit.trigger_price_ticks == 35_000_000_000
    assert risk.take_profit.child.HasField("market_ioc")


def test_proto_json_limit_gtc_child() -> None:
    risk = risk_policy_from_dict(
        {
            "take_profit": {
                "trigger_price_ticks": 36_000_000_000,
                "child": {"limit_gtc": {"price_ticks": 36_100_000_000}},
            }
        }
    )
    assert risk is not None
    assert risk.take_profit.child.limit_gtc.price_ticks == 36_100_000_000


def test_rejects_auditor_child_execution_wrapper() -> None:
    with pytest.raises(PolyesterValidationError, match="child.execution is not a wire field"):
        risk_policy_from_dict(
            {
                "take_profit": {
                    "trigger_price": "35000",
                    "child": {"execution": {"limit_gtc": {"price_ticks": 1}}},
                }
            }
        )


def test_rejects_limit_ioc_child() -> None:
    with pytest.raises(PolyesterValidationError, match="unsupported fields: limit_ioc"):
        risk_policy_from_dict(
            {
                "take_profit": {
                    "trigger_price_ticks": 1,
                    "child": {"limit_ioc": {"price_ticks": 1}},
                }
            }
        )


def test_rejects_unknown_top_level_field() -> None:
    with pytest.raises(PolyesterValidationError, match="unsupported fields: foo"):
        risk_policy_from_dict({"take_profit": {"trigger_price": "1"}, "foo": True})


def test_rejects_both_stop_loss_and_trailing() -> None:
    with pytest.raises(PolyesterValidationError, match="at most one of stop_loss"):
        risk_policy_from_dict(
            {
                "stop_loss": {"trigger_price": "80"},
                "trailing_stop": {"trailing_distance_bps": 25},
            }
        )


def test_rejects_empty_policy() -> None:
    with pytest.raises(PolyesterValidationError, match="requires take_profit"):
        risk_policy_from_dict({"oco": True})
    with pytest.raises(PolyesterValidationError, match="requires take_profit"):
        risk_policy_from_dict(AttachedRisk())


def test_market_child_rejects_limit_price() -> None:
    with pytest.raises(PolyesterValidationError, match="must not set limit_price"):
        risk_policy_from_dict(
            {
                "take_profit": {
                    "trigger_price": "140",
                    "order_type": "market",
                    "limit_price": "141",
                }
            }
        )


def test_limit_child_requires_limit_price() -> None:
    with pytest.raises(PolyesterValidationError, match="requires limit_price"):
        risk_policy_from_dict(
            {"take_profit": {"trigger_price": "140", "order_type": "limit"}}
        )


def test_create_intent_maps_friendly_attached_risk() -> None:
    intent = order_intent_from_request(
        CreateOrderRequest(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="1000",
            attached_risk={
                "take_profit": {"trigger_price": "500000", "order_type": "market"},
                "stop_loss": {"trigger_price": "500", "order_type": "market"},
                "oco": True,
            },
        ),
        quantity_scale=8,
    )
    assert intent.HasField("attached_risk")
    assert intent.attached_risk.oco is True
    assert intent.attached_risk.take_profit.trigger_price_ticks == parse_price_ticks(
        "500000", "price"
    )
    assert intent.attached_risk.take_profit.child.HasField("market_ioc")
    assert intent.attached_risk.stop_loss.trigger_price_ticks == parse_price_ticks(
        "500", "price"
    )


def test_modify_encodes_new_attached_risk() -> None:
    proto = modify_order_to_proto(
        symbol="BTC-USDT",
        key=ClientOrderId("cid-1"),
        new_attached_risk={
            "take_profit": {"trigger_price": "140", "order_type": "market"},
        },
    )
    assert proto.HasField("new_attached_risk")
    assert proto.new_attached_risk.take_profit.child.HasField("market_ioc")
    assert proto.new_attached_risk.take_profit.trigger_price_ticks == parse_price_ticks(
        "140", "price"
    )


def test_typed_trailing_stop_encodes_distance() -> None:
    risk = risk_policy_from_dict(
        AttachedRisk(trailing_stop=TrailingStop(distance_bps=25, max_slippage_ticks=10))
    )
    assert risk is not None
    assert risk.WhichOneof("stop_leg") == "trailing_stop"
    assert risk.trailing_stop.trailing_distance_bps == 25
    assert risk.trailing_stop.max_slippage_ticks == 10


@pytest.mark.asyncio
async def test_create_service_sends_friendly_attached_risk_on_wire() -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="1000",
            attached_risk={
                "take_profit": {"trigger_price": "500000", "order_type": "market"},
                "stop_loss": {"trigger_price": "500", "order_type": "market"},
                "oco": True,
            },
        )
    assert capture.calls == 1
    risk = capture.request.order.attached_risk
    assert risk.oco is True
    assert risk.take_profit.trigger_price_ticks == parse_price_ticks("500000", "price")
    assert risk.take_profit.child.HasField("market_ioc")
    assert risk.stop_loss.trigger_price_ticks == parse_price_ticks("500", "price")
    assert risk.stop_loss.child.HasField("market_ioc")


@pytest.mark.asyncio
async def test_create_service_sends_typed_attached_risk_on_wire() -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=7))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="1000",
            attached_risk=AttachedRisk(
                take_profit=RiskLeg(
                    trigger_price=Price.from_ticks(500_000_000_000),
                    order_type="market",
                )
            ),
        )
    assert capture.request.order.attached_risk.take_profit.trigger_price_ticks == (
        500_000_000_000
    )
    assert capture.request.order.attached_risk.take_profit.child.HasField("market_ioc")
