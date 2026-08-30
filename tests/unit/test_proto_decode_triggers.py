import pytest

from polyester.codecs.decode.triggers import (
    get_trigger_from_proto,
    trigger_events_list_from_proto,
    trigger_from_proto,
    trigger_mutation_from_proto,
    triggers_list_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2


def test_trigger_from_proto_maps_stop_price() -> None:
    msg = triggers_pb2.Trigger(
        trigger_id=7,
        symbol_id=2,
        status=triggers_pb2.STATUS_ARMED,
        qty_scaled=1_000_000,
        # Configuration oneof drives the thick type/side/execution projection.
        stop_loss=triggers_pb2.ConditionalTrigger(
            trigger_price_ticks=50_000_000_000,
            side=orders_pb2.SELL,
            child=triggers_pb2.ConditionalChildExecution(
                limit_gtc=triggers_pb2.TriggerLimitGtc(price_ticks=49_900_000_000, post_only=True)
            ),
        ),
        # Runtime details drive the discriminated details payload.
        stop=triggers_pb2.StopDetails(trigger_price_ticks=50_000_000_000),
        client_trigger_id="ct-1",
    )
    trigger = trigger_from_proto(msg)
    assert trigger.trigger_id == format_id(7)
    assert trigger.trigger_type == "stop_loss"
    assert trigger.status == "armed"
    assert trigger.side == "sell"
    assert trigger.order_type == "limit"
    assert trigger.time_in_force == "gtc"
    assert trigger.post_only is True
    assert trigger.limit_price is not None and trigger.limit_price.ticks == 49_900_000_000
    assert trigger.trigger_price is not None and trigger.trigger_price.ticks == 50_000_000_000
    assert trigger.details is not None and trigger.details.case == "stop"


def test_trigger_from_proto_attached_trailing_surfaces_side_and_parent() -> None:
    msg = triggers_pb2.Trigger(
        trigger_id=42,
        symbol_id=2,
        status=triggers_pb2.STATUS_ARMED,
        parent_order_id=99,
        qty_scaled=1_000_000,
        trailing_stop=triggers_pb2.TrailingStopTrigger(
            side=orders_pb2.BUY,
            trailing_distance_bps=50,
        ),
        trailing=triggers_pb2.TrailingDetails(trailing_distance_bps=50),
    )
    trigger = trigger_from_proto(msg)
    assert trigger.trigger_type == "trailing_stop"
    assert trigger.side == "buy"
    assert trigger.parent_order_id == format_id(99)
    assert trigger.order_type == "market"
    assert trigger.time_in_force == "ioc"
    assert trigger.details is not None and trigger.details.case == "trailing"


def test_trigger_from_proto_projects_twap_executed_qty() -> None:
    msg = triggers_pb2.Trigger(
        trigger_id=11,
        symbol_id=1,
        status=triggers_pb2.STATUS_RUNNING,
        qty_scaled=100_000_000,
        twap=triggers_pb2.TwapTrigger(
            side=orders_pb2.BUY,
            duration_ms=60_000,
            slice_interval_ms=5_000,
            market_ioc=triggers_pb2.TwapMarketIoc(),
        ),
        twap_state=triggers_pb2.TwapDetails(
            twap_duration_ms=60_000,
            twap_slice_interval_ms=5_000,
            slice_idx=2,
            slice_count=12,
            executed_qty_scaled=25_000_000,
        ),
        client_trigger_id="twap-1",
    )
    trigger = trigger_from_proto(msg)
    assert trigger.trigger_type == "twap"
    assert trigger.side == "buy"
    assert trigger.order_type == "market"
    assert trigger.details is not None and trigger.details.case == "twap"
    assert trigger.details.twap is not None
    assert trigger.details.twap.slice_idx == 2
    assert trigger.details.twap.slice_count == 12
    assert trigger.details.twap.executed_qty is not None
    assert trigger.details.twap.executed_qty.scaled == 25_000_000


def test_trigger_status_from_label() -> None:
    from polyester.codecs.decode.triggers import trigger_status_from_label

    assert trigger_status_from_label("armed") == triggers_pb2.STATUS_ARMED
    assert trigger_status_from_label("cancelled") == triggers_pb2.STATUS_CANCELED
    with pytest.raises(PolyesterValidationError):
        trigger_status_from_label("nope")


def test_triggers_list_from_proto() -> None:
    msg = triggers_pb2.ListTriggersResponse(
        triggers=[triggers_pb2.Trigger(trigger_id=1, symbol_id=1)],
        next_page_token="trig-page-2",
    )
    result = triggers_list_from_proto(msg)
    assert len(result.triggers) == 1
    assert result.total == 1
    assert result.next_page_token == "trig-page-2"


def test_get_trigger_from_proto() -> None:
    msg = triggers_pb2.GetTriggerResponse(trigger=triggers_pb2.Trigger(trigger_id=3, symbol_id=1))
    trigger = get_trigger_from_proto(msg)
    assert trigger is not None
    assert trigger.trigger_id == format_id(3)


def test_trigger_mutation_from_proto() -> None:
    # CreateTriggerResponse no longer carries a status field; decode synthesizes
    # "accepted" (POLY-3701).
    msg = triggers_pb2.CreateTriggerResponse(trigger_id=9)
    result = trigger_mutation_from_proto(msg)
    assert result.trigger_id == format_id(9)
    assert result.status == "accepted"


def test_trigger_status_cancelled_matches_typescript() -> None:
    msg = triggers_pb2.CancelTriggerResponse(
        trigger_id=9,
        status=triggers_pb2.STATUS_CANCELED,
    )
    result = trigger_mutation_from_proto(msg)
    assert result.status == "cancelled"


def test_trigger_events_list_from_proto() -> None:
    msg = triggers_pb2.ListTriggerEventsResponse(
        events=[
            triggers_pb2.TriggerEvent(
                trigger_id=1,
                subaccount_id=9,
                symbol_id=2,
                trigger_type=triggers_pb2.TAKE_PROFIT,
                event_type=triggers_pb2.EVENT_FIRED,
                ts_ns=123,
                child_seq=3,
                child_order_id=77,
                fire_price_ticks=100,
            )
        ],
        next_page_token="evt-page-2",
    )
    result = trigger_events_list_from_proto(msg)
    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_type == "fired"
    assert event.trigger_type == "take_profit"
    assert event.subaccount_id == format_id(9)
    assert event.child_seq == 3
    assert event.child_order_id == format_id(77)
    assert event.fire_price is not None and event.fire_price.ticks == 100
    assert event.cancel_reason == ""
    assert event.failure_reason == ""
    assert result.next_page_token == "evt-page-2"


def test_trigger_event_absent_fire_price() -> None:
    msg = triggers_pb2.ListTriggerEventsResponse(
        events=[
            triggers_pb2.TriggerEvent(
                trigger_id=1,
                trigger_type=triggers_pb2.TWAP,
                event_type=triggers_pb2.EVENT_FIRED,
                child_seq=1,
            )
        ]
    )
    result = trigger_events_list_from_proto(msg)
    assert len(result.events) == 1
    assert result.events[0].fire_price is None


def test_trigger_event_terminal_reasons() -> None:
    canceled = trigger_events_list_from_proto(
        triggers_pb2.ListTriggerEventsResponse(
            events=[
                triggers_pb2.TriggerEvent(
                    trigger_id=1,
                    event_type=triggers_pb2.EVENT_CANCELED,
                    cancel_reason=triggers_pb2.TRIGGER_CANCEL_REASON_USER_REQUEST,
                )
            ]
        )
    ).events[0]
    assert canceled.cancel_reason == "user_request"
    assert canceled.failure_reason == ""

    failed = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=2,
            symbol_id=1,
            status=triggers_pb2.STATUS_FAILED,
            failure_reason=triggers_pb2.TRIGGER_FAILURE_REASON_INSUFFICIENT_FUNDS,
        )
    )
    assert failed.failure_reason == "insufficient_funds"
    assert failed.cancel_reason == ""


def test_trigger_event_type_from_label() -> None:
    from polyester.codecs.decode.triggers import trigger_event_type_from_label

    assert trigger_event_type_from_label("fired") == triggers_pb2.EVENT_FIRED
    assert trigger_event_type_from_label("canceled") == triggers_pb2.EVENT_CANCELED
    with pytest.raises(PolyesterValidationError):
        trigger_event_type_from_label("nope")
