from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, Generic, TypeVar

import httpx

from polyester.auth import ApiKeyCredentials
from polyester.errors import PolyesterAuthError, PolyesterRealtimeError
from polyester.realtime.auth import fetch_connection_token, fetch_subscription_token

T = TypeVar("T")

try:
    import websockets
    from websockets.asyncio.client import ClientConnection
except ImportError:  # pragma: no cover - optional extra
    websockets = None
    ClientConnection = Any

# Match Go: long read deadline so Centrifugo ping/pong completes without reconnect churn.
CENTRIFUGO_READ_TIMEOUT = 30.0
CENTRIFUGO_RECONNECT_DELAY = 1.0


def normalize_ws_url(ws_url: str) -> str:
    url = ws_url.rstrip("/")
    if url.endswith("/connection/websocket"):
        return url
    return f"{url}/connection/websocket"


def is_private_channel(channel: str) -> bool:
    return channel.startswith("private:")


class AsyncSubscription(Generic[T]):
    def __init__(
        self,
        *,
        queue: asyncio.Queue[T | None],
        close: asyncio.Event,
        task: asyncio.Task[None] | None = None,
    ) -> None:
        self._queue = queue
        self._close = close
        self._task = task

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
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self._task, timeout=3.0)
        await self._queue.put(None)


