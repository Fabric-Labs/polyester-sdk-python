"""WebSocket handshake DEBUG logs must not carry URL credentials.

websockets sends credentials in a WebSocket URL's userinfo as an
``Authorization: Basic`` header, and logs every handshake header when its
``websockets.client`` logger is at DEBUG. Base64 is not redaction: the header
decodes back to the password. The header must still be sent on the wire.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from http import HTTPStatus

import pytest
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from polyester.realtime.client import AsyncRealtimeClient
from polyester.realtime.private_orders import PrivateOrderStream

# Obviously fake credentials placed in the WebSocket URL's userinfo.
FAKE_USER = "fake-ws-user"
FAKE_PASSWORD = "fake-ws-password-marker"
BASIC = base64.b64encode(f"{FAKE_USER}:{FAKE_PASSWORD}".encode()).decode()
MARKERS = (FAKE_PASSWORD, BASIC, f"{FAKE_USER}:")


@contextlib.asynccontextmanager
async def refusing_server() -> AsyncIterator[tuple[int, list[Headers]]]:
    """A local WebSocket endpoint that refuses every handshake with HTTP 403."""
    seen: list[Headers] = []

    def refuse(connection: ServerConnection, request: Request) -> Response:
        seen.append(request.headers)
        return connection.respond(HTTPStatus.FORBIDDEN, "refused\n")

    async def handler(_connection: ServerConnection) -> None:
        return None

    async with serve(
        handler,
        "127.0.0.1",
        0,
        process_request=refuse,
        # The fake server's own request log is not the SDK's.
        logger=logging.getLogger("tests.fake_ws_server"),
    ) as server:
        port = server.sockets[0].getsockname()[1]
        yield port, seen


async def _generic(url: str) -> None:
    client = AsyncRealtimeClient(url)
    try:
        await client.subscribe_proto("trades:BTC-USDT", decode=lambda b: b, auto_reconnect=False)
    finally:
        await client.aclose()


async def _private_orders(url: str) -> None:
    async def token(*_args: object) -> str:
        return "fake-token"

    stream = PrivateOrderStream(url=url, fetch_connect_token=token, fetch_subscribe_token=token)
    try:
        await asyncio.wait_for(stream.subscribe(42), 5)
    finally:
        await stream.aclose()


PATHS: list[Callable[[str], Awaitable[None]]] = [_generic, _private_orders]


@pytest.mark.asyncio
@pytest.mark.parametrize("dial", PATHS, ids=lambda dial: dial.__name__.strip("_"))
async def test_handshake_debug_log_redacts_basic_auth_from_url_userinfo(
    dial: Callable[[str], Awaitable[None]], caplog: pytest.LogCaptureFixture
) -> None:
    async with refusing_server() as (port, seen):
        url = f"ws://{FAKE_USER}:{FAKE_PASSWORD}@127.0.0.1:{port}/ws"
        with caplog.at_level(logging.DEBUG), contextlib.suppress(Exception):
            await dial(url)

    # The credentials still authenticate the handshake on the wire.
    assert seen, "the handshake never reached the server"
    assert seen[0]["Authorization"] == f"Basic {BASIC}"

    handshake = [r.getMessage() for r in caplog.records if r.name.startswith("websockets")]
    for line in handshake:
        for marker in MARKERS:
            assert marker not in line, f"handshake log leaked {marker!r}: {line!r}"
    # The other handshake diagnostics stay, the Authorization header named but redacted.
    assert any(line.startswith("> GET /ws") for line in handshake)
    assert any(line.startswith("> Host: 127.0.0.1") for line in handshake)
    assert "> Authorization: [REDACTED]" in handshake
    assert "< HTTP/1.1 403 Forbidden" in handshake


@pytest.mark.parametrize(
    ("msg", "args", "expected"),
    [
        ("> %s: %s", ("Authorization", f"Basic {BASIC}"), "> Authorization: [REDACTED]"),
        ("> %s: %s", ("authorization", f"Bearer {FAKE_PASSWORD}"), "> authorization: [REDACTED]"),
        (
            "> %s: %s",
            ("Proxy-Authorization", f"Basic {BASIC}"),
            "> Proxy-Authorization: [REDACTED]",
        ),
        (f"> Authorization: Basic {BASIC}", (), "> Authorization: [REDACTED]"),
        ("> %s: %s", ("Host", "127.0.0.1:1"), "> Host: 127.0.0.1:1"),
        ("> GET %s HTTP/1.1", ("/ws",), "> GET /ws HTTP/1.1"),
        ("< HTTP/1.1 %d %s", (403, "Forbidden"), "< HTTP/1.1 403 Forbidden"),
    ],
)
def test_ws_client_logger_redacts_only_credential_headers(
    msg: str, args: tuple[object, ...], expected: str, caplog: pytest.LogCaptureFixture
) -> None:
    from polyester.realtime._ws_log import WS_CLIENT_LOGGER

    with caplog.at_level(logging.DEBUG, logger="websockets.client"):
        WS_CLIENT_LOGGER.debug(msg, *args, extra={"websocket": "fake-connection"})
    (record,) = caplog.records
    assert record.name == "websockets.client"
    assert record.getMessage() == expected
    assert record.websocket == "fake-connection"  # type: ignore[attr-defined]


def test_ws_client_logger_is_silent_when_debug_is_off(caplog: pytest.LogCaptureFixture) -> None:
    from polyester.realtime._ws_log import WS_CLIENT_LOGGER

    with caplog.at_level(logging.INFO, logger="websockets.client"):
        WS_CLIENT_LOGGER.debug("> %s: %s", "Authorization", f"Basic {BASIC}")
    assert caplog.records == []
    assert not WS_CLIENT_LOGGER.isEnabledFor(logging.DEBUG)
