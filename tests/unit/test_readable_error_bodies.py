"""An HTTP error with no recognised code proves nothing about a mutation.

Each case goes through a public read and a public create against a local server.
Only the requested procedure is counted, and every expectation needs at least
one request, so a case that never reached the server fails.
"""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import pytest

from polyester import AsyncPolyester, Quantity
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterError,
    PolyesterNotImplementedError,
    PolyesterRateLimitError,
    PolyesterRouteNotFoundError,
    PolyesterServerError,
    is_not_found,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

READ_PATH = "/triggers.v1.TriggersService/GetTrigger"
WRITE_PATH = "/orders.v1.OrdersService/CreateOrder"
JSON = "application/json"
PROBLEM = "application/problem+json"
CATALOG = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "rest_error_codes.json").read_text()
)["codes"]

# A body a gateway or an edge could send: nothing here names a contract code.
NO_CODE_BODIES = {
    "no-code": (JSON, '{"message":"m"}'),
    "empty-code": (JSON, '{"code":"","message":"m"}'),
    "null-code": (JSON, '{"code":null,"message":"m"}'),
    "int-code": (JSON, '{"code":5,"message":"m"}'),
    "empty-object": (JSON, "{}"),
    "problem-no-code": (PROBLEM, '{"title":"t","detail":"d"}'),
    "json-array": (JSON, "[1]"),
    "broken-json": (JSON, "{broken"),
    "unknown-detail": (JSON, '{"message":"m","details":[{"type":"x.y.Unknown","value":"AA"}]}'),
    "lowercase-code": (JSON, '{"code":"nope","message":"m"}'),
}
BARE_BODIES = {
    "html": ("text/html", "<html>oops</html>"),
    "text": ("text/plain", "oops"),
    "empty-text": ("text/plain", ""),
    "empty-json": (JSON, ""),
}
UNRECOGNISED = (PROBLEM, '{"code":"NOPE_NOT_A_CODE","detail":"d"}')
INTERNAL_STATUSES = [400, 402, 405, 409, 410, 412, 413, 418, 422, 431, 500, 501, 505, 520, 599]
UNAVAILABLE_STATUSES = [429, 502, 503, 504]


async def _call(
    op: str,
    status: int,
    content_type: str,
    body: str,
    *,
    fail_for: int | None = None,
    encoding: str | None = None,
) -> tuple[BaseException | None, int]:
    """Answer one public call with this response and return its error and requests made."""
    path = READ_PATH if op == "read" else WRITE_PATH
    calls = 0

    async def handler(req: ParsedRequest) -> HttpScript:
        nonlocal calls
        if req.method != "POST" or req.path != path:
            return HttpScript.not_found()
        calls += 1
        if fail_for is not None and calls > fail_for:
            return connect_proto_response(
                triggers.GetTriggerResponse(
                    trigger=triggers.Trigger(trigger_id=9)
                ).SerializeToString()
            )
        raw = gzip.compress(body.encode()) if encoding == "gzip" else body.encode()
        headers = [("Content-Type", content_type), ("Content-Length", str(len(raw)))]
        if encoding:
            headers.append(("Content-Encoding", encoding))
        return HttpScript.raw(status, headers=headers, body=raw)

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    try:
        if op == "read":
            await client.triggers.get(trigger_id="9")
        else:
            await client.orders.create(
                symbol="BTC-USDT",
                side="buy",
                order_type="market",
                qty=Quantity.from_scaled(1, scale=8),
            )
    except PolyesterError as exc:
        return exc, calls
    else:
        return None, calls
    finally:
        await client.aclose()
        await http.aclose()


