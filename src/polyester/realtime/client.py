from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from typing import Any, Generic, TypeVar

from polyester.errors import PolyesterRealtimeError

T = TypeVar("T")

try:
    import websockets
    from websockets.asyncio.client import ClientConnection
except ImportError:  # pragma: no cover - optional extra
    websockets = None
    ClientConnection = Any


def normalize_ws_url(ws_url: str) -> str:
    url = ws_url.rstrip("/")
    if url.endswith("/connection/websocket"):
        return url
    return f"{url}/connection/websocket"


class AsyncSubscription(Generic[T]):
    def __init__(
        self,
        *,
        queue: asyncio.Queue[T | None],
        close: asyncio.Event,
    ) -> None:
        self._queue = queue
        self._close = close

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        if self._close.is_set():
            raise StopAsyncIteration
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        self._close.set()
        await self._queue.put(None)


class AsyncRealtimeClient:
    """Minimal Centrifugo client for public protobuf channels."""

    def __init__(self, ws_url: str, *, max_queue_size: int = 1000) -> None:
        if websockets is None:
            raise PolyesterRealtimeError(
                "Realtime requires the websockets package. Install polyester-sdk[realtime]."
            )
        self._ws_url = normalize_ws_url(ws_url)
        self._max_queue_size = max_queue_size

    async def subscribe_market_trades(self, symbol_id: int) -> AsyncSubscription:
        from polyester.codecs.wire_decode import decode_market_trade_bytes

        channel = f"public:spot:market:trades:{symbol_id}:proto"
        return await self._subscribe_proto(channel, decode=decode_market_trade_bytes)

    async def _subscribe_proto(self, channel: str, *, decode) -> AsyncSubscription[T]:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self._max_queue_size)
        close = asyncio.Event()
        subscription = AsyncSubscription[T](queue=queue, close=close)

        async def runner() -> None:
            try:
                async with websockets.connect(self._ws_url, open_timeout=10) as ws:
                    await self._centrifugo_connect(ws)
                    await self._centrifugo_subscribe(ws, channel)
                    async for raw in ws:
                        if close.is_set():
                            break
                        for trade in self._parse_publications(raw, decode=decode):
                            if close.is_set():
                                break
                            await queue.put(trade)
            except Exception as exc:
                if not close.is_set():
                    raise PolyesterRealtimeError(str(exc)) from exc
            finally:
                await queue.put(None)

        asyncio.create_task(runner())
        return subscription

    async def _centrifugo_connect(self, ws: ClientConnection) -> None:
        await ws.send(json.dumps({"id": 1, "connect": {}}))
        reply = await asyncio.wait_for(ws.recv(), timeout=10)
        payload = json.loads(reply)
        if payload.get("error"):
            raise PolyesterRealtimeError(str(payload["error"]))

    async def _centrifugo_subscribe(self, ws: ClientConnection, channel: str) -> None:
        await ws.send(json.dumps({"id": 2, "subscribe": {"channel": channel}}))
        reply = await asyncio.wait_for(ws.recv(), timeout=10)
        payload = json.loads(reply)
        if payload.get("error"):
            raise PolyesterRealtimeError(str(payload["error"]))

    def _parse_publications(self, raw: str | bytes, *, decode) -> list[Any]:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        message = json.loads(raw)
        publications: list[Any] = []
        push = message.get("push") or {}
        pub = push.get("pub") or {}
        data = pub.get("data")
        if data is None:
            return publications
        if isinstance(data, str):
            payload = base64.b64decode(data)
        elif isinstance(data, list):
            payload = bytes(data)
        else:
            payload = bytes(data)
        publications.append(decode(payload))
        return publications
