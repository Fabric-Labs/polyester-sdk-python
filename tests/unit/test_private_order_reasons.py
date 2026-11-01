from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models.private_orders import PrivateOrderEvent


def _event(**fields: object) -> pb.UnitEvent:
    return pb.UnitEvent(order=pb.OrderEvent(**fields))  # type: ignore[arg-type]


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
                _event(
                    order_id=3,
                    kind=pb.OrderEvent.REPLACED,
                    cancel_reason=orders_read_pb2.CANCEL_REASON_REPLACED,
                    replacement_order_id=4,
                ),
                _event(order_id=5, kind=pb.OrderEvent.ACCEPTED),
                _event(order_id=6, kind=pb.OrderEvent.CANCELED, cancel_reason=999),
            ]
        )
    )
    events = [event for event in unit.events if isinstance(event, PrivateOrderEvent)]
    assert [(e.kind, e.reject_reason, e.cancel_reason) for e in events] == [
        ("rejected", "POST_ONLY_CROSS", ""),
        ("canceled", "", "USER_REQUEST"),
        ("replaced", "", "REPLACED"),
        ("accepted", "", ""),
        ("canceled", "", "UNKNOWN_CANCEL_REASON(999)"),
    ]
