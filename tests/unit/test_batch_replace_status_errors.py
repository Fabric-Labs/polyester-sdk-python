"""GetBatchReplaceStatus errors and the exact 64-bit batch identity
(contract 1bf038e): UNAVAILABLE is retryable, NOT_FOUND is a not-found error
and never a rejected batch."""

from __future__ import annotations

import base64

import pytest
from pytest_httpserver import HTTPServer

from polyester import PolyesterServerError, is_not_found, is_retryable_error
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from tests.unit.test_wait_batch_replace import STATUS_PATH, _orders_service, _status, _working

MAX_ID = (1 << 64) - 1


@pytest.mark.asyncio
async def test_unavailable_is_the_retryable_server_error(httpserver: HTTPServer) -> None:
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value("ERROR_CODE_UNAVAILABLE"))
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_json(
        {
            "code": "unavailable",
            "message": "The batch status is temporarily unavailable; retry the request.",
            "details": [
                {
                    "type": "orders.v1.ErrorDetail",
                    "value": base64.b64encode(detail.SerializeToString()).decode(),
                }
            ],
        },
        status=503,
    )
    orders, transport = _orders_service(httpserver)
    try:
        with pytest.raises(PolyesterServerError) as caught:
            await orders.get_batch_replace_status(batch_request_id=str(MAX_ID))
    finally:
        await transport.aclose()
    assert is_retryable_error(caught.value)
    assert not is_not_found(caught.value)


@pytest.mark.asyncio
async def test_not_found_is_not_found_and_not_retryable(httpserver: HTTPServer) -> None:
    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_json(
        {"code": "not_found", "message": "batch replace status not found"}, status=404
    )
    orders, transport = _orders_service(httpserver)
    try:
        with pytest.raises(Exception) as caught:
            await orders.get_batch_replace_status(batch_request_id=str(MAX_ID))
    finally:
        await transport.aclose()
    assert is_not_found(caught.value), repr(caught.value)
    assert not is_retryable_error(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("given", [str(MAX_ID), format_id(MAX_ID)])
async def test_batch_request_id_keeps_all_64_bits(httpserver: HTTPServer, given: str) -> None:
    seen: list[int] = []

    def handle(request):
        from werkzeug import Response

        req = orders_read_pb2.GetBatchReplaceStatusRequest.FromString(request.get_data())
        seen.append(req.batch_request_id)
        message = _status(_working(0), accepted=1)
        message.batch_request_id = req.batch_request_id
        return Response(message.SerializeToString(), content_type="application/proto")

    httpserver.expect_request(STATUS_PATH, method="POST").respond_with_handler(handle)
    orders, transport = _orders_service(httpserver)
    try:
        status = await orders.get_batch_replace_status(batch_request_id=given)
    finally:
        await transport.aclose()
    assert seen == [MAX_ID]
    assert status.batch_request_id == format_id(MAX_ID)
