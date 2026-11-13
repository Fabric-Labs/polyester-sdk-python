"""Public contract 74af7f3: refusals the SDK must read the same way on both
transports."""

from __future__ import annotations

import json

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester import (
    AUTH_TEMPORARILY_UNAVAILABLE,
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRateLimitError,
    PolyesterTimestampSkewError,
    auth_error_code,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester._contract_codes import is_recognised_rest_code
from polyester._wire import map_connect_error
from polyester.errors import TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE, is_not_found
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from tests.unit.test_readable_error_bodies import PROBLEM, _call

# --- trailing-stop activation edits after tracking began (315) ----------------------------------


def test_activation_price_not_modifiable_is_code_315() -> None:
    assert orders_pb2.ERROR_CODE_TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE == 315
    assert TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE == (
        "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE"
    )
    assert is_recognised_rest_code("TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE")


def _assert_final_refusal(err: BaseException | None) -> None:
    assert type(err) is PolyesterApiError
    assert err.code == TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE
    # Nothing changed and the same edit is refused again.
    assert not is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


def test_activation_price_not_modifiable_over_connect() -> None:
    err = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "activation price cannot change after tracking began",
            details=[
                orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE
                )
            ],
        )
    )
    _assert_final_refusal(err)


@pytest.mark.asyncio
async def test_activation_price_not_modifiable_over_rest() -> None:
    body = {
        "status": 400,
        "code": "TRIGGER_ACTIVATION_PRICE_NOT_MODIFIABLE",
        "title": "Trigger Activation Price Not Modifiable",
        "detail": "The trailing stop has already started tracking.",
    }
    err, calls = await _call("write", 400, PROBLEM, json.dumps(body))
    assert calls == 1
    _assert_final_refusal(err)


def test_activation_price_edit_request_keeps_absent_apart_from_zero() -> None:
    # Omit the field to keep the activation price; zero clears it, which stays valid.
    assert not triggers_pb2.ModifyTriggerRequest(trigger_id=1).HasField("activation_price_ticks")
    assert triggers_pb2.ModifyTriggerRequest(trigger_id=1, activation_price_ticks=0).HasField(
        "activation_price_ticks"
    )


# --- REST credential refusals: the same codes on every endpoint ---------------------------------

# The API-key refusals every REST endpoint answers, as their bare codes.
API_KEY_REFUSALS = [
    ("MISSING_HEADERS", "AUTH_MISSING_HEADERS"),
    ("SIGNATURE_INVALID", "AUTH_SIGNATURE_INVALID"),
    ("RECV_WINDOW_INVALID", "AUTH_RECV_WINDOW_INVALID"),
    ("KEY_EXPIRED", "AUTH_KEY_EXPIRED"),
    ("KEY_DISABLED", "AUTH_KEY_DISABLED"),
    ("IP_NOT_ALLOWED", "AUTH_IP_NOT_ALLOWED"),
    ("UNAUTHENTICATED", "AUTH_AUTHENTICATION_REQUIRED"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "auth_code"), API_KEY_REFUSALS)
async def test_rest_credential_refusal_reads_its_auth_code(code: str, auth_code: str) -> None:
    body = {"status": 401, "code": code, "title": "t", "detail": "d"}
    err, calls = await _call("write", 401, PROBLEM, json.dumps(body))
    assert calls == 1
    assert isinstance(err, PolyesterAuthError)
    assert err.status_code == 401
    assert auth_error_code(err) == auth_code
    assert not is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


@pytest.mark.asyncio
async def test_rest_timestamp_skew_reads_its_auth_code() -> None:
    body = {"status": 401, "code": "TIMESTAMP_SKEW", "title": "t", "detail": "d"}
    err, calls = await _call("write", 401, PROBLEM, json.dumps(body))
    assert calls == 1
    assert isinstance(err, PolyesterTimestampSkewError)
    assert auth_error_code(err) == "AUTH_TIMESTAMP_SKEW"
    # Signing again with a fresh timestamp is safe: nothing was processed.
    assert is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


@pytest.mark.asyncio
async def test_rest_replay_capacity_refusal_is_retryable() -> None:
    body = {"status": 429, "code": "REPLAY_CAPACITY_EXHAUSTED", "title": "t", "detail": "d"}
    err, calls = await _call("write", 429, PROBLEM, json.dumps(body))
    assert calls == 1
    assert isinstance(err, PolyesterRateLimitError)
    assert auth_error_code(err) == "AUTH_REPLAY_CAPACITY_EXHAUSTED"
    assert is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


@pytest.mark.asyncio
@pytest.mark.parametrize("op", ["write", "read"])
async def test_rest_auth_temporarily_unavailable_reads_as_over_connect(op: str) -> None:
    body = {"status": 503, "code": "AUTH_TEMPORARILY_UNAVAILABLE", "title": "t", "detail": "d"}
    rest, _ = await _call(op, 503, PROBLEM, json.dumps(body))
    connect = map_connect_error(
        ConnectError(
            Code.UNAVAILABLE,
            "d",
            details=[auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TEMPORARILY_UNAVAILABLE)],
        )
    )
    for err in (rest, connect):
        assert type(err) is PolyesterApiError
        assert err.code == AUTH_TEMPORARILY_UNAVAILABLE
        assert auth_error_code(err) == AUTH_TEMPORARILY_UNAVAILABLE
        # Authentication could not run: nothing was processed, retry with backoff.
        assert is_retryable_error(err)
        assert not mutation_outcome_unknown(err)


@pytest.mark.asyncio
async def test_rest_unknown_procedure_problem_is_not_found() -> None:
    body = {
        "type": "https://polyester.dev/problems/not-found",
        "title": "Not Found",
        "status": 404,
        "detail": "No API operation matches this method and path.",
        "code": "NOT_FOUND",
    }
    err, calls = await _call("write", 404, PROBLEM, json.dumps(body))
    assert calls == 1
    assert isinstance(err, PolyesterApiError)
    assert is_not_found(err)
    assert not is_retryable_error(err)
    # A documented NOT_FOUND names a refusal, not an unknown outcome.
    assert not mutation_outcome_unknown(err)
