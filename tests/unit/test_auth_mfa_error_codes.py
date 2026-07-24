from __future__ import annotations

from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import (
    AUTH_MFA_ELEVATION_REQUIRED,
    AUTH_MFA_LAST_FACTOR_REQUIRED,
    AUTH_MFA_NOT_ENROLLED,
    AUTH_STEP_UP_REQUIRED,
    PolyesterApiError,
    PolyesterAuthError,
    auth_error_code,
    is_mfa_elevation_required,
    is_mfa_enrollment_required,
    is_mfa_last_factor_required,
    is_step_up_required,
)
from polyester.gen.auth.v1 import auth_pb2


def _map(code: auth_pb2.AuthErrorCode, message: str = "mfa control flow") -> PolyesterApiError:
    detail = auth_pb2.AuthErrorDetail(code=code, message=message)
    mapped = map_connect_error(ConnectError(Code.PERMISSION_DENIED, "denied", details=[detail]))
    assert isinstance(mapped, PolyesterApiError)
    return mapped


def test_map_connect_error_surfaces_stable_mfa_codes() -> None:
    cases = [
        (auth_pb2.AUTH_MFA_NOT_ENROLLED, AUTH_MFA_NOT_ENROLLED, is_mfa_enrollment_required),
        (auth_pb2.AUTH_STEP_UP_REQUIRED, AUTH_STEP_UP_REQUIRED, is_step_up_required),
        (
            auth_pb2.AUTH_MFA_ELEVATION_REQUIRED,
            AUTH_MFA_ELEVATION_REQUIRED,
            is_mfa_elevation_required,
        ),
        (
            auth_pb2.AUTH_MFA_LAST_FACTOR_REQUIRED,
            AUTH_MFA_LAST_FACTOR_REQUIRED,
            is_mfa_last_factor_required,
        ),
    ]
    for proto_code, want, predicate in cases:
        mapped = _map(proto_code)
        assert mapped.code == want
        assert auth_error_code(mapped) == want
        assert predicate(mapped)
        for _, other_code, other_predicate in cases:
            if other_code == want:
                continue
            assert not other_predicate(mapped)


def test_mfa_predicates_ignore_message_text_and_removed_api_key_code() -> None:
    assert not is_mfa_enrollment_required(Exception("must enroll mfa"))
    assert not is_mfa_enrollment_required(PolyesterAuthError("must enroll mfa"))
    assert not is_step_up_required(PolyesterApiError("step-up required", code="permission_denied"))
    assert not is_mfa_enrollment_required(
        PolyesterApiError("api key mfa", code="AUTH_API_KEY_MFA_REQUIRED")
    )
