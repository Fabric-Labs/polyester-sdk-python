"""API-key auth error codes, the session-required error and REST problem
details read the same over ConnectRPC and REST (contract notes 1747Z, 1755Z,
1734Z and 1759Z)."""

from __future__ import annotations

import json

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from pytest_httpserver import HTTPServer

from polyester import (
    AUTH_AUTHENTICATION_REQUIRED,
    AUTH_IP_NOT_ALLOWED,
    AUTH_SESSION_KIND_NOT_ALLOWED,
    AUTH_SIGNATURE_INVALID,
    AUTH_TIMESTAMP_SKEW,
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterSessionRequiredError,
    PolyesterTimestampSkewError,
    auth_error_code,
    is_retryable_error,
    is_session_required,
    mutation_outcome_unknown,
)
from polyester._wire import map_connect_error
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.services.market_data import AsyncMarketDataService
from polyester.transport import TransportConfig, TransportFactory

SPOT_CONFIG_PATH = "/marketdata.v1.MarketDataService/GetSpotConfig"

NEW_API_KEY_CODES = [
    "AUTH_SIGNATURE_INVALID",
    "AUTH_MISSING_HEADERS",
    "AUTH_KEY_EXPIRED",
    "AUTH_KEY_DISABLED",
    "AUTH_IP_NOT_ALLOWED",
    "AUTH_API_KEY_NOT_ACCEPTED",
]


def _connect_auth_error(code: int, message: str, connect_code: Code = Code.UNAUTHENTICATED):
    detail = auth_pb2.AuthErrorDetail(code=code, message=message)  # type: ignore[arg-type]
    return map_connect_error(ConnectError(connect_code, message, details=[detail]))


async def _rest_error(httpserver: HTTPServer, status: int, body: dict) -> BaseException:
    httpserver.expect_request(SPOT_CONFIG_PATH, method="POST").respond_with_data(
        json.dumps(body), status=status, content_type="application/problem+json"
    )
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        with pytest.raises(Exception) as caught:
            await AsyncMarketDataService(transport).get_spot_config()
    finally:
        await transport.aclose()
    return caught.value


@pytest.mark.parametrize("name", NEW_API_KEY_CODES)
def test_connect_api_key_refusals_are_auth_errors_with_their_code(name: str) -> None:
    mapped = _connect_auth_error(auth_pb2.AuthErrorCode.Value(name), "refused")

    assert isinstance(mapped, PolyesterAuthError)
    assert auth_error_code(mapped) == name
    assert mapped.status_code == 401
    assert str(mapped) == "refused"
    assert not is_retryable_error(mapped)


def test_connect_timestamp_skew_detail_is_the_retryable_skew_error() -> None:
    mapped = _connect_auth_error(auth_pb2.AUTH_TIMESTAMP_SKEW, "request timestamp is too far")

    assert isinstance(mapped, PolyesterTimestampSkewError)
    assert mapped.status_code == 401
    assert auth_error_code(mapped) == AUTH_TIMESTAMP_SKEW
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


def test_gateway_timestamp_skew_reads_the_same_auth_code() -> None:
    mapped = map_connect_error(ConnectError(Code.UNAUTHENTICATED, "TIMESTAMP_SKEW"))

    assert isinstance(mapped, PolyesterTimestampSkewError)
    assert auth_error_code(mapped) == AUTH_TIMESTAMP_SKEW


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "rest_code", "expected"),
    [
        (401, "SIGNATURE_INVALID", AUTH_SIGNATURE_INVALID),
        (403, "IP_NOT_ALLOWED", AUTH_IP_NOT_ALLOWED),
        (401, "UNAUTHENTICATED", AUTH_AUTHENTICATION_REQUIRED),
    ],
)
async def test_rest_problem_codes_map_to_the_same_auth_code(
    httpserver: HTTPServer, status: int, rest_code: str, expected: str
) -> None:
    error = await _rest_error(
        httpserver, status, {"status": status, "code": rest_code, "title": "Unauthorized"}
    )

    assert isinstance(error, PolyesterAuthError)
    assert auth_error_code(error) == expected
    assert error.status_code == status
    assert not is_retryable_error(error)


def test_auth_error_code_is_none_for_errors_without_an_auth_code() -> None:
    order_error = map_connect_error(
        ConnectError(
            Code.INVALID_ARGUMENT,
            "bad price",
            details=[orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_BAD_PRICE)],
        )
    )
    assert isinstance(order_error, PolyesterApiError)
    assert auth_error_code(order_error) is None
    assert auth_error_code(map_connect_error(ConnectError(Code.NOT_FOUND, "gone"))) is None
    assert auth_error_code(ValueError("x")) is None


