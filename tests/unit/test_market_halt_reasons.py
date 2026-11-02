"""A market halt ends orders (cancel reason 17) and triggers (cancel reason 13);
a trigger the halted market refused reads the unnamed failure reason 212."""

from __future__ import annotations

from polyester._wire import protobuf_to_public_dict
from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.decode.triggers import get_trigger_from_proto, trigger_event_from_proto
from polyester.codecs.realtime_decode import (
    decode_trigger_bytes,
    decode_trigger_event_batch_bytes,
)
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import TriggerEvent
from polyester.transport import TransportConfig, codec_for_config


def test_wire_numbers_match_the_published_contract() -> None:
    assert orders_read_pb2.CANCEL_REASON_MARKET_HALTED == 17
    assert triggers_pb2.TRIGGER_CANCEL_REASON_MARKET_HALTED == 13


def test_order_read_and_stream_label_the_market_halt() -> None:
    halted = orders_read_pb2.Order(
        order_id=7,
        symbol_id=1,
        status=orders_read_pb2.CANCELED,
        cancel_reason=orders_read_pb2.CANCEL_REASON_MARKET_HALTED,
    )
    assert order_from_proto(halted).cancel_reason == "MARKET_HALTED"

    unit = private_orders_unit_from_proto(
        pb.Unit(
            orders=[halted],
            events=[
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=7,
                        kind=pb.OrderEvent.CANCELED,
                        cancel_reason=orders_read_pb2.CANCEL_REASON_MARKET_HALTED,
                    )
                ),
                # Refused after admission by the halted market.
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=8,
                        kind=pb.OrderEvent.REJECTED,
                        reject_reason=orders_pb2.ERROR_CODE_MARKET_HALTED,
                    )
                ),
            ],
        )
    )
    assert unit.orders[0].cancel_reason == "MARKET_HALTED"
    assert [(e.cancel_reason, e.reject_reason) for e in unit.events] == [
        ("MARKET_HALTED", None),
        (None, "MARKET_HALTED"),
    ]


def _halted_trigger() -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=9,
        symbol_id=1,
        status=triggers_pb2.STATUS_CANCELED,
        cancel_reason=triggers_pb2.TRIGGER_CANCEL_REASON_MARKET_HALTED,
    )


def test_trigger_read_stream_and_events_label_the_market_halt() -> None:
    read = get_trigger_from_proto(triggers_pb2.GetTriggerResponse(trigger=_halted_trigger()))
    assert read is not None
    assert read.cancel_reason == "market_halted"
    assert decode_trigger_bytes(_halted_trigger().SerializeToString()).cancel_reason == (
        "market_halted"
    )

    event = triggers_pb2.TriggerEvent(
        trigger_id=9,
        symbol_id=1,
        event_type=triggers_pb2.EVENT_CANCELED,
        cancel_reason=triggers_pb2.TRIGGER_CANCEL_REASON_MARKET_HALTED,
    )
    assert trigger_event_from_proto(event).cancel_reason == "market_halted"
    [streamed] = decode_trigger_event_batch_bytes(
        triggers_pb2.TriggerEventBatch(events=[event]).SerializeToString()
    )
    assert isinstance(streamed, TriggerEvent)
    assert streamed.cancel_reason == "market_halted"


def test_unnamed_trigger_failure_reason_212_decodes_as_its_number() -> None:
    # Reads report 212 until the fix reports TRIGGER_FAILURE_REASON_MARKET_HALTED (8).
    failed = triggers_pb2.Trigger(trigger_id=9, symbol_id=1, status=triggers_pb2.STATUS_FAILED)
    failed.failure_reason = 212  # type: ignore[assignment]
    binary = get_trigger_from_proto(triggers_pb2.GetTriggerResponse(trigger=failed))
    assert binary is not None
    assert binary.failure_reason == "212"

    # ConnectRPC JSON carries it as "failureReason": 212.
    codec = codec_for_config(TransportConfig(api_url="https://example.test", wire_format="json"))
    payload = (
        b'{"trigger": {"triggerId": "9", "symbolId": 1,'
        b' "status": "STATUS_FAILED", "failureReason": 212}}'
    )
    decoded = codec.decode(payload, triggers_pb2.GetTriggerResponse())
    assert protobuf_to_public_dict(decoded)["trigger"]["failureReason"] == 212
    json_read = get_trigger_from_proto(decoded)
    assert json_read is not None
    assert json_read.failure_reason == "212"
