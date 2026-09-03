import pytest

from polyester.codecs.decode.orders import (
    batch_cancel_from_proto,
    batch_create_from_proto,
    batch_replace_from_proto,
    batch_replace_status_from_proto,
    cancel_all_after_from_proto,
    cancel_all_from_proto,
)
from polyester.codecs.orders import (
    batch_cancel_orders_to_proto,
    batch_create_orders_to_proto,
    batch_replace_orders_to_proto,
    cancel_all_after_to_proto,
    normalize_create_order_request,
    validate_batch_size,
)
from polyester.codecs.scalars import format_id, id_to_int
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.models import (
    BatchReplaceItem,
    BatchReplaceStatusItem,
    BatchReplaceStatusResult,
    ClientOrderId,
    CreateOrderRequest,
    OrderId,
)
from polyester.services.orders import is_batch_replace_settled


def test_batch_create_orders_to_proto_from_dict_and_struct() -> None:
    dict_item = {
        "symbol": "BTC-USD",
        "symbol_id": 1,
        "side": "buy",
        "order_type": "limit",
        "tif": "gtc",
        "qty": "0.1",
        "price": "50000",
        "client_order_id": "cid-1",
    }
    struct_item = normalize_create_order_request(
        symbol="ETH-USD",
        symbol_id=2,
        side="sell",
        order_type="market",
        qty="1",
        client_order_id="cid-2",
    )
    proto = batch_create_orders_to_proto(
        items=[dict_item, struct_item],
        sub_account_id="123",
        request_id="req-create-1",
        allow_partial=True,
        quantity_scale=8,
    )
    assert proto.request_id == "req-create-1"
    # allow_partial was removed from the wire (POLY-3701); the arg is ignored.
    assert "allow_partial" not in {f.name for f in proto.DESCRIPTOR.fields}
    assert proto.subaccount_id == id_to_int("123")
    assert len(proto.items) == 2
    assert proto.items[0].symbol_id == 1
    assert proto.items[0].side == orders_pb2.BUY
    assert proto.items[0].client_order_id == "cid-1"
    assert proto.items[0].base_qty_scaled == 10_000_000
    assert proto.items[0].WhichOneof("execution") == "limit_gtc"
    assert proto.items[0].limit_gtc.price_ticks == 50_000_000_000
    assert proto.items[1].symbol_id == 2
    assert proto.items[1].side == orders_pb2.SELL
    assert proto.items[1].WhichOneof("execution") == "market_ioc"


def test_batch_create_orders_to_proto_from_create_order_request() -> None:
    item = CreateOrderRequest(
        symbol="BTC-USD",
        symbol_id=1,
        side="buy",
        order_type="limit",
        qty="0.5",
        price="100",
    )
    proto = batch_create_orders_to_proto(items=[item], quantity_scale=8)
    assert len(proto.items) == 1
    assert proto.request_id, "batch create must send a non-empty request_id"
    assert proto.items[0].client_order_id == ""
    assert proto.items[0].base_qty_scaled == 50_000_000
    assert proto.items[0].limit_gtc.price_ticks == 100_000_000


def test_batch_create_requires_items() -> None:
    with pytest.raises(PolyesterValidationError, match="at least one"):
        batch_create_orders_to_proto(items=[])


def test_batch_size_guard_rejects_more_than_twenty() -> None:
    validate_batch_size("batch_create", 1)
    validate_batch_size("batch_create", 20)
    with pytest.raises(PolyesterValidationError, match="at least one"):
        validate_batch_size("batch_create", 0)
    with pytest.raises(PolyesterValidationError, match="at most 20"):
        validate_batch_size("batch_create", 21)

    item = {
        "symbol": "BTC-USD",
        "symbol_id": 1,
        "side": "buy",
        "order_type": "limit",
        "qty": "0.1",
        "price": "1",
    }
    with pytest.raises(PolyesterValidationError, match="at most 20"):
        batch_create_orders_to_proto(items=[item] * 21, quantity_scale=8)
    with pytest.raises(PolyesterValidationError, match="at most 20"):
        batch_cancel_orders_to_proto(items=[{"key": OrderId("1")}] * 21)
    with pytest.raises(PolyesterValidationError, match="at most 20"):
        batch_replace_orders_to_proto(
            items=[
                BatchReplaceItem(key=OrderId("1"), new_qty="0.1") for _ in range(21)
            ],
            symbol_id=1,
            quantity_scale=8,
        )


def test_batch_cancel_orders_to_proto() -> None:
    proto = batch_cancel_orders_to_proto(
        items=[
            # "10" is pure decimal (not a canonical base58 encoding).
            {"key": OrderId("10"), "symbol_id": 3},
            {"key": ClientOrderId("cid-9"), "symbol_id": 5},
        ],
        sub_account_id="99",
        request_id="req-cancel-1",
    )
    assert proto.request_id == "req-cancel-1"
    assert proto.subaccount_id == id_to_int("99")
    assert len(proto.items) == 2
    assert proto.items[0].order_id == 10
    assert proto.items[0].symbol_id == 3
    assert proto.items[1].client_order_id == "cid-9"
    assert proto.items[1].symbol_id == 5


