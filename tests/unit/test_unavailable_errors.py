from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.any_pb2 import Any

from polyester._wire import map_connect_error
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRateLimitError,
    PolyesterServerError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from tests.unit.test_auth_error_codes import _rest_error

TEMPORARY_CODES = [
    (orders_pb2, "ERROR_CODE_RATE_LIMIT_POLICY_UNAVAILABLE"),
    (orders_pb2, "ERROR_CODE_POLICY_UNAVAILABLE"),
    (orders_pb2, "ERROR_CODE_FEE_SCHEDULE_UNAVAILABLE"),
    (orders_pb2, "ERROR_CODE_UNAVAILABLE"),
    (orders_pb2, "ERROR_CODE_PAIR_BACKLOGGED"),
    (orders_pb2, "ERROR_CODE_ORDER_MODIFY_IN_PROGRESS"),
    (orders_pb2, "ERROR_CODE_ORDER_PLACEMENT_PENDING"),
    (orders_pb2, "ERROR_CODE_SETTLEMENT_BACKLOGGED"),
    (orders_pb2, "ERROR_CODE_TRIGGER_CONTROLS_BUSY"),
    (orders_pb2, "ERROR_CODE_TRIGGER_CONTROL_IN_PROGRESS"),
    (orders_pb2, "ERROR_CODE_ACCOUNT_ROUTING_INVALID"),
    (orders_pb2, "ERROR_CODE_UPSTREAM_ERROR"),
    (withdraw_pb2, "ERROR_CODE_SERVICE_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_ACCOUNT_SHARD_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_CHAIN_METADATA_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_DESTINATION_VALIDATION_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_FEE_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_STEP_UP_UNAVAILABLE"),
    (withdraw_pb2, "ERROR_CODE_SUPPLY_UNAVAILABLE"),
    (transfer_pb2, "ERROR_CODE_SERVICE_UNAVAILABLE"),
    (transfer_pb2, "ERROR_CODE_ACCOUNT_SHARD_UNAVAILABLE"),
    (transfer_pb2, "ERROR_CODE_CAPITAL_VIEW_UNAVAILABLE"),
    (transfer_pb2, "ERROR_CODE_STEP_UP_UNAVAILABLE"),
]
KNOWN_REFUSALS = {
    "ERROR_CODE_UNAVAILABLE",
    "ERROR_CODE_ORDER_MODIFY_IN_PROGRESS",
    "ERROR_CODE_POLICY_UNAVAILABLE",
    "ERROR_CODE_ORDER_PLACEMENT_PENDING",
    "ERROR_CODE_PAIR_BACKLOGGED",
    "ERROR_CODE_RATE_LIMIT_POLICY_UNAVAILABLE",
    "ERROR_CODE_SETTLEMENT_BACKLOGGED",
    "ERROR_CODE_FEE_SCHEDULE_UNAVAILABLE",
    "ERROR_CODE_TRIGGER_CONTROL_IN_PROGRESS",
    "ERROR_CODE_TRIGGER_CONTROLS_BUSY",
}
DENIED_CODES = [
    "ERROR_CODE_POLICY_MARKET_DENY",
    "ERROR_CODE_POLICY_TRADING_HALTED",
    "ERROR_CODE_POLICY_SPOT_TRADE_DENY",
    "ERROR_CODE_POLICY_SPOT_READ_DENY",
]


@pytest.mark.parametrize("module,name", TEMPORARY_CODES)
@pytest.mark.parametrize("packed", [False, True])
def test_connect_unavailable_preserves_service_code(module, name, packed):
    detail = module.ErrorDetail(code=module.ErrorCode.Value(name))
    wire_detail = detail
    if packed:
        wire_detail = Any()
        wire_detail.Pack(detail)
    mapped = map_connect_error(ConnectError(Code.UNAVAILABLE, "retry later", details=[wire_detail]))

    if name == "ERROR_CODE_ACCOUNT_ROUTING_INVALID":
        assert isinstance(mapped, PolyesterApiError)
        assert not is_retryable_error(mapped)
        assert not mutation_outcome_unknown(mapped)
        assert mapped.code == name
        return
    assert isinstance(mapped, PolyesterServerError)
    assert not isinstance(mapped, PolyesterAuthError)
    assert is_retryable_error(mapped) is (name in KNOWN_REFUSALS)
    assert mutation_outcome_unknown(mapped) is (name not in KNOWN_REFUSALS)
    assert mapped.code == name
    assert mapped.status_code == 503
    assert mapped.raw == detail
    assert str(mapped) == "retry later"


