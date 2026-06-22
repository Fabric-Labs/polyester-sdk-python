from polyester.codecs.decode.triggers import (
    get_trigger_from_proto,
    trigger_events_list_from_proto,
    trigger_from_proto,
    trigger_mutation_from_proto,
    triggers_list_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2


def test_trigger_from_proto_maps_stop_price() -> None:
    msg = triggers_pb2.Trigger(
        trigger_id=7,
        symbol_id=2,
        symbol="BTC-USD",
        trigger_type=triggers_pb2.STOP_LOSS,
        status=triggers_pb2.STATUS_ARMED,
        side=orders_pb2.SELL,
        qty_scaled=1_000_000,
        stop=triggers_pb2.StopDetails(trigger_price_ticks=50_000_000_000),
        client_trigger_id="ct-1",
    )
    trigger = trigger_from_proto(msg)
    assert trigger.trigger_id == format_id(7)
    assert trigger.trigger_type == "stop_loss"
    assert trigger.status == "armed"
    assert trigger.side == "sell"
    assert trigger.trigger_price_ticks == "50000000000"


def test_triggers_list_from_proto() -> None:
    msg = triggers_pb2.ListTriggersResponse(
        triggers=[triggers_pb2.Trigger(trigger_id=1, symbol_id=1)]
    )
    result = triggers_list_from_proto(msg)
    assert len(result.triggers) == 1
    assert result.total == 1


def test_get_trigger_from_proto() -> None:
    msg = triggers_pb2.GetTriggerResponse(
        trigger=triggers_pb2.Trigger(trigger_id=3, symbol_id=1)
    )
    trigger = get_trigger_from_proto(msg)
    assert trigger is not None
    assert trigger.trigger_id == format_id(3)


def test_trigger_mutation_from_proto() -> None:
    msg = triggers_pb2.CreateTriggerResponse(
        trigger_id=9,
        status=triggers_pb2.STATUS_CREATED,
    )
    result = trigger_mutation_from_proto(msg)
    assert result.trigger_id == format_id(9)
    assert result.status == "created"


def test_trigger_events_list_from_proto() -> None:
    msg = triggers_pb2.ListTriggerEventsResponse(
        events=[
            triggers_pb2.TriggerEvent(
                trigger_id=1,
                symbol_id=2,
                trigger_type=triggers_pb2.TAKE_PROFIT,
                event_type=triggers_pb2.EVENT_FIRED,
                ts_ns=123,
                fire_price_ticks=100,
                reason="hit",
            )
        ],
        next_page_token="456",
    )
    result = trigger_events_list_from_proto(msg)
    assert len(result.events) == 1
    assert result.events[0].event_type == "fired"
    assert result.next_before_ts_ns == "456"
