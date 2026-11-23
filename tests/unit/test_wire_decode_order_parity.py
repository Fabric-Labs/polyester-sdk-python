"""Order reads and order write results decode the same from JSON as from protobuf.

Each response below is decoded twice: from the generated message by the
protobuf decoder, and from its protobuf JSON (``MessageToDict``, camelCase and
snake_case alike) by the ``wire_decode`` helper. Both must give equal results,
so a field one path reads and the other drops fails here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs import wire_decode
from polyester.codecs.decode import orders as proto_decode
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from tests.unit.support import btc_market

TS = Timestamp(seconds=1_763_164_740, nanos=987_654_321)
TS_NS = 1_763_164_740_123_456_789
SCALES = {1: (8, 6), 2: (5, 4)}


def _scales(symbol_id: int) -> tuple[int | None, int | None]:
    return SCALES.get(symbol_id, (None, None))


def _u128(value: int) -> dict[str, Any]:
    return {"hi": str(value >> 64), "lo": str(value & (2**64 - 1))}


def _order(**overrides: Any) -> orders_read_pb2.Order:
    fields: dict[str, Any] = {
        "orderId": "4611686018427387911",
        "symbolId": 1,
        "clientOrderId": "cid-1",
        "side": "BUY",
        "status": "CANCELED",
        "orderType": "LIMIT",
        "timeInForce": "GTC",
        "selfTradePreventionMode": "DECREMENT",
        "feeAsset": "QUOTE",
        "postOnly": True,
        "origQtyScaled": "1000000",
        "cumQtyScaled": "250000",
        "inheritedCumQtyScaled": "50000",
        "leavesQtyScaled": "0",
        "displayQtyScaled": "100000",
        "hiddenQtyScaled": "900000",
        "avgPriceTicks": "65000000000000",
        "avgPriceE18": _u128(65_000_000_000_000_000_000),
        "cumNotional": _u128(162_500_000),
        "feeTotal": {"amountE18": _u128(12_345), "isRebate": True, "qtyScaled": "1000"},
        "priceTicks": "64900000000000",
        "createdTsNs": str(TS_NS),
        "terminalTsNs": str(TS_NS + 1),
        "cancelReason": "CANCEL_REASON_STP_DECREMENT",
        "attachedRisk": {
            "takeProfit": {"policy": {"triggerPriceTicks": "70000000000000"}},
            "stopLoss": {"policy": {"triggerPriceTicks": "60000000000000"}},
            "oco": True,
        },
        "origin": {
            "scope": "STANDALONE_TRIGGER",
            "triggerType": "STOP_LOSS",
            "triggerId": "77",
            "childSeq": 2,
        },
        "marketClientRefPriceTicks": "65000000000000",
        "marketMaxSlippageTicks": "1000000000",
        "marketMaxSlippageBps": 25,
        "version": 3,
        "batchRequestId": "88",
        "submittedMaxQuoteDebitScaled": "500000000",
        "lineage": {"id": "99", "generation": 2},
        "expireAt": "2026-11-16T00:00:00Z",
    }
    fields.update(overrides)
    return ParseDict(fields, orders_read_pb2.Order())


def _rejected_order() -> orders_read_pb2.Order:
    return _order(
        orderId="5",
        status="REJECTED",
        cancelReason="CANCEL_REASON_UNSPECIFIED",
        rejectReason="ERROR_CODE_PEG_LIMIT_VIOLATION",
    )


def _trade() -> orders_read_pb2.UserTrade:
    return ParseDict(
        {
            "symbolId": 1,
            "matchId": "12",
            "orderId": "4611686018427387911",
            "side": "SELL",
            "isMaker": True,
            "priceTicks": "65000000000000",
            "qtyScaled": "250000",
            "feeAmountE18": _u128(5),
            "feeAsset": "BASE",
            "referralShareAmountE18": _u128(1),
            "tsNs": str(TS_NS),
            "feeIsRebate": True,
            "lineage": {"id": "99", "generation": 1},
        },
        orders_read_pb2.UserTrade(),
    )


def _transfer() -> orders_read_pb2.OrderTransfer:
    return ParseDict(
        {
            "matchId": "12",
            "symbolId": 1,
            "assetId": 2,
            "amountE18": _u128(7),
            "isDebit": True,
            "tsNs": str(TS_NS),
            "txId": "tx-1",
        },
        orders_read_pb2.OrderTransfer(),
    )


def _error(code: int, **fields: Any) -> orders_pb2.ErrorDetail:
    return orders_pb2.ErrorDetail(
        code=code,
        violations=[
            orders_pb2.FieldViolation(
                field_path="order.base_qty_scaled", rule_id="minimum", message="m"
            )
        ],
        rate_limit=ratelimit_pb2.RateLimitDetail(limit=10, remaining=0, retry_after_ms=250),
        **fields,
    )


def _create() -> orders_pb2.CreateOrderResponse:
    return orders_pb2.CreateOrderResponse(
        order_id=42,
        client_order_id="c-1",
        accepted_at=TS,
        accepted_at_ts_ns=TS_NS,
        resolved_base_qty_scaled=776_079,
        submitted_max_quote_debit_scaled=500_000_000,
        take_profit_trigger_id=7,
        stop_loss_trigger_id=8,
        trailing_stop_trigger_id=9,
    )


def _batch_create() -> orders_pb2.BatchCreateOrdersResponse:
    return orders_pb2.BatchCreateOrdersResponse(
        results=[
            orders_pb2.BatchCreateResultItem(
                client_order_id="a",
                accepted=orders_pb2.BatchCreateAccepted(
                    order_id=42,
                    resolved_base_qty_scaled=1_000_000,
                    take_profit_trigger_id=7,
                    submitted_quote_proceeds_scaled=400_000_000,
                ),
            ),
            orders_pb2.BatchCreateResultItem(
                client_order_id="b",
                accepted=orders_pb2.BatchCreateAccepted(
                    order_id=43, resolved_base_qty_scaled=77_607, submitted_max_quote_debit_scaled=5
                ),
            ),
            orders_pb2.BatchCreateResultItem(
                client_order_id="c",
                rejected=orders_pb2.BatchCreateRejected(
                    error=_error(
                        orders_pb2.ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID,
                        existing_order_id=44,
                    )
                ),
            ),
        ],
        accepted_count=2,
        rejected_count=1,
        ts=TS,
    )


def _batch_replace() -> orders_pb2.BatchReplaceOrdersResponse:
    return orders_pb2.BatchReplaceOrdersResponse(
        batch_request_id=9,
        status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED,
        results=[
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=0,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                old_order_id=42,
                replacement_order_id=43,
                client_order_id="n",
                action_taken=orders_pb2.REPLACED,
            ),
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=1,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED,
                old_order_id=44,
                code="CONFLICT_DUPLICATE_CLIENT_ORDER_ID",
                error=_error(
                    orders_pb2.ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID, existing_order_id=45
                ),
            ),
        ],
        accepted_count=1,
        rejected_count=1,
        accepted_ts=TS,
    )


def _batch_replace_status() -> orders_pb2.GetBatchReplaceStatusResponse:
    return orders_read_pb2.GetBatchReplaceStatusResponse(
        batch_request_id=9,
        admission_status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED,
        items=[
            orders_read_pb2.BatchReplaceStatusItem(
                item_index=0,
                phase=orders_read_pb2.BATCH_REPLACE_PHASE_WORKING,
                old_order_id=42,
                replacement_order_id=43,
                order_status=orders_read_pb2.WORKING,
                updated_ts_ns=TS_NS,
                action_taken=orders_pb2.REPLACED,
            ),
            orders_read_pb2.BatchReplaceStatusItem(
                item_index=1,
                phase=orders_read_pb2.BATCH_REPLACE_PHASE_REJECTED,
                old_order_id=44,
                code="POST_ONLY_CROSS",
                updated_ts_ns=TS_NS,
            ),
        ],
        accepted_count=1,
        rejected_count=1,
        accepted_ts_ns=TS_NS,
        updated_ts_ns=TS_NS + 1,
    )


def _batch_cancel() -> orders_pb2.BatchCancelOrdersResponse:
    return orders_pb2.BatchCancelOrdersResponse(
        results=[
            orders_pb2.BatchCancelResultItem(
                status=orders_pb2.BatchCancelResultItem.ACCEPTED, order_id=42, client_order_id="a"
            ),
            orders_pb2.BatchCancelResultItem(
                status=orders_pb2.BatchCancelResultItem.REJECTED,
                order_id=43,
                code="ORDER_UNKNOWN",
                error=_error(orders_pb2.ERROR_CODE_ORDER_UNKNOWN),
            ),
        ],
        accepted_count=1,
        rejected_count=1,
        ts=TS,
        ts_ns=TS_NS,
    )


def _cancel_all_answer() -> orders_pb2.CancelAllOrdersResponse:
    return orders_pb2.CancelAllOrdersResponse(
        status=orders_pb2.CancelAllOrdersResponse.SUBMITTED,
        matched_orders=2,
        submitted_cancels=2,
        cancelled_orders=[orders_pb2.CancelledOrder(order_id=42, client_order_id="a")],
        total_cancelled=2,
        truncated=True,
        listing_status=orders_pb2.CancelAllOrdersResponse.INCLUDED,
        ts=TS,
        ts_ns=TS_NS,
    )


def _cancel_all_after() -> orders_pb2.CancelAllAfterResponse:
    return orders_pb2.CancelAllAfterResponse(
        status=orders_pb2.CancelAllAfterResponse.ARMED,
        effective_timeout_sec=30,
        expires_at_ts_ns=TS_NS,
        ts=TS,
        ts_ns=TS_NS,
        effective_scope=orders_pb2.DeadManSwitchScope(
            account_id=42, symbol_id=1, side=orders_pb2.BUY
        ),
    )


# (name, protobuf message, protobuf decode, JSON decode). Scaled reads pass the
# same catalog scales to both paths.
CASES: list[tuple[str, Callable[[], Message], Callable[[Any], Any], Callable[[Any], Any]]] = [
    (
        "order",
        _order,
        lambda m: proto_decode.order_from_proto(m, quantity_scale=8, quote_quantity_scale=6),
        lambda d: wire_decode.decode_order(d, quantity_scale=8, quote_quantity_scale=6),
    ),
    (
        "order unscaled",
        _order,
        proto_decode.order_from_proto,
        lambda d: wire_decode.decode_order(d),
    ),
    (
        "rejected order",
        _rejected_order,
        proto_decode.order_from_proto,
        lambda d: wire_decode.decode_order(d),
    ),
    (
        "orders list",
        lambda: orders_read_pb2.GetOpenOrdersResponse(
            orders=[_order(), _rejected_order()], next_page_token="p"
        ),
        lambda m: proto_decode.orders_list_from_proto(m, scales=_scales),
        lambda d: wire_decode.decode_orders_list(d, scales=_scales),
    ),
    (
        "get order",
        lambda: orders_read_pb2.GetOrderResponse(
            order=_order(),
            trades=[_trade()],
            transfers=[_transfer()],
            next_page_token="p",
            executions_complete=True,
        ),
        lambda m: proto_decode.get_order_from_proto(m, scales=_scales),
        lambda d: wire_decode.decode_get_order(d, scales=_scales),
    ),
    (
        "user trade",
        _trade,
        proto_decode.user_trade_from_proto,
        lambda d: wire_decode.decode_user_trade(d),
    ),
    (
        "user trades list",
        lambda: orders_read_pb2.GetUserTradesResponse(
            trades=[_trade()], transfers=[_transfer()], next_page_token="p"
        ),
        lambda m: proto_decode.user_trades_list_from_proto(m, scales=_scales),
        lambda d: wire_decode.decode_user_trades_list(d, scales=_scales),
    ),
    (
        "create",
        _create,
        lambda m: proto_decode.order_mutation_from_proto(m, market=btc_market(8)),
        lambda d: wire_decode.decode_order_mutation(d, market=btc_market(8)),
    ),
    (
        "cancel",
        lambda: orders_pb2.CancelOrderResponse(
            status=orders_pb2.CancelOrderResponse.ACCEPTED, order_id=42, ts=TS, ts_ns=TS_NS
        ),
        lambda m: proto_decode.order_mutation_from_proto(m, market=None),
        lambda d: wire_decode.decode_order_mutation(d, market=None),
    ),
    (
        "modify",
        lambda: orders_pb2.ModifyOrderResponse(
            action_taken=orders_pb2.REPLACED,
            old_order_id=42,
            final_order_id=43,
            code="OK",
            take_profit_trigger_id=7,
            ts=TS,
        ),
        proto_decode.modify_order_from_proto,
        lambda d: wire_decode.decode_modify_order_result(d),
    ),
    (
        "batch create",
        _batch_create,
        lambda m: proto_decode.batch_create_from_proto(
            m, markets=[btc_market(8), btc_market(5), btc_market(8)]
        ),
        lambda d: wire_decode.decode_batch_create_result(
            d, markets=[btc_market(8), btc_market(5), btc_market(8)]
        ),
    ),
    (
        "batch cancel",
        _batch_cancel,
        proto_decode.batch_cancel_from_proto,
        lambda d: wire_decode.decode_batch_cancel_result(d),
    ),
    (
        "batch replace",
        _batch_replace,
        proto_decode.batch_replace_from_proto,
        lambda d: wire_decode.decode_batch_replace_result(d),
    ),
    (
        "batch replace status",
        _batch_replace_status,
        proto_decode.batch_replace_status_from_proto,
        lambda d: wire_decode.decode_batch_replace_status(d),
    ),
    (
        "cancel all",
        _cancel_all_answer,
        proto_decode.cancel_all_from_proto,
        lambda d: wire_decode.decode_cancel_all_orders_result(d),
    ),
    (
        "cancel all after",
        _cancel_all_after,
        proto_decode.cancel_all_after_from_proto,
        lambda d: wire_decode.decode_cancel_all_after_result(d),
    ),
]


@pytest.mark.parametrize("snake_case", [False, True], ids=["camelCase", "snake_case"])
@pytest.mark.parametrize(
    ("name", "build", "from_proto", "from_json"), CASES, ids=[c[0] for c in CASES]
)
def test_json_decode_equals_protobuf_decode(name, build, from_proto, from_json, snake_case) -> None:
    msg = build()
    expected = from_proto(msg)
    got = from_json(MessageToDict(msg, preserving_proto_field_name=snake_case))
    assert got == expected


def test_json_order_reasons_use_the_lowercase_labels() -> None:
    canceled = wire_decode.decode_order(MessageToDict(_order()))
    rejected = wire_decode.decode_order(MessageToDict(_rejected_order()))
    assert canceled.cancel_reason == "stp_decrement"
    assert rejected.reject_reason == "peg_limit_violation"


def test_json_batch_create_keeps_resolved_quantity_and_time() -> None:
    result = wire_decode.decode_batch_create_result(
        MessageToDict(_batch_create()),
        markets=[btc_market(8), btc_market(5), btc_market(8)],
    )
    assert [item.resolved_base_qty_scaled for item in result.results] == ["1000000", "77607", ""]
    assert result.results[1].resolved_base_qty.format() == "0.77607"
    assert result.ts_ns == 1_763_164_740_987_654_321


def test_json_order_that_is_not_the_contract_shape_is_a_contract_error() -> None:
    from polyester.errors import PolyesterResponseContractError

    with pytest.raises(PolyesterResponseContractError):
        wire_decode.decode_order({"orderId": "not-a-number"})
