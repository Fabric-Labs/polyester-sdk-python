import httpx
import pytest

from polyester.realtime.auth import _auth_http_error
from tests.unit.test_auth_error_codes import _rest_error


@pytest.mark.parametrize(
    "code,status,detail",
    [
        ("UNAUTHENTICATED", 401, ""),
        ("TIMESTAMP_SKEW", 401, "clock skew"),
        ("AUTH_TIMESTAMP_SKEW", 401, "clock skew"),
        ("AUTH_AUTHENTICATION_REQUIRED", 401, "unauthenticated"),
        ("PERMISSION_DENIED", 403, "missing read permission"),
    ],
)
async def test_early_auth_and_realtime_share_problem_decoder(httpserver, code, status, detail):
    body = {
        "type": "https://polyester.dev/problems/" + code.lower().replace("_", "-"),
        "code": code,
        "status": status,
        "detail": detail,
    }
    gateway_error = await _rest_error(httpserver, status, body)
    realtime_error = _auth_http_error(
        status_code=status,
        label="token",
        endpoint="https://api.test/v1/rt/token",
        body=httpx.Response(status, json=body).content,
    )
    for error in (gateway_error, realtime_error):
        assert error.problem.code == code
        assert error.problem.status == status
        assert error.problem.detail == detail
        assert error.problem.type == body["type"]
