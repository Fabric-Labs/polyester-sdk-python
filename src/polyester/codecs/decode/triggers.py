from __future__ import annotations

from datetime import UTC, datetime

from polyester.codecs.proto_helpers import format_uint64_id, has_field, proto_enum_name
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import (
    Trigger,
    TriggerDetails,
    TriggerEvent,
    TriggerEventsList,
    TriggerLadderDetails,
    TriggerMutationResult,
    TriggersList,
    TriggerStopDetails,
    TriggerTrailingDetails,
    TriggerTwapDetails,
)
from polyester.types.money import Price, Quantity

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

_TRIGGER_STATUS_FROM_LABEL: dict[str, int] = {
    "created": triggers_pb2.STATUS_CREATED,
    "armed": triggers_pb2.STATUS_ARMED,
    "running": triggers_pb2.STATUS_RUNNING,
    "completed": triggers_pb2.STATUS_COMPLETED,
    "cancelled": triggers_pb2.STATUS_CANCELED,
    "canceled": triggers_pb2.STATUS_CANCELED,
    "failed": triggers_pb2.STATUS_FAILED,
    "paused": triggers_pb2.STATUS_PAUSED,
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


def trigger_status_from_label(label: str) -> int:
    key = label.strip().lower()
    if key not in _TRIGGER_STATUS_FROM_LABEL:
        raise ValueError(
            f"invalid trigger status {label!r}; expected one of: "
            "created, armed, running, completed, cancelled, failed, paused"
        )
    return _TRIGGER_STATUS_FROM_LABEL[key]


def _trigger_event_type_label(value: int) -> str:
    if value == 0:
        return ""
    return _TRIGGER_EVENT_TYPE_LABELS.get(
        value, proto_enum_name(triggers_pb2.TriggerEventType, value)
    )


def _price(ticks: int, *, symbol: str | None = None) -> Price | None:
    if not ticks:
        return None
    return Price.from_ticks(int(ticks), symbol=symbol or None)


def _trigger_price_source_label(value: int) -> str:
    name = proto_enum_name(orders_pb2.TriggerPriceSource, value)
    if name.endswith("_price"):
        return name.removesuffix("_price")
    return name


def _timestamp(ts) -> datetime | None:
    if ts is None:
        return None
    seconds = int(getattr(ts, "seconds", 0) or 0)
    nanos = int(getattr(ts, "nanos", 0) or 0)
    if seconds == 0 and nanos == 0:
        return None
    return datetime.fromtimestamp(seconds + nanos / 1_000_000_000, tz=UTC)


def _trigger_details(msg: triggers_pb2.Trigger) -> TriggerDetails | None:
    """Project runtime execution state (``stop``/``trailing``/``twap_state``/
    ``ladder_state``) onto the discriminated ``TriggerDetails`` payload."""
    symbol = msg.symbol or None
    symbol_id = int(msg.symbol_id)
    if has_field(msg, "stop"):
        stop = msg.stop
        return TriggerDetails(
            case="stop",
            stop=TriggerStopDetails(
                trigger_price=_price(stop.trigger_price_ticks, symbol=symbol),
                trigger_price_source=_trigger_price_source_label(stop.trigger_price_source),
                trigger_direction=proto_enum_name(
                    orders_pb2.TriggerDirection, stop.trigger_direction
                ),
            ),
        )
    if has_field(msg, "trailing"):
        trailing = msg.trailing
        return TriggerDetails(
            case="trailing",
            trailing=TriggerTrailingDetails(
                trailing_distance=_price(trailing.trailing_distance_ticks, symbol=symbol),
                trailing_distance_bps=int(trailing.trailing_distance_bps),
                activation_price=_price(trailing.activation_price_ticks, symbol=symbol),
                peak_price=_price(trailing.peak_price_ticks, symbol=symbol),
                trough_price=_price(trailing.trough_price_ticks, symbol=symbol),
                max_slippage=_price(int(trailing.max_slippage_ticks), symbol=symbol),
                max_slippage_bps=int(trailing.max_slippage_bps),
                trigger_price_source=_trigger_price_source_label(
                    trailing.trigger_price_source
                ),
                trigger_direction=proto_enum_name(
                    orders_pb2.TriggerDirection, trailing.trigger_direction
                ),
            ),
        )
    if has_field(msg, "twap_state"):
        twap = msg.twap_state
        return TriggerDetails(
            case="twap",
            twap=TriggerTwapDetails(
                twap_duration_ms=int(twap.twap_duration_ms),
                twap_slice_interval_ms=int(twap.twap_slice_interval_ms),
                slice_idx=int(twap.slice_idx),
                slice_count=int(twap.slice_count),
                executed_qty=Quantity.from_scaled(
                    int(twap.executed_qty_scaled),
                    symbol=symbol,
                    symbol_id=symbol_id,
                ),
            ),
        )
    if has_field(msg, "ladder_state"):
        ladder = msg.ladder_state
        return TriggerDetails(
            case="ladder",
            ladder=TriggerLadderDetails(
                ladder_price_min=_price(ladder.ladder_price_min_ticks, symbol=symbol),
                ladder_price_max=_price(ladder.ladder_price_max_ticks, symbol=symbol),
                ladder_levels=int(ladder.ladder_levels),
                ladder_distribution=proto_enum_name(
                    triggers_pb2.LadderDistribution, ladder.ladder_distribution
                ),
            ),
        )
    return None


class _TriggerConfig:
    """Thick projection derived from the configuration oneof."""

    __slots__ = (
        "trigger_type",
        "side",
        "order_type",
        "time_in_force",
        "post_only",
        "limit_price",
        "trigger_price",
    )

    def __init__(self) -> None:
        self.trigger_type = ""
        self.side = ""
        self.order_type = ""
        self.time_in_force = ""
        self.post_only = False
        self.limit_price = None
        self.trigger_price = None


def _child_execution_projection(child, cfg: _TriggerConfig, *, symbol: str | None) -> None:
    """Derive order_type/tif/post_only/limit_price from a conditional child."""
    if child.HasField("market_ioc"):
        cfg.order_type = "market"
        cfg.time_in_force = "ioc"
    elif child.HasField("limit_gtc"):
        cfg.order_type = "limit"
        cfg.time_in_force = "gtc"
        cfg.post_only = bool(child.limit_gtc.post_only)
        cfg.limit_price = _price(child.limit_gtc.price_ticks, symbol=symbol)
    elif child.HasField("limit_ioc"):
        cfg.order_type = "limit"
        cfg.time_in_force = "ioc"
        cfg.limit_price = _price(child.limit_ioc.price_ticks, symbol=symbol)
    elif child.HasField("limit_fok"):
        cfg.order_type = "limit"
        cfg.time_in_force = "fok"
        cfg.limit_price = _price(child.limit_fok.price_ticks, symbol=symbol)


def _trigger_config(msg: triggers_pb2.Trigger) -> _TriggerConfig:
    """Derive the thick trigger projection from the configuration oneof."""
    symbol = msg.symbol or None
    cfg = _TriggerConfig()
    if has_field(msg, "stop_loss") or has_field(msg, "take_profit"):
        conditional = msg.stop_loss if has_field(msg, "stop_loss") else msg.take_profit
        cfg.trigger_type = "stop_loss" if has_field(msg, "stop_loss") else "take_profit"
        cfg.side = proto_enum_name(orders_pb2.Side, conditional.side)
        cfg.trigger_price = _price(conditional.trigger_price_ticks, symbol=symbol)
        if conditional.HasField("child"):
            _child_execution_projection(conditional.child, cfg, symbol=symbol)
    elif has_field(msg, "trailing_stop"):
        # Trailing stops are always SELL market-IOC executions.
        cfg.trigger_type = "trailing_stop"
        cfg.side = "sell"
        cfg.order_type = "market"
        cfg.time_in_force = "ioc"
    elif has_field(msg, "twap"):
        twap = msg.twap
        cfg.trigger_type = "twap"
        cfg.side = proto_enum_name(orders_pb2.Side, twap.side)
        if twap.HasField("limit_gtc"):
            cfg.order_type = "limit"
            cfg.time_in_force = "gtc"
            cfg.limit_price = _price(twap.limit_gtc.price_ticks, symbol=symbol)
        else:
            cfg.order_type = "market"
            cfg.time_in_force = "ioc"
    elif has_field(msg, "ladder"):
        ladder = msg.ladder
        cfg.trigger_type = "ladder"
        cfg.side = proto_enum_name(orders_pb2.Side, ladder.side)
        cfg.order_type = "limit"
        cfg.time_in_force = "gtc"
        cfg.post_only = bool(ladder.post_only)
    return cfg


def trigger_from_proto(msg: triggers_pb2.Trigger, *, quantity_scale: int | None = None) -> Trigger:
    details = _trigger_details(msg)
    cfg = _trigger_config(msg)
    trigger_price = cfg.trigger_price
    if trigger_price is None and details is not None and details.case == "stop" and details.stop:
        trigger_price = details.stop.trigger_price
    parent_order_id = ""
    if has_field(msg, "parent_order_id") and msg.parent_order_id:
        parent_order_id = format_uint64_id(msg.parent_order_id)
    return Trigger(
        trigger_id=format_uint64_id(msg.trigger_id),
        subaccount_id=format_uint64_id(msg.subaccount_id) if msg.subaccount_id else "",
        symbol_id=int(msg.symbol_id),
        symbol=msg.symbol,
        trigger_type=cfg.trigger_type,
        status=_trigger_status_label(msg.status),
        parent_order_id=parent_order_id,
        side=cfg.side,
        order_type=cfg.order_type,
        time_in_force=cfg.time_in_force,
        qty=Quantity.from_scaled(
            int(msg.qty_scaled),
            scale=quantity_scale,
            symbol=msg.symbol or None,
            symbol_id=int(msg.symbol_id),
        ),
        limit_price=cfg.limit_price,
        fee_source=proto_enum_name(orders_pb2.FeeSource, msg.fee_source),
        self_trade_prevention_mode=proto_enum_name(
            orders_pb2.SelfTradePreventionMode, msg.self_trade_prevention_mode
        ),
        post_only=cfg.post_only,
        trigger_price=trigger_price,
        client_trigger_id=msg.client_trigger_id,
        created_at=_timestamp(msg.created_at) if has_field(msg, "created_at") else None,
        updated_at=_timestamp(msg.updated_at) if has_field(msg, "updated_at") else None,
        armed_at=_timestamp(msg.armed_at) if has_field(msg, "armed_at") else None,
        completed_at=_timestamp(msg.completed_at) if has_field(msg, "completed_at") else None,
        child_order_ids=[format_uint64_id(i) for i in msg.child_order_ids],
        details=details,
    )


def triggers_list_from_proto(msg: triggers_pb2.ListTriggersResponse) -> TriggersList:
    triggers = [trigger_from_proto(item) for item in msg.triggers]
    return TriggersList(
        triggers=triggers,
        total=len(triggers),
        next_page_token=msg.next_page_token,
    )


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
    # CreateTriggerResponse no longer carries a status field (POLY-3701):
    # reaching the client means the trigger was admitted, so synthesize
    # "accepted". Cancel/Modify/Pause/Resume still return a status enum.
    if any(field.name == "status" for field in msg.DESCRIPTOR.fields):
        status = _trigger_status_label(msg.status)
    else:
        status = "accepted"
    return TriggerMutationResult(
        trigger_id=format_uint64_id(msg.trigger_id),
        status=status,
    )


def trigger_event_from_proto(msg: triggers_pb2.TriggerEvent) -> TriggerEvent:
    return TriggerEvent(
        trigger_id=format_uint64_id(msg.trigger_id),
        symbol_id=int(msg.symbol_id),
        trigger_type=proto_enum_name(triggers_pb2.TriggerType, msg.trigger_type),
        event_type=_trigger_event_type_label(msg.event_type),
        ts_ns=str(msg.ts_ns),
        fire_px=Price.from_ticks(int(msg.fire_price_ticks)) if msg.fire_price_ticks else None,
        reason=msg.reason,
    )


def trigger_events_list_from_proto(
    msg: triggers_pb2.ListTriggerEventsResponse,
) -> TriggerEventsList:
    return TriggerEventsList(
        events=[trigger_event_from_proto(item) for item in msg.events],
        next_page_token=msg.next_page_token,
    )
