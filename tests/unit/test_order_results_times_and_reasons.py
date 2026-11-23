"""Order write results keep what the contract returns: the resolved base
quantity of accepted batch items, the acceptance and response times of
create, batch create, modify and batch replace, and order end reasons read as
short lowercase labels."""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester
from polyester.codecs.decode.orders import (
    batch_create_from_proto,
    batch_replace_from_proto,
    modify_order_from_proto,
    order_from_proto,
    order_mutation_from_proto,
)
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.decode.triggers import trigger_event_from_proto, trigger_from_proto
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.codecs.wire_decode import decode_batch_replace_result
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.gen.triggers.v1 import triggers_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)
from tests.unit.support import btc_market, decode_btc_batch

TS_NS = 1_763_164_740_123_456_789
TS = Timestamp(seconds=1_763_164_740, nanos=987_654_321)
TS_AS_NS = 1_763_164_740_987_654_321


def _accepted(order_id: int, resolved: int) -> orders_pb2.BatchCreateResultItem:
    return orders_pb2.BatchCreateResultItem(
        accepted=orders_pb2.BatchCreateAccepted(
            order_id=order_id, resolved_base_qty_scaled=resolved
        )
    )


def _rejected() -> orders_pb2.BatchCreateResultItem:
    return orders_pb2.BatchCreateResultItem(
        rejected=orders_pb2.BatchCreateRejected(
            error=orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_POST_ONLY_CROSS)
        )
    )


@pytest_asyncio.fixture(loop_scope="function")
async def batch_client():
    async def handler(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/BatchCreateOrders"), req.path
        response = orders_pb2.BatchCreateOrdersResponse(
            results=[_accepted(11, 775_691), _accepted(12, 1_000_000), _rejected()],
            accepted_count=2,
            rejected_count=1,
            ts_ns=TS_NS,
        )
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
                {
                    "symbol": "ETH-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 6,
                    "quote_quantity_scale": 4,
                },
            ]
        }
    )
    try:
        yield client
    finally:
        await client.aclose()
        await http.aclose()


async def test_batch_create_accepted_items_carry_resolved_base_qty(batch_client) -> None:
    result = await batch_client.orders.batch_create(
        items=[
            dict(symbol_id=1, side="buy", order_type="market", max_quote_debit="500.00"),
            dict(symbol_id=2, side="buy", order_type="limit", price="100", qty="1"),
            dict(symbol_id=1, side="buy", order_type="limit", price="100", qty="0.01"),
        ]
    )
    first, second, rejected = result.results
    assert first.resolved_base_qty_scaled == "775691"
    assert first.resolved_base_qty is not None
    assert first.resolved_base_qty.scale == 8
    assert first.resolved_base_qty.as_decimal() == Decimal("0.00775691")
    assert second.resolved_base_qty_scaled == "1000000"
    assert second.resolved_base_qty is not None
    assert second.resolved_base_qty.scale == 6
    assert second.resolved_base_qty.format() == "1"
    assert rejected.status == "rejected"
    assert rejected.resolved_base_qty_scaled == ""
    assert rejected.resolved_base_qty is None
    assert result.ts_ns == TS_NS


def test_batch_create_resolved_base_qty_without_catalog_scales() -> None:
    result = batch_create_from_proto(
        orders_pb2.BatchCreateOrdersResponse(results=[_accepted(11, 776_079)], accepted_count=1),
        markets=[btc_market(None)],
    )
    item = result.results[0]
    assert item.resolved_base_qty_scaled == "776079"
    assert item.resolved_base_qty is not None
    assert item.resolved_base_qty.scaled == 776_079
    assert item.resolved_base_qty.scale is None


@pytest.mark.parametrize(
    ("fields", "want"),
    [
        ({"accepted_at_ts_ns": TS_NS, "accepted_at": TS}, TS_NS),
        ({"accepted_at": TS}, TS_AS_NS),
        ({}, None),
    ],
    ids=["ts_ns", "timestamp_fallback", "unset"],
)
def test_create_result_carries_acceptance_time(fields: dict, want: int | None) -> None:
    result = order_mutation_from_proto(
        orders_pb2.CreateOrderResponse(order_id=42, **fields), market=btc_market()
    )
    assert result.accepted_ts_ns == want


def test_cancel_result_has_no_acceptance_time() -> None:
    result = order_mutation_from_proto(
        orders_pb2.CancelOrderResponse(
            order_id=42, status=orders_pb2.CancelOrderResponse.ACCEPTED, ts_ns=TS_NS
        ),
        market=None,
    )
    assert result.accepted_ts_ns is None


@pytest.mark.parametrize(
    ("fields", "want"),
    [
        ({"ts_ns": TS_NS, "ts": TS}, TS_NS),
        ({"ts": TS}, TS_AS_NS),
        ({}, None),
    ],
    ids=["ts_ns", "timestamp_fallback", "unset"],
)
def test_batch_create_and_modify_results_carry_response_time(
    fields: dict, want: int | None
) -> None:
    batch = decode_btc_batch(
        orders_pb2.BatchCreateOrdersResponse(results=[_accepted(11, 1)], accepted_count=1, **fields)
    )
    assert batch.ts_ns == want
    modify = modify_order_from_proto(
        orders_pb2.ModifyOrderResponse(old_order_id=42, final_order_id=43, action_taken=2, **fields)
    )
    assert modify.ts_ns == want