@pytest.mark.parametrize("module,name", TEMPORARY_CODES)
async def test_rest_unavailable_preserves_service_code(httpserver, module, name):
    code = name.removeprefix("ERROR_CODE_")
    status = 502 if code == "UPSTREAM_ERROR" else 503
    mapped = await _rest_error(
        httpserver, status, {"code": code, "status": status, "detail": "retry later"}
    )

    if name == "ERROR_CODE_ACCOUNT_ROUTING_INVALID":
        assert isinstance(mapped, PolyesterApiError)
        assert not is_retryable_error(mapped)
        assert not mutation_outcome_unknown(mapped)
        assert mapped.code == name
        return
    assert isinstance(mapped, PolyesterServerError)
    assert not isinstance(mapped, PolyesterAuthError)
    known = name in KNOWN_REFUSALS and name != "ERROR_CODE_UNAVAILABLE"
    assert is_retryable_error(mapped) is known
    assert mutation_outcome_unknown(mapped) is (not known)
    expected_code = name if name in orders_pb2.ErrorCode.DESCRIPTOR.values_by_name else code
    assert mapped.code == expected_code
    assert mapped.status_code == status
    assert mapped.problem.code == code
    assert mapped.problem.status == status
    assert str(mapped) == "retry later"


@pytest.mark.parametrize("name", DENIED_CODES)
def test_connect_policy_denial_stays_auth_error(name):
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value(name))
    mapped = map_connect_error(ConnectError(Code.PERMISSION_DENIED, "denied", details=[detail]))

    assert isinstance(mapped, PolyesterAuthError)
    assert not is_retryable_error(mapped)
    assert mapped.code == name
    assert mapped.status_code == 403


@pytest.mark.parametrize(
    "module,name",
    [
        (orders_pb2, "ERROR_CODE_MARKET_PRICE_UNAVAILABLE"),
        (orders_pb2, "ERROR_CODE_ORDER_LIMITS_UNAVAILABLE"),
        (transfer_pb2, "ERROR_CODE_SMART_ACCOUNT_UNAVAILABLE"),
        (withdraw_pb2, "ERROR_CODE_SOURCE_SMART_ACCOUNT_UNAVAILABLE"),
    ],
)
def test_unavailable_precondition_is_not_a_retryable_server_error(module, name):
    detail = module.ErrorDetail(code=module.ErrorCode.Value(name))
    mapped = map_connect_error(
        ConnectError(Code.FAILED_PRECONDITION, "not ready", details=[detail])
    )
    assert isinstance(mapped, PolyesterApiError)
    assert not is_retryable_error(mapped)


@pytest.mark.parametrize(
    "name",
    [
        name
        for name in orders_pb2.ErrorCode.DESCRIPTOR.values_by_name
        if name.endswith("_OUTCOME_UNKNOWN")
    ],
)
@pytest.mark.parametrize("packed", [False, True])
def test_connect_unavailable_outcome_unknown_stays_non_retryable(name, packed):
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value(name))
    wire_detail = detail
    if packed:
        wire_detail = Any()
        wire_detail.Pack(detail)
    mapped = map_connect_error(
        ConnectError(Code.UNAVAILABLE, "check outcome", details=[wire_detail])
    )

    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == name
    assert not is_retryable_error(mapped)
    assert mutation_outcome_unknown(mapped)


@pytest.mark.parametrize(
    "name",
    [
        "ERROR_CODE_UNAVAILABLE",
        "ERROR_CODE_RATE_LIMIT_POLICY_UNAVAILABLE",
        "ERROR_CODE_RATE_LIMIT_EXCEEDED",
    ],
)
def test_connect_unavailable_keeps_nested_rate_limit_delay(name):
    detail = orders_pb2.ErrorDetail(
        code=orders_pb2.ErrorCode.Value(name),
        rate_limit=ratelimit_pb2.RateLimitDetail(
            reason=ratelimit_pb2.AUTHORITY_UNAVAILABLE, retry_after_ms=1250
        ),
    )
    mapped = map_connect_error(ConnectError(Code.UNAVAILABLE, "back off", details=[detail]))

    assert isinstance(mapped, PolyesterRateLimitError)
    assert mapped.retry_after == 1.25
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)


@pytest.mark.parametrize("module", [orders_pb2, withdraw_pb2, transfer_pb2])
def test_connect_unavailable_keeps_rate_limit_classification(module):
    detail = module.ErrorDetail(code=module.ERROR_CODE_RATE_LIMIT_EXCEEDED)
    mapped = map_connect_error(ConnectError(Code.UNAVAILABLE, "back off", details=[detail]))

    assert isinstance(mapped, PolyesterRateLimitError)
    assert is_retryable_error(mapped)
    assert not mutation_outcome_unknown(mapped)
