"""Uniform request-size and rate-limit answers, and the wallet-already-linked
login refusal, read the same over ConnectRPC and REST (contract 1bf038e)."""

from __future__ import annotations

import base64
import json

import pytest
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import (
    AUTH_WALLET_ALREADY_LINKED,
    REQUEST_TOO_LARGE,
    PolyesterApiError,
    PolyesterRateLimitError,
    auth_error_code,
    is_request_too_large,
    is_retryable_error,
    is_wallet_already_linked,
    mutation_outcome_unknown,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2
from polyester.models.ratelimit import RateLimitDetail
from polyester.services.changelog import AsyncChangelogService
from polyester.transport import TransportConfig, TransportFactory
from tests.unit.test_auth_error_codes import _rest_error

REQUEST_TOO_LARGE_PROBLEM = {
    "type": "https://polyester.dev/problems/request-too-large",
    "title": "Request Entity Too Large",
    "status": 413,
    "detail": "request too large",
    "code": "REQUEST_TOO_LARGE",
}
GET_POST_PATH = "/changelog.v1.ChangelogService/GetPost"


def _too_large_handler(chunked: bool):
    body = json.dumps(REQUEST_TOO_LARGE_PROBLEM).encode()

    def handle(_request: Request) -> Response:
        # The refusal precedes reading the body, as the API's does.
        if chunked:
            return Response(
                iter([body[:20], body[20:]]),
                status=413,
                content_type="application/problem+json",
            )
        return Response(body, status=413, content_type="application/problem+json")

    return handle


def _assert_request_too_large(error: BaseException) -> None:
    assert isinstance(error, PolyesterApiError), repr(error)
    assert not isinstance(error, PolyesterRateLimitError)
    assert error.code == REQUEST_TOO_LARGE
    assert is_request_too_large(error)
    assert error.problem is not None
    assert error.problem.status == 413
    assert error.problem.code == "REQUEST_TOO_LARGE"
    assert error.problem.type == "https://polyester.dev/problems/request-too-large"
    assert error.problem.detail == "request too large"
    # Refused before it was read: nothing changed, and the same body is
    # refused again.
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize("chunked", [False, True])
@pytest.mark.parametrize("slug_bytes", [8, 4 << 20])
async def test_request_too_large_problem_is_a_typed_refusal(
    httpserver: HTTPServer, chunked: bool, slug_bytes: int
) -> None:
    httpserver.expect_request(GET_POST_PATH, method="POST").respond_with_handler(
        _too_large_handler(chunked)
    )
    transport = TransportFactory(TransportConfig(api_url=httpserver.url_for("").rstrip("/")))
    try:
        with pytest.raises(Exception) as caught:
            await AsyncChangelogService(transport).get_post("x" * slug_bytes)
    finally:
        await transport.aclose()
    _assert_request_too_large(caught.value)


RATE_LIMIT_PROBLEM = {
    "code": "RATE_LIMIT_EXCEEDED",
    "detail": "Rate limit exceeded",
    "status": 429,
    "title": "Rate limit exceeded",
    "type": "https://polyester.dev/problems/rate-limit-exceeded",
}


@pytest.mark.parametrize(
    "rate_limit,headers,detail,retry_after",
    [
        pytest.param(
            {
                "reason": "QUOTA_EXCEEDED",
                "limit": "30",
                "remaining": "0",
                "retry_after_ms": "1409",
                "policy_version": "5",
                "operation_id": "auth.wallet_challenge",
                "policy_class": "AUTH_PUBLIC",
                "scope": "AUTH_SUBJECT",
                "refill_model": "CONTINUOUS",
            },
            {
                "Retry-After": "2",
                "RateLimit-Limit": "30",
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": "2",
            },
            RateLimitDetail(
                reason="QUOTA_EXCEEDED",
                limit=30,
                remaining=0,
                retry_after_ms=1409,
                policy_version=5,
                operation_id="auth.wallet_challenge",
                policy_class="AUTH_PUBLIC",
                scope="AUTH_SUBJECT",
                refill_model="CONTINUOUS",
            ),
            1.409,
            id="service quota",
        ),
        pytest.param(
            {"reason": "QUOTA_EXCEEDED", "scope": "CLIENT_IP"},
            {
                "Retry-After": "59",
                "X-RateLimit-Limit": "30",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "59",
            },
            RateLimitDetail(reason="QUOTA_EXCEEDED", scope="CLIENT_IP"),
            59.0,
            id="gateway window",
        ),
        pytest.param(
            {"reason": "QUOTA_EXCEEDED", "scope": "CLIENT_IP"},
            None,
            RateLimitDetail(reason="QUOTA_EXCEEDED", scope="CLIENT_IP"),
            None,
            id="gateway concurrency",
        ),
        pytest.param(
            {"reason": "SOME_NEW_REASON", "limit": 30, "retry_after_ms": 250},
            None,
            RateLimitDetail(reason="SOME_NEW_REASON", limit=30, retry_after_ms=250),
            0.25,
            id="numbers and a newer enum value",
        ),
    ],
)
async def test_rate_limit_problem_carries_its_detail(
    httpserver: HTTPServer, rate_limit, headers, detail, retry_after
) -> None:
    error = await _rest_error(
        httpserver, 429, {**RATE_LIMIT_PROBLEM, "rate_limit": rate_limit}, headers=headers
    )
    assert isinstance(error, PolyesterRateLimitError), repr(error)
    assert error.code == "ERROR_CODE_RATE_LIMIT_EXCEEDED"
    assert error.detail == detail
    assert error.retry_after == retry_after
    assert is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


async def test_auth_resource_exhausted_problem_is_not_a_rate_limit(httpserver: HTTPServer) -> None:
    error = await _rest_error(
        httpserver,
        429,
        {
            "code": "AUTH_RESOURCE_EXHAUSTED",
            "detail": "no new account can be created",
            "status": 429,
            "title": "Resource Exhausted",
            "type": "https://polyester.dev/problems/auth-resource-exhausted",
        },
    )
    assert not isinstance(error, PolyesterRateLimitError)
    assert isinstance(error, PolyesterApiError)
    assert error.code == "AUTH_RESOURCE_EXHAUSTED"
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize(
    "headers,retry_after",
    [
        ({"Retry-After": "59", "X-RateLimit-Limit": "30", "X-RateLimit-Remaining": "0"}, 59.0),
        (None, None),
    ],
)
async def test_gateway_connect_refusal_falls_back_to_retry_after(
    httpserver: HTTPServer, headers, retry_after
) -> None:
    error = await _rest_error(
        httpserver,
        429,
        {"code": "resource_exhausted", "message": "rate limit exceeded, retry later"},
        content_type="application/json",
        headers=headers,
    )
    assert isinstance(error, PolyesterRateLimitError), repr(error)
    assert error.detail is None
    assert error.retry_after == retry_after
    assert is_retryable_error(error)


async def test_connect_rate_limit_detail_is_typed_retry_information(
    httpserver: HTTPServer,
) -> None:
    detail = types_pb2.RateLimitDetail(
        reason=types_pb2.QUOTA_EXCEEDED,
        limit=30,
        retry_after_ms=1409,
        operation_id="auth.wallet_challenge",
        policy_class=types_pb2.AUTH_PUBLIC,
        scope=types_pb2.AUTH_SUBJECT,
    )
    error = await _rest_error(
        httpserver,
        429,
        {
            "code": "resource_exhausted",
            "message": "rate limit exceeded",
            "details": [
                {
                    "type": "polyester.ratelimit.v1.RateLimitDetail",
                    "value": base64.b64encode(detail.SerializeToString()).decode(),
                }
            ],
        },
        content_type="application/json",
        headers={"Retry-After": "2"},
    )
    assert isinstance(error, PolyesterRateLimitError), repr(error)
    assert isinstance(error.detail, RateLimitDetail)
    assert error.detail.scope == "AUTH_SUBJECT"
    assert error.detail.operation_id == "auth.wallet_challenge"
    assert error.retry_after == 1.409


WALLET_LINKED_MESSAGE = (
    "this wallet is already linked to another account; "
    "log in with the account address it already uses"
)


@pytest.mark.parametrize("protocol", ["connect", "rest"])
async def test_wallet_already_linked_is_a_terminal_auth_refusal(
    httpserver: HTTPServer, protocol: str
) -> None:
    if protocol == "connect":
        detail = auth_pb2.AuthErrorDetail(
            code=auth_pb2.AuthErrorCode.Value("AUTH_WALLET_ALREADY_LINKED"),
            message=WALLET_LINKED_MESSAGE,
        )
        body = {
            "code": "already_exists",
            "message": WALLET_LINKED_MESSAGE,
            "details": [
                {
                    "type": "auth.v1.AuthErrorDetail",
                    "value": base64.b64encode(detail.SerializeToString()).decode(),
                }
            ],
        }
        content_type = "application/json"
    else:
        body = {
            "status": 409,
            "code": "AUTH_WALLET_ALREADY_LINKED",
            "title": "Wallet Already Linked",
            "type": "https://polyester.dev/problems/auth-wallet-already-linked",
            "detail": WALLET_LINKED_MESSAGE,
        }
        content_type = "application/problem+json"
    error = await _rest_error(httpserver, 409, body, content_type=content_type)
    assert auth_error_code(error) == AUTH_WALLET_ALREADY_LINKED, repr(error)
    assert is_wallet_already_linked(error)
    assert str(error) == WALLET_LINKED_MESSAGE
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


def test_request_size_and_wallet_predicates_read_only_their_codes() -> None:
    assert not is_request_too_large(PolyesterApiError("x", code="PAYLOAD_TOO_LARGE"))
    assert not is_request_too_large(PolyesterRateLimitError("x", code="REQUEST_TOO_LARGE"))
    assert not is_wallet_already_linked(PolyesterApiError("x", code="AUTH_WALLET_LOGIN_FAILED"))
    assert is_wallet_already_linked(PolyesterApiError("x", code="AUTH_WALLET_ALREADY_LINKED"))
