"""Attached exits never trade with the order they protect.

An exit that fires while its parent still rests cancels the parent's rest
first (``ATTACHED_EXIT_FIRED``); self-trade prevention that expires an exit's
order is a ``fire_refused`` event (``self_trade_prevented``) whose
``child_seq`` names that order, and the trigger stays live. Orders carry the
self-trade prevention mode their attached exits use.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester import is_terminal_trigger_event
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.decode.triggers import get_trigger_from_proto, trigger_event_from_proto
from polyester.codecs.orders import (
    batch_create_orders_to_proto,
    normalize_create_order_request,
    order_intent_from_request,
)
from polyester.codecs.realtime_decode import decode_trigger_event_batch_bytes
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary


def test_wire_numbers_match_the_published_contract() -> None:
    assert orders_read_pb2.CANCEL_REASON_ATTACHED_EXIT_FIRED == 18
    assert orders_pb2.ERROR_CODE_SELF_TRADE_PREVENTED == 307
    assert triggers_pb2.TRIGGER_FAILURE_REASON_SELF_TRADE_PREVENTED == 249


def test_order_read_and_stream_label_the_attached_exit_cancel() -> None:
    ended = orders_read_pb2.Order(
        order_id=7,
        symbol_id=1,
        status=orders_read_pb2.CANCELED,
        cancel_reason=orders_read_pb2.CANCEL_REASON_ATTACHED_EXIT_FIRED,
    )
    assert order_from_proto(ended).cancel_reason == "ATTACHED_EXIT_FIRED"

    unit = private_orders_unit_from_proto(
        pb.Unit(
            orders=[ended],
            events=[
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=7,
                        kind=pb.OrderEvent.CANCELED,
                        cancel_reason=orders_read_pb2.CANCEL_REASON_ATTACHED_EXIT_FIRED,
                    )
                )
            ],
        )
    )
    assert unit.orders[0].cancel_reason == "ATTACHED_EXIT_FIRED"
    assert unit.events[0].cancel_reason == "ATTACHED_EXIT_FIRED"


def test_unknown_cancel_reason_decodes_to_a_generic_label() -> None:
    newer = orders_read_pb2.Order(order_id=7, symbol_id=1, status=orders_read_pb2.CANCELED)
    newer.cancel_reason = 321  # type: ignore[assignment]
    assert order_from_proto(newer).cancel_reason == "UNKNOWN_CANCEL_REASON(321)"


def _stp_refusal(child_order_id: int = 0) -> triggers_pb2.TriggerEvent:
    return triggers_pb2.TriggerEvent(
        trigger_id=9,
        symbol_id=1,
        event_type=triggers_pb2.EVENT_FIRE_REFUSED,
        child_seq=2,
        child_order_id=child_order_id,
        fire_price_ticks=104_000_000_000,
        fire_refusal_reason=triggers_pb2.TRIGGER_FAILURE_REASON_SELF_TRADE_PREVENTED,
    )


def test_self_trade_prevented_is_a_fire_refusal_naming_the_expired_child() -> None:
    event = trigger_event_from_proto(_stp_refusal(child_order_id=55))
    assert event.event_type == "fire_refused"
    assert event.fire_refusal_reason == "self_trade_prevented"
    assert event.failure_reason == ""
    assert event.child_seq == 2
    # Self-trade prevention expired a placed order: the event names it.
    assert event.child_order_id != ""
    assert not is_terminal_trigger_event(event.event_type)

    [streamed] = decode_trigger_event_batch_bytes(
        triggers_pb2.TriggerEventBatch(events=[_stp_refusal()]).SerializeToString()
    )
    assert streamed.fire_refusal_reason == "self_trade_prevented"


def test_unknown_fire_refusal_reason_decodes_without_failing() -> None:
    event = _stp_refusal()
    event.fire_refusal_reason = 321  # type: ignore[assignment]
    assert trigger_event_from_proto(event).fire_refusal_reason == "321"


def test_halted_market_refusal_reads_market_halted() -> None:
    failed = triggers_pb2.Trigger(
        trigger_id=9,
        symbol_id=1,
        status=triggers_pb2.STATUS_FAILED,
        failure_reason=triggers_pb2.TRIGGER_FAILURE_REASON_MARKET_HALTED,
    )
    read = get_trigger_from_proto(triggers_pb2.GetTriggerResponse(trigger=failed))
    assert read is not None
    assert (read.status, read.failure_reason) == ("failed", "market_halted")

    refused = _stp_refusal()
    refused.fire_refusal_reason = triggers_pb2.TRIGGER_FAILURE_REASON_MARKET_HALTED
    assert trigger_event_from_proto(refused).fire_refusal_reason == "market_halted"


# --- self-trade prevention mode on order create and read --------------------


def _limit_with_exits(**extra: object):
    return normalize_create_order_request(
        symbol="BTC-USDT",
        symbol_id=1,
        side="buy",
        order_type="limit",
        tif="gtc",
        post_only=True,
        qty="0.001",
        price="10000",
        attached_risk={"take_profit": {"trigger_price": "12000"}},
        **extra,
    )


@pytest.mark.parametrize(
    ("label", "wire"),
    [
        ("expire_taker", orders_pb2.EXPIRE_TAKER),
        ("expire_maker", orders_pb2.EXPIRE_MAKER),
        ("EXPIRE_BOTH", orders_pb2.EXPIRE_BOTH),
    ],
)
def test_create_sends_self_trade_prevention_mode(label: str, wire: int) -> None:
    intent = order_intent_from_request(
        _limit_with_exits(self_trade_prevention_mode=label), quantity_scale=8
    )
    assert intent.self_trade_prevention_mode == wire


def test_create_without_mode_leaves_the_server_default() -> None:
    intent = order_intent_from_request(_limit_with_exits(), quantity_scale=8)
    assert intent.self_trade_prevention_mode == orders_pb2.SELF_TRADE_PREVENTION_MODE_UNSPECIFIED


def test_create_rejects_an_unknown_self_trade_prevention_mode() -> None:
    with pytest.raises(PolyesterValidationError, match="self_trade_prevention_mode"):
        order_intent_from_request(
            _limit_with_exits(self_trade_prevention_mode="cancel_newest"), quantity_scale=8
        )


def test_batch_create_sends_each_item_mode() -> None:
    proto = batch_create_orders_to_proto(
        items=[
            {
                "symbol": "BTC-USDT",
                "symbol_id": 1,
                "side": "buy",
                "order_type": "limit",
                "qty": "0.001",
                "price": "10000",
                "self_trade_prevention_mode": "expire_both",
            },
            {
                "symbol": "BTC-USDT",
                "symbol_id": 1,
                "side": "buy",
                "order_type": "limit",
                "qty": "0.001",
                "price": "10000",
            },
        ],
        quantity_scale=8,
    )
    assert [item.self_trade_prevention_mode for item in proto.items] == [
        orders_pb2.EXPIRE_BOTH,
        orders_pb2.SELF_TRADE_PREVENTION_MODE_UNSPECIFIED,
    ]


@pytest.mark.asyncio
async def test_orders_create_sends_the_mode() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), catalogs, None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            qty="0.001",
            price="10000",
            post_only=True,
            self_trade_prevention_mode="expire_taker",
            attached_risk={"stop_loss": {"trigger_price": "9000"}},
        )
    assert isinstance(capture.request, orders_pb2.CreateOrderRequest)
    assert capture.request.order.self_trade_prevention_mode == orders_pb2.EXPIRE_TAKER


def test_order_read_carries_the_self_trade_prevention_mode() -> None:
    read = orders_read_pb2.Order(
        order_id=7, symbol_id=1, self_trade_prevention_mode=orders_pb2.EXPIRE_TAKER
    )
    assert order_from_proto(read).self_trade_prevention_mode == "expire_taker"
    assert order_from_proto(orders_read_pb2.Order(order_id=7)).self_trade_prevention_mode == ""

    newer = orders_read_pb2.Order(order_id=7, symbol_id=1)
    newer.self_trade_prevention_mode = 9  # type: ignore[assignment]
    assert order_from_proto(newer).self_trade_prevention_mode == "9"
