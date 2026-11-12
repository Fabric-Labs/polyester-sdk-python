"""REST auth and permission refusals Python already classifies.

POLY-8756 and POLY-8757 were found in the Rust SDK; these cases pin the same
answers here, through a public create against a local server.
"""

from __future__ import annotations

import pytest

from polyester.errors import (
    PolyesterAuthError,
    auth_error_code,
    is_retryable_error,
    mutation_outcome_unknown,
)
from tests.unit.test_readable_error_bodies import PROBLEM, _call


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401])
async def test_poly_8756_missing_headers_keeps_its_auth_reason(status: int) -> None:
    err, calls = await _call("write", status, PROBLEM, '{"code":"MISSING_HEADERS","detail":"d"}')
    assert calls == 1
    assert err is not None
    assert auth_error_code(err) == "AUTH_MISSING_HEADERS"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["SUBACCOUNT_READ_FORBIDDEN", "QUICKSWAP_NOT_PERMITTED"])
async def test_poly_8757_rest_service_refusal_keeps_its_code(code: str) -> None:
    body = f'{{"status":403,"code":"{code}","detail":"not allowed"}}'
    err, calls = await _call("write", 403, PROBLEM, body)
    assert calls == 1
    assert isinstance(err, PolyesterAuthError)
    # The same code as the typed ConnectRPC detail names.
    assert (err.status_code, err.code, str(err)) == (403, f"ERROR_CODE_{code}", "not allowed")
    assert auth_error_code(err) is None
    assert not is_retryable_error(err)
    assert not mutation_outcome_unknown(err)
