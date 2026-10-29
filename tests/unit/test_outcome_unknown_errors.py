"""Retry and outcome classification of structured order and auth error codes."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import (
    AUTH_TEMPORARILY_UNAVAILABLE,
    PolyesterApiError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.orders.v1 import orders_pb2


@pytest.mark.parametrize(
    "code",
    [
        orders_pb2.ERROR_CODE_ORDER_CANCEL_OUTCOME_UNKNOWN,
        orders_pb2.ERROR_CODE_ORDER_MODIFY_OUTCOME_UNKNOWN,
        orders_pb2.ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN,
        orders_pb2.ERROR_CODE_TRIGGER_CREATE_OUTCOME_UNKNOWN,
    ],
)
def test_outcome_unknown_order_codes_are_retryable_and_ambiguous(code: int) -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.DEADLINE_EXCEEDED,
            "not confirmed in time",
            details=[orders_pb2.ErrorDetail(code=code)],
        )
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == orders_pb2.ErrorCode.Name(code)
    assert is_retryable_error(mapped)
    assert mutation_outcome_unknown(mapped)


def test_auth_temporarily_unavailable_is_retryable_and_changed_nothing() -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.UNAVAILABLE,
            "try again",
            details=[auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TEMPORARILY_UNAVAILABLE)],
        )
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == AUTH_TEMPORARILY_UNAVAILABLE
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


@pytest.mark.parametrize(
    "detail",
    [
        orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_TRIGGER_WOULD_TRIGGER_IMMEDIATELY),
        orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_ORDER_ALREADY_TERMINAL),
        auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_INTERNAL_ERROR),
    ],
    ids=["would_trigger_immediately", "already_terminal", "auth_internal"],
)
def test_definite_api_errors_are_neither_retryable_nor_ambiguous(detail: object) -> None:
    mapped = map_connect_error(
        ConnectError(Code.FAILED_PRECONDITION, "refused", details=[detail])  # type: ignore[list-item]
    )
    assert type(mapped) is PolyesterApiError
    assert not is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)
