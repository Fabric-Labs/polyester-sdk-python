"""Cancel-all results list the orders whose cancellation was requested."""

from __future__ import annotations

from polyester.codecs.decode.orders import cancel_all_from_proto
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CancelledOrder

Status = orders_pb2.CancelAllOrdersResponse


def test_cancel_all_lists_cancelled_orders_oldest_first() -> None:
    result = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(
            status=Status.SUBMITTED,
            matched_orders=3,
            submitted_cancels=3,
            cancelled_orders=[
                orders_pb2.CancelledOrder(order_id=101, client_order_id="bot-1"),
                orders_pb2.CancelledOrder(order_id=102),
                orders_pb2.CancelledOrder(order_id=103, client_order_id="bot-3"),
            ],
            total_cancelled=3,
        )
    )
    assert result.cancelled_orders == [
        CancelledOrder(order_id=format_id(101), client_order_id="bot-1"),
        CancelledOrder(order_id=format_id(102), client_order_id=""),
        CancelledOrder(order_id=format_id(103), client_order_id="bot-3"),
    ]
    assert result.total_cancelled == 3
    assert result.truncated is False


def test_cancel_all_reports_a_truncated_list() -> None:
    listed = [orders_pb2.CancelledOrder(order_id=1_000 + i) for i in range(200)]
    result = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(
            status=Status.SUBMITTED,
            matched_orders=250,
            submitted_cancels=250,
            cancelled_orders=listed,
            total_cancelled=250,
            truncated=True,
        )
    )
    assert len(result.cancelled_orders) == 200
    assert result.cancelled_orders[0].order_id == format_id(1_000)
    assert result.total_cancelled == 250
    assert result.truncated is True


def test_cancel_all_dry_run_lists_nothing() -> None:
    result = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(status=Status.DRY_RUN, matched_orders=4)
    )
    assert result.status == "dry_run"
    assert result.matched_orders == 4
    assert result.cancelled_orders == []
    assert result.total_cancelled == 0
