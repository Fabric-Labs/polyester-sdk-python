import httpx
import pytest

from polyester.realtime.auth import _auth_http_error
from tests.unit.test_auth_error_codes import _rest_error


@pytest.mark.parametrize(
    "code,status,detail,expected_type",
    [
        ("UNAUTHENTICATED", 401, "", "https://polyester.dev/problems/unauthenticated"),
        ("TIMESTAMP_SKEW", 401, "clock skew", "https://polyester.dev/problems/timestamp-skew"),
        (
            "AUTH_TIMESTAMP_SKEW",
            401,
            "clock skew",
            "https://polyester.dev/problems/auth-timestamp-skew",
        ),
        (
            "AUTH_AUTHENTICATION_REQUIRED",
            401,
            "unauthenticated",
            "https://polyester.dev/problems/auth-authentication-required",
        ),
        (
            "PERMISSION_DENIED",
            403,
            "missing read permission",
            "https://polyester.dev/problems/permission-denied",
        ),
        (
            "AUTH_SESSION_KIND_NOT_ALLOWED",
            403,
            "",
            "https://polyester.dev/problems/auth-session-kind-not-allowed",
        ),
    ],
)
@pytest.mark.parametrize(
    "supplied_type", [None, "https://polyester.dev/problems/AUTH_SESSION_KIND_NOT_ALLOWED"]
)
async def test_early_auth_and_realtime_share_problem_decoder(
    httpserver, code, status, detail, expected_type, supplied_type
):
    body = {
        "code": code,
        "status": status,
        "detail": detail,
    }
    if supplied_type is not None:
        body["type"] = supplied_type
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
        assert error.problem.type == expected_type
