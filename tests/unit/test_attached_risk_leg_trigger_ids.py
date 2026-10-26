"""Create, modify and batch-create results carry the trigger IDs of configured legs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import (
    batch_create_from_proto,
    modify_order_from_proto,
    order_mutation_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary

TP_ID = 9_000_000_000_000_001
SL_ID = 9_000_000_000_000_002
TRAIL_ID = 9_000_000_000_000_003


def test_create_result_carries_configured_leg_trigger_ids_only() -> None:
    result = order_mutation_from_proto(
        orders_pb2.CreateOrderResponse(
            order_id=42, take_profit_trigger_id=TP_ID, stop_loss_trigger_id=SL_ID
        )
    )
    assert result.take_profit_trigger_id == format_id(TP_ID)
    assert result.stop_loss_trigger_id == format_id(SL_ID)
    assert result.trailing_stop_trigger_id == ""


def test_create_result_without_attached_risk_has_no_leg_trigger_ids() -> None:
    result = order_mutation_from_proto(orders_pb2.CreateOrderResponse(order_id=42))
    assert (
        result.take_profit_trigger_id,
        result.stop_loss_trigger_id,
        result.trailing_stop_trigger_id,
    ) == ("", "", "")


def test_cancel_result_has_no_leg_trigger_ids() -> None:
    result = order_mutation_from_proto(
        orders_pb2.CancelOrderResponse(order_id=42, status=orders_pb2.CancelOrderResponse.ACCEPTED)
    )
    assert result.take_profit_trigger_id == ""


def test_modify_result_carries_configured_leg_trigger_ids_only() -> None:
    result = modify_order_from_proto(
        orders_pb2.ModifyOrderResponse(
            action_taken=orders_pb2.REPLACED,
            old_order_id=7,
            final_order_id=8,
            trailing_stop_trigger_id=TRAIL_ID,
        )
    )
    assert result.trailing_stop_trigger_id == format_id(TRAIL_ID)
    assert result.take_profit_trigger_id == ""
    assert result.stop_loss_trigger_id == ""


def test_batch_create_accepted_items_carry_configured_leg_trigger_ids() -> None:
    result = batch_create_from_proto(
        orders_pb2.BatchCreateOrdersResponse(
            results=[
                orders_pb2.BatchCreateResultItem(
                    client_order_id="a",
                    accepted=orders_pb2.BatchCreateAccepted(
                        order_id=1, stop_loss_trigger_id=SL_ID, trailing_stop_trigger_id=TRAIL_ID
                    ),
                ),
                orders_pb2.BatchCreateResultItem(
                    client_order_id="b",
                    accepted=orders_pb2.BatchCreateAccepted(order_id=2),
                ),
            ],
            accepted_count=2,
        )
    )
    first, second = result.results
    assert first.take_profit_trigger_id == ""
    assert first.stop_loss_trigger_id == format_id(SL_ID)
    assert first.trailing_stop_trigger_id == format_id(TRAIL_ID)
    assert (
        second.take_profit_trigger_id,
        second.stop_loss_trigger_id,
        second.trailing_stop_trigger_id,
    ) == ("", "", "")


@pytest.mark.asyncio
async def test_orders_create_returns_leg_trigger_ids() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    capture = CaptureUnary(
        orders_pb2.CreateOrderResponse(order_id=42, take_profit_trigger_id=TP_ID)
    )
    service = AsyncOrdersService(MagicMock(), catalogs, None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        result = await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.01",
            price="83589",
        )
    assert result.take_profit_trigger_id == format_id(TP_ID)
    assert result.stop_loss_trigger_id == ""