def test_batch_cancel_item_requires_order_key() -> None:
    with pytest.raises(PolyesterValidationError):
        batch_cancel_orders_to_proto(items=[{}])
    with pytest.raises(PolyesterValidationError, match="not accepted"):
        batch_cancel_orders_to_proto(items=[{"order_id": "1", "client_order_id": "cid"}])
    with pytest.raises(PolyesterValidationError, match="not accepted"):
        batch_cancel_orders_to_proto(items=[{"order_id": "1"}])


def test_batch_cancel_requires_items() -> None:
    with pytest.raises(PolyesterValidationError):
        batch_cancel_orders_to_proto(items=[])


def test_cancel_all_after_to_proto() -> None:
    proto = cancel_all_after_to_proto(
        sub_account_id="7",
        timeout_sec=60,
        symbol_id=1,
        side="sell",
        request_id="req-deadman-1",
    )
    assert proto.request_id == "req-deadman-1"
    assert proto.subaccount_id == id_to_int("7")
    assert proto.timeout_sec == 60
    assert proto.symbol_id == 1
    assert proto.side == orders_pb2.SELL


def test_cancel_all_after_rejects_invalid_side() -> None:
    with pytest.raises(PolyesterValidationError):
        cancel_all_after_to_proto(timeout_sec=30, side="invalid")


def test_batch_create_from_proto() -> None:
    msg = orders_pb2.BatchCreateOrdersResponse(
        results=[
            orders_pb2.BatchCreateResultItem(
                client_order_id="cid-a",
                accepted=orders_pb2.BatchCreateAccepted(order_id=101),
            ),
            orders_pb2.BatchCreateResultItem(
                client_order_id="cid-b",
                rejected=orders_pb2.BatchCreateRejected(
                    error=orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_BAD_QTY)
                ),
            ),
        ],
        accepted_count=1,
        rejected_count=1,
    )
    result = batch_create_from_proto(msg)
    assert result.accepted_count == 1
    assert result.rejected_count == 1
    assert len(result.results) == 2
    assert result.results[0].status == "accepted"
    assert result.results[0].order_id == format_id(101)
    assert result.results[0].client_order_id == "cid-a"
    assert result.results[1].status == "rejected"
    assert result.results[1].client_order_id == "cid-b"
    assert result.results[1].code == "error_code_bad_qty"


def test_batch_create_rejects_missing_outcome() -> None:
    msg = orders_pb2.BatchCreateOrdersResponse(
        results=[orders_pb2.BatchCreateResultItem(client_order_id="missing")]
    )
    with pytest.raises(PolyesterResponseContractError, match="neither accepted nor rejected"):
        batch_create_from_proto(msg)


def test_batch_create_preserves_unknown_rejection_code() -> None:
    msg = orders_pb2.BatchCreateOrdersResponse(
        results=[
            orders_pb2.BatchCreateResultItem(
                client_order_id="rejected",
                rejected=orders_pb2.BatchCreateRejected(error=orders_pb2.ErrorDetail(code=99_999)),
            )
        ],
        rejected_count=1,
    )
    result = batch_create_from_proto(msg)
    assert result.results[0].code == "unknown_error_code(99999)"


def test_batch_create_rejects_count_mismatch() -> None:
    msg = orders_pb2.BatchCreateOrdersResponse(
        results=[
            orders_pb2.BatchCreateResultItem(accepted=orders_pb2.BatchCreateAccepted(order_id=1))
        ],
        rejected_count=1,
    )
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_create_from_proto(msg)


def test_batch_cancel_from_proto() -> None:
    msg = orders_pb2.BatchCancelOrdersResponse(
        results=[
            orders_pb2.BatchCancelResultItem(
                status=orders_pb2.BatchCancelResultItem.ACCEPTED,
                order_id=55,
                client_order_id="cid-x",
                code="ok",
            ),
        ],
        accepted_count=1,
        rejected_count=0,
    )
    result = batch_cancel_from_proto(msg)
    assert result.accepted_count == 1
    assert result.rejected_count == 0
    assert result.results[0].order_id == format_id(55)
    assert result.results[0].client_order_id == "cid-x"


def test_batch_cancel_rejects_count_mismatch_and_unknown_status() -> None:
    mismatch = orders_pb2.BatchCancelOrdersResponse(
        results=[orders_pb2.BatchCancelResultItem(status=orders_pb2.BatchCancelResultItem.ACCEPTED)],
        rejected_count=1,
    )
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_cancel_from_proto(mismatch)

    unknown = orders_pb2.BatchCancelOrdersResponse(
        results=[orders_pb2.BatchCancelResultItem(status=99)],
        accepted_count=1,
    )
    with pytest.raises(PolyesterResponseContractError, match="unknown status"):
        batch_cancel_from_proto(unknown)


