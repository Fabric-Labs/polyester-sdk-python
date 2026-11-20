"""Public contract 6c18dd0 (0.93.6): cancel-all that stops triggers, the typed answer to
an oversized ConnectRPC request, and the other handwritten follow-ups."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.codecs.decode.orders import cancel_all_from_proto
from polyester.codecs.orders import cancel_all_after_to_proto, cancel_all_orders_to_proto
from polyester.errors import (
    REQUEST_TOO_LARGE,
    PolyesterApiError,
    PolyesterRateLimitError,
    PolyesterValidationError,
    is_request_too_large,
    is_retryable_error,
)
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.api.v1 import request_error_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2

# --- cancel-all stops triggers -------------------------------------------------------------------


def test_cancel_all_sends_include_triggers_only_when_asked() -> None:
    assert not cancel_all_orders_to_proto().include_triggers
    assert cancel_all_orders_to_proto(include_triggers=True).include_triggers
    assert not cancel_all_after_to_proto(timeout_sec=30).include_triggers
    assert cancel_all_after_to_proto(timeout_sec=30, include_triggers=True).include_triggers


@pytest.mark.parametrize("value", [1, "true", None, 0])
def test_include_triggers_must_be_a_bool(value) -> None:
    with pytest.raises(PolyesterValidationError, match="include_triggers"):
        cancel_all_orders_to_proto(include_triggers=value)
    with pytest.raises(PolyesterValidationError, match="include_triggers"):
        cancel_all_after_to_proto(timeout_sec=30, include_triggers=value)


def test_cancel_all_result_counts_the_triggers_it_matched() -> None:
    result = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(
            status=orders_pb2.CancelAllOrdersResponse.SUBMITTED, matched_triggers=3
        )
    )
    assert result.matched_triggers == 3
    without = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(status=orders_pb2.CancelAllOrdersResponse.SUBMITTED)
    )
    assert without.matched_triggers == 0


# --- oversized ConnectRPC requests ---------------------------------------------------------------


def _too_large(**fields) -> ConnectError:
    detail = request_error_pb2.RequestErrorDetail(**fields)
    return ConnectError(Code.RESOURCE_EXHAUSTED, "request too large", details=[detail])


def test_request_error_detail_is_a_final_too_large_refusal_with_its_limit() -> None:
    error = map_connect_error(
        _too_large(code=request_error_pb2.REQUEST_TOO_LARGE, limit_bytes=4_194_304)
    )
    assert isinstance(error, PolyesterApiError)
    assert not isinstance(error, PolyesterRateLimitError)
    assert (error.code, error.limit_bytes) == (REQUEST_TOO_LARGE, 4_194_304)
    assert is_request_too_large(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize("code", [0, 99])
def test_request_error_detail_without_a_known_code_reads_as_a_plain_rate_limit(code) -> None:
    error = map_connect_error(_too_large(code=code, limit_bytes=1))
    assert isinstance(error, PolyesterRateLimitError)
    assert is_retryable_error(error)


def test_resource_exhausted_without_the_detail_stays_a_rate_limit() -> None:
    # Only the typed detail marks a request too large, never the message text.
    error = map_connect_error(ConnectError(Code.RESOURCE_EXHAUSTED, "request too large"))
    assert isinstance(error, PolyesterRateLimitError)
    detail = ratelimit_pb2.RateLimitDetail(retry_after_ms=1500)
    with_rate_limit = map_connect_error(
        ConnectError(Code.RESOURCE_EXHAUSTED, "rate limited", details=[detail])
    )
    assert isinstance(with_rate_limit, PolyesterRateLimitError)


# --- Me names an API key's scope ------------------------------------------------------------------


def test_me_names_a_sub_account_keys_scope_and_sub_account() -> None:
    from polyester.codecs.decode.auth import me_from_proto
    from polyester.codecs.scalars import format_id
    from polyester.gen.auth.v1 import account_scope_pb2, auth_pb2

    me = me_from_proto(
        auth_pb2.MeResponse(
            account_id=7,
            api_key_id="key-1",
            api_key_scope=account_scope_pb2.SCOPE_SUBACCOUNT,
            subaccount_id=12,
        )
    )
    assert (me.api_key_scope, me.subaccount_id) == ("subaccount", format_id(12))
    root = me_from_proto(
        auth_pb2.MeResponse(
            account_id=7, api_key_id="key-1", api_key_scope=account_scope_pb2.SCOPE_ROOT
        )
    )
    assert (root.api_key_scope, root.subaccount_id) == ("root", "")
    session = me_from_proto(auth_pb2.MeResponse(account_id=7))
    assert (session.api_key_scope, session.subaccount_id) == ("", "")


def test_me_refuses_a_sub_account_key_without_its_sub_account() -> None:
    from polyester.codecs.decode.auth import me_from_proto
    from polyester.errors import PolyesterResponseContractError
    from polyester.gen.auth.v1 import account_scope_pb2, auth_pb2

    with pytest.raises(PolyesterResponseContractError):
        me_from_proto(
            auth_pb2.MeResponse(
                account_id=7, api_key_id="key-1", api_key_scope=account_scope_pb2.SCOPE_SUBACCOUNT
            )
        )


# --- policy template copies -----------------------------------------------------------------------


def test_policy_copies_name_their_template_revision() -> None:
    from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
    from polyester.codecs.scalars import format_id
    from polyester.gen.auth.v1 import policies_pb2

    api = api_policy_from_proto(
        policies_pb2.ApiPolicyView(id=1, source_template_id=9, source_template_revision=4)
    )
    sub = subaccount_policy_from_proto(
        policies_pb2.SubaccountPolicyView(id=2, source_template_id=9, source_template_revision=5)
    )
    assert (api.source_template_id, api.source_template_revision) == (format_id(9), 4)
    assert (sub.source_template_id, sub.source_template_revision) == (format_id(9), 5)


# --- review round 1: every reply names what the contract guarantees ------------------------------


def test_request_error_detail_without_its_limit_is_refused() -> None:
    from polyester.errors import PolyesterResponseContractError

    error = map_connect_error(_too_large(code=request_error_pb2.REQUEST_TOO_LARGE))
    assert isinstance(error, PolyesterResponseContractError)
    assert not is_retryable_error(error)


@pytest.mark.parametrize(("template_id", "revision"), [(9, 0), (0, 3)])
def test_policy_lineage_must_name_both_template_and_revision(template_id, revision) -> None:
    from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
    from polyester.errors import PolyesterResponseContractError
    from polyester.gen.auth.v1 import policies_pb2

    lineage = dict(source_template_id=template_id, source_template_revision=revision)
    with pytest.raises(PolyesterResponseContractError):
        api_policy_from_proto(policies_pb2.ApiPolicyView(id=1, **lineage))
    with pytest.raises(PolyesterResponseContractError):
        subaccount_policy_from_proto(policies_pb2.SubaccountPolicyView(id=2, **lineage))


def test_a_policy_that_is_no_copy_has_no_lineage() -> None:
    from polyester.codecs.decode.policies import api_policy_from_proto
    from polyester.gen.auth.v1 import policies_pb2

    policy = api_policy_from_proto(policies_pb2.ApiPolicyView(id=1))
    assert (policy.source_template_id, policy.source_template_revision) == ("", 0)


@pytest.mark.parametrize("served", [0, 42, "DEPTH_20"])
def test_heatmap_reply_without_the_requested_tier_is_refused(served) -> None:
    from polyester.codecs.decode.heatmap import heatmap_from_proto
    from polyester.errors import PolyesterResponseContractError
    from polyester.gen.marketdata.v1 import heatmap_pb2
    from polyester.gen.polyester.type.v1 import depth_tier_pb2

    value = depth_tier_pb2.DepthTier.Value(served) if isinstance(served, str) else served
    msg = heatmap_pb2.GetOrderbookHeatmapResponse(symbol_id=1, depth=value)
    with pytest.raises(PolyesterResponseContractError):
        heatmap_from_proto(msg, depth=50)


def test_heatmap_reply_with_the_requested_tier_reads() -> None:
    from polyester.codecs.decode.heatmap import heatmap_from_proto
    from polyester.gen.marketdata.v1 import heatmap_pb2
    from polyester.gen.polyester.type.v1 import depth_tier_pb2

    msg = heatmap_pb2.GetOrderbookHeatmapResponse(symbol_id=1, depth=depth_tier_pb2.DEPTH_50)
    assert heatmap_from_proto(msg, depth=50) is not None


@pytest.mark.parametrize("served", [0, 42, 4])
async def test_managed_book_snapshot_without_its_tier_fails_closed(served) -> None:
    from polyester.codecs.orderbook import require_served_tier
    from polyester.errors import PolyesterResponseContractError

    with pytest.raises(PolyesterResponseContractError):
        require_served_tier("GetOrderBook", served, 50)


# --- review round 1: message text and Me scope pairs ---------------------------------------------


@pytest.mark.parametrize("message", ["REQUEST_TOO_LARGE", "request too large"])
def test_message_text_never_makes_a_request_too_large(message: str) -> None:
    for details in ([], [request_error_pb2.RequestErrorDetail(code=99, limit_bytes=1)]):
        error = map_connect_error(ConnectError(Code.RESOURCE_EXHAUSTED, message, details=details))
        assert isinstance(error, PolyesterRateLimitError), (message, details)
        assert error.code != REQUEST_TOO_LARGE
        assert is_retryable_error(error)


@pytest.mark.parametrize(
    ("key", "scope", "subaccount"),
    [
        ("key-1", 0, 0),  # an API key must name its scope
        ("key-1", 99, 0),  # a scope this SDK does not know
        ("key-1", "SCOPE_ROOT", 12),  # a root key has no bound sub-account
        ("key-1", "SCOPE_SUBACCOUNT", 0),
        ("", "SCOPE_ROOT", 0),  # a session has no key scope
        ("", 0, 12),
    ],
)
def test_me_refuses_an_inconsistent_scope(key, scope, subaccount) -> None:
    from polyester.codecs.decode.auth import me_from_proto
    from polyester.errors import PolyesterResponseContractError
    from polyester.gen.auth.v1 import account_scope_pb2, auth_pb2

    value = account_scope_pb2.AccountScopeType.Value(scope) if isinstance(scope, str) else scope
    msg = auth_pb2.MeResponse(
        account_id=7, api_key_id=key, api_key_scope=value, subaccount_id=subaccount
    )
    with pytest.raises(PolyesterResponseContractError):
        me_from_proto(msg)


# --- batch transfers: every 5xx failure is an unknown outcome -----------------------------------
#
# A batch whose answer is a server failure may or may not have been admitted.
# The contract's safe path is to send it again with the same idempotency key and
# legs, which is safe either way; the SDK never claims more than that.


def _b64(message) -> str:
    import base64

    return base64.b64encode(message.SerializeToString()).decode()


def _transfer_detail(code_name: str):
    from polyester.gen.transfer.v1 import internal_transfer_pb2 as it_pb2

    return it_pb2.ErrorDetail(code=it_pb2.ErrorCode.Value(code_name))


def _detail(type_name: str, message) -> dict:
    return {"type": type_name, "value": _b64(message)}


def _service(code: str = "ERROR_CODE_SERVICE_UNAVAILABLE") -> dict:
    return _detail("transfer.v1.ErrorDetail", _transfer_detail(code))


def _catalog_problem(code: str, status: int = 503) -> dict:
    return {
        "code": code,
        "status": status,
        "title": "Service Unavailable",
        "detail": "A required service is temporarily unavailable.",
        "type": "https://polyester.dev/problems/" + code.lower().replace("_", "-"),
    }


def _answer(status: int, body, *, content_type="application/json", headers=()):
    import json

    from tests.hardening_support import HttpScript

    text = body if isinstance(body, str) else json.dumps(body)
    return HttpScript.raw(
        status,
        headers=[("Content-Type", content_type), ("Retry-After", "7"), *headers],
        body=text.encode(),
    )


def _connect(status: int, details: list, code="unavailable", **kwargs):
    body: dict = {"message": "transfer checks unavailable", "details": details}
    if code is not None:
        body["code"] = code
    return _answer(status, body, **kwargs)


def _problem(status: int, code: str, content_type="application/problem+json", **kwargs):
    return _answer(status, _catalog_problem(code, status), content_type=content_type, **kwargs)


async def _batch_error(script):
    from polyester import AsyncPolyester
    from polyester.errors import PolyesterError
    from polyester.models import InternalTransferLeg
    from tests.hardening_support import MockHttpServer, make_test_credentials

    creds = make_test_credentials()

    async def handler(_req):
        return script

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    leg = InternalTransferLeg(
        asset_id=1, quantity="1", destination_smart_account_address="0x" + "2" * 40
    )
    try:
        with pytest.raises(PolyesterError) as raised:
            await client.internal_transfers.batch_create(legs=[leg], idempotency_key="k")
    finally:
        await client.aclose()
        await http.aclose()
    return raised.value


def _orders_unavailable():
    return orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_UNAVAILABLE)


def _auth_unavailable():
    from polyester.gen.auth.v1 import auth_pb2

    return auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TEMPORARILY_UNAVAILABLE)


def _entry_json() -> str:
    import json

    return json.dumps(_service())


# (id, HTTP status the answer has, the answer) for every failure class met in review,
# the published 503 refusals included.
_BATCH_FAILURES = [
    ("typed-service-unavailable", 503, lambda: _connect(503, [_service()])),
    (
        "typed-account-shard",
        503,
        lambda: _connect(503, [_service("ERROR_CODE_ACCOUNT_SHARD_UNAVAILABLE")]),
    ),
    ("problem-service-unavailable", 503, lambda: _problem(503, "SERVICE_UNAVAILABLE")),
    ("problem-account-shard", 503, lambda: _problem(503, "ACCOUNT_SHARD_UNAVAILABLE")),
    ("typed-504", 504, lambda: _connect(504, [_service()])),
    ("typed-502", 502, lambda: _connect(502, [_service()])),
    ("problem-504", 504, lambda: _problem(504, "SERVICE_UNAVAILABLE")),
    ("problem-502", 502, lambda: _problem(502, "SERVICE_UNAVAILABLE")),
    (
        "foreign-detail",
        503,
        lambda: _connect(503, [_detail("orders.v1.ErrorDetail", _orders_unavailable())]),
    ),
    (
        "rate-limit-detail-503",
        503,
        lambda: _connect(
            503,
            [
                _detail(
                    "polyester.ratelimit.v1.RateLimitDetail",
                    ratelimit_pb2.RateLimitDetail(retry_after_ms=1500),
                )
            ],
            code="resource_exhausted",
        ),
    ),
    (
        "rate-limit-detail-502",
        502,
        lambda: _connect(
            502,
            [
                _detail(
                    "polyester.ratelimit.v1.RateLimitDetail",
                    ratelimit_pb2.RateLimitDetail(retry_after_ms=1500),
                )
            ],
            code="resource_exhausted",
        ),
    ),
    (
        "auth-unavailable",
        503,
        lambda: _connect(503, [_detail("auth.v1.AuthErrorDetail", _auth_unavailable())]),
    ),
    ("inferred-code", 503, lambda: _connect(503, [_service()], code=None)),
    (
        "two-details",
        503,
        lambda: _connect(503, [_service(), _service("ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE")]),
    ),
    (
        "undecodable-extra-entry",
        503,
        lambda: _connect(503, [_service(), {"type": "transfer.v1.ErrorDetail"}]),
    ),
    (
        "invalid-base64-detail",
        503,
        lambda: _connect(503, [{"type": "transfer.v1.ErrorDetail", "value": "!!not base64!!"}]),
    ),
    (
        "nan-in-body",
        503,
        lambda: _answer(
            503,
            '{"code": "unavailable", "message": "m", "x": NaN, "details": [' + _entry_json() + "]}",
        ),
    ),
    (
        "infinity-in-body",
        503,
        lambda: _answer(
            503,
            '{"code": "unavailable", "x": Infinity, "details": [' + _entry_json() + "]}",
        ),
    ),
    (
        "duplicate-code",
        503,
        lambda: _answer(
            503,
            '{"code": "internal", "code": "unavailable", "details": [' + _entry_json() + "]}",
        ),
    ),
    (
        "typed-under-problem-media-type",
        503,
        lambda: _connect(503, [_service()], content_type="application/problem+json"),
    ),
    (
        "typed-with-duplicate-media-type",
        503,
        lambda: _connect(503, [_service()], headers=[("Content-Type", "text/plain")]),
    ),
    (
        "problem-as-plain-json",
        503,
        lambda: _problem(503, "SERVICE_UNAVAILABLE", content_type="application/json"),
    ),
    (
        "problem-vendor-media-type",
        503,
        lambda: _problem(503, "SERVICE_UNAVAILABLE", content_type="application/vnd.gateway+json"),
    ),
    (
        "problem-two-content-types",
        503,
        lambda: _problem(
            503, "SERVICE_UNAVAILABLE", headers=[("Content-Type", "application/json")]
        ),
    ),
    (
        "generic-prefixed-code",
        503,
        lambda: _answer(503, {"code": "ERROR_CODE_SERVICE_UNAVAILABLE", "message": "x"}),
    ),
    ("generic-bare-code", 503, lambda: _answer(503, {"code": "SERVICE_UNAVAILABLE"})),
    (
        "diagnostic-field",
        503,
        lambda: _answer(503, {"message": "x", "diagnostic": "SERVICE_UNAVAILABLE"}),
    ),
    (
        "header-forged-code",
        503,
        lambda: _connect(
            503, [_service()], code=None, headers=[("Connect-Error-Code", "unavailable")]
        ),
    ),
    (
        "trailer-forged-code",
        503,
        lambda: _connect(
            503,
            [_service()],
            code=None,
            headers=[("Trailer-Grpc-Status", "14"), ("Trailer-Connect-Error-Code", "unavailable")],
        ),
    ),
    ("opaque-503", 503, lambda: _answer(503, {"code": "unavailable", "message": "busy"})),
    ("plain-text-503", 503, lambda: _answer(503, "busy", content_type="text/plain")),
]


@pytest.mark.parametrize(
    ("status", "answer"),
    [(status, answer) for _id, status, answer in _BATCH_FAILURES],
    ids=[case_id for case_id, _status, _answer in _BATCH_FAILURES],
)
async def test_every_batch_server_failure_is_an_unknown_outcome(status, answer) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(answer())
    # The answer's own status stays on the error, never promoted to a refusal.
    assert error.status_code == status
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


async def test_a_batch_failure_keeps_its_code_and_retry_after() -> None:
    error = await _batch_error(_connect(503, [_service()]))
    assert (error.status_code, error.retry_after) == (503, 7)
    assert getattr(error, "code", None) == "ERROR_CODE_SERVICE_UNAVAILABLE"


async def test_a_genuine_429_on_a_batch_stays_a_retryable_throttle() -> None:
    # The batch guard covers server failures only: a 4xx keeps its meaning.
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(
        _connect(
            429,
            [
                _detail(
                    "polyester.ratelimit.v1.RateLimitDetail",
                    ratelimit_pb2.RateLimitDetail(retry_after_ms=1500),
                )
            ],
            code="resource_exhausted",
        )
    )
    assert isinstance(error, PolyesterRateLimitError)
    assert error.status_code == 429
    assert not mutation_outcome_unknown(error)
    assert is_retryable_error(error)
