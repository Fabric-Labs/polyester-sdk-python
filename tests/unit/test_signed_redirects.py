"""Signed requests must never be forwarded to another origin by a redirect.

Each test runs isolated loopback HTTP servers and signs with a disposable
Ed25519 key generated here. The redirecting origin answers with 307 or 308
and a Location on another host or another port that keeps the request path.
"""

from __future__ import annotations

import re
import socket
from collections.abc import Iterator

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester
from polyester.auth import ApiKeyCredentials
from polyester.gen.auth.v1.auth_pb2 import MeResponse
from polyester.realtime.auth import fetch_connection_token

_SIGNED_HEADERS = ("X-API-KEY-ID", "X-API-TIMESTAMP", "X-API-SIGNATURE")
_KEY_ID = "ak_redirect_test"
_ANY_PATH = re.compile(".*")


def _disposable_key_hex() -> str:
    return Ed25519PrivateKey.generate().private_bytes_raw().hex()


def _me_answer(request: Request) -> Response:
    message = MeResponse(account_id=7, api_key_id=_KEY_ID)
    if request.headers.get("Content-Type", "").startswith("application/json"):
        return Response(
            '{"accountId":"7","apiKeyId":"ak_redirect_test"}', 200, content_type="application/json"
        )
    return Response(message.SerializeToString(), 200, content_type="application/proto")


def _signed(request: Request) -> bool:
    return any(request.headers.get(name) for name in _SIGNED_HEADERS)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _start(host: str, port: int) -> HTTPServer:
    server = HTTPServer(host=host, port=port)
    try:
        server.start()
    except OSError as exc:  # pragma: no cover - depends on the loopback setup
        pytest.skip(f"cannot listen on {host}:{port}: {exc}")
    return server


@pytest.fixture(params=["port-only", "host-only"])
def origins(request: pytest.FixtureRequest) -> Iterator[tuple[HTTPServer, HTTPServer]]:
    """The redirecting origin and the destination on another port or host."""
    if request.param == "port-only":
        redirecting, destination = _start("127.0.0.1", 0), _start("127.0.0.1", 0)
    else:
        port = _free_port()
        redirecting, destination = _start("127.0.0.1", port), _start("127.0.0.2", port)
    destination.expect_request(_ANY_PATH).respond_with_handler(_me_answer)
    try:
        yield redirecting, destination
    finally:
        for server in (redirecting, destination):
            server.clear()
            if server.is_running():
                server.stop()


def _base_url(server: HTTPServer) -> str:
    return f"http://{server.host}:{server.port}"


def _redirect_to(destination: HTTPServer, status: int):
    def handler(request: Request) -> Response:
        return Response(status=status, headers={"Location": _base_url(destination) + request.path})

    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["json", "binary"])
@pytest.mark.parametrize("status", [307, 308])
async def test_signed_call_is_not_forwarded_across_origins(
    origins: tuple[HTTPServer, HTTPServer], status: int, wire_format: str
) -> None:
    redirecting, destination = origins
    assert _base_url(redirecting) != _base_url(destination)
    redirecting.expect_request(_ANY_PATH).respond_with_handler(_redirect_to(destination, status))
    client = AsyncPolyester(
        api_url=_base_url(redirecting),
        api_key_id=_KEY_ID,
        api_private_key=_disposable_key_hex(),
        wire_format=wire_format,  # type: ignore[arg-type]
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(Exception):  # noqa: B017 - the red test asserts only that it fails
            await client.auth.me()
    finally:
        await client.aclose()

    received = [request for request, _ in destination.log]
    assert [r for r in received if _signed(r)] == []
    assert received == []
    assert len(redirecting.log) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("caller_client", [False, True])
async def test_realtime_token_request_is_not_forwarded_across_origins(
    origins: tuple[HTTPServer, HTTPServer], status: int, caller_client: bool
) -> None:
    redirecting, destination = origins
    redirecting.expect_request(_ANY_PATH).respond_with_handler(_redirect_to(destination, status))
    credentials = ApiKeyCredentials(
        key_id=_KEY_ID, private_key=Ed25519PrivateKey.generate().private_bytes_raw()
    )
    # A caller-supplied httpx client that follows redirects, or one like the
    # SDK's own.
    http = httpx.AsyncClient(timeout=5.0, follow_redirects=caller_client)
    try:
        with pytest.raises(Exception):  # noqa: B017 - the red test asserts only that it fails
            await fetch_connection_token(http, credentials, api_url=_base_url(redirecting))
    finally:
        await http.aclose()

    received = [request for request, _ in destination.log]
    assert [r for r in received if _signed(r)] == []
    assert received == []


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["json", "binary"])
async def test_signed_call_without_redirect_succeeds(wire_format: str) -> None:
    origin = _start("127.0.0.1", 0)
    origin.expect_request(_ANY_PATH).respond_with_handler(_me_answer)
    client = AsyncPolyester(
        api_url=_base_url(origin),
        api_key_id=_KEY_ID,
        api_private_key=_disposable_key_hex(),
        wire_format=wire_format,  # type: ignore[arg-type]
        hydrate_catalogs=False,
    )
    try:
        me = await client.auth.me()
        received = [request for request, _ in origin.log]
    finally:
        await client.aclose()
        origin.clear()
        origin.stop()
    assert me.api_key_id == _KEY_ID
    assert len(received) == 1
    assert _signed(received[0])