def _assert_flags(error: BaseException | None, *, retryable: bool, unknown: bool) -> None:
    assert is_retryable_error(error) is retryable, repr(error)
    assert mutation_outcome_unknown(error) is unknown, repr(error)


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("status", INTERNAL_STATUSES)
@pytest.mark.parametrize(
    "shape",
    [
        *NO_CODE_BODIES,
        *BARE_BODIES,
        "unrecognised",
        "connect-unknown",
        "connect-data-loss",
        "connect-canceled",
    ],
)
async def test_no_recognised_code_is_a_server_error_with_outcome_unknown(
    op: str, status: int, shape: str
) -> None:
    content_type, body = {
        **NO_CODE_BODIES,
        **BARE_BODIES,
        "unrecognised": UNRECOGNISED,
        "connect-unknown": (JSON, '{"code":"unknown","message":"m"}'),
        "connect-data-loss": (JSON, '{"code":"data_loss","message":"m"}'),
        "connect-canceled": (JSON, '{"code":"canceled","message":"m"}'),
    }[shape]
    error, calls = await _call(op, status, content_type, body)
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    # Not unavailable, so a read doesn't retry it either.
    assert calls == 1
    if shape == "unrecognised":
        assert error.code == "NOPE_NOT_A_CODE"
        assert error.status_code == status
        assert error.problem is not None and error.problem.status == status


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("shape", list(NO_CODE_BODIES))
async def test_json_404_without_a_code_is_not_a_missing_route(op: str, shape: str) -> None:
    content_type, body = NO_CODE_BODIES[shape]
    error, calls = await _call(op, 404, content_type, body)
    assert type(error) is PolyesterServerError, repr(error)
    assert error.status_code == 404
    assert not is_not_found(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        *BARE_BODIES.values(),
        (JSON, '{"message":"404 page not found"}'),
        (JSON, '{"message":"Not Found"}'),
    ],
)
async def test_bare_404_stays_a_missing_route_with_outcome_unknown(
    op: str, content_type: str, body: str
) -> None:
    error, calls = await _call(op, 404, content_type, body)
    assert type(error) is PolyesterRouteNotFoundError, repr(error)
    assert isinstance(error, PolyesterNotImplementedError)
    assert not is_not_found(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("op", ["read", "write"])
async def test_unrecognised_404_code_is_kept_on_a_server_error(op: str) -> None:
    error, calls = await _call(op, 404, *UNRECOGNISED)
    assert type(error) is PolyesterServerError, repr(error)
    assert (error.code, error.status_code) == ("NOPE_NOT_A_CODE", 404)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize(
    "shape", [*NO_CODE_BODIES, *BARE_BODIES, "unrecognised", "connect-unknown"]
)
async def test_401_and_403_stay_definite_auth_refusals(op: str, status: int, shape: str) -> None:
    content_type, body = {
        **NO_CODE_BODIES,
        **BARE_BODIES,
        "unrecognised": UNRECOGNISED,
        "connect-unknown": (JSON, '{"code":"unknown","message":"m"}'),
    }[shape]
    error, calls = await _call(op, status, content_type, body)
    assert type(error) is PolyesterAuthError, repr(error)
    assert error.status_code == status
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
@pytest.mark.parametrize("shape", [*NO_CODE_BODIES, *BARE_BODIES])
async def test_unavailable_statuses_stay_unknown_and_send_a_create_once(
    status: int, shape: str
) -> None:
    content_type, body = {**NO_CODE_BODIES, **BARE_BODIES}[shape]
    error, calls = await _call("write", status, content_type, body)
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
@pytest.mark.parametrize("shape", [*NO_CODE_BODIES, *BARE_BODIES])
async def test_reads_still_retry_unavailable_statuses(status: int, shape: str) -> None:
    content_type, body = {**NO_CODE_BODIES, **BARE_BODIES}[shape]
    error, calls = await _call("read", status, content_type, body, fail_for=2)
    assert error is None, repr(error)
    assert calls == 3


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("code", ["FUTURE_CAPACITY", "NOPE_NOT_A_CODE"])
async def test_well_formed_unrecognised_429_stays_a_known_refusal(op: str, code: str) -> None:
    error, calls = await _call(op, 429, PROBLEM, json.dumps({"code": code, "detail": "d"}))
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == code
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("code", ["TRIGGER_NOT_FOUND", "not_found"])
async def test_trigger_not_found_keeps_its_typed_error(op: str, code: str) -> None:
    body = {"code": code, "detail": "d"} if code.isupper() else {"code": code, "message": "m"}
    error, calls = await _call(op, 404, PROBLEM if code.isupper() else JSON, json.dumps(body))
    assert type(error) is PolyesterApiError, repr(error)
    assert is_not_found(error)
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


PLACEHOLDER_CODES = ["UNSPECIFIED", "ERROR_CODE_UNSPECIFIED", "AUTH_UNSPECIFIED"]
DETAIL_TYPES = [
    "orders.v1.ErrorDetail",
    "auth.v1.AuthErrorDetail",
    "chain.withdraw.v1.ErrorDetail",
    "transfer.v1.ErrorDetail",
    "ledger.read.v1.ErrorDetail",
    "polyester.ratelimit.v1.RateLimitDetail",
]


def _detail_body(detail_type: str, value: bytes = b"", code: str | None = None) -> str:
    body: dict[str, object] = {
        "message": "m",
        "details": [{"type": detail_type, "value": base64.b64encode(value).decode()}],
    }
    if code is not None:
        body["code"] = code
    return json.dumps(body)


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("code", PLACEHOLDER_CODES)
@pytest.mark.parametrize("status", [*INTERNAL_STATUSES, 404])
async def test_placeholder_code_is_no_code(op: str, code: str, status: int) -> None:
    body = json.dumps({"code": code, "detail": "d"})
    error, calls = await _call(op, status, PROBLEM, body)
    assert type(error) is PolyesterServerError, repr(error)
    assert error.code is None
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("code", PLACEHOLDER_CODES)
@pytest.mark.parametrize("status", [401, 403])
async def test_placeholder_code_keeps_a_definite_auth_refusal(code: str, status: int) -> None:
    error, calls = await _call("write", status, PROBLEM, json.dumps({"code": code}))
    assert type(error) is PolyesterAuthError, repr(error)
    assert error.status_code == status
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


@pytest.mark.parametrize("code", PLACEHOLDER_CODES)
@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
async def test_placeholder_code_at_unavailable_statuses(code: str, status: int) -> None:
    body = json.dumps({"code": code})
    error, calls = await _call("write", status, PROBLEM, body)
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1
    error, calls = await _call("read", status, PROBLEM, body, fail_for=2)
    assert error is None, repr(error)
    assert calls == 3


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("detail_type", DETAIL_TYPES)
@pytest.mark.parametrize("status", [*INTERNAL_STATUSES, 404])
async def test_empty_detail_is_no_code(op: str, detail_type: str, status: int) -> None:
    error, calls = await _call(op, status, JSON, _detail_body(detail_type))
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("detail_type", DETAIL_TYPES)
@pytest.mark.parametrize("status", [400, 404, 409, 500])
async def test_undecodable_detail_is_no_code(op: str, detail_type: str, status: int) -> None:
    body = _detail_body(detail_type, b"\x00")
    error, calls = await _call(op, status, JSON, body)
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("detail_type", DETAIL_TYPES)
@pytest.mark.parametrize("status", [401, 403])
async def test_empty_detail_keeps_a_definite_auth_refusal(detail_type: str, status: int) -> None:
    error, calls = await _call("write", status, JSON, _detail_body(detail_type))
    assert type(error) is PolyesterAuthError, repr(error)
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


@pytest.mark.parametrize("detail_type", DETAIL_TYPES)
@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
async def test_empty_detail_at_unavailable_statuses(detail_type: str, status: int) -> None:
    error, calls = await _call("write", status, JSON, _detail_body(detail_type))
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("detail_type", DETAIL_TYPES)
@pytest.mark.parametrize(
    ("status", "connect_code"),
    [(500, "internal"), (500, "unknown"), (500, "data_loss"), (503, "unavailable")],
)
async def test_empty_detail_does_not_turn_a_server_failure_into_a_refusal(
    detail_type: str, status: int, connect_code: str
) -> None:
    error, calls = await _call("write", status, JSON, _detail_body(detail_type, code=connect_code))
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("detail_type", DETAIL_TYPES)
@pytest.mark.parametrize(
    ("status", "connect_code"),
    [(400, "invalid_argument"), (404, "not_found"), (409, "already_exists")],
)
async def test_recognised_connect_code_stands_without_its_empty_detail(
    detail_type: str, status: int, connect_code: str
) -> None:
    error, calls = await _call("write", status, JSON, _detail_body(detail_type, code=connect_code))
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == connect_code
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


@pytest.mark.parametrize(
    "body",
    [
        _detail_body("orders.v1.ErrorDetail", code="resource_exhausted"),
        json.dumps({"code": "resource_exhausted", "message": "ERROR_CODE_UNSPECIFIED"}),
        json.dumps({"code": "resource_exhausted", "message": "UNSPECIFIED"}),
    ],
)
async def test_placeholder_does_not_name_a_resource_refusal(body: str) -> None:
    error, calls = await _call("write", 429, JSON, body)
    assert type(error) is PolyesterRateLimitError, repr(error)
    assert error.code is None
    assert calls == 1


@pytest.mark.parametrize("status", [400, 500])
async def test_real_typed_detail_is_still_a_code_control(status: int) -> None:
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_BAD_PRICE)
    body = _detail_body("orders.v1.ErrorDetail", detail.SerializeToString())
    error, calls = await _call("write", status, JSON, body)
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == "ERROR_CODE_BAD_PRICE"
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