def test_batch_replace_encodes_admission_request() -> None:
    proto = batch_replace_orders_to_proto(
        items=[
            BatchReplaceItem(
                key=OrderId(10),
                new_price="100",
                new_qty="0.25",
                new_client_order_id="replacement-cid",
            )
        ],
        symbol_id=7,
        sub_account_id="123",
        request_id="request-1",
        quantity_scale=6,
    )
    assert proto.symbol_id == 7
    assert proto.request_id == "request-1"
    assert proto.subaccount_id == id_to_int("123")
    assert proto.items[0].order_id == 10
    assert proto.items[0].new_price_ticks == 100_000_000
    assert proto.items[0].new_qty_scaled == 250_000
    assert proto.items[0].new_client_order_id == "replacement-cid"


def test_batch_replace_reconciles_admission_counts() -> None:
    valid = orders_pb2.BatchReplaceOrdersResponse(
        batch_request_id=77,
        status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED,
        results=[
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=0,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED,
                old_order_id=10,
                replacement_order_id=11,
            ),
            orders_pb2.BatchReplaceAdmissionItem(
                item_index=1,
                status=orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED,
                code="conflict",
            ),
        ],
        accepted_count=1,
        rejected_count=1,
    )
    result = batch_replace_from_proto(valid)
    assert result.status == "partially_admitted"
    assert (result.accepted_count, result.rejected_count) == (1, 1)
    assert result.results[0].old_order_id == format_id(10)

    valid.accepted_count = 2
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_replace_from_proto(valid)


def test_batch_replace_status_decodes_phases() -> None:
    result = batch_replace_status_from_proto(
        orders_read_pb2.GetBatchReplaceStatusResponse(
            batch_request_id=77,
            admission_status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
            items=[
                orders_read_pb2.BatchReplaceStatusItem(
                    item_index=0,
                    phase=orders_read_pb2.BATCH_REPLACE_PHASE_WORKING,
                    old_order_id=10,
                    replacement_order_id=11,
                    order_status=orders_read_pb2.WORKING,
                    updated_ts_ns=123,
                )
            ],
            accepted_count=1,
            rejected_count=0,
        )
    )
    assert result.batch_request_id == format_id(77)
    assert result.admission_status == "admitted"
    assert result.items[0].phase == "working"
    assert result.items[0].updated_ts_ns == 123


def test_batch_replace_status_reconciles_phase_counts() -> None:
    msg = orders_read_pb2.GetBatchReplaceStatusResponse(
        batch_request_id=77,
        admission_status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
        items=[
            orders_read_pb2.BatchReplaceStatusItem(
                item_index=0,
                phase=orders_read_pb2.BATCH_REPLACE_PHASE_REJECTED,
            )
        ],
        accepted_count=1,
        rejected_count=0,
    )
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_replace_status_from_proto(msg)


def test_batch_replace_settled_means_status_reconciled_not_final() -> None:
    status = BatchReplaceStatusResult(
        batch_request_id="batch",
        admission_status="admitted",
        items=[BatchReplaceStatusItem(item_index=0, phase="working")],
    )
    assert is_batch_replace_settled(status)
    assert not is_batch_replace_settled(
        BatchReplaceStatusResult(
            batch_request_id="batch",
            admission_status="admitted",
            items=[BatchReplaceStatusItem(item_index=0, phase="admitted")],
        )
    )


def test_cancel_all_after_from_proto() -> None:
    msg = orders_pb2.CancelAllAfterResponse(
        status=orders_pb2.CancelAllAfterResponse.ARMED,
        effective_timeout_sec=120,
        expires_at_ts_ns=1_700_000_000_000_000_000,
    )
    result = cancel_all_after_from_proto(msg)
    assert result.status == "armed"
    assert result.effective_timeout_sec == 120
    assert result.expires_at_ts_ns == "1700000000000000000"


def test_cancel_all_requires_known_status() -> None:
    ok = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(
            status=orders_pb2.CancelAllOrdersResponse.SUBMITTED,
            matched_orders=3,
            submitted_cancels=2,
            failed_cancels=1,
        )
    )
    assert ok.status == "submitted"
    assert ok.failed_cancels == 1
    assert (
        cancel_all_from_proto(
            orders_pb2.CancelAllOrdersResponse(status=orders_pb2.CancelAllOrdersResponse.DRY_RUN)
        ).status
        == "dry_run"
    )
    for status in (
        orders_pb2.CancelAllOrdersResponse.STATUS_UNSPECIFIED,
        99,
    ):
        with pytest.raises(PolyesterResponseContractError, match="unknown status"):
            cancel_all_from_proto(
                orders_pb2.CancelAllOrdersResponse(status=status, matched_orders=1)
            )


def test_cancel_all_after_rejects_unknown_status() -> None:
    for status in (
        orders_pb2.CancelAllAfterResponse.STATUS_UNSPECIFIED,
        99,
    ):
        with pytest.raises(PolyesterResponseContractError, match="unknown status"):
            cancel_all_after_from_proto(
                orders_pb2.CancelAllAfterResponse(status=status, effective_timeout_sec=10)
            )
