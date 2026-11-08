"""Errors and diagnostics must not carry the userinfo (password) of a URL."""

from __future__ import annotations

import base64
import logging
import socket

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester import AsyncPolyester
from polyester.auth import ApiKeyCredentials, sign_request
from polyester.errors import PolyesterAuthError, PolyesterError
from polyester.realtime.auth import fetch_connection_token, fetch_subscription_token
from polyester.realtime.client import AsyncRealtimeClient
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


TOKEN_PATHS = ["connection", "subscription"]


async def _fetch(http: httpx.AsyncClient, path: str, api_url: str) -> str:
    if path == "connection":
        return await fetch_connection_token(http, _credentials(), api_url=api_url)
    return await fetch_subscription_token(http, _credentials(), api_url=api_url, channel="orders:1")


def _scripted_http(
    outcome: str, seen: list[httpx.Request], *, auth: httpx.Auth | None = None
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if outcome == "transport":
            raise httpx.ConnectError("connection failed", request=request)
        if outcome == "timeout":
            raise httpx.ReadTimeout("read timed out", request=request)
        if outcome == "refusal":
            return httpx.Response(403, json={"code": "permission_denied", "message": "refused"})
        return httpx.Response(200, json={"token": "fake-token"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), auth=auth)


def _assert_nothing_carries_userinfo(path: str, rendered: str) -> None:
    assert FAKE_URL_PASSWORD not in rendered, f"{path} leaked URL userinfo: {rendered}"
    assert "fake-user" not in rendered, f"{path} leaked URL userinfo: {rendered}"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", TOKEN_PATHS)
@pytest.mark.parametrize("outcome", ["success", "refusal", "transport", "timeout"])
async def test_token_requests_keep_userinfo_out_of_logs_and_errors(
    path: str, outcome: str, caplog: pytest.LogCaptureFixture
) -> None:
    api_url = f"https://fake-user:{FAKE_URL_PASSWORD}@{HOST}"
    seen: list[httpx.Request] = []
    caught: BaseException | None = None
    with caplog.at_level(logging.DEBUG):
        async with _scripted_http(outcome, seen) as http:
            try:
                assert await _fetch(http, path, api_url) == "fake-token"
            except Exception as exc:  # noqa: BLE001 - every outcome but success raises
                caught = exc
    assert (caught is None) == (outcome == "success")
    label = f"{path} {outcome}"
    for record in caplog.records:
        _assert_nothing_carries_userinfo(f"{label} log", record.getMessage())
    for request in seen:
        _assert_nothing_carries_userinfo(f"{label} request URL", str(request.url))
    chained = caught
    while chained is not None:
        _assert_nothing_carries_userinfo(f"{label} {type(chained).__name__}", str(chained))
        _assert_nothing_carries_userinfo(f"{label} {type(chained).__name__}", repr(chained))
        _assert_nothing_carries_userinfo(
            f"{label} {type(chained).__name__} vars", repr(getattr(chained, "__dict__", {}))
        )
        request = getattr(chained, "_request", None)
        if request is not None:
            _assert_nothing_carries_userinfo(f"{label} error request", repr(request))
            _assert_nothing_carries_userinfo(f"{label} error request URL", str(request.url))
        chained = chained.__cause__ or chained.__context__


@pytest.mark.asyncio
@pytest.mark.parametrize("path", TOKEN_PATHS)
@pytest.mark.parametrize(
    ("userinfo", "expected"),
    [
        ("fake-user:fake-pass", "fake-user:fake-pass"),
        ("fake%3Auser%40x:p%2Bw%3A%40+x", "fake:user@x:p+w:@+x"),
        ("fake-user", "fake-user:"),
        (":fake-pass", ":fake-pass"),
    ],
)
async def test_token_requests_keep_basic_auth_from_userinfo(
    path: str, userinfo: str, expected: str
) -> None:
    seen: list[httpx.Request] = []
    async with _scripted_http("success", seen) as http:
        await _fetch(http, path, f"https://{userinfo}@{HOST}")
    (request,) = seen
    assert request.headers["authorization"] == (
        "Basic " + base64.b64encode(expected.encode()).decode()
    )
    assert "x-api-signature" in {name.lower() for name in request.headers}
    assert request.url.host == HOST
    assert request.url.raw_path == (
        b"/v1/rt/token" if path == "connection" else b"/v1/rt/subscribe?channel=orders%3A1"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", TOKEN_PATHS)
async def test_client_auth_still_wins_over_url_userinfo(path: str) -> None:
    seen: list[httpx.Request] = []
    async with _scripted_http("success", seen, auth=httpx.BasicAuth("fake-client", "x")) as http:
        await _fetch(http, path, f"https://fake-user:{FAKE_URL_PASSWORD}@{HOST}")
    (request,) = seen
    assert (
        request.headers["authorization"] == "Basic " + base64.b64encode(b"fake-client:x").decode()
    )


MALFORMED_API_URLS = [
    f"ftp://fake-user:{FAKE_URL_PASSWORD}@{HOST}",
    f"https:fake-user:{FAKE_URL_PASSWORD}@{HOST}",
]


def _assert_chain_has_no_userinfo(label: str, err: BaseException | None) -> None:
    chained = err
    while chained is not None:
        name = type(chained).__name__
        _assert_nothing_carries_userinfo(f"{label} {name}", str(chained))
        _assert_nothing_carries_userinfo(f"{label} {name}", repr(chained))
        _assert_nothing_carries_userinfo(
            f"{label} {name} vars", repr(getattr(chained, "__dict__", {}))
        )
        chained = chained.__cause__ or chained.__context__


@pytest.mark.asyncio
@pytest.mark.parametrize("path", TOKEN_PATHS)
@pytest.mark.parametrize("api_url", MALFORMED_API_URLS)
async def test_malformed_api_url_token_errors_redact_userinfo(
    path: str, api_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    seen: list[httpx.Request] = []
    with caplog.at_level(logging.DEBUG):
        async with _scripted_http("success", seen) as http:
            with pytest.raises(PolyesterAuthError) as caught:
                await _fetch(http, path, api_url)
    assert not seen, "a malformed URL must be refused before any request"
    assert str(caught.value) == "Cannot sign malformed absolute HTTP URL"
    for record in caplog.records:
        _assert_nothing_carries_userinfo(f"{path} log", record.getMessage())
    _assert_chain_has_no_userinfo(f"{path} {api_url.split(':')[0]}", caught.value)


@pytest.mark.parametrize("url", [*MALFORMED_API_URLS, f"fake-user:{FAKE_URL_PASSWORD}@{HOST}/p"])
def test_signing_malformed_url_error_redacts_userinfo(url: str) -> None:
    with pytest.raises(PolyesterAuthError) as caught:
        sign_request(_credentials(), method="GET", url=url, body=b"")
    _assert_chain_has_no_userinfo("sign_request", caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ws_url",
    [
        f"http://fake-user:{FAKE_URL_PASSWORD}@127.0.0.1:1/ws",
        f"ftp://fake-user:{FAKE_URL_PASSWORD}@127.0.0.1/ws",
        f"wss:fake-user:{FAKE_URL_PASSWORD}@{HOST}/ws",
        f"fake-user:{FAKE_URL_PASSWORD}@{HOST}/ws",
    ],
)
async def test_malformed_ws_url_dial_errors_redact_userinfo(ws_url: str) -> None:
    client = AsyncRealtimeClient(ws_url)
    with pytest.raises(Exception) as caught:  # noqa: PT011 - websockets' own URI error
        await client.subscribe_proto("trades:BTC-USDT", decode=lambda b: b, auto_reconnect=False)
    _assert_chain_has_no_userinfo(f"dial {ws_url.split(':')[0]}", caught.value)