async def test_connect_refusal_code_at_500_stays_known_control() -> None:
    error, calls = await _call("write", 500, JSON, '{"code":"invalid_argument","message":"m"}')
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == "invalid_argument"
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


async def test_backoff_detail_without_a_code_stays_a_rate_limit_control() -> None:
    backoff = ratelimit_pb2.RateLimitDetail(retry_after_ms=1250)
    for body in (
        _detail_body(
            "orders.v1.ErrorDetail",
            orders_pb2.ErrorDetail(rate_limit=backoff).SerializeToString(),
            code="resource_exhausted",
        ),
        _detail_body(
            "polyester.ratelimit.v1.RateLimitDetail",
            backoff.SerializeToString(),
            code="resource_exhausted",
        ),
    ):
        error, calls = await _call("write", 429, JSON, body)
        assert type(error) is PolyesterRateLimitError, repr(error)
        assert error.retry_after == 1.25
        _assert_flags(error, retryable=True, unknown=False)
        assert calls == 1


async def test_placeholder_detail_keeps_field_violations_on_a_recognised_code() -> None:
    detail = orders_pb2.ErrorDetail(
        violations=[orders_pb2.FieldViolation(field_path="x", rule_id="r", message="v")]
    )
    raw = detail.SerializeToString()
    error, calls = await _call(
        "write", 400, JSON, _detail_body("orders.v1.ErrorDetail", raw, code="invalid_argument")
    )
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == "invalid_argument"
    assert [item.field_path for item in error.violations] == ["x"]
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1
    error, calls = await _call("write", 500, JSON, _detail_body("orders.v1.ErrorDetail", raw))
    assert type(error) is PolyesterServerError, repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


