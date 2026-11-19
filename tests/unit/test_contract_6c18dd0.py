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
            account_id=7, api_key_scope=address_book_pb2.SCOPE_SUBACCOUNT, subaccount_id=12
        )
    )
    assert (me.api_key_scope, me.subaccount_id) == ("subaccount", format_id(12))
    root = me_from_proto(
        auth_pb2.MeResponse(account_id=7, api_key_scope=address_book_pb2.SCOPE_ROOT)
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
            auth_pb2.MeResponse(account_id=7, api_key_scope=address_book_pb2.SCOPE_SUBACCOUNT)
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
