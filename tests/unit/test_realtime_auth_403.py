"""POLY-3746: realtime token 403 maps to structured auth/permission error."""

from __future__ import annotations

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError, PolyesterRealtimeError
from polyester.realtime.auth import fetch_rt_token


def _creds() -> ApiKeyCredentials:
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    return ApiKeyCredentials(key_id="ak_test", private_key=private)


@pytest.mark.asyncio
async def test_fetch_rt_token_403_is_auth_error_with_fields() -> None:
    body = b'{"code":"permission_denied","message":"missing rt:subscribe"}'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, timeout=2.0) as http:
        with pytest.raises(PolyesterAuthError) as exc_info:
            await fetch_rt_token(
                http,
                _creds(),
                url="https://api.example.test/v1/rt/token",
                label="realtime connection token",
            )
    err = exc_info.value
    assert err.status_code == 403
    assert err.label == "realtime connection token"
    assert err.body is not None
    assert "permission_denied" in err.body
    assert "HTTP 403" in str(err)
    assert not isinstance(err, PolyesterRealtimeError)


@pytest.mark.asyncio
async def test_fetch_rt_token_401_remains_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, content=b"unauthorized")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, timeout=2.0) as http:
        with pytest.raises(PolyesterAuthError) as exc_info:
            await fetch_rt_token(
                http,
                _creds(),
                url="https://api.example.test/v1/rt/token",
                label="realtime connection token",
            )
    assert exc_info.value.status_code == 401
