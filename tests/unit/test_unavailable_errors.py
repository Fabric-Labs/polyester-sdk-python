from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.any_pb2 import Any

from polyester._wire import map_connect_error
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterServerError,
    is_retryable_error,
)
from polyester.gen.orders.v1 import orders_pb2
from tests.unit.test_auth_error_codes import _rest_error

TEMPORARY_CODES = [
    "ERROR_CODE_RATE_LIMIT_POLICY_UNAVAILABLE",
    "ERROR_CODE_POLICY_UNAVAILABLE",
    "ERROR_CODE_FEE_SCHEDULE_UNAVAILABLE",
    "ERROR_CODE_UNAVAILABLE",
]
DENIED_CODES = [
    "ERROR_CODE_POLICY_MARKET_DENY",
    "ERROR_CODE_POLICY_TRADING_HALTED",
    "ERROR_CODE_POLICY_SPOT_TRADE_DENY",
    "ERROR_CODE_POLICY_SPOT_READ_DENY",
]


@pytest.mark.parametrize("name", TEMPORARY_CODES)
@pytest.mark.parametrize("packed", [False, True])
def test_connect_unavailable_is_retryable_server_error(name, packed):
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value(name))
    wire_detail = detail
    if packed:
        wire_detail = Any()
        wire_detail.Pack(detail)
    mapped = map_connect_error(ConnectError(Code.UNAVAILABLE, "retry later", details=[wire_detail]))

    assert isinstance(mapped, PolyesterServerError)
    assert not isinstance(mapped, PolyesterAuthError)
    assert is_retryable_error(mapped)
    assert mapped.code == name
    assert mapped.status_code == 503
    assert mapped.raw == detail
    assert str(mapped) == "retry later"


@pytest.mark.parametrize("name", TEMPORARY_CODES)
async def test_rest_unavailable_is_retryable_server_error(httpserver, name):
    code = name.removeprefix("ERROR_CODE_")
    mapped = await _rest_error(
        httpserver, 503, {"code": code, "status": 503, "detail": "retry later"}
    )

    assert isinstance(mapped, PolyesterServerError)
    assert not isinstance(mapped, PolyesterAuthError)
    assert is_retryable_error(mapped)
    assert mapped.code == name
    assert mapped.status_code == 503
    assert mapped.problem.code == code
    assert mapped.problem.status == 503
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
    "name", ["ERROR_CODE_MARKET_PRICE_UNAVAILABLE", "ERROR_CODE_ORDER_LIMITS_UNAVAILABLE"]
)
def test_unavailable_precondition_is_not_a_retryable_server_error(name):
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value(name))
    mapped = map_connect_error(
        ConnectError(Code.FAILED_PRECONDITION, "not ready", details=[detail])
    )
    assert isinstance(mapped, PolyesterApiError)
    assert not is_retryable_error(mapped)