# Code 999999, in the first field of every coded detail: an enum this SDK can't
# name. It could be a future refusal or a future unknown outcome.
FUTURE_CODE = bytes([0x08, 0xBF, 0x84, 0x3D])
CODED_DETAIL_TYPES = DETAIL_TYPES[:-1]


@pytest.mark.parametrize("op", ["read", "write"])
@pytest.mark.parametrize("detail_type", CODED_DETAIL_TYPES)
@pytest.mark.parametrize("status", [400, 404, 409, 500, 501, 520])
async def test_future_typed_code_with_no_connect_code_proves_nothing(
    op: str, detail_type: str, status: int
) -> None:
    error, calls = await _call(op, status, JSON, _detail_body(detail_type, FUTURE_CODE))
    assert type(error) is PolyesterServerError, repr(error)
    assert error.code == "UNKNOWN_ERROR_CODE(999999)"
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("detail_type", CODED_DETAIL_TYPES)
@pytest.mark.parametrize(
    ("status", "connect_code"),
    [
        (500, "internal"),
        (500, "unknown"),
        (500, "data_loss"),
        (500, "canceled"),
        (503, "unavailable"),
        (504, "deadline_exceeded"),
    ],
)
async def test_future_typed_code_does_not_turn_a_server_failure_into_a_refusal(
    detail_type: str, status: int, connect_code: str
) -> None:
    body = _detail_body(detail_type, FUTURE_CODE, code=connect_code)
    error, calls = await _call("write", status, JSON, body)
    assert not isinstance(error, PolyesterApiError), repr(error)
    if isinstance(error, PolyesterServerError):
        assert error.code == "UNKNOWN_ERROR_CODE(999999)"
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("detail_type", CODED_DETAIL_TYPES)
@pytest.mark.parametrize("connect_code", ["internal", "unknown", "data_loss"])
async def test_read_of_a_future_typed_code_on_a_server_failure_sends_once(
    detail_type: str, connect_code: str
) -> None:
    body = _detail_body(detail_type, FUTURE_CODE, code=connect_code)
    error, calls = await _call("read", 500, JSON, body)
    assert type(error) is PolyesterServerError, repr(error)
    assert error.code == "UNKNOWN_ERROR_CODE(999999)"
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("detail_type", CODED_DETAIL_TYPES)
async def test_read_retries_a_future_typed_code_on_unavailable(detail_type: str) -> None:
    body = _detail_body(detail_type, FUTURE_CODE, code="unavailable")
    error, calls = await _call("read", 503, JSON, body, fail_for=2)
    assert error is None, repr(error)
    assert calls == 3


