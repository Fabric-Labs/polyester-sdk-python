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


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"message": 5}, id="no-code-message-int"),
        pytest.param({"code": "", "message": 5}, id="empty-code-message-int"),
        pytest.param({"code": None, "message": ["m"]}, id="null-code-message-list"),
        pytest.param({"code": 5, "message": 5}, id="int-code-message-int"),
        pytest.param({"details": [1]}, id="no-code-detail-int"),
        pytest.param({"code": "", "details": "nope"}, id="empty-code-details-string"),
        pytest.param({"code": None, "details": 5}, id="null-code-details-int"),
        pytest.param(
            {"details": [{"type": ORDER_DETAIL, "value": "a"}]}, id="no-code-value-bad-base64"
        ),
    ],
)
async def test_malformed_body_without_a_connect_code_is_ambiguous(body: object) -> None:
    error, calls = await _status_error(400, body)
    assert calls == 1
    assert type(error) is PolyesterServerError
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)
    assert str(error) == "400 Bad Request"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"details": [1]}, id="no-code-detail-int"),
        pytest.param({"message": "m", "details": [1]}, id="no-code-readable-message"),
        pytest.param({"message": 5}, id="no-code-message-int"),
        pytest.param({"code": "internal", "details": [1]}, id="internal-detail-int"),
        pytest.param({"code": "invalid_argument", "details": [1]}, id="refusal-code-detail-int"),
    ],
)
@pytest.mark.parametrize(
    "status", [400, 402, 404, 405, 409, 412, 418, 422, 429, 431, 500, 501, 502, 503, 505, 520]
)
async def test_unreadable_body_proves_nothing_at_other_statuses(status: int, body: object) -> None:
    """Only a definite 401 or 403 survives an unreadable body; the rest stays ambiguous."""
    error, calls = await _status_error(status, body)
    assert calls == 1
    assert type(error) is PolyesterServerError
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)
    assert str(error).startswith(str(status))


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        pytest.param(
            401, {"code": "unauthenticated", "details": "nope"}, "401 Unauthorized", id="401-coded"
        ),
        pytest.param(401, {"message": 5}, "401 Unauthorized", id="401-no-code"),
        pytest.param(401, {"code": "", "details": [1]}, "401 Unauthorized", id="401-empty-code"),
        pytest.param(403, {"code": None, "message": ["m"]}, "403 Forbidden", id="403-null-code"),
    ],
)
async def test_malformed_body_keeps_a_definite_http_refusal(
    status: int, body: object, message: str
) -> None:
    error, calls = await _status_error(status, body)
    assert calls == 1
    assert type(error) is PolyesterAuthError
    assert error.status_code == status
    assert str(error) == message
    assert not mutation_outcome_unknown(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize(
    ("status", "body", "expected", "message"),
    [
        pytest.param(400, {"message": "m"}, PolyesterServerError, "m", id="400-no-code"),
        pytest.param(400, {"code": "", "message": "m"}, PolyesterServerError, "m", id="400-empty"),
        pytest.param(400, {"code": None, "details": []}, PolyesterServerError, None, id="400-null"),
        pytest.param(400, {"code": 5, "message": "m"}, PolyesterServerError, "m", id="400-int"),
        pytest.param(401, {"message": "m"}, PolyesterAuthError, "m", id="401-no-code"),
        pytest.param(504, {"message": 5}, PolyesterServerError, None, id="504-gateway"),
        pytest.param(
            500, {"code": "internal", "message": "m"}, PolyesterServerError, "m", id="500-internal"
        ),
        pytest.param(
            503, {"code": "unavailable", "message": "m"}, PolyesterServerError, "m", id="503-coded"
        ),
        pytest.param(
            401, {"code": "unauthenticated", "message": "m"}, PolyesterAuthError, "m", id="401-ok"
        ),
    ],
)
async def test_readable_fallback_body_is_unchanged_control(
    status: int, body: object, expected: type[PolyesterError], message: str | None
) -> None:
    error, calls = await _status_error(status, body)
    assert calls == 1
    assert type(error) is expected
    if message is not None:
        assert str(error) == message


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
