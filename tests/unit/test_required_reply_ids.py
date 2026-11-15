"""A reply that must name what it created or changed refuses ID 0.

0 is the proto default of an absent field: the reply is refused with
``PolyesterResponseContractError`` instead of reporting the ID ``"0"``, and
the same reply with a real ID decodes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from polyester.codecs.decode.address_book import (
    entry_from_create_proto,
    entry_from_update_proto,
    tag_from_create_proto,
    tag_from_update_proto,
)
from polyester.codecs.decode.orders import batch_create_from_proto, cancel_all_from_proto
from polyester.codecs.decode.triggers import (
    batch_cancel_triggers_from_proto,
    cancel_oco_from_proto,
    create_oco_from_proto,
    trigger_mutation_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
from polyester.gen.auth.v1 import address_book_pb2 as ab
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.gen.triggers.v1 import triggers_pb2 as triggers

ARMED = triggers.TriggerStatus.STATUS_ARMED


def _batch_create(order_id: int) -> orders.BatchCreateOrdersResponse:
    return orders.BatchCreateOrdersResponse(
        results=[
            orders.BatchCreateResultItem(
                client_order_id="c1", accepted=orders.BatchCreateAccepted(order_id=order_id)
            )
        ],
        accepted_count=1,
    )


def _cancel_all_reply(order_id: int) -> orders.CancelAllOrdersResponse:
    return orders.CancelAllOrdersResponse(
        status=orders.CancelAllOrdersResponse.SUBMITTED,
        matched_orders=1,
        submitted_cancels=1,
        total_cancelled=1,
        cancelled_orders=[orders.CancelledOrder(order_id=order_id, client_order_id="c1")],
    )


def _batch_cancel_triggers(trigger_id: int) -> triggers.BatchCancelTriggersResponse:
    return triggers.BatchCancelTriggersResponse(
        results=[
            triggers.BatchCancelTriggersResultItem(
                status=triggers.BatchCancelTriggersResultItem.ACCEPTED, trigger_id=trigger_id
            )
        ],
        accepted_count=1,
    )


def _create_oco(order_list_id: int, tp: int, sl: int) -> triggers.CreateOcoResponse:
    return triggers.CreateOcoResponse(
        order_list_id=order_list_id,
        client_list_id="oco-1",
        take_profit_trigger_id=tp,
        stop_loss_trigger_id=sl,
    )


ZERO_REPLIES: dict[str, Callable[[], Any]] = {
    "CreateTrigger": lambda: trigger_mutation_from_proto(triggers.CreateTriggerResponse()),
    "CancelTrigger": lambda: trigger_mutation_from_proto(
        triggers.CancelTriggerResponse(status=ARMED)
    ),
    "PauseTrigger": lambda: trigger_mutation_from_proto(
        triggers.PauseTriggerResponse(status=ARMED)
    ),
    "ResumeTrigger": lambda: trigger_mutation_from_proto(
        triggers.ResumeTriggerResponse(status=ARMED)
    ),
    "ModifyTrigger": lambda: trigger_mutation_from_proto(
        triggers.ModifyTriggerResponse(status=ARMED)
    ),
    "CreateOco order_list_id": lambda: create_oco_from_proto(_create_oco(0, 2, 3)),
    "CreateOco take_profit_trigger_id": lambda: create_oco_from_proto(_create_oco(1, 0, 3)),
    "CreateOco stop_loss_trigger_id": lambda: create_oco_from_proto(_create_oco(1, 2, 0)),
    "CancelOco": lambda: cancel_oco_from_proto(triggers.CancelOcoResponse()),
    "BatchCancelTriggers item": lambda: batch_cancel_triggers_from_proto(_batch_cancel_triggers(0)),
    "BatchCreateOrders accepted item": lambda: batch_create_from_proto(_batch_create(0)),
    "CancelAllOrders cancelled order": lambda: cancel_all_from_proto(_cancel_all_reply(0)),
    "CreateAddressBookEntry": lambda: entry_from_create_proto(
        ab.CreateAddressBookEntryResponse(entry=ab.AddressBookEntry())
    ),
    "UpdateAddressBookEntry": lambda: entry_from_update_proto(
        ab.UpdateAddressBookEntryResponse(entry=ab.AddressBookEntry())
    ),
    "CreateAddressBookTag": lambda: tag_from_create_proto(
        ab.CreateAddressBookTagResponse(tag=ab.AddressBookTag())
    ),
    "UpdateAddressBookTag": lambda: tag_from_update_proto(
        ab.UpdateAddressBookTagResponse(tag=ab.AddressBookTag())
    ),
}


@pytest.mark.parametrize("name", sorted(ZERO_REPLIES))
def test_reply_with_zero_required_id_is_refused(name: str) -> None:
    with pytest.raises(PolyesterResponseContractError):
        ZERO_REPLIES[name]()


def test_reply_with_real_required_id_decodes() -> None:
    created = trigger_mutation_from_proto(triggers.CreateTriggerResponse(trigger_id=7))
    assert (created.trigger_id, created.status) == (format_id(7), "accepted")
    canceled = trigger_mutation_from_proto(
        triggers.CancelTriggerResponse(trigger_id=7, status=triggers.TriggerStatus.STATUS_CANCELED)
    )
    assert canceled.trigger_id == format_id(7)
    assert create_oco_from_proto(_create_oco(1, 2, 3)).order_list_id == format_id(1)
    assert cancel_oco_from_proto(triggers.CancelOcoResponse(order_list_id=1)).order_list_id == (
        format_id(1)
    )
    assert batch_cancel_triggers_from_proto(_batch_cancel_triggers(7)).results[0].trigger_id == (
        format_id(7)
    )
    assert batch_create_from_proto(_batch_create(9)).results[0].order_id == format_id(9)
    assert cancel_all_from_proto(_cancel_all_reply(9)).cancelled_orders[0].order_id == format_id(9)
    entry = entry_from_create_proto(
        ab.CreateAddressBookEntryResponse(entry=ab.AddressBookEntry(address_book_entry_id=4))
    )
    assert entry.address_book_entry_id == format_id(4)
    tag = tag_from_create_proto(ab.CreateAddressBookTagResponse(tag=ab.AddressBookTag(tag_id=5)))
    assert tag.tag_id == format_id(5)
