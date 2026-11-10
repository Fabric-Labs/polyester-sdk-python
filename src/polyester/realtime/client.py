from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Sequence
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import httpx
import websockets
from websockets.asyncio.client import ClientConnection

from polyester.auth import ApiKeyCredentials
from polyester.errors import (
    PolyesterAuthError,
    PolyesterRealtimeError,
    PolyesterRealtimeOverflowError,
    PolyesterRedirectError,
    PolyesterSubscriptionEndedError,
)
from polyester.realtime._ws_log import WS_CLIENT_LOGGER
from polyester.realtime._ws_uri import checked_ws_uri, connect_without_redirects
from polyester.realtime.auth import fetch_connection_token, fetch_subscription_token
from polyester.realtime.protocol import (
    Ping,
    Publication,
    Reply,
    Unsubscribe,
    connect_command,
    decode_replies,
    pong_command,
    subscribe_command,
)
from polyester.realtime.renewal import RenewalKind, TokenRenewer
from polyester.realtime.resubscribe import (
    SUBACCOUNTS_CHANNEL_PREFIX,
    ResubscribeAttempt,
    ServerUnsubscribedError,
    SubaccountAccess,
)

if TYPE_CHECKING:
    from polyester.models.private_orders import PrivateOrdersEvent
    from polyester.realtime.private_orders import PrivateOrderStream

T = TypeVar("T")

# Match Go: long read deadline so Centrifugo ping/pong completes without reconnect churn.
CENTRIFUGO_READ_TIMEOUT = 30.0
# Pings keep a connection alive without answering, so each handshake reply has a deadline.
CENTRIFUGO_REPLY_DEADLINE = 30.0
CENTRIFUGO_RECONNECT_INITIAL_CAP = 0.5
CENTRIFUGO_RECONNECT_MAX_CAP = 30.0
CENTRIFUGO_PROTOBUF_SUBPROTOCOL = "centrifuge-protobuf"
# Bound inbound websocket frames (DoS / memory); Centrifugo pubs stay well below this.
WS_MAX_MESSAGE_BYTES = 4 * 1024 * 1024


class _TerminalRealtimeError(PolyesterRealtimeError):
    """Protocol/data failure that reconnecting cannot repair."""


class _ReconnectBackoff:
    """Exponential reconnect backoff with full-width cryptographic jitter."""

    def __init__(self) -> None:
        self._cap = CENTRIFUGO_RECONNECT_INITIAL_CAP

    def reset(self) -> None:
        self._cap = CENTRIFUGO_RECONNECT_INITIAL_CAP

    def next_delay(self) -> float:
        half = self._cap / 2
        delay = half + (secrets.randbelow(1_000_001) / 1_000_000) * half
        self._cap = min(self._cap * 2, CENTRIFUGO_RECONNECT_MAX_CAP)
        return delay


def _is_oversized_websocket_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "1009" in message or "message too big" in message or "exceeds limit" in message


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
        self._on_error: Callable[[BaseException], None] | None = None
        # Successful reconnects after the initial handshake. Each increment means
        # the consumer must treat prior stream continuity as lost (possible gap).
        self._resubscribed = 0
        self._resubscribed_pending = False
        self._on_closed: Callable[[AsyncSubscription[Any]], None] | None = None

    @property
    def error(self) -> BaseException | None:
        """Terminal subscription error, if the stream failed."""
        return self._error

    @property
    def is_alive(self) -> bool:
        """True while the subscription task is still running and not closed."""
        if self._close.is_set():
            return False
        if self._task is None:
            return True
        return not self._task.done()

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
        self._notify_error(exc)

    def _notify_error(self, exc: BaseException) -> None:
        if self._on_error is not None:
            with contextlib.suppress(BaseException):
                self._on_error(exc)

    def set_on_error(self, callback: Callable[[BaseException], None] | None) -> None:
        """Set a callback for background transport and terminal stream errors.

        Callback exceptions are isolated from the subscription worker. If a
        terminal error already occurred, the callback is invoked immediately.
        """
        self._on_error = callback
        if callback is not None and self._error is not None:
            with contextlib.suppress(BaseException):
                callback(self._error)

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
                # Cancel must unwind promptly (in-flight token HTTP + WS).
                await asyncio.wait_for(self._task, timeout=1.0)
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)
        if self._on_closed is not None:
            with contextlib.suppress(Exception):
                self._on_closed(self)

    async def __aenter__(self) -> AsyncSubscription[T]:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


