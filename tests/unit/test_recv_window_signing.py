"""A receive window is signed on its own line right after the timestamp and
sent as X-API-RECV-WINDOW; a value the server would refuse fails first."""

from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pytest_httpserver import HTTPServer

from polyester import AsyncPolyester, PolyesterValidationError
from polyester.auth import (
    MAX_RECV_WINDOW_MS,
    MIN_RECV_WINDOW_MS,
    ApiKeyCredentials,
    canonical_signing_string,
    sign_request,
    sign_request_async,
)
from polyester.gen.auth.v1.auth_connect import AuthServiceClient
from polyester.gen.auth.v1.auth_pb2 import MeRequest, MeResponse
from polyester.transport import TransportConfig, TransportFactory

_URL = "https://api.example.test/foo/bar?b=2&a=1"
_BODY_HASH = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def _credentials() -> tuple[Ed25519PrivateKey, ApiKeyCredentials]:
    private = Ed25519PrivateKey.generate()
    return private, ApiKeyCredentials(key_id="ak_test", private_key=private.private_bytes_raw())


def test_canonical_string_puts_the_window_after_the_timestamp() -> None:
    signed = canonical_signing_string(
        timestamp_ms="123", method="post", url=_URL, body=b"{}", recv_window_ms=5000
    )
    assert signed == f"123\n5000\nPOST\n/foo/bar\na=1&b=2\n{_BODY_HASH}"
    plain = canonical_signing_string(timestamp_ms="123", method="post", url=_URL, body=b"{}")
    assert plain == f"123\nPOST\n/foo/bar\na=1&b=2\n{_BODY_HASH}"


async def test_sign_request_sends_and_signs_the_window() -> None:
    private, credentials = _credentials()
    url = "https://api.example.test/orders.v1.OrdersService/CreateOrder"
    for headers in (
        sign_request(
            credentials,
            method="POST",
            url=url,
            body=b"body",
            timestamp_ms="1762553700123",
            recv_window_ms=5000,
        ),
        await sign_request_async(
            credentials,
            method="POST",
            url=url,
            body=b"body",
            timestamp_ms="1762553700123",
            recv_window_ms=5000,
        ),
    ):
        assert headers["X-API-RECV-WINDOW"] == "5000"
        body_hash = hashlib.sha256(b"body").hexdigest()
        payload = f"1762553700123\n5000\nPOST\n/orders.v1.OrdersService/CreateOrder\n\n{body_hash}"
        private.public_key().verify(bytes.fromhex(headers["X-API-SIGNATURE"]), payload.encode())
    plain = sign_request(
        credentials, method="POST", url=url, body=b"body", timestamp_ms="1762553700123"
    )
    assert "X-API-RECV-WINDOW" not in plain


@pytest.mark.parametrize("window", [0, -1, 60_001, True, 5000.0, "5000"])
def test_a_window_the_server_would_refuse_fails_before_signing(window: object) -> None:
    _, credentials = _credentials()
    with pytest.raises(PolyesterValidationError):
        sign_request(
            credentials, method="GET", url="https://api.example.test/x", recv_window_ms=window
        )  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError):
        TransportConfig(api_url="https://api.example.test", recv_window_ms=window)  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError):
        AsyncPolyester(recv_window_ms=window, hydrate_catalogs=False)  # type: ignore[arg-type]


def test_window_bounds_are_accepted() -> None:
    _, credentials = _credentials()
    for window in (MIN_RECV_WINDOW_MS, MAX_RECV_WINDOW_MS):
        headers = sign_request(
            credentials, method="GET", url="https://api.example.test/x", recv_window_ms=window
        )
        assert headers["X-API-RECV-WINDOW"] == str(window)


@pytest.mark.parametrize("window", [2500, None])
async def test_transport_sends_the_configured_window_signed(
    httpserver: HTTPServer, window: int | None
) -> None:
    private, credentials = _credentials()
    api_url = httpserver.url_for("/").rstrip("/")
    httpserver.expect_request("/auth.v1.AuthService/Me", method="POST").respond_with_data(
        MeResponse().SerializeToString(),
        content_type="application/proto",
        headers={"Connect-Protocol-Version": "1"},
    )
    factory = TransportFactory(
        TransportConfig(api_url=api_url, recv_window_ms=window), credentials=credentials
    )
    try:
        await factory.create_auth_client(AuthServiceClient).me(MeRequest())
    finally:
        await factory.aclose()
    captured, _ = httpserver.log[0]
    assert captured.headers.get("X-API-RECV-WINDOW") == (None if window is None else str(window))
    canonical = canonical_signing_string(
        timestamp_ms=captured.headers["X-API-TIMESTAMP"],
        method="POST",
        url=f"{api_url}/auth.v1.AuthService/Me",
        body=captured.data,
        recv_window_ms=window,
    )
    private.public_key().verify(
        bytes.fromhex(captured.headers["X-API-SIGNATURE"]), canonical.encode()
    )
