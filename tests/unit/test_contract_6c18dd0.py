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
    from polyester.gen.auth.v1 import address_book_pb2, auth_pb2

    me = me_from_proto(
        auth_pb2.MeResponse(
            account_id=7,
            api_key_id="key-1",
            api_key_scope=address_book_pb2.SCOPE_SUBACCOUNT,
            subaccount_id=12,
        )
    )
    assert (me.api_key_scope, me.subaccount_id) == ("subaccount", format_id(12))
    root = me_from_proto(
        auth_pb2.MeResponse(
            account_id=7, api_key_id="key-1", api_key_scope=address_book_pb2.SCOPE_ROOT
        )
    )
    assert (root.api_key_scope, root.subaccount_id) == ("root", "")
    session = me_from_proto(auth_pb2.MeResponse(account_id=7))
    assert (session.api_key_scope, session.subaccount_id) == ("", "")


def test_me_refuses_a_sub_account_key_without_its_sub_account() -> None:
    from polyester.codecs.decode.auth import me_from_proto
    from polyester.errors import PolyesterResponseContractError
    from polyester.gen.auth.v1 import address_book_pb2, auth_pb2

    with pytest.raises(PolyesterResponseContractError):
        me_from_proto(
            auth_pb2.MeResponse(
                account_id=7, api_key_id="key-1", api_key_scope=address_book_pb2.SCOPE_SUBACCOUNT
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


# --- review round 1: message text, Me scope pairs and batch pre-admission refusals ---------------


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
    from polyester.gen.auth.v1 import address_book_pb2, auth_pb2

    value = address_book_pb2.AccountScopeType.Value(scope) if isinstance(scope, str) else scope
    msg = auth_pb2.MeResponse(
        account_id=7, api_key_id=key, api_key_scope=value, subaccount_id=subaccount
    )
    with pytest.raises(PolyesterResponseContractError):
        me_from_proto(msg)


def _connect_unavailable(status: int, detail_type: str, detail):
    import base64
    import json

    from tests.hardening_support import HttpScript

    body = {
        "code": "unavailable",
        "message": "transfer checks unavailable",
        "details": [
            {"type": detail_type, "value": base64.b64encode(detail.SerializeToString()).decode()}
        ],
    }
    return HttpScript.raw(
        status,
        headers=[("Content-Type", "application/json"), ("Retry-After", "7")],
        body=json.dumps(body).encode(),
    )


def _transfer_detail(code_name: str):
    from polyester.gen.transfer.v1 import internal_transfer_pb2 as it_pb2

    return it_pb2.ErrorDetail(code=it_pb2.ErrorCode.Value(code_name))


def _problem_answer(status: int, body: dict, content_type: str = "application/problem+json"):
    import json

    from tests.hardening_support import HttpScript

    return HttpScript.raw(
        status,
        headers=[("Content-Type", content_type), ("Retry-After", "7")],
        body=json.dumps(body).encode(),
    )


def _catalog_problem(code: str, status: int = 503) -> dict:
    return {
        "code": code,
        "status": status,
        "title": "Service Unavailable",
        "detail": "A required service is temporarily unavailable.",
        "type": "https://polyester.dev/problems/" + code.lower().replace("_", "-"),
    }


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


_PRE_ADMISSION = ["ERROR_CODE_SERVICE_UNAVAILABLE", "ERROR_CODE_ACCOUNT_SHARD_UNAVAILABLE"]


@pytest.mark.parametrize("code", _PRE_ADMISSION)
async def test_batch_refused_before_admission_is_a_retryable_known_outcome(code: str) -> None:
    from polyester.errors import mutation_outcome_unknown

    for script in (
        _connect_unavailable(503, "transfer.v1.ErrorDetail", _transfer_detail(code)),
        _problem_answer(503, _catalog_problem(code.removeprefix("ERROR_CODE_"))),
    ):
        error = await _batch_error(script)
        assert (error.status_code, error.retry_after) == (503, 7)
        assert getattr(error, "code", None) == code
        assert not mutation_outcome_unknown(error)
        assert is_retryable_error(error)


def _orders_unavailable():
    return orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_UNAVAILABLE)


@pytest.mark.parametrize(
    "script",
    [
        # A 504 or 502 is an unknown outcome, whatever detail it carries.
        _connect_unavailable(
            504, "transfer.v1.ErrorDetail", _transfer_detail("ERROR_CODE_SERVICE_UNAVAILABLE")
        ),
        _connect_unavailable(
            502, "transfer.v1.ErrorDetail", _transfer_detail("ERROR_CODE_SERVICE_UNAVAILABLE")
        ),
        _problem_answer(504, _catalog_problem("SERVICE_UNAVAILABLE", 504)),
        _problem_answer(502, _catalog_problem("SERVICE_UNAVAILABLE", 502)),
        # A detail type foreign to the transfer service.
        _connect_unavailable(503, "orders.v1.ErrorDetail", _orders_unavailable()),
        # Generic JSON: a prefixed code, or a bare code with no problem type.
        _problem_answer(
            503, {"code": "ERROR_CODE_SERVICE_UNAVAILABLE", "message": "x"}, "application/json"
        ),
        _problem_answer(503, {"code": "SERVICE_UNAVAILABLE", "message": "x"}, "application/json"),
        _problem_answer(503, {**_catalog_problem("SERVICE_UNAVAILABLE"), "type": "about:blank"}),
        # The code only in a diagnostic field.
        _problem_answer(
            503, {"message": "x", "diagnostic": "SERVICE_UNAVAILABLE"}, "application/json"
        ),
        _problem_answer(
            503,
            {**_catalog_problem("UNAVAILABLE"), "detail": "SERVICE_UNAVAILABLE"},
        ),
    ],
    ids=[
        "connect-504",
        "connect-502",
        "problem-504",
        "problem-502",
        "foreign-detail",
        "generic-prefixed",
        "generic-bare",
        "problem-wrong-type",
        "diagnostic-field",
        "detail-text",
    ],
)
async def test_other_batch_failures_stay_unknown_and_unretried(script) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(script)
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


async def test_an_opaque_503_on_a_batch_stays_an_unknown_outcome() -> None:
    from polyester import AsyncPolyester
    from polyester.errors import PolyesterError, mutation_outcome_unknown
    from polyester.models import InternalTransferLeg
    from tests.hardening_support import HttpScript, MockHttpServer, make_test_credentials

    creds = make_test_credentials()

    async def handler(_req):
        return HttpScript.json(503, {"code": "unavailable", "message": "busy"})

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
    assert mutation_outcome_unknown(raised.value)
    assert not is_retryable_error(raised.value)


# --- review round 2: the REST proof needs its media type; no 5xx class escapes -----------------


@pytest.mark.parametrize(
    "content_type",
    ["application/problem+json-gateway", "application/json", "application/vnd.gateway+json"],
)
async def test_a_canonical_problem_under_another_media_type_proves_nothing(content_type) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(
        _problem_answer(503, _catalog_problem("SERVICE_UNAVAILABLE"), content_type)
    )
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize(
    "content_type", ["Application/Problem+JSON", "application/problem+json; charset=utf-8"]
)
async def test_the_problem_media_type_matches_in_any_case_with_parameters(content_type) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(
        _problem_answer(503, _catalog_problem("SERVICE_UNAVAILABLE"), content_type)
    )
    assert (error.status_code, error.retry_after) == (503, 7)
    assert not mutation_outcome_unknown(error)
    assert is_retryable_error(error)


def _connect_answer(status: int, connect_code: str, detail_type: str, detail):
    import base64
    import json

    from tests.hardening_support import HttpScript

    body = {
        "code": connect_code,
        "message": "m",
        "details": [
            {"type": detail_type, "value": base64.b64encode(detail.SerializeToString()).decode()}
        ],
    }
    return HttpScript.raw(
        status,
        headers=[("Content-Type", "application/json"), ("Retry-After", "7")],
        body=json.dumps(body).encode(),
    )


def _auth_unavailable():
    from polyester.gen.auth.v1 import auth_pb2

    return auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TEMPORARILY_UNAVAILABLE)


