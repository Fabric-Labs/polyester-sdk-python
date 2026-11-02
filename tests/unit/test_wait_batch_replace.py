"""Batch replace items refused after admission, and ``wait_batch_replace``."""

from __future__ import annotations

import asyncio
import time

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import PolyesterAuthError, PolyesterBatchReplaceTimeoutError
from polyester.auth import ApiKeyCredentials
from polyester.codecs.decode.orders import (
    batch_replace_item_error_code,
    batch_replace_status_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.services.orders import AsyncOrdersService
from polyester.transport import TransportConfig, TransportFactory

STATUS_PATH = "/orders.v1.OrdersReadService/GetBatchReplaceStatus"
BATCH_ID = 1234567890123456789


def _status(
    *items: orders_read_pb2.BatchReplaceStatusItem,
    accepted: int,
    rejected: int = 0,
    accepted_ts_ns: int | None = None,
) -> orders_read_pb2.GetBatchReplaceStatusResponse:
    return orders_read_pb2.GetBatchReplaceStatusResponse(
        batch_request_id=BATCH_ID,
        admission_status=orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
        items=list(items),
        accepted_count=accepted,
        rejected_count=rejected,
        accepted_ts_ns=time.time_ns() if accepted_ts_ns is None else accepted_ts_ns,
    )


def _admitted(index: int = 0) -> orders_read_pb2.BatchReplaceStatusItem:
    return orders_read_pb2.BatchReplaceStatusItem(
        item_index=index,
        phase=orders_read_pb2.BATCH_REPLACE_PHASE_ADMITTED,
        old_order_id=1234567890123450001,
    )


def _refused(
    index: int = 0, code: str = "POST_ONLY_CROSS"
) -> orders_read_pb2.BatchReplaceStatusItem:
    return orders_read_pb2.BatchReplaceStatusItem(
        item_index=index,
        phase=orders_read_pb2.BATCH_REPLACE_PHASE_REJECTED,
        old_order_id=1234567890123450001,
        code=code,
        updated_ts_ns=1793594333241957468,
    )


def _working(index: int = 0) -> orders_read_pb2.BatchReplaceStatusItem:
    return orders_read_pb2.BatchReplaceStatusItem(
        item_index=index,
        phase=orders_read_pb2.BATCH_REPLACE_PHASE_WORKING,
        old_order_id=1234567890123450002,
        replacement_order_id=1234567890123450003,
        order_status=orders_read_pb2.WORKING,
        action_taken=orders_pb2.REPLACED,
    )


def test_item_refused_after_admission_decodes_while_counted_as_accepted() -> None:
    # Admission counted the item as accepted; applying it refused it.
    status = batch_replace_status_from_proto(_status(_refused(), accepted=1))

    item = status.items[0]
    assert item.phase == "rejected"
    assert item.code == "POST_ONLY_CROSS"
    assert item.error_code == "ERROR_CODE_POST_ONLY_CROSS"
    assert item.old_order_id == format_id(1234567890123450001)
    assert item.replacement_order_id == ""
    assert (status.accepted_count, status.rejected_count) == (1, 0)


def test_rejected_item_never_exposes_a_replacement_order_id() -> None:
    refused = _refused()
    refused.replacement_order_id = 1234567890123450009
    status = batch_replace_status_from_proto(_status(refused, accepted=1))

    assert status.items[0].replacement_order_id == ""


@pytest.mark.parametrize(
    ("items", "accepted", "rejected"),
    [
        # More items rejected at admission than read rejected.
        ((_working(),), 0, 1),
        # Counts that do not cover every item.
        ((_working(0), _refused(1)), 1, 0),
    ],
)
def test_status_counts_that_cannot_describe_admission_are_contract_errors(
    items: tuple[orders_read_pb2.BatchReplaceStatusItem, ...], accepted: int, rejected: int
) -> None:
    with pytest.raises(PolyesterResponseContractError, match="counts do not match"):
        batch_replace_status_from_proto(_status(*items, accepted=accepted, rejected=rejected))


@pytest.mark.parametrize(
    ("code", "want"),
    [
        ("POST_ONLY_CROSS", "ERROR_CODE_POST_ONLY_CROSS"),
        ("PRICE_LEVELS_EXHAUSTED", "ERROR_CODE_PRICE_LEVELS_EXHAUSTED"),
        ("ERROR_CODE_POST_ONLY_CROSS", "ERROR_CODE_POST_ONLY_CROSS"),
        ("SOME_FUTURE_REFUSAL", "SOME_FUTURE_REFUSAL"),
        ("", ""),
    ],
)
def test_item_code_maps_to_the_error_code_a_modify_raises(code: str, want: str) -> None:
    assert batch_replace_item_error_code(code) == want


def _orders_service(httpserver: HTTPServer) -> tuple[AsyncOrdersService, TransportFactory]:
    private = Ed25519PrivateKey.generate()
    transport = TransportFactory(
        TransportConfig(api_url=httpserver.url_for("").rstrip("/")),
        credentials=ApiKeyCredentials(key_id="ak_test", private_key=private.private_bytes_raw()),
    )
    return AsyncOrdersService(transport, None, None), transport  # type: ignore[arg-type]


def _respond(
    httpserver: HTTPServer, message: orders_read_pb2.GetBatchReplaceStatusResponse
) -> None:
    httpserver.expect_oneshot_request(STATUS_PATH, method="POST").respond_with_data(
        message.SerializeToString(), content_type="application/proto"
    )


def _respond_unavailable(httpserver: HTTPServer) -> None:
    httpserver.expect_oneshot_request(STATUS_PATH, method="POST").respond_with_json(
        {"code": "unavailable", "message": "catching up"}, status=503
    )


@pytest.mark.asyncio
async def test_wait_batch_replace_polls_until_no_item_is_admitted(httpserver: HTTPServer) -> None:
    _respond(httpserver, _status(_admitted(0), _admitted(1), accepted=2))
    _respond_unavailable(httpserver)
    _respond(httpserver, _status(_working(0), _admitted(1), accepted=2))
    _respond(httpserver, _status(_working(0), _refused(1), accepted=2))
    orders, transport = _orders_service(httpserver)
    try:
        status = await orders.wait_batch_replace(batch_request_id=str(BATCH_ID))
    finally:
        await transport.aclose()

    assert len(httpserver.log) == 4
    assert {request.data for request, _ in httpserver.log} == {
        orders_read_pb2.GetBatchReplaceStatusRequest(batch_request_id=BATCH_ID).SerializeToString()
    }
    assert [item.phase for item in status.items] == ["working", "rejected"]
    assert status.items[0].replacement_order_id == format_id(1234567890123450003)
    assert status.items[1].error_code == "ERROR_CODE_POST_ONLY_CROSS"
    assert status.items[1].replacement_order_id == ""


@pytest.mark.asyncio
async def test_wait_batch_replace_stops_at_the_status_window(httpserver: HTTPServer) -> None:
    # Accepted 59.7 s ago: the 60 s status window ends in about 0.3 s.
    accepted_ts_ns = time.time_ns() - 59_700_000_000
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_data(
        _status(_admitted(), accepted=1, accepted_ts_ns=accepted_ts_ns).SerializeToString(),
        content_type="application/proto",
    )
    orders, transport = _orders_service(httpserver)
    started = time.monotonic()
    try:
        with pytest.raises(PolyesterBatchReplaceTimeoutError, match="reconcile") as caught:
            await orders.wait_batch_replace(batch_request_id=str(BATCH_ID))
    finally:
        await transport.aclose()

    assert time.monotonic() - started < 2.0
    assert caught.value.batch_request_id == str(BATCH_ID)
    assert caught.value.last_status is not None
    assert caught.value.last_status.items[0].phase == "admitted"


@pytest.mark.asyncio
async def test_wait_batch_replace_honours_a_shorter_timeout(httpserver: HTTPServer) -> None:
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_data(
        _status(_admitted(), accepted=1).SerializeToString(), content_type="application/proto"
    )
    orders, transport = _orders_service(httpserver)
    started = time.monotonic()
    try:
        with pytest.raises(PolyesterBatchReplaceTimeoutError):
            await orders.wait_batch_replace(batch_request_id=str(BATCH_ID), timeout=0.3)
    finally:
        await transport.aclose()

    assert time.monotonic() - started < 1.5


def _respond_not_found(httpserver: HTTPServer) -> None:
    httpserver.expect_oneshot_request(STATUS_PATH, method="POST").respond_with_json(
        {"code": "not_found", "message": "batch replace status not found"}, status=404
    )


@pytest.mark.asyncio
async def test_wait_batch_replace_polls_through_not_found_until_the_status_appears(
    httpserver: HTTPServer,
) -> None:
    # Right after admission the status read answers not_found for a few seconds.
    _respond_not_found(httpserver)
    _respond_not_found(httpserver)
    _respond(httpserver, _status(_working(), accepted=1))
    orders, transport = _orders_service(httpserver)
    try:
        status = await orders.wait_batch_replace(batch_request_id=str(BATCH_ID))
    finally:
        await transport.aclose()

    assert len(httpserver.log) == 3
    assert status.items[0].phase == "working"


@pytest.mark.asyncio
async def test_wait_batch_replace_not_found_until_the_end_is_a_timeout(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_json(
        {"code": "not_found", "message": "batch replace status not found"}, status=404
    )
    orders, transport = _orders_service(httpserver)
    try:
        with pytest.raises(PolyesterBatchReplaceTimeoutError, match="reconcile") as caught:
            await orders.wait_batch_replace(batch_request_id=str(BATCH_ID), timeout=0.3)
    finally:
        await transport.aclose()

    assert caught.value.last_status is None
    assert len(httpserver.log) >= 2


@pytest.mark.asyncio
async def test_wait_batch_replace_raises_other_errors(httpserver: HTTPServer) -> None:
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_json(
        {"code": "permission_denied", "message": "denied"}, status=403
    )
    orders, transport = _orders_service(httpserver)
    try:
        with pytest.raises(PolyesterAuthError):
            await orders.wait_batch_replace(batch_request_id=str(BATCH_ID))
    finally:
        await transport.aclose()

    assert len(httpserver.log) == 1


def _delayed(seconds: float, message: orders_read_pb2.GetBatchReplaceStatusResponse):
    def handler(_request: Request) -> Response:
        time.sleep(seconds)
        return Response(message.SerializeToString(), content_type="application/proto")

    return handler


@pytest.mark.asyncio
async def test_wait_batch_replace_deadline_bounds_an_in_flight_read(
    httpserver: HTTPServer,
) -> None:
    _respond(httpserver, _status(_admitted(), accepted=1))
    # The next read answers only after the caller's timeout has passed.
    httpserver.expect_oneshot_request(STATUS_PATH, method="POST").respond_with_handler(
        _delayed(1.0, _status(_working(), accepted=1))
    )
    orders, transport = _orders_service(httpserver)
    started = time.monotonic()
    try:
        with pytest.raises(PolyesterBatchReplaceTimeoutError, match="reconcile") as caught:
            await orders.wait_batch_replace(batch_request_id=str(BATCH_ID), timeout=0.4)
    finally:
        await transport.aclose()

    assert time.monotonic() - started < 0.8
    assert caught.value.last_status is not None
    assert caught.value.last_status.items[0].phase == "admitted"


@pytest.mark.asyncio
async def test_wait_batch_replace_persistent_unavailable_ends_in_the_timeout_error(
    httpserver: HTTPServer,
) -> None:
    # Accepted 59.7 s ago, then every read answers unavailable until the window ends.
    accepted_ts_ns = time.time_ns() - 59_700_000_000
    _respond(httpserver, _status(_admitted(), accepted=1, accepted_ts_ns=accepted_ts_ns))
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_json(
        {"code": "unavailable", "message": "catching up"}, status=503
    )
    orders, transport = _orders_service(httpserver)
    started = time.monotonic()
    try:
        with pytest.raises(PolyesterBatchReplaceTimeoutError, match="reconcile") as caught:
            await orders.wait_batch_replace(batch_request_id=str(BATCH_ID))
    finally:
        await transport.aclose()

    assert time.monotonic() - started < 2.0
    assert len(httpserver.log) >= 2
    assert caught.value.last_status is not None
    assert caught.value.last_status.items[0].phase == "admitted"


@pytest.mark.asyncio
async def test_wait_batch_replace_caller_cancellation_still_cancels(
    httpserver: HTTPServer,
) -> None:
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_handler(
        _delayed(1.0, _status(_working(), accepted=1))
    )
    orders, transport = _orders_service(httpserver)
    try:
        task = asyncio.create_task(
            orders.wait_batch_replace(batch_request_id=str(BATCH_ID), timeout=5.0)
        )
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await transport.aclose()
