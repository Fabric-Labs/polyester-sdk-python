"""Batch item limits follow the public contract: create 20, cancel and replace 50."""

from __future__ import annotations

import pytest

from polyester.codecs.orders import (
    batch_cancel_orders_to_proto,
    batch_create_orders_to_proto,
    batch_replace_orders_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import OrderId


def _contract_max_items(message: type) -> int:
    field = message.DESCRIPTOR.fields_by_name["items"]
    return field.GetOptions().Extensions[validate_pb2.field].repeated.max_items


def _cancel(count: int) -> orders_pb2.BatchCancelOrdersRequest:
    return batch_cancel_orders_to_proto(items=[{"key": OrderId(i + 1)} for i in range(count)])


def _replace(count: int) -> orders_pb2.BatchReplaceOrdersRequest:
    return batch_replace_orders_to_proto(
        items=[{"key": OrderId(i + 1), "new_price": "100"} for i in range(count)],
        symbol_id=1,
        symbol="BTC-USDT",
        quantity_scale=8,
    )


def _create(count: int) -> orders_pb2.BatchCreateOrdersRequest:
    item = {
        "symbol_id": 1,
        "side": "buy",
        "order_type": "limit",
        "tif": "gtc",
        "qty": "1",
        "price": "100",
    }
    return batch_create_orders_to_proto(items=[dict(item) for _ in range(count)], quantity_scale=8)


def test_contract_limits_are_what_the_sdk_expects() -> None:
    assert _contract_max_items(orders_pb2.BatchCancelOrdersRequest) == 50
    assert _contract_max_items(orders_pb2.BatchReplaceOrdersRequest) == 50
    assert _contract_max_items(orders_pb2.BatchCreateOrdersRequest) == 20


@pytest.mark.parametrize("count", [1, 20, 21, 50])
def test_batch_cancel_accepts_up_to_50(count: int) -> None:
    assert len(_cancel(count).items) == count


@pytest.mark.parametrize("count", [1, 20, 21, 50])
def test_batch_replace_accepts_up_to_50(count: int) -> None:
    assert len(_replace(count).items) == count


def test_batch_cancel_refuses_51() -> None:
    with pytest.raises(PolyesterValidationError, match="batch_cancel accepts at most 50 items"):
        _cancel(51)


def test_batch_replace_refuses_51() -> None:
    with pytest.raises(PolyesterValidationError, match="batch_replace accepts at most 50 items"):
        _replace(51)


def test_batch_create_keeps_its_20_item_limit() -> None:
    assert len(_create(20).items) == 20
    with pytest.raises(PolyesterValidationError, match="batch_create accepts at most 20 items"):
        _create(21)


@pytest.mark.parametrize("build", [_cancel, _replace, _create])
def test_empty_batches_are_refused(build) -> None:
    with pytest.raises(PolyesterValidationError, match="requires at least one item"):
        build(0)