@pytest.mark.parametrize("status", [502, 503])
@pytest.mark.parametrize(
    "answer",
    [
        lambda status: _connect_answer(
            status,
            "resource_exhausted",
            "polyester.ratelimit.v1.RateLimitDetail",
            ratelimit_pb2.RateLimitDetail(retry_after_ms=1500),
        ),
        lambda status: _connect_answer(
            status, "unavailable", "auth.v1.AuthErrorDetail", _auth_unavailable()
        ),
    ],
    ids=["rate-limit-detail", "auth-unavailable"],
)
async def test_no_5xx_escapes_the_batch_guard_whatever_it_maps_to(answer, status) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(answer(status))
    assert error.status_code == status
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


async def test_a_genuine_429_on_a_batch_stays_a_retryable_throttle() -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(
        _connect_answer(
            429,
            "resource_exhausted",
            "polyester.ratelimit.v1.RateLimitDetail",
            ratelimit_pb2.RateLimitDetail(retry_after_ms=1500),
        )
    )
    assert isinstance(error, PolyesterRateLimitError)
    assert error.status_code == 429
    assert not mutation_outcome_unknown(error)
    assert is_retryable_error(error)


# --- review round 3: exactly one Content-Type field, parsed by the standard library -----------


def _problem_with_headers(headers: list[tuple[str, str]]):
    import json

    from tests.hardening_support import HttpScript

    return HttpScript.raw(
        503,
        headers=[*headers, ("Retry-After", "7")],
        body=json.dumps(_catalog_problem("SERVICE_UNAVAILABLE")).encode(),
    )


