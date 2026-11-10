"""Signed requests must never be forwarded to another origin by a redirect.

Each test runs isolated loopback HTTP servers and signs with a disposable
Ed25519 key generated here. The redirecting origin answers with 307 or 308
and a Location on another host or another port that keeps the request path.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import socket
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import websockets.asyncio.server
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, PolyesterError, PolyesterRedirectError
from polyester.auth import ApiKeyCredentials
from polyester.codecs.scalars import format_id
from polyester.errors import is_retryable_error, mutation_outcome_unknown
from polyester.gen.auth.v1.auth_connect import AuthServiceClient
from polyester.gen.auth.v1.auth_pb2 import MeRequest, MeResponse
from polyester.models.order_key import OrderId
from polyester.realtime.auth import fetch_connection_token
from polyester.realtime.private_orders import _is_terminal_token_error

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


def _assert_refusal(
    err: PolyesterRedirectError, status: int, origin: str, *, same_origin: bool
) -> None:
    assert (err.status_code, err.origin, err.same_origin) == (status, origin, same_origin)
    assert isinstance(err, PolyesterError)
    assert not is_retryable_error(err)
    assert not mutation_outcome_unknown(err)


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
        with pytest.raises(PolyesterRedirectError) as raised:
            await client.auth.me()
    finally:
        await client.aclose()

    received = [request for request, _ in destination.log]
    assert [r for r in received if _signed(r)] == []
    assert received == []
    assert len(redirecting.log) == 1
    _assert_refusal(raised.value, status, _base_url(destination), same_origin=False)


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
        with pytest.raises(PolyesterRedirectError) as raised:
            await fetch_connection_token(http, credentials, api_url=_base_url(redirecting))
    finally:
        await http.aclose()

    received = [request for request, _ in destination.log]
    assert [r for r in received if _signed(r)] == []
    assert received == []
    _assert_refusal(raised.value, status, _base_url(destination), same_origin=False)
    assert _is_terminal_token_error(raised.value)


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


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["json", "binary"])
async def test_signed_same_origin_redirect_is_refused(wire_format: str) -> None:
    """The signature covers the path: a redirect to another path is refused too."""
    origin = _start("127.0.0.1", 0)
    moved: list[str] = []

    def handler(request: Request) -> Response:
        if request.path.startswith("/moved"):
            moved.append(request.path)
            return _me_answer(request)
        return Response(status=307, headers={"Location": "/moved" + request.path})

    origin.expect_request(_ANY_PATH).respond_with_handler(handler)
    client = AsyncPolyester(
        api_url=_base_url(origin),
        api_key_id=_KEY_ID,
        api_private_key=_disposable_key_hex(),
        wire_format=wire_format,  # type: ignore[arg-type]
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(PolyesterRedirectError) as raised:
            await client.auth.me()
    finally:
        await client.aclose()
        origin.clear()
        origin.stop()
    assert moved == []
    _assert_refusal(raised.value, 307, _base_url(origin), same_origin=True)


@pytest.mark.asyncio
async def test_refusal_names_only_the_origin(origins: tuple[HTTPServer, HTTPServer]) -> None:
    redirecting, destination = origins
    secret_location = (
        f"http://fake-user:fake-password@{destination.host}:{destination.port}"
        "/private/path?q=fake-query"
    )
    redirecting.expect_request(_ANY_PATH).respond_with_data(
        "", status=308, headers={"Location": secret_location}
    )
    client = AsyncPolyester(
        api_url=_base_url(redirecting),
        api_key_id=_KEY_ID,
        api_private_key=_disposable_key_hex(),
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(PolyesterRedirectError) as raised:
            await client.auth.me()
    finally:
        await client.aclose()
    assert raised.value.origin == _base_url(destination)
    for secret in ("fake-user", "fake-password", "/private/path", "fake-query"):
        assert secret not in str(raised.value)
    assert destination.log == []


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["json", "binary"])
async def test_unsigned_call_still_follows_redirect(
    origins: tuple[HTTPServer, HTTPServer], wire_format: str
) -> None:
    """Unsigned public calls carry no credentials and keep following redirects."""
    redirecting, destination = origins
    redirecting.expect_request(_ANY_PATH).respond_with_handler(_redirect_to(destination, 307))
    client = AsyncPolyester(
        api_url=_base_url(redirecting),
        wire_format=wire_format,  # type: ignore[arg-type]
        hydrate_catalogs=False,
    )
    try:
        public = client._transport.create_public_client(AuthServiceClient)
        await public.me(MeRequest())
        received = [request for request, _ in destination.log]
    finally:
        await client.aclose()
    assert len(received) == 1
    assert not _signed(received[0])


class _WsRecorder:
    """A WebSocket server that records every handshake attempt and message."""

    def __init__(self) -> None:
        self.handshakes = 0
        self.messages: list[bytes | str] = []
        self.url = ""

    def count(self, _connection: Any, _request: Any) -> None:
        self.handshakes += 1

    async def handler(self, ws: Any) -> None:
        with contextlib.suppress(Exception):
            async for message in ws:
                self.messages.append(message)


@contextlib.asynccontextmanager
async def _ws_recorder() -> AsyncIterator[_WsRecorder]:
    recorder = _WsRecorder()
    async with websockets.asyncio.server.serve(
        recorder.handler,
        "127.0.0.1",
        0,
        subprotocols=["centrifuge-protobuf", "polyester.v1.proto"],
        process_request=recorder.count,
    ) as server:
        port = next(iter(server.sockets)).getsockname()[1]
        recorder.url = f"ws://127.0.0.1:{port}"
        yield recorder


@contextlib.asynccontextmanager
async def _token_origin(ws_destination: str) -> AsyncIterator[str]:
    """An HTTP origin that answers token requests with a token and WebSocket
    upgrades with a 307 to ``ws_destination``, keeping the path."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with contextlib.suppress(Exception):
            head = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1")
            path = head.split(" ", 2)[1]
            if "upgrade: websocket" in head.lower():
                answer = (
                    "HTTP/1.1 307 Temporary Redirect\r\n"
                    f"Location: {ws_destination}{path}\r\nContent-Length: 0\r\n\r\n"
                )
            else:
                body = '{"token":"rt-token-marker"}'
                answer = (
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}"
                )
            writer.write(answer.encode())
            await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    async with server:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"


