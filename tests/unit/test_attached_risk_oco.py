"""An OCO attached-risk policy needs a take-profit and exactly one stop leg.

Every order write that carries attached risk refuses a one-leg OCO before
sending, with the rule the server's contract names.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import batch_replace_orders_to_proto, modify_order_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import AttachedRisk, ClientOrderId, RiskLeg
from polyester.services.orders import AsyncOrdersService
from polyester.types.money import Price
from tests.unit.support import CaptureUnary

OCO_RULE = "risk_policy.oco_requires_tp_and_one_stop"
UNARY = "polyester.services.orders.unary_auth_decoded"


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


ONE_LEG_OCO = [
    pytest.param({"take_profit": {"trigger_price": "140"}, "oco": True}, id="take_profit"),
    pytest.param({"stop_loss": {"trigger_price": "80"}, "oco": True}, id="stop_loss"),
    pytest.param({"trailing_stop": {"trailing_distance_bps": 25}, "oco": True}, id="trailing"),
    pytest.param(
        AttachedRisk(take_profit=RiskLeg(trigger_price=Price.from_ticks(140_000_000)), oco=True),
        id="typed_take_profit",
    ),
]


def _assert_oco_refusal(exc: PolyesterValidationError, risk_field: str) -> None:
    assert [(v.field_path, v.rule_id) for v in exc.violations] == [(risk_field, OCO_RULE)]


@pytest.mark.asyncio
@pytest.mark.parametrize("risk", ONE_LEG_OCO)
async def test_modify_refuses_one_leg_oco_before_sending(risk: object) -> None:
    capture = CaptureUnary(orders_pb2.ModifyOrderResponse())
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch(UNARY, capture),
        pytest.raises(PolyesterValidationError, match="oco requires") as caught,
    ):
        await service.modify(
            key=ClientOrderId("cid-1"),
            symbol="BTC-USDT",
            new_price="1000",
            new_attached_risk=risk,  # type: ignore[arg-type]
        )
    assert capture.calls == 0
    _assert_oco_refusal(caught.value, "new_attached_risk")


@pytest.mark.asyncio
@pytest.mark.parametrize("risk", ONE_LEG_OCO)
async def test_batch_replace_refuses_one_leg_oco_before_sending(risk: object) -> None:
    capture = CaptureUnary(orders_pb2.BatchReplaceOrdersResponse())
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch(UNARY, capture),
        pytest.raises(PolyesterValidationError, match="oco requires") as caught,
    ):
        await service.batch_replace(
            symbol="BTC-USDT",
            items=[{"key": ClientOrderId("cid-1"), "new_price": "1000", "new_attached_risk": risk}],
        )
    assert capture.calls == 0
    _assert_oco_refusal(caught.value, "new_attached_risk")


@pytest.mark.asyncio
@pytest.mark.parametrize("risk", ONE_LEG_OCO)
async def test_create_refuses_one_leg_oco_before_sending(risk: object) -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch(UNARY, capture),
        pytest.raises(PolyesterValidationError, match="oco requires") as caught,
    ):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="1000",
            attached_risk=risk,  # type: ignore[arg-type]
        )
    assert capture.calls == 0
    _assert_oco_refusal(caught.value, "order.attached_risk")


@pytest.mark.parametrize(
    "risk",
    [
        pytest.param({"take_profit": {"trigger_price": "140"}}, id="one_leg"),
        pytest.param({"stop_loss": {"trigger_price": "80"}, "oco": False}, id="one_leg_oco_false"),
        pytest.param(
            {
                "take_profit": {"trigger_price": "140"},
                "stop_loss": {"trigger_price": "80"},
                "oco": True,
            },
            id="take_profit_and_stop_loss",
        ),
        pytest.param(
            {
                "take_profit": {"trigger_price": "140"},
                "trailing_stop": {"trailing_distance_bps": 25},
                "oco": True,
            },
            id="take_profit_and_trailing",
        ),
    ],
)
def test_modify_and_batch_replace_keep_valid_attached_risk(risk: dict) -> None:
    modify = modify_order_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        key=ClientOrderId("cid-1"),
        new_price="1000",
        new_attached_risk=risk,
    )
    batch = batch_replace_orders_to_proto(
        items=[{"key": ClientOrderId("cid-1"), "new_price": "1000", "new_attached_risk": risk}],
        symbol_id=1,
        symbol="BTC-USDT",
    )
    for encoded in (modify.new_attached_risk, batch.items[0].new_attached_risk):
        assert encoded.oco is bool(risk.get("oco"))
        assert encoded.HasField("take_profit") is ("take_profit" in risk)
        assert encoded.HasField("stop_loss") is ("stop_loss" in risk)
        assert encoded.HasField("trailing_stop") is ("trailing_stop" in risk)
