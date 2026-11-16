"""Public contract 5c2119f: trigger refusals name the field's code, a sell
trigger pays its fee in quote, insufficient funds is an account-state refusal,
and REST answers a temporary failure with 503."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.codecs.oco import create_oco_to_proto
from polyester.codecs.orders import create_order_to_proto
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import (
    PolyesterApiError,
    PolyesterRateLimitError,
    PolyesterServerError,
    PolyesterTimeoutError,
    PolyesterValidationError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CreateOrderRequest
from polyester.types.money import Quantity
from tests.unit.test_readable_error_bodies import JSON, PROBLEM, _call

# --- trigger and OCO refusals carry the API's code --------------------------------------------


def _create(**overrides: Any):
    args: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "stop_loss",
        "side": "sell",
        "qty": "0.1",
        "trigger_price": "100",
        "quantity_scale": 8,
    }
    args.update(overrides)
    return create_trigger_to_proto(**args)


def _code(call) -> str | None:
    with pytest.raises(PolyesterValidationError) as refused:
        call()
    return refused.value.code


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"client_trigger_id": "x" * 37}, "ERROR_CODE_CLIENT_TRIGGER_ID_INVALID"),
        ({"qty": "0"}, "ERROR_CODE_TRIGGER_QTY_INVALID"),
        ({"qty": "-1"}, "ERROR_CODE_TRIGGER_QTY_INVALID"),
        ({"trigger_price": "-1"}, "ERROR_CODE_TRIGGER_PRICE_INVALID"),
        (
            {"order_type": "limit", "limit_price": "-1"},
            "ERROR_CODE_BAD_PRICE",
        ),
        ({"max_slippage_ticks": 0}, "ERROR_CODE_SLIPPAGE_TICKS_INVALID"),
        ({"max_slippage_bps": 0}, "ERROR_CODE_SLIPPAGE_BPS_INVALID"),
        ({"max_slippage_bps": 10_001}, "ERROR_CODE_SLIPPAGE_BPS_INVALID"),
        # 10000 leaves a sell no price: the cap the API refuses for a sell child.
        ({"max_slippage_bps": 10_000}, "ERROR_CODE_MAX_SLIPPAGE_INVALID"),
        (
            {
                "trigger_type": "trailing_stop",
                "trigger_price": None,
                "trailing_distance_ticks": 0,
            },
            "ERROR_CODE_TRAILING_DISTANCE_INVALID",
        ),
        (
            {
                "trigger_type": "trailing_stop",
                "trigger_price": None,
                "trailing_distance_bps": 10_001,
            },
            "ERROR_CODE_TRAILING_DISTANCE_INVALID",
        ),
        (
            {
                "trigger_type": "trailing_stop",
                "trigger_price": None,
                "trailing_distance_bps": 100,
                "activation_price": "-1",
            },
            "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_INVALID",
        ),
        (
            {
                "trigger_type": "trailing_stop",
                "trigger_price": None,
                "trailing_distance_bps": 100,
                "max_slippage_bps": 10_000,
            },
            "ERROR_CODE_MAX_SLIPPAGE_INVALID",
        ),
        (
            {
                "trigger_type": "trailing_stop",
                "side": "buy",
                "trigger_price": None,
                "trailing_distance_bps": 100,
                "order_type": "limit",
                "limit_price": "0",
            },
            "ERROR_CODE_BAD_PRICE",
        ),
        (
            {"trigger_type": "twap", "trigger_price": None, "twap_slice_interval_ms": 100},
            "ERROR_CODE_TWAP_DURATION_INVALID",
        ),
        (
            {
                "trigger_type": "twap",
                "trigger_price": None,
                "twap_duration_ms": 999,
                "twap_slice_interval_ms": 100,
            },
            "ERROR_CODE_TWAP_DURATION_INVALID",
        ),
        (
            {
                "trigger_type": "twap",
                "trigger_price": None,
                "twap_duration_ms": 1000,
                "twap_slice_interval_ms": 99,
            },
            "ERROR_CODE_TWAP_INTERVAL_INVALID",
        ),
        (
            {
                "trigger_type": "twap",
                "trigger_price": None,
                "twap_duration_ms": 1000,
                "twap_slice_interval_ms": 2000,
            },
            "ERROR_CODE_TWAP_INTERVAL_INVALID",
        ),
        (
            {
                "trigger_type": "ladder",
                "trigger_price": None,
                "ladder_price_min": "100",
                "ladder_price_max": "110",
                "ladder_levels": 1,
            },
            "ERROR_CODE_LADDER_LEVELS_INVALID",
        ),
        (
            {
                "trigger_type": "ladder",
                "trigger_price": None,
                "ladder_price_min": "110",
                "ladder_price_max": "100",
                "ladder_levels": 5,
            },
            "ERROR_CODE_TRIGGER_PRICE_INVALID",
        ),
        (
            {
                "trigger_type": "ladder",
                "trigger_price": None,
                "ladder_price_min": "-1",
                "ladder_price_max": "100",
                "ladder_levels": 5,
            },
            "ERROR_CODE_TRIGGER_PRICE_INVALID",
        ),
    ],
)
def test_trigger_create_refusal_carries_the_fields_code(overrides, code) -> None:
    assert _code(lambda: _create(**overrides)) == code


def test_oco_leg_off_the_tick_grid_keeps_its_own_code() -> None:
    # A code the refusal already names is never replaced.
    assert (
        _code(lambda: _oco(stop_loss={"trigger_price": "90.0000000001"}))
        == "ERROR_CODE_PRICE_TICK_SIZE"
    )


def test_shape_refusals_stay_without_a_code() -> None:
    # A buy trailing stop without its maximum price refuses the request's shape.
    assert (
        _code(
            lambda: _create(
                trigger_type="trailing_stop",
                side="buy",
                trigger_price=None,
                trailing_distance_bps=100,
            )
        )
        is None
    )
    assert _code(lambda: _create(side="hold")) is None


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"trigger_price": "-1"}, "ERROR_CODE_TRIGGER_PRICE_INVALID"),
        ({"trailing_distance_ticks": -1}, "ERROR_CODE_TRAILING_DISTANCE_INVALID"),
        ({"trailing_distance_bps": 10_001}, "ERROR_CODE_TRAILING_DISTANCE_INVALID"),
        # Was refused without a code; the API now answers this, not TRIGGER_PRICE_INVALID.
        ({"activation_price": "-1"}, "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_INVALID"),
        ({"max_slippage_ticks": -1}, "ERROR_CODE_SLIPPAGE_TICKS_INVALID"),
        ({"max_slippage_bps": -1}, "ERROR_CODE_SLIPPAGE_BPS_INVALID"),
        ({"max_slippage_bps": 10_001}, "ERROR_CODE_SLIPPAGE_BPS_INVALID"),
    ],
)
def test_trigger_modify_refusal_carries_the_fields_code(overrides, code) -> None:
    assert _code(lambda: modify_trigger_to_proto(trigger_id="9", **overrides)) == code


def test_trigger_modify_still_clears_caps_with_zero() -> None:
    proto = modify_trigger_to_proto(trigger_id="9", max_slippage_ticks=0, max_slippage_bps=None)
    assert proto.max_slippage_ticks == 0
    proto = modify_trigger_to_proto(trigger_id="9", max_slippage_bps=10_000)
    assert proto.max_slippage_bps == 10_000


def _oco(**overrides: Any):
    args: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "sell",
        "qty": "0.1",
        "take_profit": {"trigger_price": "110"},
        "stop_loss": {"trigger_price": "90"},
        "quantity_scale": 8,
    }
    args.update(overrides)
    return create_oco_to_proto(**args)


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"qty": "0"}, "ERROR_CODE_BAD_QTY"),
        ({"take_profit": {"trigger_price": "-1"}}, "ERROR_CODE_TRIGGER_PRICE_INVALID"),
        ({"stop_loss": {"trigger_price_ticks": 0}}, "ERROR_CODE_TRIGGER_PRICE_INVALID"),
        (
            {"take_profit": {"trigger_price": "110", "order_type": "limit", "limit_price": "-1"}},
            "ERROR_CODE_BAD_PRICE",
        ),
        (
            {"stop_loss": {"trigger_price": "90", "child": {"limit_gtc": {"price_ticks": 0}}}},
            "ERROR_CODE_BAD_PRICE",
        ),
    ],
)
def test_oco_refusal_carries_the_fields_code(overrides, code) -> None:
    assert _code(lambda: _oco(**overrides)) == code


def test_oco_sends_no_fee_asset() -> None:
    assert "fee_asset" not in {field.name for field in _oco().oco.DESCRIPTOR.fields}


# --- fee asset ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"trigger_type": "take_profit"},
        {"trigger_type": "trailing_stop", "trigger_price": None, "trailing_distance_bps": 100},
        {
            "trigger_type": "twap",
            "trigger_price": None,
            "twap_duration_ms": 1000,
            "twap_slice_interval_ms": 100,
        },
        {
            "trigger_type": "ladder",
            "trigger_price": None,
            "ladder_price_min": "100",
            "ladder_price_max": "110",
            "ladder_levels": 5,
        },
    ],
)
@pytest.mark.parametrize("fee_asset", ["base", "BASE"])
def test_sell_trigger_with_a_base_fee_is_refused_before_sending(overrides, fee_asset) -> None:
    with pytest.raises(PolyesterValidationError, match="fee_asset=quote") as refused:
        _create(fee_asset=fee_asset, **overrides)
    assert refused.value.code == "ERROR_CODE_FEE_ASSET_NOT_ALLOWED"


def test_buy_trigger_may_select_a_base_fee_and_a_sell_quote() -> None:
    # Whether the pair allows it is the server's to say.
    buy = _create(side="buy", fee_asset="base")
    assert buy.trigger.fee_asset == orders_pb2.BASE
    sell = _create(fee_asset="quote")
    assert sell.trigger.fee_asset == orders_pb2.QUOTE


def test_sell_order_with_a_base_fee_carries_the_apis_code() -> None:
    request = CreateOrderRequest(
        symbol="BTC-USDT",
        symbol_id=1,
        side="sell",
        order_type="market",
        qty=Quantity.from_scaled(1, scale=8),
        fee_asset="base",
    )
    with pytest.raises(PolyesterValidationError) as refused:
        create_order_to_proto(request, quantity_scale=8)
    assert refused.value.code == "ERROR_CODE_FEE_ASSET_NOT_ALLOWED"


# --- insufficient funds -------------------------------------------------------------------------


def _detail(code: int) -> ConnectError:
    detail = orders_pb2.ErrorDetail(code=code)
    return ConnectError(Code.FAILED_PRECONDITION, "INSUFFICIENT_FUNDS", details=[detail])


def test_insufficient_funds_at_failed_precondition_keeps_its_code() -> None:
    mapped = map_connect_error(_detail(orders_pb2.ERROR_CODE_INSUFFICIENT_FUNDS))
    assert type(mapped) is PolyesterApiError, repr(mapped)
    assert mapped.code == "ERROR_CODE_INSUFFICIENT_FUNDS"
    # An account-state refusal: final for the unchanged request, nothing applied.
    assert not is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


async def test_insufficient_funds_rest_problem_is_unchanged() -> None:
    error, calls = await _call(
        "write", 400, PROBLEM, json.dumps({"code": "INSUFFICIENT_FUNDS", "detail": "d"})
    )
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == "ERROR_CODE_INSUFFICIENT_FUNDS"
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)
    assert calls == 1


# --- REST answers a temporary failure with 503 ---------------------------------------------------


@pytest.mark.parametrize(
    "code", ["SERVICE_UNAVAILABLE", "UPSTREAM_ERROR", "WALLET_RESOLUTION_UNAVAILABLE"]
)
async def test_503_problem_is_unavailable_with_its_code(code: str) -> None:
    body = json.dumps({"code": code, "detail": "temporarily unavailable", "status": 503})
    # A create may have reached the API: sent once, outcome unknown, as ConnectRPC
    # unavailable reads.
    error, calls = await _call("write", 503, PROBLEM, body)
    assert type(error) is PolyesterServerError, repr(error)
    assert error.status_code == 503
    assert code in (error.code or "")
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    assert calls == 1
    connect = map_connect_error(ConnectError(Code.UNAVAILABLE, "unavailable"))
    assert type(connect) is type(error)
    # A read retries it.
    error, calls = await _call("read", 503, PROBLEM, body, fail_for=2)
    assert error is None, repr(error)
    assert calls == 3


async def test_503_with_a_deadline_code_reads_as_connect_deadline_exceeded() -> None:
    error, calls = await _call(
        "write", 503, JSON, json.dumps({"code": "deadline_exceeded", "message": "deadline"})
    )
    assert type(error) is PolyesterTimeoutError, repr(error)
    assert type(map_connect_error(ConnectError(Code.DEADLINE_EXCEEDED, "x"))) is type(error)
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    assert calls == 1
    error, calls = await _call(
        "write", 503, PROBLEM, json.dumps({"code": "DEADLINE_EXCEEDED", "detail": "deadline"})
    )
    assert isinstance(error, PolyesterServerError), repr(error)
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    assert calls == 1


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        (PROBLEM, json.dumps({"code": "SERVICE_UNAVAILABLE", "detail": "d"})),
        (PROBLEM, json.dumps({"code": "API_KEY_CREATE_OUTCOME_UNKNOWN", "detail": "d"})),
        ("text/plain", "error code: 504"),
    ],
)
async def test_504_is_an_unknown_outcome_never_resent(content_type: str, body: str) -> None:
    error, calls = await _call("write", 504, content_type, body)
    assert error is not None
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    assert calls == 1


@pytest.mark.parametrize("status", [502, 504])
async def test_edge_plain_text_failure_retries_a_read(status: int) -> None:
    error, calls = await _call("read", status, "text/plain", "error code: 502", fail_for=2)
    assert error is None, repr(error)
    assert calls == 3


# --- a 504 stays an unknown outcome whatever its body names -------------------------------------

_RETRYABLE_AT_504 = [
    (PROBLEM, {"code": "RATE_LIMIT_EXCEEDED", "rateLimit": {"reason": "QUOTA_EXCEEDED"}}),
    (PROBLEM, {"code": "RATE_LIMIT_AUTHORITY_UNAVAILABLE"}),
    (PROBLEM, {"code": "OVERLOADED"}),
    (PROBLEM, {"code": "SYSTEM_RATE_LIMITED"}),
    (PROBLEM, {"code": "REPLAY_CAPACITY_EXHAUSTED"}),
    (PROBLEM, {"code": "AUTH_REPLAY_CAPACITY_EXHAUSTED"}),
    (PROBLEM, {"code": "AUTH_TEMPORARILY_UNAVAILABLE"}),
    (PROBLEM, {"code": "TIMESTAMP_SKEW"}),
    (PROBLEM, {"code": "ORDER_SEQUENCE_EXHAUSTED"}),
    (JSON, {"code": "resource_exhausted", "message": "rate limit exceeded, retry later"}),
]


@pytest.mark.parametrize(("content_type", "body"), _RETRYABLE_AT_504)
async def test_504_with_a_retryable_code_stays_unknown(content_type: str, body: dict) -> None:
    error, calls = await _call(
        "write", 504, content_type, json.dumps(body), headers={"Retry-After": "2"}
    )
    assert type(error) is PolyesterServerError, repr(error)
    assert error.status_code == 504
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    assert calls == 1
    # A safe read retries it.
    error, calls = await _call("read", 504, content_type, json.dumps(body), fail_for=1)
    assert error is None, repr(error)
    assert calls == 2


@pytest.mark.parametrize(
    "body",
    [
        {"code": "RATE_LIMIT_EXCEEDED", "rateLimit": {"reason": "QUOTA_EXCEEDED"}},
        {"code": "AUTH_REPLAY_CAPACITY_EXHAUSTED"},
    ],
)
async def test_429_control_stays_a_retryable_refusal(body: dict) -> None:
    error, calls = await _call("write", 429, PROBLEM, json.dumps(body))
    assert type(error) is PolyesterRateLimitError, repr(error)
    assert is_retryable_error(error)
    assert not mutation_outcome_unknown(error)
    assert calls == 1


async def test_504_outcome_unknown_code_keeps_its_code() -> None:
    error, _ = await _call(
        "write", 504, PROBLEM, json.dumps({"code": "ORDER_CREATE_OUTCOME_UNKNOWN", "detail": "d"})
    )
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == "ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN"
    assert mutation_outcome_unknown(error)


# --- a 503 keeps its code and Retry-After, and reads wait for it ---------------------------------


async def test_503_keeps_its_code_and_retry_after() -> None:
    body = json.dumps({"code": "UPSTREAM_ERROR", "detail": "upstream_unavailable", "status": 503})
    error, _ = await _call("write", 503, PROBLEM, body, headers={"Retry-After": "30"})
    assert type(error) is PolyesterServerError, repr(error)
    assert (error.code or "").endswith("UPSTREAM_ERROR")
    assert error.retry_after == 30
    error, _ = await _call(
        "write",
        503,
        JSON,
        json.dumps({"code": "unavailable", "message": "temporarily unavailable"}),
        headers={"Retry-After": "7"},
    )
    assert type(error) is PolyesterServerError, repr(error)
    assert error.retry_after == 7
    error, _ = await _call("write", 503, PROBLEM, json.dumps({"code": "SERVICE_UNAVAILABLE"}))
    assert type(error) is PolyesterServerError and error.retry_after is None, repr(error)


async def test_read_retry_waits_for_retry_after_or_gives_up() -> None:
    body = json.dumps({"code": "UPSTREAM_ERROR", "status": 503})
    # Past the 2-second budget: no retry, the delay is on the error.
    started = time.monotonic()
    error, calls = await _call(
        "read", 503, PROBLEM, body, fail_for=1, headers={"Retry-After": "30"}
    )
    assert time.monotonic() - started < 1.5
    assert type(error) is PolyesterServerError and error.retry_after == 30, repr(error)
    assert calls == 1
    # Within the budget: the retry waits at least that long.
    started = time.monotonic()
    error, calls = await _call(
        "read", 503, PROBLEM, body, fail_for=1, headers={"Retry-After": "0.4"}
    )
    assert error is None, repr(error)
    assert calls == 2
    assert time.monotonic() - started >= 0.4


# --- round 3: status first, and Retry-After on every answer -------------------------------------


def _connect_detail(type_name: str, message) -> dict:
    import base64

    return {
        "type": type_name,
        "value": base64.b64encode(message.SerializeToString()).decode().rstrip("="),
    }


def _round3_504_bodies() -> list[dict]:
    from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2

    rate = _connect_detail(
        "orders.v1.ErrorDetail",
        orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED),
    )
    limit = _connect_detail(
        "polyester.ratelimit.v1.RateLimitDetail", ratelimit_pb2.RateLimitDetail(retry_after_ms=1500)
    )
    return [
        {"code": "unavailable", "message": "TIMESTAMP_SKEW"},
        {"code": "unavailable", "message": "rate limited", "details": [rate]},
        {"code": "unavailable", "message": "rate limited", "details": [limit]},
        {"code": "resource_exhausted", "message": "rate limited", "details": [rate]},
        {"code": "unavailable", "message": "AUTH_TEMPORARILY_UNAVAILABLE"},
        {"code": "unavailable", "message": "temporarily unavailable"},
        {"code": "internal", "message": "boom"},
        {"code": "unknown", "message": "?"},
    ]


@pytest.mark.parametrize("index", range(8))
async def test_round3_504_connect_bodies_are_unknown(index: int) -> None:
    body = json.dumps(_round3_504_bodies()[index])
    error, calls = await _call("write", 504, JSON, body)
    assert error is not None
    assert not is_retryable_error(error), repr(error)
    assert mutation_outcome_unknown(error), repr(error)
    assert calls == 1
    error, calls = await _call("read", 504, JSON, body, fail_for=1)
    assert error is None, repr(error)
    assert calls == 2


async def test_round3_504_outcome_unknown_beside_a_rate_limit_detail() -> None:
    from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2

    limit = _connect_detail(
        "polyester.ratelimit.v1.RateLimitDetail", ratelimit_pb2.RateLimitDetail(retry_after_ms=1500)
    )
    body = json.dumps(
        {
            "code": "resource_exhausted",
            "message": "ORDER_CREATE_OUTCOME_UNKNOWN",
            "details": [limit],
        }
    )
    error, _ = await _call("write", 504, JSON, body)
    assert type(error) is PolyesterApiError, repr(error)
    assert error.code == "ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN"
    assert mutation_outcome_unknown(error) and not is_retryable_error(error)


@pytest.mark.parametrize(
    ("status", "content_type", "body"),
    [
        (503, PROBLEM, {"code": "AUTH_TEMPORARILY_UNAVAILABLE", "status": 503}),
        (503, PROBLEM, {"code": "ACCOUNT_ROUTING_INVALID", "status": 503}),
        (503, PROBLEM, {"code": "PAIR_BACKLOGGED", "status": 503}),
        (503, JSON, {"code": "unavailable", "message": "AUTH_TEMPORARILY_UNAVAILABLE"}),
        (429, PROBLEM, {"code": "RATE_LIMIT_EXCEEDED", "status": 429}),
        (504, PROBLEM, {"code": "ORDER_CREATE_OUTCOME_UNKNOWN", "status": 504}),
    ],
)
async def test_round3_retry_after_on_every_answer(
    status: int, content_type: str, body: dict
) -> None:
    error, _ = await _call(
        "write", status, content_type, json.dumps(body), headers={"Retry-After": "30"}
    )
    assert error is not None
    assert getattr(error, "retry_after", None) == 30, repr(error)


@pytest.mark.parametrize(
    "body",
    [
        {"code": "UPSTREAM_ERROR", "status": 503},
        {"code": "AUTH_TEMPORARILY_UNAVAILABLE", "status": 503},
    ],
)
async def test_round3_read_retry_waits_for_retry_after(body: dict) -> None:
    started = time.monotonic()
    error, calls = await _call(
        "read", 503, PROBLEM, json.dumps(body), fail_for=1, headers={"Retry-After": "30"}
    )
    assert time.monotonic() - started < 1.5
    assert calls == 1
    assert error is not None and getattr(error, "retry_after", None) == 30, repr(error)
    started = time.monotonic()
    error, calls = await _call(
        "read", 503, PROBLEM, json.dumps(body), fail_for=1, headers={"Retry-After": "0.4"}
    )
    assert error is None, repr(error)
    assert calls == 2
    assert time.monotonic() - started >= 0.4


def test_round3_retry_delay_reads_every_errors_retry_after() -> None:
    from polyester._wire import retry_delay
    from polyester.errors import AUTH_TEMPORARILY_UNAVAILABLE

    auth = PolyesterApiError("busy", code=AUTH_TEMPORARILY_UNAVAILABLE)
    assert retry_delay(auth, 0.025) == 0.025
    auth.retry_after = 30
    assert retry_delay(auth, 0.025) == 30
    assert retry_delay(PolyesterServerError("x", retry_after=0.001), 0.025) == 0.025
    assert retry_delay(PolyesterRateLimitError("x", retry_after=1.5), 0.025) == 1.5


@pytest.mark.parametrize("message", ["context deadline exceeded", "TIMESTAMP_SKEW"])
async def test_round3_connect_deadline_at_504_is_the_deadline(message: str) -> None:
    # ConnectRPC answers a server-side deadline_exceeded with HTTP 504: the
    # request's deadline, whatever its message says, never a refusal.
    body = json.dumps({"code": "deadline_exceeded", "message": message})
    error, calls = await _call("write", 504, JSON, body)
    assert type(error) is PolyesterTimeoutError, repr(error)
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)
    assert calls == 1
    error, calls = await _call("read", 504, JSON, body, fail_for=1)
    assert error is None, repr(error)
    assert calls == 2
