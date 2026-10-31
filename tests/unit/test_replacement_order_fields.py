"""Replacement orders expose inherited fills and the batch action taken."""

from __future__ import annotations

from polyester.codecs.decode.orders import (
    batch_replace_from_proto,
    batch_replace_status_from_proto,
    order_from_proto,
)
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2


def test_order_exposes_inherited_cum_qty_from_replaced_predecessors() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=11,
            symbol_id=1,
            orig_qty_scaled=500,
            cum_qty_scaled=300,
            inherited_cum_qty_scaled=200,
            leaves_qty_scaled=200,
        ),
        quantity_scale=2,
    )

    assert order.inherited_cum_qty is not None
    assert order.inherited_cum_qty.format() == "2"
    assert order.cum_qty is not None and order.cum_qty.format() == "3"


def test_order_never_replaced_inherits_zero() -> None:
    order = order_from_proto(
        orders_read_pb2.Order(order_id=11, symbol_id=1, cum_qty_scaled=300), quantity_scale=2
    )

    assert order.inherited_cum_qty is not None
    assert order.inherited_cum_qty.scaled == 0


def test_batch_replace_admission_items_expose_action_taken() -> None:
    result = batch_replace_from_proto(
        orders_pb2.BatchReplaceOrdersResponse(
            batch_request_id=77,
            status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
            results=[
                orders_pb2.BatchReplaceAdmissionItem(
                    item_index=0,
                    status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                    old_order_id=10,
                    replacement_order_id=11,
                    action_taken=orders_pb2.REPLACED,
                ),
                orders_pb2.BatchReplaceAdmissionItem(
                    item_index=1,
                    status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                    old_order_id=12,
                    action_taken=orders_pb2.AMENDED,
                ),
                orders_pb2.BatchReplaceAdmissionItem(
                    item_index=2,
                    status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                    old_order_id=13,
                ),
            ],
            accepted_count=3,
        )
    )

    assert [item.action_taken for item in result.results] == ["replaced", "amended", ""]


def test_batch_replace_status_items_expose_action_taken() -> None:
    result = batch_replace_status_from_proto(
        orders_read_pb2.GetBatchReplaceStatusResponse(
            batch_request_id=77,
            admission_status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
            items=[
                orders_read_pb2.BatchReplaceStatusItem(
                    item_index=0,
                    phase=orders_read_pb2.BATCH_REPLACE_PHASE_TERMINAL,
                    old_order_id=12,
                    action_taken=orders_pb2.AMENDED,
                    updated_ts_ns=1,
                ),
            ],
            accepted_count=1,
        )
    )

    assert result.items[0].action_taken == "amended"
    assert result.items[0].replacement_order_id == ""