@pytest.mark.asyncio
async def test_private_order_stream_does_not_follow_a_websocket_redirect() -> None:
    """The private order stream sends its token after the handshake: a
    redirected handshake must not reach the redirect target."""
    async with _ws_recorder() as destination, _token_origin(destination.url) as origin:
        client = AsyncPolyester(
            api_url=origin,
            api_key_id=_KEY_ID,
            api_private_key=_disposable_key_hex(),
            hydrate_catalogs=False,
        )
        try:
            with pytest.raises(PolyesterRedirectError) as raised:
                await asyncio.wait_for(client.realtime.subscribe_private_orders(1), 5)
        finally:
            await client.aclose()
        assert destination.messages == []
        assert destination.handshakes == 0
        _assert_refusal(raised.value, 307, destination.url, same_origin=False)


@pytest.mark.asyncio
async def test_private_channel_does_not_follow_a_websocket_redirect() -> None:
    """A private Centrifugo channel sends its tokens after the handshake: a
    redirected handshake must not reach the redirect target."""
    async with _ws_recorder() as destination, _token_origin(destination.url) as origin:
        client = AsyncPolyester(
            api_url=origin,
            ws_url=origin.replace("http://", "ws://"),
            api_key_id=_KEY_ID,
            api_private_key=_disposable_key_hex(),
            hydrate_catalogs=False,
        )
        try:
            with pytest.raises(PolyesterRedirectError) as raised:
                await asyncio.wait_for(
                    client.realtime.subscribe_proto(
                        "private:orders:1", decode=bytes, auto_reconnect=False
                    ),
                    5,
                )
        finally:
            await client.aclose()
        assert destination.messages == []
        assert destination.handshakes == 0
        _assert_refusal(raised.value, 307, destination.url, same_origin=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["json", "binary"])
@pytest.mark.parametrize("status", [307, 308])
async def test_redirected_mutation_outcome_is_unknown(
    origins: tuple[HTTPServer, HTTPServer], status: int, wire_format: str
) -> None:
    """A redirect proves nothing about whether the origin that answered with it
    applied the mutation first: the outcome of a refused orders.cancel is
    unknown, it is not retryable, and the redirect target receives nothing."""
    redirecting, destination = origins
    applied: list[str] = []

    def apply_then_redirect(request: Request) -> Response:
        if request.path == "/orders.v1.OrdersService/CancelOrder" and _signed(request):
            applied.append(request.path)
        return Response(status=status, headers={"Location": _base_url(destination) + request.path})

    redirecting.expect_request(_ANY_PATH).respond_with_handler(apply_then_redirect)
    client = AsyncPolyester(
        api_url=_base_url(redirecting),
        api_key_id=_KEY_ID,
        api_private_key=_disposable_key_hex(),
        wire_format=wire_format,  # type: ignore[arg-type]
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(PolyesterRedirectError) as raised:
            await client.orders.cancel(key=OrderId(format_id(1)), symbol_id=1)
    finally:
        await client.aclose()

    assert applied == ["/orders.v1.OrdersService/CancelOrder"]
    assert destination.log == []
    assert mutation_outcome_unknown(raised.value)
    assert not is_retryable_error(raised.value)