class AsyncRealtimeClient:
    """Realtime client: Centrifugo protobuf channels and the private order WebSocket."""

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
        # Decides whether a subscription the server ended may resume.
        self._access = SubaccountAccess(self)
        self._max_queue_size = max_queue_size
        self._active_subs: set[AsyncSubscription[Any]] = set()
        self._private_orders: PrivateOrderStream | None = None
        self._closed = False
        # Seconds per Centrifugo token TTL unit; tests shorten it.
        self._renewal_unit = 1.0

    async def aclose(self) -> None:
        self._access.close()
        """Cancel all active subscriptions and await their tasks."""
        self._closed = True
        subs = list(self._active_subs)
        self._active_subs.clear()
        for sub in subs:
            await sub.aclose()
        if self._private_orders is not None:
            await self._private_orders.aclose()
            self._private_orders = None

    async def subscribe_private_orders(
        self, account_id: str | int
    ) -> AsyncSubscription[PrivateOrdersEvent]:
        """Stream an account's orders over the private WebSocket (``/v1/ws/private``).

        Every subscription shares one connection, and each account one server
        subscription. Returns once the server confirmed the subscription.
        """
        from polyester.realtime.private_orders import (
            PrivateOrderStream,
            private_orders_channel,
            private_ws_url,
        )

        if self._closed:
            raise PolyesterRealtimeError("realtime client is closed")
        self._require_private_auth(private_orders_channel(account_id))
        if self._private_orders is None:
            http = self._require_http()
            credentials = self._require_credentials()
            api_url = self._require_api_url()

            async def fetch_connect_token() -> str:
                return await fetch_connection_token(http, credentials, api_url=api_url)

            async def fetch_subscribe_token(channel: str) -> str:
                return await fetch_subscription_token(
                    http, credentials, api_url=api_url, channel=channel
                )

            self._private_orders = PrivateOrderStream(
                url=private_ws_url(api_url),
                fetch_connect_token=fetch_connect_token,
                fetch_subscribe_token=fetch_subscribe_token,
                max_queue_size=self._max_queue_size,
            )
        return await self._private_orders.subscribe(account_id)

    def _track_sub(self, sub: AsyncSubscription[Any]) -> None:
        self._active_subs.add(sub)

        def _untrack(closed: AsyncSubscription[Any]) -> None:
            self._active_subs.discard(closed)

        sub._on_closed = _untrack

    async def subscribe_market_trades(
        self, symbol_id: int, *, quantity_scale: int
    ) -> AsyncSubscription[Any]:
        """Stream public trades; each batched publication is emitted trade by trade."""
        from polyester.codecs.realtime_decode import decode_market_trade_batch_bytes

        channel = f"public:spot:market:trades:{symbol_id}:proto"
        return await self.subscribe_proto_batch(
            channel,
            decode_batch=lambda payload: decode_market_trade_batch_bytes(
                payload, quantity_scale=quantity_scale
            ),
        )

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
        return await self._subscribe(
            channel,
            decode_batch=lambda payload: [decode(payload)],
            auto_reconnect=auto_reconnect,
        )

    async def subscribe_proto_batch(
        self,
        channel: str,
        *,
        decode_batch: Callable[[bytes], Sequence[T | BaseException]],
        auto_reconnect: bool = True,
    ) -> AsyncSubscription[T]:
        """Subscribe to a channel whose publications batch several events.

        ``decode_batch`` returns the events of one publication in order; each is
        yielded on its own. A member returned as an exception is reported through
        the subscription's ``set_on_error`` callback without dropping the rest of
        its batch. Handshake semantics match :meth:`subscribe_proto`.
        """
        return await self._subscribe(
            channel, decode_batch=decode_batch, auto_reconnect=auto_reconnect
        )

    async def _subscribe(
        self,
        channel: str,
        *,
        decode_batch: Callable[[bytes], Sequence[T | BaseException]],
        auto_reconnect: bool,
    ) -> AsyncSubscription[T]:
        if self._closed:
            raise PolyesterRealtimeError("realtime client is closed")
        if is_private_channel(channel):
            self._require_private_auth(channel)
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=self._max_queue_size)
        close = asyncio.Event()

        sub = AsyncSubscription[T](queue=queue, close=close, task=None)
        ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        handshake_count = 0
        backoff = _ReconnectBackoff()
        resume: ResubscribeAttempt | None = None

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
            backoff.reset()
            if handshake_count > 1:
                sub._mark_resubscribed()
            if resume is not None:
                resume.note_ready()
            signal_ready(None)

        async def runner() -> None:
            nonlocal resume
            try:
                while not close.is_set():
                    try:
                        await self._run_subscription_once(
                            channel=channel,
                            decode_batch=decode_batch,
                            queue=queue,
                            close=close,
                            on_ready=on_ready,
                            on_member_error=sub._notify_error,
                            on_renewal_error=sub._notify_error,
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
                    except _TerminalRealtimeError as exc:
                        sub._set_error(exc)
                        signal_ready(exc)
                        break
                    except ServerUnsubscribedError as exc:
                        if close.is_set():
                            break
                        if exc.temporary:
                            # The server asks for a new subscribe: an ordinary reconnect.
                            if not auto_reconnect:
                                sub._set_error(exc)
                                break
                            sub._notify_error(exc)
                        elif not auto_reconnect:
                            sub._set_error(exc.ended(channel, "not_resubscribable"))
                            break
                        else:
                            resume = self._access.attempt_after(resume, exc)
                            try:
                                await self._access.await_resume(channel, resume)
                            except PolyesterSubscriptionEndedError as ended:
                                sub._set_error(ended)
                                break
                            continue
                    except (PolyesterAuthError, PolyesterRedirectError) as exc:
                        # Auth failures, and a redirect of a signed token
                        # request, must be observable; never hide behind reconnect.
                        if resume is not None and not resume.ready:
                            sub._set_error(resume.unsubscribed.ended(channel, "token_refused", exc))
                        else:
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
                        if resume is not None and not resume.ready:
                            # An attempt to resume failed: retry within its limit.
                            resume.last_error = exc
                            sub._notify_error(exc)
                            try:
                                await self._access.await_resume(channel, resume)
                            except PolyesterSubscriptionEndedError as ended:
                                sub._set_error(ended)
                                break
                            continue
                        # Transient transport failures reconnect after a successful handshake.
                        if not auto_reconnect:
                            sub._set_error(exc)
                            break
                        sub._notify_error(exc)
                    else:
                        if close.is_set():
                            break
                        if not auto_reconnect:
                            break
                    if close.is_set():
                        break
                    if not auto_reconnect:
                        break
                    await asyncio.sleep(backoff.next_delay())
            finally:
                if not ready.done():
                    signal_ready(
                        PolyesterRealtimeError("realtime subscription ended before handshake")
                    )
                with contextlib.suppress(Exception):
                    queue.put_nowait(None)

        task = asyncio.create_task(runner())
        sub._task = task
        self._track_sub(sub)
        try:
            await ready
        except asyncio.CancelledError:
            # Cancellation is sticky: shield teardown so in-flight token HTTP / WS
            # peers are aborted promptly (E6 cancel-during-token-stall).
            close.set()
            if not task.done():
                task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.shield(asyncio.wait_for(task, timeout=1.0))
            self._active_subs.discard(sub)
            raise
        except BaseException:
            await sub.aclose()
            raise
        return sub

    async def _run_subscription_once(
        self,
        *,
        channel: str,
        decode_batch: Callable[[bytes], Sequence[T | BaseException]],
        queue: asyncio.Queue[Any],
        close: asyncio.Event,
        on_ready: Callable[[], None] | None = None,
        on_member_error: Callable[[BaseException], None] | None = None,
        on_renewal_error: Callable[[BaseException], None] | None = None,
    ) -> None:
        # A private channel sends its tokens once the handshake succeeds: never
        # follow a handshake redirect for one.
        connector = connect_without_redirects if is_private_channel(channel) else websockets.connect
        async with connector(
            checked_ws_uri(self._ws_url),
            open_timeout=10,
            max_size=WS_MAX_MESSAGE_BYTES,
            subprotocols=[CENTRIFUGO_PROTOBUF_SUBPROTOCOL],
            logger=WS_CLIENT_LOGGER,
        ) as ws:
            if ws.subprotocol != CENTRIFUGO_PROTOBUF_SUBPROTOCOL:
                raise PolyesterRealtimeError(
                    "server did not negotiate centrifuge-protobuf websocket subprotocol"
                )
            pending: deque[Ping | Publication | Reply | Unsubscribe] = deque()
            renewer: TokenRenewer | None = None
            if is_private_channel(channel):
                http = self._require_http()
                credentials = self._require_credentials()
                api_url = self._require_api_url()
                connection_token = await fetch_connection_token(
                    http,
                    credentials,
                    api_url=api_url,
                )
                connected = await self._centrifugo_connect(
                    ws, token=connection_token, pending=pending
                )
                # The connection token's TTL runs from here, through the rest of setup.
                connected_at = time.monotonic()
                subscription_token = await fetch_subscription_token(
                    http,
                    credentials,
                    api_url=api_url,
                    channel=channel,
                )
                subscribed = await self._centrifugo_subscribe(
                    ws,
                    channel,
                    token=subscription_token,
                    pending=pending,
                )
                subscribed_at = time.monotonic()

                async def fetch_renewal_token(kind: RenewalKind) -> str:
                    if kind == "connection":
                        return await fetch_connection_token(http, credentials, api_url=api_url)
                    return await fetch_subscription_token(
                        http, credentials, api_url=api_url, channel=channel
                    )

                renewer = TokenRenewer(
                    ws,
                    channel,
                    unit=self._renewal_unit,
                    first_id=3,
                    fetch=fetch_renewal_token,
                    report=on_renewal_error or (lambda _exc: None),
                )
                renewer.schedule("connection", connected_at, connected.expires, connected.ttl)
                renewer.schedule("subscription", subscribed_at, subscribed.expires, subscribed.ttl)
            else:
                await self._centrifugo_connect(ws, pending=pending)
                await self._centrifugo_subscribe(ws, channel, pending=pending)
            try:
                await self._read_subscription(
                    ws,
                    channel=channel,
                    decode_batch=decode_batch,
                    queue=queue,
                    close=close,
                    pending=pending,
                    renewer=renewer,
                    on_ready=on_ready,
                    on_member_error=on_member_error,
                )
            finally:
                if renewer is not None:
                    await renewer.stop()

    async def _read_subscription(
        self,
        ws: ClientConnection,
        *,
        channel: str,
        decode_batch: Callable[[bytes], Sequence[T | BaseException]],
        queue: asyncio.Queue[Any],
        close: asyncio.Event,
        pending: deque[Ping | Publication | Reply | Unsubscribe],
        renewer: TokenRenewer | None,
        on_ready: Callable[[], None] | None,
        on_member_error: Callable[[BaseException], None] | None,
    ) -> None:
        if on_ready is not None:
            on_ready()
        subaccounts_channel = channel.startswith(SUBACCOUNTS_CHANNEL_PREFIX)
        send = renewer.send if renewer is not None else ws.send
        while not close.is_set():
            if pending:
                incoming_messages = list(pending)
                pending.clear()
            else:
                incoming_messages = await self._read_live_frame(ws)
            for incoming in incoming_messages:
                if isinstance(incoming, Ping):
                    await send(pong_command())
                elif isinstance(incoming, Publication):
                    if subaccounts_channel:
                        self._access.note_update(incoming.data)
                    members = decode_batch(incoming.data)
                    if close.is_set():
                        return
                    for member in members:
                        if isinstance(member, BaseException):
                            if on_member_error is not None:
                                on_member_error(member)
                            continue
                        enqueue_or_overflow(queue, member, close=close)
                elif isinstance(incoming, Unsubscribe):
                    if incoming.channel in ("", channel):
                        raise ServerUnsubscribedError(incoming.code, incoming.reason)
                elif isinstance(incoming, Reply):
                    if renewer is not None and renewer.handle_reply(incoming):
                        continue
                    if incoming.error is not None:
                        raise self._protocol_error(incoming)

    async def _read_live_frame(
        self, ws: ClientConnection
    ) -> list[Ping | Publication | Reply | Unsubscribe]:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=CENTRIFUGO_READ_TIMEOUT)
        except TimeoutError as exc:
            raise PolyesterRealtimeError("realtime read timeout") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if _is_oversized_websocket_error(exc):
                raise _TerminalRealtimeError(
                    f"realtime message exceeds {WS_MAX_MESSAGE_BYTES} bytes"
                ) from exc
            raise PolyesterRealtimeError(str(exc)) from exc
        if not isinstance(raw, bytes):
            raise _TerminalRealtimeError("received JSON text frame on protobuf websocket")
        try:
            return decode_replies(raw)
        except Exception as exc:
            raise _TerminalRealtimeError(f"invalid realtime protobuf frame: {exc}") from exc

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

    async def _centrifugo_connect(
        self,
        ws: ClientConnection,
        *,
        token: str | None = None,
        pending: deque[Ping | Publication | Reply | Unsubscribe] | None = None,
    ) -> Reply:
        await ws.send(connect_command(1, token))
        return await self._read_centrifugo_reply(ws, expected_id=1, pending=pending)

    async def _centrifugo_subscribe(
        self,
        ws: ClientConnection,
        channel: str,
        *,
        token: str | None = None,
        pending: deque[Ping | Publication | Reply | Unsubscribe] | None = None,
    ) -> Reply:
        await ws.send(subscribe_command(2, channel, token))
        return await self._read_centrifugo_reply(ws, expected_id=2, pending=pending)

    async def _read_centrifugo_reply(
        self,
        ws: ClientConnection,
        *,
        expected_id: int,
        pending: deque[Ping | Publication | Reply | Unsubscribe] | None = None,
    ) -> Reply:
        """Return the reply to ``expected_id``, holding back anything that arrives first."""
        deadline = time.monotonic() + CENTRIFUGO_REPLY_DEADLINE
        while True:
            remaining = deadline - time.monotonic()
            raw = await asyncio.wait_for(ws.recv(), timeout=min(10, remaining))
            if not isinstance(raw, bytes):
                raise PolyesterRealtimeError("received JSON text reply on protobuf websocket")
            matched: Reply | None = None
            for incoming in decode_replies(raw):
                if isinstance(incoming, Ping):
                    await ws.send(pong_command())
                elif isinstance(incoming, Reply) and incoming.id == expected_id:
                    if incoming.error is not None:
                        raise self._protocol_error(incoming)
                    matched = incoming
                elif pending is not None:
                    if len(pending) >= 200:
                        raise PolyesterRealtimeOverflowError("realtime setup buffer full")
                    pending.append(incoming)
            if matched is not None:
                return matched

    @staticmethod
    def _protocol_error(reply: Reply) -> PolyesterRealtimeError:
        assert reply.error is not None
        temporary = " (temporary)" if reply.error.temporary else ""
        return PolyesterRealtimeError(
            f"centrifugo error {reply.error.code}: {reply.error.message}{temporary}"
        )
