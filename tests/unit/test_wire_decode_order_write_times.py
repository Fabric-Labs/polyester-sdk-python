"""The JSON order-write decoders keep the server's times as the protobuf path does.

``decode_order_mutation``, ``decode_modify_order_result`` and
``decode_batch_replace_result`` read the exact ``*_ts_ns`` field first, then its
paired timestamp, from proto-JSON and snake_case keys alike, and give the same
value as the protobuf decoders for the same response.
"""

from __future__ import annotations

import pytest
from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.orders import (
    batch_replace_from_proto,
    modify_order_from_proto,
    order_mutation_from_proto,
)
from polyester.codecs.wire_decode import (
    decode_batch_replace_result,
    decode_modify_order_result,
    decode_order_mutation,
)
from polyester.errors import PolyesterResponseContractError
from polyester.gen.orders.v1 import orders_pb2

EXACT_TS_NS = 1_763_164_740_123_456_789
TIMESTAMP = Timestamp(seconds=1_763_164_740, nanos=987_654_321)
TIMESTAMP_NS = 1_763_164_740_987_654_321

KEY_STYLES = pytest.mark.parametrize("snake_case", [False, True], ids=["camelCase", "snake_case"])


def _json(msg, snake_case: bool) -> dict:
    return MessageToDict(msg, preserving_proto_field_name=snake_case)


def _create(**fields) -> orders_pb2.CreateOrderResponse:
    return orders_pb2.CreateOrderResponse(order_id=42, client_order_id="c-1", **fields)


def _modify(**fields) -> orders_pb2.ModifyOrderResponse:
    return orders_pb2.ModifyOrderResponse(
        action_taken=orders_pb2.AMENDED, old_order_id=42, final_order_id=42, **fields
    )


def _replace(**fields) -> orders_pb2.BatchReplaceOrdersResponse:
    return orders_pb2.BatchReplaceOrdersResponse(
        batch_request_id=9, status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED, **fields
    )


@KEY_STYLES
@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"accepted_at_ts_ns": EXACT_TS_NS, "accepted_at": TIMESTAMP}, EXACT_TS_NS),
        ({"accepted_at": TIMESTAMP}, TIMESTAMP_NS),
        ({}, None),
    ],
    ids=["ts_ns", "timestamp_fallback", "unset"],
)
def test_json_create_result_keeps_acceptance_time(snake_case, fields, expected) -> None:
    msg = _create(**fields)
    assert order_mutation_from_proto(msg).accepted_ts_ns == expected
    assert decode_order_mutation(_json(msg, snake_case)).accepted_ts_ns == expected


@KEY_STYLES
@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"ts_ns": EXACT_TS_NS, "ts": TIMESTAMP}, EXACT_TS_NS),
        ({"ts": TIMESTAMP}, TIMESTAMP_NS),
        ({}, None),
    ],
    ids=["ts_ns", "timestamp_fallback", "unset"],
)
def test_json_modify_result_keeps_response_time(snake_case, fields, expected) -> None:
    msg = _modify(**fields)
    assert modify_order_from_proto(msg).ts_ns == expected
    assert decode_modify_order_result(_json(msg, snake_case)).ts_ns == expected


@KEY_STYLES
@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"accepted_ts_ns": EXACT_TS_NS, "accepted_ts": TIMESTAMP}, EXACT_TS_NS),
        ({"accepted_ts": TIMESTAMP}, TIMESTAMP_NS),
        ({}, 0),
    ],
    ids=["ts_ns", "timestamp_fallback", "unset"],
)
def test_json_batch_replace_keeps_acceptance_time(snake_case, fields, expected) -> None:
    msg = _replace(**fields)
    assert batch_replace_from_proto(msg).accepted_ts_ns == expected
    assert decode_batch_replace_result(_json(msg, snake_case)).accepted_ts_ns == expected


def test_json_cancel_result_has_no_acceptance_time() -> None:
    cancel = {"status": "accepted", "orderId": "1", "tsNs": "5"}
    assert decode_order_mutation(cancel).accepted_ts_ns is None


def test_json_timestamp_as_seconds_and_nanos_object() -> None:
    data = {"orderId": "1", "acceptedAt": {"seconds": "1763164740", "nanos": 987654321}}
    assert decode_order_mutation(data).accepted_ts_ns == TIMESTAMP_NS


@pytest.mark.parametrize("bad", ["not-a-time", {"seconds": "x"}, 7])
def test_json_malformed_timestamp_is_a_contract_error(bad) -> None:
    with pytest.raises(PolyesterResponseContractError):
        decode_modify_order_result({"actionTaken": "amended", "ts": bad})
