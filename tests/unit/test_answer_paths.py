"""Every path that turns an HTTP answer into an error keeps the answer's own
status and the delay it asked for: the realtime token and subscription answer,
a refused WebSocket upgrade and a JSON-RPC endpoint's failed answer."""

from __future__ import annotations

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from polyester._answer import refused_upgrade
from polyester.auth import ApiKeyCredentials
from polyester.chain.rpc import JsonRpcClient, JsonRpcHttpError
from polyester.errors import (
    PolyesterAuthError,
    PolyesterRealtimeError,
    PolyesterTransportError,
)
from polyester.realtime.auth import fetch_rt_token


def _creds() -> ApiKeyCredentials:
    return ApiKeyCredentials(
        key_id="ak_test", private_key=Ed25519PrivateKey.generate().private_bytes_raw()
    )


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (503, b'{"code":"AUTH_TEMPORARILY_UNAVAILABLE","status":503}', PolyesterRealtimeError),
        (401, b'{"code":"unauthenticated","message":"bad signature"}', PolyesterAuthError),
        (403, b'{"code":"permission_denied","message":"missing"}', PolyesterAuthError),
        (403, b"error code: 1010", PolyesterTransportError),
    ],
)
async def test_realtime_token_answer_carries_its_metadata(
    status: int, body: bytes, kind: type
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"Retry-After": "30"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=2.0) as http:
        with pytest.raises(kind) as raised:
            await fetch_rt_token(
                http,
                _creds(),
                url="https://api.example.test/v1/rt/token",
                label="realtime connection token",
            )
    assert raised.value.status_code == status
    assert raised.value.retry_after == 30


def test_refused_upgrade_carries_its_answer() -> None:
    refused = InvalidStatus(
        Response(503, "Service Unavailable", Headers({"Retry-After": "30"}), b"")
    )
    error = refused_upgrade(refused, "private WebSocket connection failed")
    assert isinstance(error, PolyesterRealtimeError)
    assert (error.status_code, error.retry_after) == (503, 30)
    assert error.__cause__ is refused
    # A failure with no answer, such as a refused connection, is none.
    assert refused_upgrade(ConnectionRefusedError(), "failed") is None


async def test_jsonrpc_failed_answer_carries_its_metadata() -> None:
    from tests.hardening_support import HttpScript, MockHttpServer

    async def handler(req) -> HttpScript:
        return HttpScript.raw(
            503, headers=[("Retry-After", "30"), ("Content-Length", "4")], body=b"busy"
        )

    http = await MockHttpServer.spawn(handler)
    try:
        with pytest.raises(httpx.HTTPStatusError) as raised:
            await JsonRpcClient(http.base_url, timeout=2.0).arequest("eth_chainId")
    finally:
        await http.aclose()
    assert isinstance(raised.value, JsonRpcHttpError)
    assert (raised.value.status_code, raised.value.retry_after) == (503, 30)