@pytest.mark.parametrize(
    "headers",
    [
        # Two Content-Type fields: the first alone looks like a problem.
        [("Content-Type", "application/problem+json"), ("Content-Type", "application/json")],
        # One field listing two media types behind an unquoted comma.
        [("Content-Type", "application/problem+json; charset=utf-8, application/json")],
        [("Content-Type", "application/problem+json, application/json")],
    ],
    ids=["duplicate-field", "comma-after-parameter", "comma-list"],
)
async def test_an_ambiguous_content_type_proves_nothing(headers) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(_problem_with_headers(headers))
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


async def test_a_quoted_parameter_keeps_the_problem_media_type() -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(
        _problem_with_headers([("Content-Type", 'application/problem+json; profile="a, b"')])
    )
    assert (error.status_code, error.retry_after) == (503, 7)
    assert not mutation_outcome_unknown(error)
    assert is_retryable_error(error)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["application/problem+json"], "application/problem+json"),
        (["Application/Problem+JSON; charset=utf-8"], "application/problem+json"),
        (['application/problem+json; profile="a, b"'], "application/problem+json"),
        (["application/problem+json; charset=utf-8, application/json"], ""),
        (["application/problem+json garbage"], ""),
        (["application/problem+json", "application/json"], ""),
        ([], ""),
        ([""], ""),
    ],
)
def test_media_type_of_reads_exactly_one_well_formed_field(values, expected) -> None:
    from polyester._problem import media_type_of

    assert media_type_of(values) == expected


# --- review round 4: the typed proof needs the explicit wire code and only that detail ---------


def _connect_body(status: int, code, details: list[tuple[str, bytes]]):
    import base64
    import json

    from tests.hardening_support import HttpScript

    body: dict = {
        "message": "transfer checks unavailable",
        "details": [
            {"type": name, "value": base64.b64encode(value).decode()} for name, value in details
        ],
    }
    if code is not ...:
        body["code"] = code
    return HttpScript.raw(
        status,
        headers=[("Content-Type", "application/json"), ("Retry-After", "7")],
        body=json.dumps(body).encode(),
    )


