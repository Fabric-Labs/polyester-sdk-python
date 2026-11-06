"""A malformed Connect error body surfaces as an SDK error, never a raw exception."""

from __future__ import annotations

import base64
import json

import pytest

from polyester import AsyncPolyester
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterError,
    PolyesterRateLimitError,
    PolyesterServerError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

STATUS_PATH = "/orders.v1.OrdersReadService/GetBatchReplaceStatus"
GARBAGE = base64.b64encode(b"\xff\xff\xff").decode()
ORDER_DETAIL = "orders.v1.ErrorDetail"


async def _status_error(status: int, body: object) -> tuple[BaseException, int]:
    """Read through the public client and return its error and the reads made."""
    calls = 0

    async def handler(req: ParsedRequest) -> HttpScript:
        nonlocal calls
        if req.method != "POST" or req.path != STATUS_PATH:
            return HttpScript.not_found()
        calls += 1
        return HttpScript.json(status, json.dumps(body).encode())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(BaseException) as raised:
            await client.orders.get_batch_replace_status(batch_request_id="1")
        return raised.value, calls
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        # The body names a Connect code, and its detail bytes can't be decoded:
        # the code still stands, without the detail.
        pytest.param(
            400,
            {
                "code": "invalid_argument",
                "message": "m",
                "details": [{"type": ORDER_DETAIL, "value": GARBAGE}],
            },
            PolyesterApiError,
            id="order-detail-bytes",
        ),
        pytest.param(
            401,
            {
                "code": "unauthenticated",
                "message": "m",
                "details": [{"type": "auth.v1.AuthErrorDetail", "value": GARBAGE}],
            },
            PolyesterAuthError,
            id="auth-detail-bytes",
        ),
        pytest.param(
            429,
            {
                "code": "resource_exhausted",
                "message": "m",
                "details": [{"type": ORDER_DETAIL, "value": GARBAGE}],
            },
            PolyesterRateLimitError,
            id="rate-limit-detail-bytes",
        ),
    ],
)
async def test_undecodable_detail_keeps_the_connect_code(
    status: int, body: object, expected: type[PolyesterError]
) -> None:
    error, calls = await _status_error(status, body)
    assert calls == 1
    assert type(error) is expected
    assert str(error) == "m"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"code": "invalid_argument", "message": 5}, id="message-int"),
        pytest.param({"code": "invalid_argument", "message": ["m"]}, id="message-list"),
        pytest.param({"code": "invalid_argument", "details": "nope"}, id="details-string"),
        pytest.param({"code": "invalid_argument", "details": 5}, id="details-int"),
        pytest.param({"code": "invalid_argument", "details": [1]}, id="detail-int"),
        pytest.param(
            {"code": "invalid_argument", "details": [{"type": ORDER_DETAIL, "value": 123}]},
            id="value-int",
        ),
        pytest.param(
            {"code": "invalid_argument", "details": [{"type": 5, "value": "AA"}]},
            id="type-int",
        ),
        pytest.param(
            {"code": "invalid_argument", "details": [{"type": ORDER_DETAIL, "value": "a"}]},
            id="value-bad-base64",
        ),
    ],
)
async def test_malformed_envelope_is_an_ambiguous_server_error(body: object) -> None:
    error, calls = await _status_error(400, body)
    assert calls == 1
    assert type(error) is PolyesterServerError
    # Not a readable Connect error, so it can't prove a refusal, and the
    # message is the HTTP status rather than a Python internal.
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)
    assert str(error) == "400 Bad Request"


async def test_malformed_envelope_keeps_a_definite_http_status() -> None:
    error, calls = await _status_error(401, {"code": "unauthenticated", "details": "nope"})
    assert calls == 1
    assert type(error) is PolyesterAuthError
    assert str(error) == "401 Unauthorized"


async def test_well_formed_error_is_unchanged_control() -> None:
    error, calls = await _status_error(400, {"code": "invalid_argument", "message": "m"})
    assert calls == 1
    assert type(error) is PolyesterApiError
    assert error.code == "invalid_argument"
    assert not mutation_outcome_unknown(error)


async def test_detail_missing_a_value_is_still_ignored_control() -> None:
    error, calls = await _status_error(
        400, {"code": "invalid_argument", "message": "m", "details": [{"type": ORDER_DETAIL}]}
    )
    assert calls == 1
    assert type(error) is PolyesterApiError
    assert str(error) == "m"
