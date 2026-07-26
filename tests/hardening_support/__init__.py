"""Local mock HTTP/WS servers for POLY-3746 L2 tests."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.asyncio.server import ServerConnection, serve

from polyester.auth import ApiKeyCredentials

CENTRIFUGE_PROTOBUF = "centrifuge-protobuf"


@dataclass(frozen=True)
class ParsedRequest:
    method: str
    path: str
    body: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)


class HttpScriptKind(Enum):
    NOT_FOUND = auto()
    JSON = auto()
    RAW = auto()
    HEADERS_THEN_STALL = auto()
    NEVER_RESPOND = auto()
    CHUNKED_BODY = auto()
    SLOW_DRIP = auto()


@dataclass(frozen=True)
class HttpScript:
    kind: HttpScriptKind
    status: int = 200
    body: bytes = b""
    headers: tuple[tuple[str, str], ...] = ()
    stall: float = 30.0
    total_bytes: int = 0
    chunk_size: int = 4096
    delay: float = 0.15
    chunks: tuple[bytes, ...] = ()

    @staticmethod
    def not_found() -> HttpScript:
        return HttpScript(kind=HttpScriptKind.NOT_FOUND)

    @staticmethod
    def json(status: int, body: bytes | str | dict[str, Any]) -> HttpScript:
        if isinstance(body, dict):
            raw = json.dumps(body).encode()
        elif isinstance(body, str):
            raw = body.encode()
        else:
            raw = body
        return HttpScript(kind=HttpScriptKind.JSON, status=status, body=raw)

    @staticmethod
    def raw(
        status: int,
        *,
        headers: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
        body: bytes = b"",
    ) -> HttpScript:
        return HttpScript(
            kind=HttpScriptKind.RAW,
            status=status,
            headers=tuple(headers),
            body=body,
        )

    @staticmethod
    def headers_then_stall(
        status: int = 200,
        *,
        headers: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
        stall: float = 30.0,
    ) -> HttpScript:
        return HttpScript(
            kind=HttpScriptKind.HEADERS_THEN_STALL,
            status=status,
            headers=tuple(headers),
            stall=stall,
        )

    @staticmethod
    def never_respond() -> HttpScript:
        return HttpScript(kind=HttpScriptKind.NEVER_RESPOND)

    @staticmethod
    def chunked_body(
        status: int = 200,
        *,
        total_bytes: int,
        chunk_size: int = 4096,
    ) -> HttpScript:
        return HttpScript(
            kind=HttpScriptKind.CHUNKED_BODY,
            status=status,
            total_bytes=total_bytes,
            chunk_size=chunk_size,
        )

    @staticmethod
    def slow_drip(
        status: int = 200,
        *,
        chunks: Sequence[bytes],
        delay: float = 0.15,
        headers: list[tuple[str, str]] | tuple[tuple[str, str], ...] = (),
    ) -> HttpScript:
        return HttpScript(
            kind=HttpScriptKind.SLOW_DRIP,
            status=status,
            chunks=tuple(chunks),
            delay=delay,
            headers=tuple(headers),
        )


HttpHandler = Callable[[ParsedRequest], HttpScript | Awaitable[HttpScript]]


class MockHttpServer:
    """Async TCP HTTP mock with active-connection + request counters."""

    def __init__(self) -> None:
        self.base_url: str = ""
        self.request_count = 0
        self.active = 0
        self._server: asyncio.AbstractServer | None = None
        self._handler: HttpHandler | None = None

    @classmethod
    async def spawn(cls, handler: HttpHandler) -> MockHttpServer:
        self = cls()
        self._handler = handler
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        sockets = self._server.sockets
        assert sockets
        host, port = sockets[0].getsockname()[:2]
        self.base_url = f"http://{host}:{port}"
        return self

    async def aclose(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self.active += 1
        try:
            raw = await _read_http_request(reader)
            if raw is None:
                return
            req = _parse_http_request(raw)
            self.request_count += 1
            assert self._handler is not None
            script = self._handler(req)
            if asyncio.iscoroutine(script):
                script = await script
            await _write_http_script(reader, writer, script)
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            return
        finally:
            self.active = max(0, self.active - 1)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def _read_http_request(reader: asyncio.StreamReader) -> bytes | None:
    try:
        header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5.0)
    except (asyncio.IncompleteReadError, TimeoutError, asyncio.LimitOverrunError):
        return None
    headers_text = header.decode("iso-8859-1", errors="replace")
    content_length = 0
    for line in headers_text.split("\r\n")[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().lower() == "content-length":
            try:
                content_length = int(value.strip())
            except ValueError:
                content_length = 0
    body = b""
    if content_length > 0:
        try:
            body = await reader.readexactly(content_length)
        except asyncio.IncompleteReadError:
            return None
    return header + body


def _parse_http_request(raw: bytes) -> ParsedRequest:
    header_blob, _, body = raw.partition(b"\r\n\r\n")
    text = header_blob.decode("iso-8859-1", errors="replace")
    lines = text.split("\r\n")
    request_line = lines[0] if lines else ""
    parts = request_line.split()
    method = parts[0] if parts else ""
    path = parts[1] if len(parts) > 1 else "/"
    path = path.split("?", 1)[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return ParsedRequest(method=method, path=path, body=body, headers=headers)


async def _await_peer_close_or_timeout(
    reader: asyncio.StreamReader,
    timeout: float | None,
) -> None:
    """Block until the client closes, or ``timeout`` elapses.

    Polls in short slices so a cancelled/httpx-aborted peer is noticed promptly
    even when the OS does not deliver a full read wake-up immediately.
    """
    if timeout is None:
        try:
            await reader.read(1)
        except (asyncio.CancelledError, ConnectionResetError):
            return
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if reader.at_eof():
            return
        slice_timeout = min(0.05, max(0.0, deadline - time.monotonic()))
        if slice_timeout <= 0:
            return
        try:
            data = await asyncio.wait_for(reader.read(1), timeout=slice_timeout)
            if not data:
                return
        except TimeoutError:
            continue
        except (asyncio.CancelledError, ConnectionResetError):
            return


async def _write_http_script(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    script: HttpScript,
) -> None:
    if script.kind is HttpScriptKind.NEVER_RESPOND:
        await _await_peer_close_or_timeout(reader, None)
        return

    if script.kind is HttpScriptKind.NOT_FOUND:
        writer.write(
            b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        return

    if script.kind is HttpScriptKind.JSON:
        head = (
            f"HTTP/1.1 {script.status} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(script.body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        writer.write(head + script.body)
        await writer.drain()
        return

    if script.kind is HttpScriptKind.RAW:
        head = f"HTTP/1.1 {script.status} OK\r\n".encode()
        for key, value in script.headers:
            head += f"{key}: {value}\r\n".encode()
        head += b"Connection: close\r\n\r\n"
        writer.write(head + script.body)
        await writer.drain()
        return

    if script.kind is HttpScriptKind.HEADERS_THEN_STALL:
        head = f"HTTP/1.1 {script.status} OK\r\n".encode()
        for key, value in script.headers:
            head += f"{key}: {value}\r\n".encode()
        head += b"\r\n"
        writer.write(head)
        await writer.drain()
        await _await_peer_close_or_timeout(reader, script.stall)
        return

    if script.kind is HttpScriptKind.CHUNKED_BODY:
        head = (
            f"HTTP/1.1 {script.status} OK\r\n"
            f"Transfer-Encoding: chunked\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        writer.write(head)
        await writer.drain()
        sent = 0
        chunk_size = max(script.chunk_size, 1)
        while sent < script.total_bytes:
            n = min(script.total_bytes - sent, chunk_size)
            chunk = b"x" * n
            try:
                writer.write(f"{n:x}\r\n".encode() + chunk + b"\r\n")
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                return
            sent += n
        try:
            writer.write(b"0\r\n\r\n")
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            return
        return

    if script.kind is HttpScriptKind.SLOW_DRIP:
        head = f"HTTP/1.1 {script.status} OK\r\n".encode()
        has_te = any(k.lower() == "transfer-encoding" for k, _ in script.headers)
        for key, value in script.headers:
            head += f"{key}: {value}\r\n".encode()
        if not has_te:
            head += b"Transfer-Encoding: chunked\r\n"
        head += b"Connection: close\r\n\r\n"
        writer.write(head)
        await writer.drain()
        for chunk in script.chunks:
            await asyncio.sleep(script.delay)
            try:
                writer.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                return
        try:
            writer.write(b"0\r\n\r\n")
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            return
        return


class MockWsServer:
    """Async WebSocket mock with optional Centrifugo protobuf replies + active count."""

    def __init__(self) -> None:
        self.addr: str = ""
        self.active = 0
        self.connects = 0
        self._server: Any = None
        self._mode: str = "hang"

    def ws_url(self) -> str:
        return f"ws://{self.addr}/connection/websocket"

    @classmethod
    async def spawn_hang_after_accept(cls) -> MockWsServer:
        self = cls()
        self._mode = "hang"
        await self._start()
        return self

    @classmethod
    async def spawn_centrifugo_public(cls) -> MockWsServer:
        self = cls()
        self._mode = "centrifugo"
        await self._start()
        return self

    @classmethod
    async def spawn_centrifugo_disconnect_after_handshake(cls) -> MockWsServer:
        """First connection: reply then close. Later connections stay up (centrifugo)."""
        self = cls()
        self._mode = "disconnect_once"
        await self._start()
        return self

    async def _start(self) -> None:
        self._server = await serve(
            self._handler,
            "127.0.0.1",
            0,
            subprotocols=[CENTRIFUGE_PROTOBUF],
            select_subprotocol=_select_centrifuge_subprotocol,
            ping_interval=None,
            ping_timeout=None,
        )
        sockets = self._server.sockets
        assert sockets
        host, port = sockets[0].getsockname()[:2]
        self.addr = f"{host}:{port}"

    async def aclose(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handler(self, ws: ServerConnection) -> None:
        self.connects += 1
        connect_index = self.connects
        self.active += 1
        try:
            if self._mode == "hang":
                async for _ in ws:
                    pass
                return
            disconnect_after = self._mode == "disconnect_once" and connect_index == 1
            replies = 0
            async for message in ws:
                if isinstance(message, bytes) and replies < 2:
                    replies += 1
                    await ws.send(centrifugo_ok_reply(replies))
                    if disconnect_after and replies >= 2:
                        await ws.close()
                        return
        except Exception:
            return
        finally:
            self.active = max(0, self.active - 1)


def _select_centrifuge_subprotocol(
    connection: ServerConnection,
    subprotocols: Sequence[str],
) -> str | None:
    del connection
    for proto in subprotocols:
        if str(proto).strip() == CENTRIFUGE_PROTOBUF:
            return CENTRIFUGE_PROTOBUF
    return None


def centrifugo_ok_reply(reply_id: int) -> bytes:
    """Encode a Centrifugo protobuf Reply with ``id`` and no error."""
    message = bytearray()
    # field 1 (id), wire varint
    message.append((1 << 3) | 0)
    _put_varint(message, reply_id)
    return _length_delimit(bytes(message))


def _put_varint(buf: bytearray, value: int) -> None:
    value = int(value)
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            buf.append(byte | 0x80)
        else:
            buf.append(byte)
            break


def _length_delimit(message: bytes) -> bytes:
    out = bytearray()
    _put_varint(out, len(message))
    out.extend(message)
    return bytes(out)


def make_test_credentials(key_id: str = "ak_test") -> ApiKeyCredentials:
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    return ApiKeyCredentials(key_id=key_id, private_key=private)


async def wait_until(
    pred: Callable[[], bool],
    timeout: float,
    *,
    interval: float = 0.01,
) -> None:
    start = time.monotonic()
    while not pred():
        if time.monotonic() - start > timeout:
            raise AssertionError(f"condition not met within {timeout:.3f}s")
        await asyncio.sleep(interval)


def connect_proto_response(body: bytes) -> HttpScript:
    """Unary Connect/protobuf success response for local L2 mocks."""
    return HttpScript.raw(
        200,
        headers=[("Content-Type", "application/proto")],
        body=body,
    )