async def test_future_typed_code_with_backoff_is_not_retryable_on_a_server_failure() -> None:
    backoff = ratelimit_pb2.RateLimitDetail(retry_after_ms=1250).SerializeToString()
    # Field 3 of orders.v1.ErrorDetail carries the backoff.
    raw = FUTURE_CODE + bytes([0x1A, len(backoff)]) + backoff
    for body in (
        _detail_body("orders.v1.ErrorDetail", raw),
        _detail_body("orders.v1.ErrorDetail", raw, code="internal"),
    ):
        error, calls = await _call("write", 500, JSON, body)
        assert type(error) is PolyesterServerError, repr(error)
        _assert_flags(error, retryable=False, unknown=True)
        assert calls == 1


@pytest.mark.parametrize("detail_type", CODED_DETAIL_TYPES)
@pytest.mark.parametrize(
    ("status", "connect_code"),
    [(400, "failed_precondition"), (400, "invalid_argument"), (409, "already_exists")],
)
async def test_future_typed_code_keeps_its_label_on_a_recognised_refusal_control(
    detail_type: str, status: int, connect_code: str
) -> None:
    body = _detail_body(detail_type, FUTURE_CODE, code=connect_code)
    error, calls = await _call("write", status, JSON, body)
    assert isinstance(error, PolyesterApiError), repr(error)
    assert "999999" in str(error.code), repr(error)
    _assert_flags(error, retryable=False, unknown=False)
    assert calls == 1


@pytest.mark.parametrize("encoding", ["br", "zstd"])
@pytest.mark.parametrize("status", [400, 404, 409, 429, 500, 503, 504])
async def test_body_the_client_cannot_decode_is_not_a_known_failure(
    encoding: str, status: int
) -> None:
    body = '{"code":"BAD_PRICE"}'
    error, calls = await _call("write", status, PROBLEM, body, encoding=encoding)
    assert isinstance(error, PolyesterServerError | PolyesterRouteNotFoundError), repr(error)
    _assert_flags(error, retryable=False, unknown=True)
    assert calls == 1


@pytest.mark.parametrize("encoding", ["identity", "gzip"])
@pytest.mark.parametrize(
    ("status", "content_type", "body", "expected", "code", "unknown"),
    [
        (
            400,
            JSON,
            '{"code":"invalid_argument","message":"m"}',
            PolyesterApiError,
            "invalid_argument",
            False,
        ),
        (404, JSON, '{"code":"not_found","message":"m"}', PolyesterApiError, "not_found", False),
        (
            400,
            PROBLEM,
            '{"code":"BAD_PRICE","detail":"d"}',
            PolyesterApiError,
            "ERROR_CODE_BAD_PRICE",
            False,
        ),
        (500, JSON, '{"message":"m"}', PolyesterServerError, None, True),
        (500, PROBLEM, '{"code":"NOPE_NOT_A_CODE"}', PolyesterServerError, "NOPE_NOT_A_CODE", True),
        (
            404,
            "text/plain",
            "404 page not found",
            PolyesterRouteNotFoundError,
            "route_not_found",
            True,
        ),
    ],
)
async def test_compression_neither_hides_a_code_nor_invents_one(
    encoding: str,
    status: int,
    content_type: str,
    body: str,
    expected: type[PolyesterError],
    code: str | None,
    unknown: bool,
) -> None:
    error, calls = await _call("write", status, content_type, body, encoding=encoding)
    assert type(error) is expected, repr(error)
    assert error.code == code
    _assert_flags(error, retryable=False, unknown=unknown)
    assert calls == 1


@pytest.mark.parametrize(
    "entry", CATALOG, ids=lambda entry: f"{entry['status']}-{entry['code']}-{entry['connect']}"
)
async def test_every_contract_code_keeps_its_meaning_on_a_create(entry: dict) -> None:
    """REST form, from the published catalog. Sent once, code kept, never a guess by status."""
    code, status = entry["code"], entry["status"]
    error, calls = await _call("write", status, PROBLEM, json.dumps({"code": code, "detail": "d"}))
    assert calls == 1
    assert error is not None
    assert str(getattr(error, "code", None) or "") != "unknown", repr(error)
    if status == 501:
        assert isinstance(error, PolyesterNotImplementedError), repr(error)
        _assert_flags(error, retryable=False, unknown=False)
    elif status == 500:
        assert type(error) is PolyesterServerError, repr(error)
        assert error.status_code == 500
        _assert_flags(error, retryable=False, unknown=True)
    elif status == 504:
        _assert_flags(error, retryable=False, unknown=True)
    elif status < 500:
        assert not isinstance(error, PolyesterServerError), repr(error)
        assert not mutation_outcome_unknown(error), repr(error)
