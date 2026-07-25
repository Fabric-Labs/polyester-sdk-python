from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any, Generic, TypeVar

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from polyester.auth import ApiKeyCredentials
from polyester.errors import (
    PolyesterAuthError,
    PolyesterRealtimeError,
    PolyesterRealtimeOverflowError,
)
from polyester.realtime.auth import fetch_connection_token, fetch_subscription_token
from polyester.realtime.protocol import (
    Ping,
    Publication,
    Reply,
    connect_command,
    decode_replies,
    pong_command,
    subscribe_command,
)

T = TypeVar("T")

# Match Go: long read deadline so Centrifugo ping/pong completes without reconnect churn.
CENTRIFUGO_READ_TIMEOUT = 30.0
CENTRIFUGO_RECONNECT_DELAY = 1.0
CENTRIFUGO_PROTOBUF_SUBPROTOCOL = "centrifuge-protobuf"


def normalize_ws_url(ws_url: str) -> str:
    url = ws_url.rstrip("/")
    if url.endswith("/connection/websocket"):
        return url
    return f"{url}/connection/websocket"


def is_private_channel(channel: str) -> bool:
    return channel.startswith("private:")


def enqueue_or_overflow(
    queue: asyncio.Queue[Any],
    item: Any,
    *,
    close: asyncio.Event,
    message: str = "realtime subscription queue full; consumer too slow",
) -> None:
    """Put an item or fail the subscription on overflow (never silent drop)."""
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull as exc:
        close.set()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(None)
        raise PolyesterRealtimeOverflowError(message) from exc


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
        self._error: BaseException | None = None
        # Successful reconnects after the initial handshake. Each increment means
        # the consumer must treat prior stream continuity as lost (possible gap).
        self._resubscribed = 0
        self._resubscribed_pending = False

    @property
    def error(self) -> BaseException | None:
        """Terminal subscription error, if the stream failed."""
        return self._error

    @property
    def resubscribed(self) -> int:
        """Count of successful reconnects after the first connect.

        Consumers must treat a non-zero / increasing value as possible data loss
        (missed publications while disconnected).
        """
        return self._resubscribed

    def take_resubscribed(self) -> bool:
        """Return True once per reconnect gap since the previous take."""
        if not self._resubscribed_pending:
            return False
        self._resubscribed_pending = False
        return True

    def _mark_resubscribed(self) -> None:
        self._resubscribed += 1
        self._resubscribed_pending = True

    def _set_error(self, exc: BaseException) -> None:
        if self._error is None:
            self._error = exc

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        if self._error is not None and self._queue.empty():
            raise self._error
        if self._close.is_set() and self._queue.empty():
            if self._error is not None:
                raise self._error
            raise StopAsyncIteration
        item = await self._queue.get()
        if item is None:
            if self._error is not None:
                raise self._error
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        self._close.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self._task, timeout=3.0)
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)

    async def __aenter__(self) -> AsyncSubscription[T]:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


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
        auto_reconnect: bool = True,
    ) -> AsyncSubscription[T]:
        """Subscribe to a Centrifugo protobuf channel.

        Waits for the connect/subscribe handshake (including private token fetch)
        to succeed before returning. Initial auth/handshake failures raise and do
        not reconnect in the background.
        """
        if is_private_channel(channel):
            self._require_private_auth(channel)
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self._max_queue_size)
        close = asyncio.Event()

        sub = AsyncSubscription[T](queue=queue, close=close, task=None)
        ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        handshake_count = 0

        def signal_ready(exc: BaseException | None = None) -> None:
            if ready.done():
                return
            if exc is None:
                ready.set_result(None)
            else:
                ready.set_exception(exc)

        def on_ready() -> None:
            nonlocal handshake_count
            handshake_count += 1
            if handshake_count > 1:
                sub._mark_resubscribed()
            signal_ready(None)

        async def runner() -> None:
            try:
                while not close.is_set():
                    try:
                        await self._run_subscription_once(
                            channel=channel,
                            decode=decode,
                            queue=queue,
                            close=close,
                            on_ready=on_ready,
                        )
                    except asyncio.CancelledError:
                        if not ready.done():
                            signal_ready(
                                PolyesterRealtimeError(
                                    "realtime subscription cancelled before handshake"
                                )
                            )
                        break
                    except PolyesterRealtimeOverflowError as exc:
                        sub._set_error(exc)
                        signal_ready(exc)
                        break
                    except PolyesterAuthError as exc:
                        # Auth failures must be observable; never hide behind reconnect.
                        sub._set_error(exc)
                        signal_ready(exc)
                        break
                    except Exception as exc:
                        if close.is_set():
                            break
                        if not ready.done():
                            # Match Rust/Go: first handshake failure is terminal.
                            signal_ready(exc)
                            break
                        # Transient transport failures reconnect after a successful handshake.
                        if not auto_reconnect:
                            sub._set_error(exc)
                            break
                    else:
                        if close.is_set():
                            break
                        if not auto_reconnect:
                            break
                    if close.is_set():
                        break
                    if not auto_reconnect:
                        break
                    await asyncio.sleep(CENTRIFUGO_RECONNECT_DELAY)
            finally:
                if not ready.done():
                    signal_ready(
                        PolyesterRealtimeError("realtime subscription ended before handshake")
                    )
                with contextlib.suppress(Exception):
                    queue.put_nowait(None)

        task = asyncio.create_task(runner())
        sub._task = task
        try:
            await ready
        except BaseException:
            await sub.aclose()
            raise
        return sub

    async def _run_subscription_once(
        self,
        *,
        channel: str,
        decode: Callable[[bytes], T],
        queue: asyncio.Queue[Any],
        close: asyncio.Event,
        on_ready: Callable[[], None] | None = None,
    ) -> None:
        async with websockets.connect(
            self._ws_url,
            open_timeout=10,
            max_size=None,
            subprotocols=[CENTRIFUGO_PROTOBUF_SUBPROTOCOL],
        ) as ws:
            if ws.subprotocol != CENTRIFUGO_PROTOBUF_SUBPROTOCOL:
                raise PolyesterRealtimeError(
                    "server did not negotiate centrifuge-protobuf websocket subprotocol"
                )
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
            if on_ready is not None:
                on_ready()
            while not close.is_set():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=CENTRIFUGO_READ_TIMEOUT)
                except TimeoutError as exc:
                    # Timeout = connection death (half-open). Exit so reconnect
                    # can run when enabled; do not spin forever on continue.
                    raise PolyesterRealtimeError("realtime read timeout") from exc
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    raise PolyesterRealtimeError(str(exc)) from exc
                if not isinstance(raw, bytes):
                    raise PolyesterRealtimeError("received JSON text frame on protobuf websocket")
                for incoming in decode_replies(raw):
                    if isinstance(incoming, Ping):
                        await ws.send(pong_command())
                    elif isinstance(incoming, Publication):
                        item = decode(incoming.data)
                        if close.is_set():
                            return
                        enqueue_or_overflow(queue, item, close=close)
                    elif isinstance(incoming, Reply) and incoming.error is not None:
                        raise self._protocol_error(incoming)

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
        await ws.send(connect_command(1, token))
        await self._read_centrifugo_reply(ws, expected_id=1)

    async def _centrifugo_subscribe(
        self,
        ws: ClientConnection,
        channel: str,
        *,
        token: str | None = None,
    ) -> None:
        await ws.send(subscribe_command(2, channel, token))
        await self._read_centrifugo_reply(ws, expected_id=2)

    async def _read_centrifugo_reply(
        self,
        ws: ClientConnection,
        *,
        expected_id: int,
    ) -> None:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            if not isinstance(raw, bytes):
                raise PolyesterRealtimeError("received JSON text reply on protobuf websocket")
            for incoming in decode_replies(raw):
                if isinstance(incoming, Ping):
                    await ws.send(pong_command())
                elif isinstance(incoming, Reply) and incoming.id == expected_id:
                    if incoming.error is not None:
                        raise self._protocol_error(incoming)
                    return

    @staticmethod
    def _protocol_error(reply: Reply) -> PolyesterRealtimeError:
        assert reply.error is not None
        temporary = " (temporary)" if reply.error.temporary else ""
        return PolyesterRealtimeError(
            f"centrifugo error {reply.error.code}: {reply.error.message}{temporary}"
        )
