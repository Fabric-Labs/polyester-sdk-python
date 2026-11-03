"""A refused trigger fire is a non-terminal ``fire_refused`` event with its
``fire_refusal_reason`` (contract note 1721Z)."""

from __future__ import annotations

import pytest

from polyester import is_terminal_trigger_event
from polyester.codecs.decode.triggers import (
    trigger_event_from_proto,
    trigger_event_type_from_label,
    trigger_events_list_from_proto,
)
from polyester.codecs.realtime_decode import decode_trigger_event_batch_bytes
from polyester.codecs.wire_decode import decode_trigger_event
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import TriggerEvent
from polyester.transport import TransportConfig, codec_for_config


def test_wire_numbers_match_the_published_contract() -> None:
    assert triggers_pb2.EVENT_FIRE_REFUSED == 7
    assert triggers_pb2.TRIGGER_FAILURE_REASON_ACCOUNT_REPAIRING == 239


def _refused(reason: int) -> triggers_pb2.TriggerEvent:
    return triggers_pb2.TriggerEvent(
        trigger_id=9,
        symbol_id=1,
        event_type=triggers_pb2.EVENT_FIRE_REFUSED,
        child_seq=1,
        fire_price_ticks=104_000_000_000,
        fire_refusal_reason=reason,  # type: ignore[arg-type]
        ts_ns=1_700_000_000_000_000_000,
    )


@pytest.mark.parametrize(
    ("reason", "label"),
    [
        (triggers_pb2.TRIGGER_FAILURE_REASON_RATE_LIMITED, "rate_limited"),
        (triggers_pb2.TRIGGER_FAILURE_REASON_ACCOUNT_REPAIRING, "account_repairing"),
        (triggers_pb2.TRIGGER_FAILURE_REASON_MARKET_HALTED, "market_halted"),
        (triggers_pb2.TRIGGER_FAILURE_REASON_MIN_NOTIONAL, "min_notional"),
    ],
)
def test_fire_refused_event_reads_its_reason(reason: int, label: str) -> None:
    event = trigger_event_from_proto(_refused(reason))

    assert event.event_type == "fire_refused"
    assert event.fire_refusal_reason == label
    assert event.child_seq == 1
    assert event.child_order_id == ""
    assert event.fire_price is not None and event.fire_price.ticks == 104_000_000_000
    # Outside the terminal_reason oneof: no cancel or failure reason.
    assert event.cancel_reason == ""
    assert event.failure_reason == ""


def test_other_events_carry_no_fire_refusal_reason() -> None:
    fired = trigger_event_from_proto(
        triggers_pb2.TriggerEvent(trigger_id=9, event_type=triggers_pb2.EVENT_FIRED, child_seq=2)
    )
    assert fired.fire_refusal_reason == ""


def test_stream_and_json_decode_the_refused_fire() -> None:
    [streamed] = decode_trigger_event_batch_bytes(
        triggers_pb2.TriggerEventBatch(
            events=[_refused(triggers_pb2.TRIGGER_FAILURE_REASON_RATE_LIMITED)]
        ).SerializeToString()
    )
    assert isinstance(streamed, TriggerEvent)
    assert (streamed.event_type, streamed.fire_refusal_reason) == ("fire_refused", "rate_limited")

    codec = codec_for_config(TransportConfig(api_url="https://example.test", wire_format="json"))
    decoded = codec.decode(
        b'{"events": [{"triggerId": "9", "eventType": "EVENT_FIRE_REFUSED", "childSeq": 1,'
        b' "fireRefusalReason": "TRIGGER_FAILURE_REASON_ACCOUNT_REPAIRING"}]}',
        triggers_pb2.ListTriggerEventsResponse(),
    )
    [event] = trigger_events_list_from_proto(decoded).events
    assert (event.event_type, event.fire_refusal_reason) == ("fire_refused", "account_repairing")

    rest = decode_trigger_event(
        {"triggerId": "9", "eventType": "FIRE_REFUSED", "childSeq": 1,
         "fireRefusalReason": "RATE_LIMITED"}
    )
    assert rest.fire_refusal_reason == "rate_limited"


def test_unknown_event_type_and_reason_numbers_decode() -> None:
    event = triggers_pb2.TriggerEvent(trigger_id=9)
    event.event_type = 99  # type: ignore[assignment]
    event.fire_refusal_reason = 777  # type: ignore[assignment]
    decoded = trigger_event_from_proto(event)
    assert decoded.event_type == "99"
    assert decoded.fire_refusal_reason == "777"
    assert not is_terminal_trigger_event(decoded.event_type)


def test_fire_refused_filters_list_events() -> None:
    assert trigger_event_type_from_label("fire_refused") == triggers_pb2.EVENT_FIRE_REFUSED
    assert trigger_event_type_from_label("FIRE_REFUSED") == triggers_pb2.EVENT_FIRE_REFUSED


def test_fire_refused_is_not_terminal() -> None:
    assert not is_terminal_trigger_event("fire_refused")
    assert not is_terminal_trigger_event("fired")
    assert is_terminal_trigger_event("canceled")
    assert is_terminal_trigger_event("failed")
