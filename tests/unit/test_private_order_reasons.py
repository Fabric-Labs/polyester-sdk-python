"""Why an order ended: ``reject_reason`` and ``cancel_reason`` on order reads,
the private stream's orders and its order events."""

from __future__ import annotations

import pytest

from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.decode.private_orders import (
    private_orders_from_proto,
    private_orders_unit_from_proto,
)
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models.private_orders import PrivateOrderEvent


def _order(**fields: object) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(order_id=7, symbol_id=101, **fields)  # type: ignore[arg-type]


def _event(**fields: object) -> pb.UnitEvent:
    return pb.UnitEvent(order=pb.OrderEvent(**fields))  # type: ignore[arg-type]


def test_rejected_order_read_carries_the_orders_api_error_code() -> None:
    order = order_from_proto(
        _order(
            status=orders_read_pb2.REJECTED,
            reject_reason=orders_pb2.ERROR_CODE_INSUFFICIENT_FUNDS,
        )
    )
    assert order.status == "rejected"
    assert order.reject_reason == "INSUFFICIENT_FUNDS"
    assert order.cancel_reason is None


def test_canceled_order_read_carries_its_cancel_reason() -> None:
    order = order_from_proto(
        _order(
            status=orders_read_pb2.CANCELED,
            cancel_reason=orders_read_pb2.CANCEL_REASON_STP_EXPIRE_MAKER,
        )
    )
    assert order.cancel_reason == "STP_EXPIRE_MAKER"
    assert order.reject_reason is None


@pytest.mark.parametrize(
    "status",
    [orders_read_pb2.PENDING, orders_read_pb2.WORKING, orders_read_pb2.FILLED],
    ids=orders_read_pb2.OrderStatus.Name,
)
def test_reasons_are_none_for_other_statuses(status: int) -> None:
    order = order_from_proto(_order(status=status))
    assert order.reject_reason is None
    assert order.cancel_reason is None


@pytest.mark.parametrize(
    ("name", "value"),
    [(name, value) for name, value in orders_read_pb2.CancelReason.items() if value],
)
def test_every_cancel_reason_decodes_without_its_prefix(name: str, value: int) -> None:
    order = order_from_proto(_order(status=orders_read_pb2.CANCELED, cancel_reason=value))
    assert order.cancel_reason == name.removeprefix("CANCEL_REASON_")


def test_unknown_reason_numbers_decode_without_raising() -> None:
    rejected = order_from_proto(_order(status=orders_read_pb2.REJECTED, reject_reason=9999))
    canceled = order_from_proto(_order(status=orders_read_pb2.CANCELED, cancel_reason=999))
    assert rejected.reject_reason == "UNKNOWN_ERROR_CODE(9999)"
    assert canceled.cancel_reason == "UNKNOWN_CANCEL_REASON(999)"


def test_reasons_are_omitted_from_the_encoded_order_when_unset() -> None:
    import msgspec

    encoded = msgspec.to_builtins(order_from_proto(_order(status=orders_read_pb2.WORKING)))
    assert "reject_reason" not in encoded
    assert "cancel_reason" not in encoded


def test_stream_snapshot_and_unit_orders_carry_reasons() -> None:
    snapshot = private_orders_from_proto(
        [
            _order(
                status=orders_read_pb2.REJECTED,
                reject_reason=orders_pb2.ERROR_CODE_POST_ONLY_CROSS,
            ),
            _order(status=orders_read_pb2.WORKING),
        ]
    )
    assert [(o.reject_reason, o.cancel_reason) for o in snapshot] == [
        ("POST_ONLY_CROSS", None),
        (None, None),
    ]

    unit = private_orders_unit_from_proto(
        pb.Unit(
            orders=[
                _order(
                    status=orders_read_pb2.CANCELED,
                    cancel_reason=orders_read_pb2.CANCEL_REASON_REPLACED,
                )
            ]
        )
    )
    assert unit.orders[0].cancel_reason == "REPLACED"
    assert unit.orders[0].reject_reason is None


def test_order_event_reasons() -> None:
    unit = private_orders_unit_from_proto(
        pb.Unit(
            events=[
                _event(
                    order_id=1,
                    kind=pb.OrderEvent.REJECTED,
                    reject_reason=orders_pb2.ERROR_CODE_POST_ONLY_CROSS,
                ),
                _event(
                    order_id=2,
                    kind=pb.OrderEvent.CANCELED,
                    cancel_reason=orders_read_pb2.CANCEL_REASON_USER_REQUEST,
                ),
                # The REPLACED update of the order a replace ended.
                _event(
                    order_id=3,
                    kind=pb.OrderEvent.REPLACED,
                    cancel_reason=orders_read_pb2.CANCEL_REASON_REPLACED,
                    replacement_order_id=4,
                ),
                # The REPLACED update that installs the successor carries none.
                _event(order_id=4, kind=pb.OrderEvent.REPLACED),
                _event(order_id=5, kind=pb.OrderEvent.ACCEPTED),
                _event(order_id=6, kind=pb.OrderEvent.CANCELED, cancel_reason=999),
                _event(order_id=8, kind=pb.OrderEvent.REJECTED, reject_reason=9999),
            ]
        )
    )
    events = [event for event in unit.events if isinstance(event, PrivateOrderEvent)]
    assert [(e.kind, e.reject_reason, e.cancel_reason) for e in events] == [
        ("rejected", "POST_ONLY_CROSS", None),
        ("canceled", None, "USER_REQUEST"),
        ("replaced", None, "REPLACED"),
        ("replaced", None, None),
        ("accepted", None, None),
        ("canceled", None, "UNKNOWN_CANCEL_REASON(999)"),
        ("rejected", "UNKNOWN_ERROR_CODE(9999)", None),
    ]