def test_unknown_auth_code_number_does_not_crash() -> None:
    mapped = _connect_auth_error(999, "newer reason")

    assert isinstance(mapped, PolyesterApiError)
    assert auth_error_code(mapped) is None


def test_connect_session_kind_not_allowed_is_session_required() -> None:
    mapped = _connect_auth_error(
        auth_pb2.AUTH_SESSION_KIND_NOT_ALLOWED,
        "interactive session required",
        Code.PERMISSION_DENIED,
    )

    assert isinstance(mapped, PolyesterSessionRequiredError)
    # Both errors these refusals raised before still catch it.
    assert isinstance(mapped, PolyesterAuthError)
    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == AUTH_SESSION_KIND_NOT_ALLOWED
    assert mapped.status_code == 403
    assert str(mapped) == "interactive session required"
    assert is_session_required(mapped)
    assert not is_retryable_error(mapped)


@pytest.mark.asyncio
async def test_rest_session_kind_not_allowed_is_session_required(httpserver: HTTPServer) -> None:
    error = await _rest_error(
        httpserver,
        403,
        {
            "type": "https://polyester.dev/problems/auth-session-kind-not-allowed",
            "title": "Interactive Session Required",
            "status": 403,
            "detail": "interactive session required",
            "code": "AUTH_SESSION_KIND_NOT_ALLOWED",
        },
    )

    assert isinstance(error, PolyesterSessionRequiredError)
    assert error.status_code == 403
    assert str(error) == "interactive session required"
    assert auth_error_code(error) == AUTH_SESSION_KIND_NOT_ALLOWED


def test_connect_withdraw_policy_refusal_keeps_the_server_message() -> None:
    message = "api key policy does not allow READ_AUTO_WITHDRAW"
    mapped = map_connect_error(
        ConnectError(
            Code.PERMISSION_DENIED,
            message,
            details=[withdraw_pb2.ErrorDetail(code=withdraw_pb2.ERROR_CODE_PERMISSION_DENIED)],
        )
    )

    assert isinstance(mapped, PolyesterAuthError)
    assert str(mapped) == message


@pytest.mark.asyncio
async def test_rest_withdraw_policy_refusal_keeps_the_problem_detail(
    httpserver: HTTPServer,
) -> None:
    message = "api key policy does not allow EXTERNAL_WITHDRAW"
    error = await _rest_error(
        httpserver,
        403,
        {"status": 403, "title": "Forbidden", "code": "PERMISSION_DENIED", "detail": message},
    )

    assert isinstance(error, PolyesterAuthError)
    assert str(error) == message
    assert error.code == "PERMISSION_DENIED"
    assert error.status_code == 403


def test_connect_order_error_carries_its_field_violations() -> None:
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_QTY_STEP_SIZE)
    violation = detail.violations.add()
    violation.field_path = "order.base_qty_scaled"
    violation.rule_id = "step_size"
    violation.message = "quantity does not align with the pair step size"
    mapped = map_connect_error(ConnectError(Code.INVALID_ARGUMENT, "step", details=[detail]))

    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == "ERROR_CODE_QTY_STEP_SIZE"
    assert [(v.field_path, v.rule_id) for v in mapped.violations] == [
        ("order.base_qty_scaled", "step_size")
    ]


@pytest.mark.asyncio
async def test_rest_order_problem_carries_its_violations(httpserver: HTTPServer) -> None:
    error = await _rest_error(
        httpserver,
        400,
        {
            "type": "https://polyester.dev/problems/validation-error",
            "title": "Validation Error",
            "status": 400,
            "detail": "Quantity must align with the step size.",
            "code": "QTY_STEP_SIZE",
            "violations": [
                {
                    "fieldPath": "order.baseQty",
                    "ruleId": "step_size",
                    "message": "quantity does not align with the pair step size",
                }
            ],
        },
    )

    # A refused request, not a retryable server error.
    assert type(error) is PolyesterApiError
    assert not is_retryable_error(error)
    assert error.code == "ERROR_CODE_QTY_STEP_SIZE"
    assert str(error) == "Quantity must align with the step size."
    assert [(v.field_path, v.rule_id, v.message) for v in error.violations] == [
        ("order.baseQty", "step_size", "quantity does not align with the pair step size")
    ]


@pytest.mark.asyncio
async def test_rest_problem_without_violations_has_none(httpserver: HTTPServer) -> None:
    error = await _rest_error(
        httpserver,
        400,
        {"status": 400, "code": "VALIDATION_ERROR", "detail": "Request validation failed."},
    )

    assert isinstance(error, PolyesterApiError)
    assert error.code == "ERROR_CODE_VALIDATION_ERROR"
    assert error.violations == []