_SERVICE = "ERROR_CODE_SERVICE_UNAVAILABLE"
_CAPITAL_VIEW = "ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE"


def _transfer(code_name: str) -> tuple[str, bytes]:
    return ("transfer.v1.ErrorDetail", _transfer_detail(code_name).SerializeToString())


@pytest.mark.parametrize(
    "code", [..., "", None, "unspecified"], ids=["missing", "empty", "null", "unspecified"]
)
async def test_an_inferred_connect_code_proves_nothing(code) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(
        _connect_body(503, code, [_transfer("ERROR_CODE_SERVICE_UNAVAILABLE")])
    )
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize(
    "details",
    [
        [
            _transfer("ERROR_CODE_SERVICE_UNAVAILABLE"),
            _transfer("ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE"),
        ],
        [
            _transfer("ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE"),
            _transfer("ERROR_CODE_SERVICE_UNAVAILABLE"),
        ],
        [_transfer("ERROR_CODE_SERVICE_UNAVAILABLE"), _transfer("ERROR_CODE_SERVICE_UNAVAILABLE")],
        [
            _transfer("ERROR_CODE_SERVICE_UNAVAILABLE"),
            ("orders.v1.ErrorDetail", _orders_unavailable().SerializeToString()),
        ],
        [_transfer("ERROR_CODE_SERVICE_UNAVAILABLE"), ("x.y.Unknown", b"\x08\x01")],
        [_transfer("ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE")],
    ],
    ids=["then-other", "other-then", "repeated", "plus-foreign", "plus-unknown", "other-code"],
)
async def test_only_a_single_admission_detail_proves_the_refusal(details) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(_connect_body(503, "unavailable", details))
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize("code", _PRE_ADMISSION)
async def test_the_explicit_wire_code_with_its_single_detail_is_the_refusal(code) -> None:
    from polyester.errors import mutation_outcome_unknown

    error = await _batch_error(_connect_body(503, "unavailable", [_transfer(code)]))
    assert (error.status_code, error.retry_after) == (503, 7)
    assert not mutation_outcome_unknown(error)
    assert is_retryable_error(error)


@pytest.mark.parametrize(
    "spoof",
    [
        [("Connect-Error-Code", "unavailable")],
        [("X-Connect-Code", "unavailable")],
        [("Grpc-Status", "14"), ("Grpc-Message", "unavailable")],
        [("Code", "unavailable")],
        # ConnectRPC merges Trailer-prefixed headers into error metadata.
        [("Trailer-Connect-Error-Code", "unavailable")],
        [("Trailer-Code", "unavailable")],
        [("Trailer-Grpc-Status", "14"), ("Trailer-Grpc-Message", "unavailable")],
        [("Trailer-Http-Status", "503"), ("Trailer-Wire-Code", "unavailable")],
    ],
    ids=[
        "connect-header",
        "x-header",
        "grpc-status",
        "bare-header",
        "trailer-connect-code",
        "trailer-code",
        "trailer-grpc-status",
        "trailer-status",
    ],
)
async def test_a_header_cannot_forge_the_wire_code(spoof) -> None:
    import base64
    import json

    from polyester.errors import mutation_outcome_unknown
    from tests.hardening_support import HttpScript

    name, value = _transfer(_SERVICE)
    body = {
        "message": "transfer checks unavailable",
        "details": [{"type": name, "value": base64.b64encode(value).decode()}],
    }
    script = HttpScript.raw(
        503,
        headers=[("Content-Type", "application/json"), ("Retry-After", "7"), *spoof],
        body=json.dumps(body).encode(),
    )
    error = await _batch_error(script)
    assert mutation_outcome_unknown(error), repr(error)
    assert not is_retryable_error(error)