class AsyncRealtimeClient:
    """Centrifugo client for public and private protobuf channels."""

    def __init__(
        self,
        ws_url: str,
        *,
        api_url: str | None = None,
        credentials: ApiKeyCredentials | None = None,
        http: httpx.AsyncClient | None = None,
        max_queue_size: int = 1000,
    ) -> None:
        if websockets is None:
            raise PolyesterRealtimeError(
                "Realtime requires the websockets package. Install polyester-sdk[realtime]."
            )
        self._ws_url = normalize_ws_url(ws_url)
        self._api_url = api_url
        self._credentials = credentials
        self._http = http
        self._max_queue_size = max_queue_size

    async def subscribe_market_trades(self, symbol_id: int) -> AsyncSubscription[Any]:
        channel = f"public:spot:market:trades:{symbol_id}:proto"
        return await self.subscribe_proto(channel, decode=self._decode_market_trade)

    async def subscribe_proto(
        self,
        channel: str,
        *,
        decode: Callable[[bytes], T],
    ) -> AsyncSubscription[T]:
        if is_private_channel(channel):
            self._require_private_auth(channel)
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self._max_queue_size)
        close = asyncio.Event()

        async def runner() -> None:
            try:
                while not close.is_set():
                    try:
                        await self._run_subscription_once(
                            channel=channel,
                            decode=decode,
                            queue=queue,
                            close=close,
                        )
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        if close.is_set():
                            break
                    else:
                        if close.is_set():
                            break
                    if close.is_set():
                        break
                    await asyncio.sleep(CENTRIFUGO_RECONNECT_DELAY)
            finally:
                with contextlib.suppress(Exception):
                    await queue.put(None)

        task = asyncio.create_task(runner())
        return AsyncSubscription[T](queue=queue, close=close, task=task)

    async def _run_subscription_once(
        self,
        *,
        channel: str,
        decode: Callable[[bytes], T],
        queue: asyncio.Queue[Any],
        close: asyncio.Event,
    ) -> None:
        async with websockets.connect(
            self._ws_url,
            open_timeout=10,
            max_size=None,
        ) as ws:
            if is_private_channel(channel):
                http = self._require_http()
                credentials = self._require_credentials()
                api_url = self._require_api_url()
                connection_token = await fetch_connection_token(
                    http,
                    credentials,
                    api_url=api_url,
                )
                await self._centrifugo_connect(ws, token=connection_token)
                subscription_token = await fetch_subscription_token(
                    http,
                    credentials,
                    api_url=api_url,
                    channel=channel,
                )
                await self._centrifugo_subscribe(
                    ws,
                    channel,
                    token=subscription_token,
                )
            else:
                await self._centrifugo_connect(ws)
                await self._centrifugo_subscribe(ws, channel)
            while not close.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=CENTRIFUGO_READ_TIMEOUT)
                except TimeoutError:
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    raise PolyesterRealtimeError(str(exc)) from exc
                for frame in self._split_centrifugo_frames(raw):
                    if close.is_set():
                        return
                    publications = await self._handle_centrifugo_frame(
                        ws,
                        frame,
                        decode=decode,
                    )
                    for item in publications:
                        if close.is_set():
                            return
                        await queue.put(item)

    def _require_private_auth(self, channel: str) -> None:
        if self._credentials is None:
            raise PolyesterAuthError(
                f'Cannot subscribe to private channel "{channel}" without API-key credentials'
            )
        if not self._api_url:
            raise PolyesterRealtimeError("Realtime private channels require api_url")

    def _require_credentials(self) -> ApiKeyCredentials:
        if self._credentials is None:
            raise PolyesterAuthError("Realtime private channels require API-key credentials")
        return self._credentials

    def _require_api_url(self) -> str:
        if not self._api_url:
            raise PolyesterRealtimeError("Realtime private channels require api_url")
        return self._api_url

    def _require_http(self) -> httpx.AsyncClient:
        if self._http is None:
            raise PolyesterRealtimeError("Realtime private channels require an HTTP client")
        return self._http

    @staticmethod
    def _decode_market_trade(payload: bytes):
        from polyester.codecs.wire_decode import decode_market_trade_bytes

        return decode_market_trade_bytes(payload)

    async def _centrifugo_connect(
        self,
        ws: ClientConnection,
        *,
        token: str | None = None,
    ) -> None:
        connect_payload: dict[str, Any] = {}
        if token:
            connect_payload["token"] = token
        await ws.send(json.dumps({"id": 1, "connect": connect_payload}))
        reply = await asyncio.wait_for(ws.recv(), timeout=10)
        payload = json.loads(self._coerce_frame_text(reply))
        if payload.get("error"):
            raise PolyesterRealtimeError(str(payload["error"]))

    async def _centrifugo_subscribe(
        self,
        ws: ClientConnection,
        channel: str,
        *,
        token: str | None = None,
    ) -> None:
        subscribe_payload: dict[str, Any] = {"channel": channel}
        if token:
            subscribe_payload["token"] = token
        await ws.send(json.dumps({"id": 2, "subscribe": subscribe_payload}))
        reply = await asyncio.wait_for(ws.recv(), timeout=10)
        payload = json.loads(self._coerce_frame_text(reply))
        if payload.get("error"):
            raise PolyesterRealtimeError(str(payload["error"]))

    @staticmethod
    def _coerce_frame_text(raw: str | bytes) -> str:
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return raw

    @staticmethod
    def _split_centrifugo_frames(raw: str | bytes) -> list[str]:
        text = AsyncRealtimeClient._coerce_frame_text(raw).strip()
        if not text:
            return []
        return [frame for frame in text.split("\n") if frame.strip()]

    async def _handle_centrifugo_frame(
        self,
        ws: ClientConnection,
        frame: str,
        *,
        decode: Callable[[bytes], T],
    ) -> list[T]:
        try:
            message = json.loads(frame)
        except json.JSONDecodeError:
            return []
        if not message:
            await ws.send("{}")
            return []

        push = message.get("push")
        if isinstance(push, dict):
            if push.get("ping") is not None:
                await ws.send("{}")
                return []
            pub = push.get("pub") or {}
            data = pub.get("data")
            if data is not None:
                return [decode(self._decode_publication_data(data))]

        if message.get("ping") is not None and not message.get("id"):
            await ws.send("{}")
            return []

        return []

    @staticmethod
    def _decode_publication_data(data: Any) -> bytes:
        if isinstance(data, str):
            return base64.b64decode(data)
        if isinstance(data, list):
            return bytes(data)
        return bytes(data)
