"""Errors and diagnostics must not carry the userinfo (password) of a URL."""

from __future__ import annotations

import socket

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester import AsyncPolyester
from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError, PolyesterError
from polyester.realtime.auth import fetch_connection_token, fetch_subscription_token
from polyester.transport import TransportConfig, TransportFactory

# An obviously fake password placed in URL userinfo.
FAKE_URL_PASSWORD = "fake-url-password-marker"
HOST = "api.example.test"


def _credentials() -> ApiKeyCredentials:
    return ApiKeyCredentials(
        key_id="key_userinfo", private_key=Ed25519PrivateKey.generate().private_bytes_raw()
    )


def _http(status: int) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"code": "permission_denied", "message": "refused"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _assert_no_userinfo(path: str, err: BaseException) -> None:
    for rendered in (str(err), repr(err), repr(vars(err)), repr(err.args)):
        assert FAKE_URL_PASSWORD not in rendered, f"{path} leaked URL userinfo: {rendered}"
        assert "fake-user" not in rendered, f"{path} leaked URL userinfo: {rendered}"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize("path", ["connection", "subscription"])
@pytest.mark.parametrize("userinfo", [True, False])
async def test_token_auth_errors_redact_url_userinfo(
    status: int, path: str, userinfo: bool
) -> None:
    api_url = f"https://fake-user:{FAKE_URL_PASSWORD}@{HOST}" if userinfo else f"https://{HOST}"
    async with _http(status) as http:
        with pytest.raises(PolyesterAuthError) as caught:
            if path == "connection":
                await fetch_connection_token(http, _credentials(), api_url=api_url)
            else:
                await fetch_subscription_token(
                    http, _credentials(), api_url=api_url, channel="orders:1"
                )
    err = caught.value
    label = f"{path} HTTP {status} userinfo={userinfo}"
    _assert_no_userinfo(label, err)
    endpoint = (
        f"https://{HOST}/v1/rt/token"
        if path == "connection"
        else f"https://{HOST}/v1/rt/subscribe?channel=orders%3A1"
    )
    assert err.status_code == status
    assert err.endpoint == endpoint
    assert f"[{endpoint}]" in str(err)


@pytest.mark.asyncio
async def test_unparsable_api_url_error_redacts_userinfo() -> None:
    api_url = f"https://fake-user:{FAKE_URL_PASSWORD}@{HOST}:notaport"
    async with _http(401) as http:
        with pytest.raises((PolyesterError, httpx.InvalidURL, ValueError)) as caught:
            await fetch_connection_token(http, _credentials(), api_url=api_url)
    _assert_no_userinfo("unparsable URL", caught.value)


@pytest.mark.asyncio
async def test_rest_connection_error_redacts_url_userinfo() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    api_url = f"http://fake-user:{FAKE_URL_PASSWORD}@127.0.0.1:{port}"
    async with AsyncPolyester(
        api_url=api_url,
        api_key_id="key_userinfo",
        api_private_key=Ed25519PrivateKey.generate().private_bytes_raw().hex(),
        hydrate_catalogs=False,
    ) as client:
        with pytest.raises(PolyesterError) as caught:
            await client.api_keys.get(key_id="x")
    chained: BaseException | None = caught.value
    while chained is not None:
        _assert_no_userinfo(f"REST {type(chained).__name__}", chained)
        chained = chained.__cause__ or chained.__context__


def test_transport_config_repr_redacts_url_userinfo() -> None:
    config = TransportConfig(api_url=f"https://fake-user:{FAKE_URL_PASSWORD}@{HOST}")
    factory = TransportFactory(config)
    for rendered in (repr(config), str(config), repr(factory)):
        assert FAKE_URL_PASSWORD not in rendered
        assert f"https://{HOST}" in rendered
