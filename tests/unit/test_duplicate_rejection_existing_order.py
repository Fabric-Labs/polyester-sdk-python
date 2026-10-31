"""Duplicate-client-order-ID rejections keep the existing order's identity."""

from __future__ import annotations

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.codecs.decode.orders import batch_create_from_proto
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterApiError
from polyester.gen.orders.v1 import orders_pb2


def _order_error(**detail: object) -> PolyesterApiError:
    mapped = map_connect_error(
        ConnectError(
            Code.ALREADY_EXISTS,
            "client order id already used",
            details=[orders_pb2.ErrorDetail(**detail)],  # type: ignore[arg-type]
        )
    )
    assert isinstance(mapped, PolyesterApiError)
    return mapped


def test_single_duplicate_rejection_exposes_existing_order_id() -> None:
    error = _order_error(
        code=orders_pb2.ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID, existing_order_id=4242
    )

    assert error.code == "ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID"
    assert error.existing_order_id == format_id(4242)


def test_rejection_without_known_existing_order_leaves_it_unset() -> None:
    error = _order_error(code=orders_pb2.ERROR_CODE_MAX_OPEN_ORDERS_PER_PAIR)

    assert error.code == "ERROR_CODE_MAX_OPEN_ORDERS_PER_PAIR"
    assert error.existing_order_id is None


def test_batch_create_rejection_exposes_existing_order_id() -> None:
    result = batch_create_from_proto(
        orders_pb2.BatchCreateOrdersResponse(
            results=[
                orders_pb2.BatchCreateResultItem(
                    client_order_id="dup",
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(
                            code=orders_pb2.ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID,
                            existing_order_id=4242,
                        )
                    ),
                ),
                orders_pb2.BatchCreateResultItem(
                    client_order_id="full",
                    rejected=orders_pb2.BatchCreateRejected(
                        error=orders_pb2.ErrorDetail(
                            code=orders_pb2.ERROR_CODE_MAX_OPEN_ORDERS_TOTAL
                        )
                    ),
                ),
            ],
            rejected_count=2,
        )
    )

    duplicate, capacity = result.results
    assert duplicate.code == "error_code_conflict_duplicate_client_order_id"
    assert duplicate.existing_order_id == format_id(4242)
    assert capacity.existing_order_id == ""