@pytest.mark.parametrize(
    ("fields", "want"),
    [
        ({"accepted_ts_ns": TS_NS, "accepted_ts": TS}, TS_NS),
        ({"accepted_ts": TS}, TS_AS_NS),
        ({}, 0),
    ],
    ids=["ts_ns", "timestamp_fallback", "unset"],
)
def test_batch_replace_acceptance_time_falls_back_to_timestamp(fields: dict, want: int) -> None:
    result = batch_replace_from_proto(
        orders_pb2.BatchReplaceOrdersResponse(batch_request_id=7, status=1, **fields)
    )
    assert result.accepted_ts_ns == want


def test_order_reads_name_end_reasons_as_lowercase_labels() -> None:
    def read(**fields: object):
        return order_from_proto(orders_read_pb2.Order(order_id=7, symbol_id=1, **fields))  # type: ignore[arg-type]

    stp = read(
        status=orders_read_pb2.CANCELED, cancel_reason=orders_read_pb2.CANCEL_REASON_STP_DECREMENT
    )
    user = read(
        status=orders_read_pb2.CANCELED, cancel_reason=orders_read_pb2.CANCEL_REASON_USER_REQUEST
    )
    rejected = read(
        status=orders_read_pb2.REJECTED, reject_reason=orders_pb2.ERROR_CODE_PEG_LIMIT_VIOLATION
    )
    assert stp.cancel_reason == "stp_decrement"
    assert user.cancel_reason == "user_request"
    assert rejected.reject_reason == "peg_limit_violation"
    # A value newer than this SDK reads as before.
    assert read(status=orders_read_pb2.CANCELED, cancel_reason=999).cancel_reason == (
        "UNKNOWN_CANCEL_REASON(999)"
    )
    assert read(status=orders_read_pb2.REJECTED, reject_reason=9999).reject_reason == (
        "UNKNOWN_ERROR_CODE(9999)"
    )


def test_order_stream_names_reasons_as_lowercase_labels() -> None:
    unit = private_orders_unit_from_proto(
        pb.Unit(
            events=[
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=1,
                        kind=pb.OrderEvent.CANCELED,
                        cancel_reason=orders_read_pb2.CANCEL_REASON_STP_DECREMENT,
                    )
                ),
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=2,
                        kind=pb.OrderEvent.REJECTED,
                        reject_reason=orders_pb2.ERROR_CODE_PEG_LIMIT_VIOLATION,
                    )
                ),
                pb.UnitEvent(
                    outcome=pb.CommandOutcome(
                        kind=pb.CommandOutcome.AMEND_REJECTED,
                        order_id=3,
                        reason=orders_pb2.ERROR_CODE_INSUFFICIENT_FUNDS,
                    )
                ),
                pb.UnitEvent(
                    outcome=pb.CommandOutcome(
                        kind=pb.CommandOutcome.CANCEL_REJECTED, order_id=4, reason=9999
                    )
                ),
            ]
        )
    )
    canceled, rejected, outcome, unknown = unit.events
    assert canceled.cancel_reason == "stp_decrement"  # type: ignore[union-attr]
    assert rejected.reject_reason == "peg_limit_violation"  # type: ignore[union-attr]
    assert outcome.reason == "insufficient_funds"  # type: ignore[union-attr]
    assert unknown.reason == "UNKNOWN_ERROR_CODE(9999)"  # type: ignore[union-attr]


def test_trigger_reasons_already_read_as_lowercase_labels() -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=9, cancel_reason=triggers_pb2.TRIGGER_CANCEL_REASON_USER_REQUEST
        )
    )
    event = trigger_event_from_proto(
        triggers_pb2.TriggerEvent(
            trigger_id=9,
            failure_reason=triggers_pb2.TRIGGER_FAILURE_REASON_INSUFFICIENT_FUNDS,
        )
    )
    assert trigger.cancel_reason == "user_request"
    assert event.failure_reason == "insufficient_funds"


def test_batch_replace_duplicate_rejection_names_the_existing_order() -> None:
    response = orders_pb2.BatchReplaceOrdersResponse(
        batch_request_id=7,
        status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_REJECTED,
        rejected_count=1,
        results=[
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=0,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED,
                old_order_id=42,
                client_order_id="dup",
                code="CONFLICT_DUPLICATE_CLIENT_ORDER_ID",
                error=orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID,
                    existing_order_id=99,
                ),
            )
        ],
    )
    result = batch_replace_from_proto(response)
    assert result.results[0].existing_order_id == format_uint64_id(99)
    for preserving in (True, False):
        decoded = decode_batch_replace_result(
            MessageToDict(response, preserving_proto_field_name=preserving)
        )
        assert decoded.results[0].existing_order_id == format_uint64_id(99)
