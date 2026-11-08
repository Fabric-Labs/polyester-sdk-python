"""Receive-window, replay-capacity and request-deadline refusals are typed by
their retry rule over ConnectRPC and REST alike (contract c8d9827)."""

from __future__ import annotations

import base64

import pytest
from pytest_httpserver import HTTPServer

from polyester import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRateLimitError,
    auth_error_code,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.orders.v1 import orders_pb2
from tests.unit.test_auth_error_codes import _rest_error


def _connect_body(code: str, message: str, type_name: str, detail) -> dict:
    return {
        "code": code,
        "message": message,
        "details": [
            {"type": type_name, "value": base64.b64encode(detail.SerializeToString()).decode()}
        ],
    }


REPLAY_MESSAGE = "replay capacity exhausted for this API key"


@pytest.mark.parametrize(
    ("protocol", "headers", "retry_after"),
    [("connect", None, None), ("rest", None, None), ("rest", {"Retry-After": "1"}, 1.0)],
)
async def test_replay_capacity_exhausted_is_a_retryable_rate_refusal(
    httpserver: HTTPServer, protocol: str, headers: dict | None, retry_after: float | None
) -> None:
    # Valid credentials and nothing processed: the key's share of the replay
    # record frees as earlier windows end, so it is a rate refusal, never an
    # authentication failure or an unknown outcome.
    if protocol == "connect":
        body = _connect_body(
            "resource_exhausted",
            REPLAY_MESSAGE,
            "auth.v1.AuthErrorDetail",
            auth_pb2.AuthErrorDetail(
                code=auth_pb2.AuthErrorCode.Value("AUTH_REPLAY_CAPACITY_EXHAUSTED"),
                message=REPLAY_MESSAGE,
            ),
        )
        content_type = "application/json"
    else:
        body = {"status": 429, "code": "REPLAY_CAPACITY_EXHAUSTED", "detail": REPLAY_MESSAGE}
        content_type = "application/problem+json"
    error = await _rest_error(httpserver, 429, body, content_type=content_type, headers=headers)
    assert isinstance(error, PolyesterRateLimitError), repr(error)
    assert not isinstance(error, PolyesterAuthError)
    assert error.code == "AUTH_REPLAY_CAPACITY_EXHAUSTED"
    assert auth_error_code(error) == "AUTH_REPLAY_CAPACITY_EXHAUSTED"
    assert error.retry_after == retry_after
    assert is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize("protocol", ["connect", "rest"])
async def test_recv_window_invalid_is_a_terminal_auth_refusal(
    httpserver: HTTPServer, protocol: str
) -> None:
    message = "X-API-RECV-WINDOW must be an integer from 1 to 60000"
    if protocol == "connect":
        body = _connect_body(
            "unauthenticated",
            message,
            "auth.v1.AuthErrorDetail",
            auth_pb2.AuthErrorDetail(
                code=auth_pb2.AuthErrorCode.Value("AUTH_RECV_WINDOW_INVALID"), message=message
            ),
        )
        content_type = "application/json"
    else:
        body = {"status": 401, "code": "RECV_WINDOW_INVALID", "detail": message}
        content_type = "application/problem+json"
    error = await _rest_error(httpserver, 401, body, content_type=content_type)
    assert isinstance(error, PolyesterAuthError), repr(error)
    assert error.status_code == 401
    assert auth_error_code(error) == "AUTH_RECV_WINDOW_INVALID"
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize("protocol", ["connect", "rest"])
async def test_request_deadline_exceeded_is_retryable_and_known(
    httpserver: HTTPServer, protocol: str
) -> None:
    # The write's window ended before admission: nothing changed, and a retry
    # signs it again with a fresh timestamp.
    message = "request deadline exceeded before admission"
    if protocol == "connect":
        body = _connect_body(
            "failed_precondition",
            message,
            "orders.v1.ErrorDetail",
            orders_pb2.ErrorDetail(
                code=orders_pb2.ErrorCode.Value("ERROR_CODE_REQUEST_DEADLINE_EXCEEDED")
            ),
        )
        content_type = "application/json"
    else:
        body = {"status": 400, "code": "REQUEST_DEADLINE_EXCEEDED", "detail": message}
        content_type = "application/problem+json"
    error = await _rest_error(httpserver, 400, body, content_type=content_type)
    assert isinstance(error, PolyesterApiError), repr(error)
    assert error.code == "ERROR_CODE_REQUEST_DEADLINE_EXCEEDED"
    assert is_retryable_error(error)
    assert not mutation_outcome_unknown(error)
