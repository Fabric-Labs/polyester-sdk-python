"""Public error decoding for temporary admission failures and refused calls."""

from __future__ import annotations

import base64

import pytest

from polyester import is_retryable_error, mutation_outcome_unknown
from polyester.errors import PolyesterAuthError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from tests.unit.test_auth_error_codes import _rest_error


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize(
    "name,retryable",
    [("OVERLOADED", True), ("SYSTEM_RATE_LIMITED", True), ("ORDER_SEQUENCE_EXHAUSTED", False)],
)
async def test_connect_admission_classification(httpserver, name, retryable, typed):
    body = {"code": "resource_exhausted", "message": name}
    if typed:
        detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value("ERROR_CODE_" + name))
        body["details"] = [
            {
                "type": "orders.v1.ErrorDetail",
                "value": base64.b64encode(detail.SerializeToString()).decode(),
            }
        ]
    error = await _rest_error(httpserver, 429, body, content_type="application/json")
    assert is_retryable_error(error) is retryable
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize(
    "name,status,retryable",
    [
        ("OVERLOADED", 503, True),
        ("SYSTEM_RATE_LIMITED", 429, True),
        ("ORDER_SEQUENCE_EXHAUSTED", 429, False),
    ],
)
async def test_rest_admission_classification(httpserver, name, status, retryable):
    error = await _rest_error(httpserver, status, {"code": name, "detail": "admission refused"})
    assert is_retryable_error(error) is retryable
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize("status", [503, 504])
@pytest.mark.parametrize("connect", [False, True])
async def test_future_outcome_code_on_public_decoder(httpserver, status, connect):
    name = "TWAP_CREATE_OUTCOME_UNKNOWN"
    body = (
        {"code": "unavailable" if status == 503 else "deadline_exceeded", "message": name}
        if connect
        else {"code": name}
    )
    error = await _rest_error(httpserver, status, body, content_type="application/json")
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("status,code", [(401, "unauthenticated"), (403, "permission_denied")])
async def test_connect_auth_refusal_keeps_code_and_status(httpserver, typed, status, code):
    body = {"code": code, "message": "api_key_action_deny"}
    expected_code = code
    if typed:
        detail = transfer_pb2.ErrorDetail(code=transfer_pb2.ERROR_CODE_PERMISSION_DENIED)
        body["details"] = [
            {
                "type": "transfer.v1.ErrorDetail",
                "value": base64.b64encode(detail.SerializeToString()).decode(),
            }
        ]
        expected_code = "ERROR_CODE_PERMISSION_DENIED"
    error = await _rest_error(httpserver, status, body, content_type="application/json")
    assert isinstance(error, PolyesterAuthError)
    assert error.code == expected_code
    assert error.status_code == status
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


async def test_rest_admission_keeps_retry_delay(httpserver):
    from polyester.errors import PolyesterRateLimitError

    error = await _rest_error(
        httpserver, 429, {"code": "SYSTEM_RATE_LIMITED"}, headers={"Retry-After": "1.25"}
    )
    assert isinstance(error, PolyesterRateLimitError)
    assert error.retry_after == 1.25
