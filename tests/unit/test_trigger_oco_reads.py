"""Triggers read back the OCO they belong to: ``order_list_id`` and ``client_list_id``.

Both legs of an OCO carry the OCO's ID and its client list ID, and have no
parent order. Every other trigger reads both as empty. The fields are checked
on the unary reads (binary and JSON wire), on the trigger stream decoders and
on the JSON-dict decoder.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.realtime_decode import decode_trigger_bytes
from polyester.codecs.scalars import format_id
from polyester.codecs.wire_decode import decode_trigger
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.trading import Trigger
from polyester.services.triggers import AsyncTriggersService
from tests.unit.test_trigger_read_caps_and_symbol import _catalogs, _reads, _stop

LIST_ID = (1 << 63) + 5  # above the int64 range: kept exact as a public ID
CLIENT_LIST_ID = "ordre-été-1"


def _leg(kind: str = "take_profit") -> triggers_pb2.Trigger:
    leg = _stop(kind)
    leg.order_list_id = LIST_ID
    leg.client_list_id = CLIENT_LIST_ID
    return leg


def _assert_leg(trigger: Trigger | None) -> None:
    assert trigger is not None
    assert trigger.order_list_id == format_id(LIST_ID)
    assert trigger.client_list_id == CLIENT_LIST_ID
    assert trigger.parent_order_id == ""


def _assert_not_a_leg(trigger: Trigger | None) -> None:
    assert trigger is not None
    assert trigger.order_list_id == ""
    assert trigger.client_list_id == ""


@pytest.mark.parametrize("kind", ["take_profit", "stop_loss"])
def test_trigger_from_proto_reads_the_oco(kind: str) -> None:
    _assert_leg(trigger_from_proto(_leg(kind)))


def test_a_trigger_of_no_oco_reads_both_empty() -> None:
    plain = _stop("stop_loss")
    assert not plain.HasField("order_list_id")
    _assert_not_a_leg(trigger_from_proto(plain))
    # An explicit 0 is the contract's "none", never the public ID of 0.
    plain.order_list_id = 0
    assert plain.HasField("order_list_id")
    _assert_not_a_leg(trigger_from_proto(plain))


def test_the_oco_fields_are_left_out_of_serialization_when_empty() -> None:
    import msgspec

    encoded = msgspec.json.decode(msgspec.json.encode(trigger_from_proto(_stop("stop_loss"))))
    assert "order_list_id" not in encoded and "client_list_id" not in encoded
    encoded = msgspec.json.decode(msgspec.json.encode(trigger_from_proto(_leg())))
    assert encoded["order_list_id"] == format_id(LIST_ID)
    assert encoded["client_list_id"] == CLIENT_LIST_ID


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
async def test_get_and_list_read_the_oco(json_wire: bool) -> None:
    for trigger in await _reads(_leg(), json_wire=json_wire, catalogs=True):
        _assert_leg(trigger)
    for trigger in await _reads(_stop("stop_loss"), json_wire=json_wire, catalogs=True):
        _assert_not_a_leg(trigger)


def test_trigger_stream_reads_the_oco() -> None:
    payload = _leg("stop_loss").SerializeToString()
    _assert_leg(decode_trigger_bytes(payload))
    # The decoder triggers.subscribe uses, with the pair's catalog scales.
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    _assert_leg(service._decode_trigger(payload))
    _assert_not_a_leg(service._decode_trigger(_stop("stop_loss").SerializeToString()))


def test_json_dict_decoder_reads_the_oco() -> None:
    leg = decode_trigger(
        {
            "triggerId": format_id(23),
            "orderListId": format_id(LIST_ID),
            "clientListId": CLIENT_LIST_ID,
        }
    )
    _assert_leg(leg)
    _assert_not_a_leg(decode_trigger({"triggerId": format_id(23)}))
