"""Clearing an order's attached risk, and refusing an empty one.

``new_attached_risk={}`` was dropped: a modify with a new price succeeded and
the order kept its take-profit and stop-loss. An empty risk is now refused
before sending, and ``clear_attached_risk=True`` removes the legs by sending an
empty ``RiskPolicy``, as the TypeScript SDK's ``clearRisk`` does.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import batch_replace_item_to_proto, modify_order_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import AttachedRisk, BatchReplaceItem, ClientOrderId, OrderId
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary

RISK = {"take_profit": {"trigger_price": "140", "order_type": "market"}}


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
                    "reference_price_scale": 9,
                }
            ]
        }
    )
    return catalogs


def _modify(**kwargs):
    return modify_order_to_proto(
        symbol="BTC-USDT", symbol_id=1, key=ClientOrderId("cid-1"), **kwargs
    )


def _cleared(risk: orders_pb2.RiskPolicy) -> bool:
    return risk == orders_pb2.RiskPolicy()


@pytest.mark.parametrize("empty", [{}, AttachedRisk()])
@pytest.mark.parametrize("new_price", [None, "64672.97"])
def test_modify_refuses_an_empty_new_attached_risk(empty, new_price) -> None:
    with pytest.raises(PolyesterValidationError, match="clear_attached_risk"):
        _modify(new_price=new_price, new_attached_risk=empty)


@pytest.mark.parametrize("new_price", [None, "64672.97"])
def test_modify_clear_attached_risk_sends_an_empty_risk_policy(new_price) -> None:
    proto = _modify(new_price=new_price, clear_attached_risk=True)
    assert proto.HasField("new_attached_risk")
    assert _cleared(proto.new_attached_risk)
    assert proto.HasField("new_price_ticks") == (new_price is not None)


def test_modify_refuses_clear_with_new_attached_risk() -> None:
    with pytest.raises(PolyesterValidationError, match="not both"):
        _modify(new_attached_risk=RISK, clear_attached_risk=True)


@pytest.mark.parametrize(
    "item",
    [
        BatchReplaceItem(key=OrderId("9"), clear_attached_risk=True),
        BatchReplaceItem(key=OrderId("9"), new_price="100", clear_attached_risk=True),
        {"key": OrderId("9"), "clear_attached_risk": True},
    ],
)
def test_batch_replace_clear_attached_risk_sends_an_empty_risk_policy(item) -> None:
    proto = batch_replace_item_to_proto(item, quantity_scale=8, symbol="BTC-USDT")
    assert proto.HasField("new_attached_risk")
    assert _cleared(proto.new_attached_risk)


@pytest.mark.parametrize(
    "item",
    [
        BatchReplaceItem(key=OrderId("9"), new_price="100", new_attached_risk={}),
        BatchReplaceItem(key=OrderId("9"), new_attached_risk=RISK, clear_attached_risk=True),
        {"key": OrderId("9"), "new_price": "100", "new_attached_risk": {}},
    ],
)
def test_batch_replace_refuses_an_empty_or_conflicting_risk(item) -> None:
    with pytest.raises(PolyesterValidationError):
        batch_replace_item_to_proto(item, quantity_scale=8, symbol="BTC-USDT")


@pytest.mark.asyncio
async def test_orders_modify_clears_attached_risk_and_refuses_empty_before_sending() -> None:
    capture = CaptureUnary(
        orders_pb2.ModifyOrderResponse(
            action_taken=orders_pb2.REPLACED, old_order_id=9, final_order_id=10
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        with pytest.raises(PolyesterValidationError):
            await service.modify(
                key=OrderId("9"), symbol="BTC-USDT", new_price="64672.97", new_attached_risk={}
            )
        assert capture.calls == 0
        await service.modify(
            key=OrderId("9"), symbol="BTC-USDT", new_price="64672.97", clear_attached_risk=True
        )
    assert capture.calls == 1
    assert _cleared(capture.request.new_attached_risk)


@pytest.mark.asyncio
async def test_orders_create_refuses_an_empty_attached_risk_before_sending() -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=9))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch("polyester.services.orders.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError),
    ):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="1000",
            attached_risk={},
        )
    assert capture.calls == 0
