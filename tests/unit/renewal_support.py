"""A Centrifugo-shaped server that issues short-lived, single-use tokens.

Connection and subscription tokens expire ``ttl`` units after they are used.
Like Centrifugo the server lets a token run ``grace`` past its TTL, then ends
the subscription with unsubscribe 2501 or closes the connection with 3005.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

import httpx
import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.auth import ApiKeyCredentials
from polyester.realtime.client import AsyncRealtimeClient


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _varint_field(number: int, value: int) -> bytes:
    return _varint(number << 3) + _varint(value)


def _bytes_field(number: int, payload: bytes) -> bytes:
    return _varint((number << 3) | 2) + _varint(len(payload)) + payload


def _frame(reply: bytes) -> bytes:
    return _varint(len(reply)) + reply


def expiry_result(expires_field: int, ttl_field: int, ttl: int) -> bytes:
    if not ttl:
        return b""
    return _varint_field(expires_field, 1) + _varint_field(ttl_field, ttl)


def reply_frame(reply_id: int, result_field: int, result: bytes) -> bytes:
    return _frame(_varint_field(1, reply_id) + _bytes_field(result_field, result))


def error_frame(reply_id: int, code: int, message: str) -> bytes:
    error = _varint_field(1, code) + _bytes_field(2, message.encode())
    return _frame(_varint_field(1, reply_id) + _bytes_field(2, error))


def unsubscribe_push(channel: str, code: int, reason: str) -> bytes:
    body = _varint_field(2, code) + _bytes_field(3, reason.encode())
    return _frame(_bytes_field(4, _bytes_field(2, channel.encode()) + _bytes_field(7, body)))


def publication_frame(data: bytes) -> bytes:
    return _frame(_bytes_field(4, _bytes_field(4, _bytes_field(4, data))))


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    @property
    def remaining(self) -> int:
        return len(self.data) - self.offset

    def varint(self) -> int:
        value = shift = 0
        while True:
            byte = self.data[self.offset]
            self.offset += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return value

    def take(self, length: int) -> bytes:
        value = self.data[self.offset : self.offset + length]
        self.offset += length
        return value

    def skip(self, wire: int) -> None:
        if wire == 0:
            self.varint()
        elif wire == 2:
            self.take(self.varint())
        elif wire == 1:
            self.take(8)
        elif wire == 5:
            self.take(4)


_COMMAND_KINDS = {4: "connect", 5: "subscribe", 14: "refresh", 15: "sub_refresh"}


@dataclass
class Command:
    id: int = 0
    kind: str = "pong"
    channel: str = ""
    token: str = ""


def parse_commands(frame: bytes) -> list[Command]:
    reader = _Reader(frame)
    out: list[Command] = []
    while reader.remaining:
        record = _Reader(reader.take(reader.varint()))
        command = Command()
        while record.remaining:
            key = record.varint()
            number, wire = key >> 3, key & 7
            if number == 1 and wire == 0:
                command.id = record.varint()
            elif wire == 2 and number in _COMMAND_KINDS:
                command.kind = _COMMAND_KINDS[number]
                body = _Reader(record.take(record.varint()))
                while body.remaining:
                    inner = body.varint()
                    inner_number, inner_wire = inner >> 3, inner & 7
                    if inner_wire != 2:
                        body.skip(inner_wire)
                        continue
                    value = body.take(body.varint()).decode()
                    if command.kind in ("connect", "refresh") and inner_number == 1:
                        command.token = value
                    elif inner_number == 1:
                        command.channel = value
                    elif inner_number == 2:
                        command.token = value
            else:
                raise AssertionError(f"unexpected command field {number}")
        out.append(command)
    return out


class Action(Enum):
    ANSWER = "answer"
    # Answer with Centrifugo error 109, token expired.
    REFUSE = "refuse"


def token_serial(token: str) -> int:
    _, _, serial = token.partition("-")
    return int(serial or 0)


@dataclass
class RenewalServer:
    unit: float
    conn_ttl: int = 0
    sub_ttl: int = 0
    # Defaults to three tenths of a unit.
    grace: float | None = None
    publication: bytes | None = None
    publish_every: float = 0.0
    # Runs before each token response; a status other than 200 refuses it.
    token_hook: Callable[[str], Awaitable[int]] | None = None
    # Decides how the server answers each renewal command.
    command_hook: Callable[[str], Awaitable[Action]] | None = None

    url: str = ""
    minted: dict[str, bool] = field(default_factory=dict)
    conns: list[websockets.ServerConnection] = field(default_factory=list)
    conn_tokens: int = 0
    sub_tokens: int = 0
    accepted: int = 0
    subscribes: int = 0
    refreshes: int = 0
    sub_renewals: int = 0
    sub_expiries: int = 0
    conn_expiries: int = 0
    reused: int = 0
    # Renewals carrying a subscription token minted before the connection's
    # own subscribe: work left over from an earlier connection.
    stale: int = 0
    published: int = 0
    _server: websockets.Server | None = None

    def __post_init__(self) -> None:
        if self.grace is None:
            self.grace = self.unit * 0.3
        self.transport = httpx.MockTransport(self._handle_http)

    async def __aenter__(self) -> RenewalServer:
        self._server = await websockets.serve(
            self._handle,
            "127.0.0.1",
            0,
            subprotocols=[websockets.Subprotocol("centrifuge-protobuf")],
        )
        self.url = f"ws://127.0.0.1:{self._server.sockets[0].getsockname()[1]}"
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        assert self._server is not None
        self._server.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._server.wait_closed(), timeout=2)

    def client(self, *, renewal_unit: float | None = None) -> AsyncRealtimeClient:
        private = Ed25519PrivateKey.generate().private_bytes_raw()
        client = AsyncRealtimeClient(
            self.url,
            api_url="https://api.test",
            credentials=ApiKeyCredentials(key_id="ak_test", private_key=private),
            http=httpx.AsyncClient(transport=self.transport),
            max_queue_size=10_000,
        )
        if renewal_unit is not None:
            client._renewal_unit = renewal_unit
        return client

    async def _handle_http(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/rt/token":
            self.conn_tokens += 1
            kind, serial = "conn", self.conn_tokens
        elif request.url.path == "/v1/rt/subscribe":
            self.sub_tokens += 1
            kind, serial = "sub", self.sub_tokens
        else:
            return httpx.Response(404)
        if self.token_hook is not None:
            status = await self.token_hook(kind)
            if status != 200:
                return httpx.Response(
                    status, json={"code": "permission_denied", "message": "token refused"}
                )
        token = f"{kind}-{serial}"
        self.minted[token] = False
        return httpx.Response(200, json={"token": token})

    def _use_token(self, token: str) -> bool:
        if self.minted.get(token, True):
            self.reused += 1
            return False
        self.minted[token] = True
        return True

    def drop_all(self) -> int:
        """Close every open connection from the server side; return how many."""
        dropped = len(self.conns)
        for ws in self.conns:
            ws.transport.abort()
        self.conns = []
        return dropped

    def _deadline(self, ttl: int) -> float | None:
        if not ttl:
            return None
        assert self.grace is not None
        return time.monotonic() + ttl * self.unit + self.grace

    async def _handle(self, ws: websockets.ServerConnection) -> None:
        self.accepted += 1
        self.conns.append(ws)
        commands: asyncio.Queue[Command | None] = asyncio.Queue()

        async def read() -> None:
            try:
                async for raw in ws:
                    assert isinstance(raw, bytes)
                    for command in parse_commands(raw):
                        if command.kind != "pong":
                            commands.put_nowait(command)
            except websockets.ConnectionClosed:
                pass
            finally:
                commands.put_nowait(None)

        reader = asyncio.create_task(read())
        try:
            await self._serve(ws, commands)
        except websockets.ConnectionClosed:
            pass
        finally:
            reader.cancel()
            with contextlib.suppress(BaseException):
                await reader

    async def _serve(
        self, ws: websockets.ServerConnection, commands: asyncio.Queue[Command | None]
    ) -> None:
        command = await commands.get()
        if command is None or command.kind != "connect" or not self._use_token(command.token):
            return
        await ws.send(reply_frame(command.id, 5, expiry_result(3, 4, self.conn_ttl)))
        conn_expires = self._deadline(self.conn_ttl)
        command = await commands.get()
        if command is None or command.kind != "subscribe" or not self._use_token(command.token):
            return
        self.subscribes += 1
        channel = command.channel
        subscribed_with = token_serial(command.token)
        await ws.send(reply_frame(command.id, 6, expiry_result(1, 2, self.sub_ttl)))
        sub_expires = self._deadline(self.sub_ttl)
        next_publish = time.monotonic() + self.publish_every if self.publish_every else None
        while True:
            deadlines = [d for d in (sub_expires, conn_expires, next_publish) if d is not None]
            timeout = max(0.0, min(deadlines) - time.monotonic()) if deadlines else None
            try:
                command = await asyncio.wait_for(commands.get(), timeout=timeout)
            except TimeoutError:
                now = time.monotonic()
                if sub_expires is not None and now >= sub_expires:
                    self.sub_expiries += 1
                    sub_expires = None
                    await ws.send(unsubscribe_push(channel, 2501, "subscription expired"))
                if conn_expires is not None and now >= conn_expires:
                    self.conn_expiries += 1
                    await ws.close(3005, "expired")
                    return
                if next_publish is not None and now >= next_publish:
                    next_publish = now + self.publish_every
                    if self.publication is not None:
                        await ws.send(publication_frame(self.publication))
                        self.published += 1
                continue
            if command is None:
                return
            action = Action.ANSWER
            if self.command_hook is not None:
                action = await self.command_hook(command.kind)
            if action is Action.REFUSE:
                await ws.send(error_frame(command.id, 109, "token expired"))
                continue
            if command.kind == "sub_refresh":
                if token_serial(command.token) <= subscribed_with:
                    self.stale += 1
                if command.channel != channel or not self._use_token(command.token):
                    await ws.send(error_frame(command.id, 109, "token expired"))
                    continue
                self.sub_renewals += 1
                sub_expires = self._deadline(self.sub_ttl)
                await ws.send(reply_frame(command.id, 15, expiry_result(1, 2, self.sub_ttl)))
            elif command.kind == "refresh":
                if not self._use_token(command.token):
                    await ws.send(error_frame(command.id, 109, "token expired"))
                    continue
                self.refreshes += 1
                conn_expires = self._deadline(self.conn_ttl)
                await ws.send(reply_frame(command.id, 14, expiry_result(3, 4, self.conn_ttl)))
            else:
                raise AssertionError(f"unexpected {command.kind} command after subscribe")


async def wait_until(predicate: Callable[[], bool], timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)
