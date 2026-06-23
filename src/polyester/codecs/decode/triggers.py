from __future__ import annotations

from polyester.codecs.proto_helpers import format_uint64_id, has_field, proto_enum_name
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import (
    Trigger,
    TriggerEvent,
    TriggerEventsList,
    TriggerMutationResult,
    TriggersList,
)

# Match TypeScript TriggerStatusCodec.protoToOutput (British "cancelled" for status).
_TRIGGER_STATUS_LABELS: dict[int, str] = {
    triggers_pb2.STATUS_CREATED: "created",
    triggers_pb2.STATUS_ARMED: "armed",
    triggers_pb2.STATUS_RUNNING: "running",
    triggers_pb2.STATUS_COMPLETED: "completed",
    triggers_pb2.STATUS_CANCELED: "cancelled",
    triggers_pb2.STATUS_FAILED: "failed",
    triggers_pb2.STATUS_PAUSED: "paused",
}

# Match TypeScript TriggerEventTypeCodec.protoToOutput (American "canceled" for events).
_TRIGGER_EVENT_TYPE_LABELS: dict[int, str] = {
    triggers_pb2.EVENT_FIRED: "fired",
    triggers_pb2.EVENT_CANCELED: "canceled",
    triggers_pb2.EVENT_UPDATED: "updated",
}


def _trigger_status_label(value: int) -> str:
    if value == 0:
        return ""
    return _TRIGGER_STATUS_LABELS.get(
        value, proto_enum_name(triggers_pb2.TriggerStatus, value)
    )


def _trigger_event_type_label(value: int) -> str:
    if value == 0:
        return ""
    return _TRIGGER_EVENT_TYPE_LABELS.get(
        value, proto_enum_name(triggers_pb2.TriggerEventType, value)
    )


def _trigger_price_ticks(msg: triggers_pb2.Trigger) -> str:
    if has_field(msg, "stop") and msg.stop.trigger_price_ticks:
        return str(msg.stop.trigger_price_ticks)
    return ""


def trigger_from_proto(msg: triggers_pb2.Trigger) -> Trigger:
    return Trigger(
        trigger_id=format_uint64_id(msg.trigger_id),
        symbol_id=int(msg.symbol_id),
        symbol=msg.symbol,
        trigger_type=proto_enum_name(triggers_pb2.TriggerType, msg.trigger_type),
        status=_trigger_status_label(msg.status),
        side=proto_enum_name(orders_pb2.Side, msg.side),
        qty_scaled=str(msg.qty_scaled),
        trigger_price_ticks=_trigger_price_ticks(msg),
        client_trigger_id=msg.client_trigger_id,
    )


def triggers_list_from_proto(msg: triggers_pb2.ListTriggersResponse) -> TriggersList:
    triggers = [trigger_from_proto(item) for item in msg.triggers]
    return TriggersList(triggers=triggers, total=len(triggers))


def get_trigger_from_proto(msg: triggers_pb2.GetTriggerResponse) -> Trigger | None:
    if has_field(msg, "trigger"):
        return trigger_from_proto(msg.trigger)
    return None


def trigger_mutation_from_proto(
    msg: triggers_pb2.CreateTriggerResponse
    | triggers_pb2.CancelTriggerResponse
    | triggers_pb2.ModifyTriggerResponse
    | triggers_pb2.PauseTriggerResponse
    | triggers_pb2.ResumeTriggerResponse,
) -> TriggerMutationResult:
    return TriggerMutationResult(
        trigger_id=format_uint64_id(msg.trigger_id),
        status=_trigger_status_label(msg.status),
    )


def trigger_event_from_proto(msg: triggers_pb2.TriggerEvent) -> TriggerEvent:
    return TriggerEvent(
        trigger_id=format_uint64_id(msg.trigger_id),
        symbol_id=int(msg.symbol_id),
        trigger_type=proto_enum_name(triggers_pb2.TriggerType, msg.trigger_type),
        event_type=_trigger_event_type_label(msg.event_type),
        ts_ns=str(msg.ts_ns),
        fire_px_ticks=str(msg.fire_price_ticks),
        reason=msg.reason,
    )


def trigger_events_list_from_proto(
    msg: triggers_pb2.ListTriggerEventsResponse,
) -> TriggerEventsList:
    return TriggerEventsList(
        events=[trigger_event_from_proto(item) for item in msg.events],
        next_before_ts_ns=msg.next_page_token or "0",
    )
