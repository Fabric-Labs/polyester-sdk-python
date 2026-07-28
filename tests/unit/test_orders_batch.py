import pytest

from polyester.codecs.decode.orders import (
    batch_cancel_from_proto,
    batch_create_from_proto,
    batch_modify_from_proto,
    cancel_all_after_from_proto,
    cancel_all_from_proto,
)
from polyester.codecs.orders import (
    batch_cancel_orders_to_proto,
    batch_create_orders_to_proto,
    cancel_all_after_to_proto,
    normalize_create_order_request,
)
from polyester.codecs.scalars import format_id, id_to_int
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import ClientOrderId, CreateOrderRequest, OrderId


def test_batch_create_orders_to_proto_from_dict_and_struct() -> None:
    dict_item = {
        "symbol": "BTC-USD",
        "side": "buy",
        "order_type": "limit",
        "tif": "gtc",
        "qty": "0.1",
        "price": "50000",
        "client_order_id": "cid-1",
    }
    struct_item = normalize_create_order_request(
        symbol="ETH-USD",
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
    assert proto.items[0].symbol == "BTC-USD"
    assert proto.items[0].side == orders_pb2.BUY
    assert proto.items[0].client_order_id == "cid-1"
    assert proto.items[0].qty_scaled == 10_000_000
    assert proto.items[0].WhichOneof("execution") == "limit_gtc"
    assert proto.items[0].limit_gtc.price_ticks == 50_000_000_000
    assert proto.items[1].symbol == "ETH-USD"
    assert proto.items[1].side == orders_pb2.SELL
    assert proto.items[1].WhichOneof("execution") == "market_ioc"


def test_batch_create_orders_to_proto_from_create_order_request() -> None:
    item = CreateOrderRequest(
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        qty="0.5",
        price="100",
    )
    proto = batch_create_orders_to_proto(items=[item], quantity_scale=8)
    assert len(proto.items) == 1
    assert proto.items[0].qty_scaled == 50_000_000
    assert proto.items[0].limit_gtc.price_ticks == 100_000_000


def test_batch_create_requires_items() -> None:
    with pytest.raises(PolyesterValidationError):
        batch_create_orders_to_proto(items=[])


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
        symbol="BTC-USD",
        side="sell",
        request_id="req-deadman-1",
    )
    assert proto.request_id == "req-deadman-1"
    assert proto.subaccount_id == id_to_int("7")
    assert proto.timeout_sec == 60
    assert proto.symbol == "BTC-USD"
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
                status="accepted",
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
        results=[orders_pb2.BatchCancelResultItem(status="accepted")],
        rejected_count=1,
    )
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_cancel_from_proto(mismatch)

    unknown = orders_pb2.BatchCancelOrdersResponse(
        results=[orders_pb2.BatchCancelResultItem(status="maybe")],
        accepted_count=1,
    )
    with pytest.raises(PolyesterResponseContractError, match="unknown status"):
        batch_cancel_from_proto(unknown)


def test_batch_modify_reconciles_actions_and_counts() -> None:
    valid = orders_pb2.BatchModifyOrdersResponse(
        results=[
            orders_pb2.BatchModifyResultItem(
                status="modified", action_taken=orders_pb2.AMENDED
            ),
            orders_pb2.BatchModifyResultItem(
                status="modified", action_taken=orders_pb2.REPLACED
            ),
            orders_pb2.BatchModifyResultItem(status="rejected"),
        ],
        amended_count=1,
        replaced_count=1,
        rejected_count=1,
    )
    result = batch_modify_from_proto(valid)
    assert (result.amended_count, result.replaced_count, result.rejected_count) == (1, 1, 1)

    valid.amended_count = 2
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_modify_from_proto(valid)


def test_cancel_all_after_from_proto() -> None:
    msg = orders_pb2.CancelAllAfterResponse(
        status="armed",
        effective_timeout_sec=120,
        expires_at_ts_ns=1_700_000_000_000,
    )
    result = cancel_all_after_from_proto(msg)
    assert result.status == "armed"
    assert result.effective_timeout_sec == 120
    assert result.expires_at_ts_ns == "1700000000000"


def test_cancel_all_requires_known_status() -> None:
    ok = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(
            status="submitted",
            matched_orders=3,
            submitted_cancels=2,
            failed_cancels=1,
        )
    )
    assert ok.status == "submitted"
    assert ok.failed_cancels == 1
    assert cancel_all_from_proto(orders_pb2.CancelAllOrdersResponse(status="dry_run")).status == (
        "dry_run"
    )
    for status in ("", "ok", "maybe", "accepted"):
        with pytest.raises(PolyesterResponseContractError, match="unknown status"):
            cancel_all_from_proto(
                orders_pb2.CancelAllOrdersResponse(status=status, matched_orders=1)
            )


def test_cancel_all_after_rejects_unknown_status() -> None:
    for status in ("", "ok", "submitted", "maybe"):
        with pytest.raises(PolyesterResponseContractError, match="unknown status"):
            cancel_all_after_from_proto(
                orders_pb2.CancelAllAfterResponse(status=status, effective_timeout_sec=10)
            )
