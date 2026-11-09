"""POLY-8998: the public JSON batch-replace decoder keeps item rejection details.

``decode_batch_replace_result`` decodes each item's field violations (and
the rate-limit detail and action taken beside them) as the protobuf path
does, from proto-JSON and snake_case keys alike.
"""

from __future__ import annotations

import pytest
from google.protobuf.json_format import MessageToDict

from polyester.codecs.decode.orders import batch_replace_from_proto
from polyester.codecs.wire_decode import decode_batch_replace_result
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.models import OrderFieldViolation

TICK = orders_pb2.FieldViolation(
    field_path="order.limit_gtc.price_ticks",
    rule_id="tick_size",
    message="Price must be a multiple of the tick size.",
)
QTY = orders_pb2.FieldViolation(
    field_path="order.base_qty_scaled", rule_id="minimum", message="Quantity is below the minimum."
)


def _response() -> orders_pb2.BatchReplaceOrdersResponse:
    return orders_pb2.BatchReplaceOrdersResponse(
        batch_request_id=9,
        status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED,
        results=[
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=0,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                old_order_id=42,
                replacement_order_id=43,
                action_taken=orders_pb2.REPLACED,
            ),
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=1,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED,
                old_order_id=44,
                code="PRICE_TICK_SIZE",
                error=orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_PRICE_TICK_SIZE, violations=[TICK, QTY]
                ),
            ),
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=2,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED,
                old_order_id=45,
                code="RESOURCE_EXHAUSTED",
                error=orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                    rate_limit=ratelimit_pb2.RateLimitDetail(
                        limit=10, remaining=0, retry_after_ms=250
                    ),
                ),
            ),
        ],
        accepted_count=1,
        rejected_count=2,
    )


@pytest.mark.parametrize("names", ["json", "proto"])
def test_json_decoder_keeps_each_items_violations_as_the_protobuf_path_does(names: str) -> None:
    response = _response()
    payload = MessageToDict(response, preserving_proto_field_name=names == "proto")
    decoded = decode_batch_replace_result(payload)
    expected = batch_replace_from_proto(response)

    assert [item.violations for item in decoded.results] == [
        [],
        [
            OrderFieldViolation(
                field_path=TICK.field_path, rule_id=TICK.rule_id, message=TICK.message
            ),
            OrderFieldViolation(
                field_path=QTY.field_path, rule_id=QTY.rule_id, message=QTY.message
            ),
        ],
        [],
    ]
    for got, want in zip(decoded.results, expected.results, strict=True):
        assert got.violations == want.violations
        assert got.rate_limit == want.rate_limit
        assert got.action_taken == want.action_taken
        assert got.code == want.code
