"""Private order stream over a local fake ``/v1/ws/private`` server."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from polyester import PolyesterAuthError, PolyesterRealtimeError
from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models import (
    Order,
    PrivateOrderCommandOutcome,
    PrivateOrderEvent,
    PrivateOrdersConnected,
    PrivateOrdersDisconnected,
    PrivateOrdersError,
    PrivateOrdersReady,
    PrivateOrdersSnapshot,
    PrivateOrdersStale,
    PrivateOrdersUnit,
)
from polyester.realtime import private_orders
from polyester.realtime.client import AsyncSubscription
from polyester.realtime.private_orders import (
    PRIVATE_WS_SUBPROTOCOL,
    PrivateOrderStream,
    private_ws_url,
)
from polyester.services.orders import AsyncOrdersService
from tests.hardening_support import make_test_credentials

ACCOUNT = 42
ACCOUNT_B58 = format_id(ACCOUNT)
CHANNEL = f"private:spot:orders:{ACCOUNT_B58}"
EVENT_TIMEOUT = 3.0


def order(order_id: int, version: int = 1) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(
        order_id=order_id,
        symbol_id=1,
        side=orders_pb2.BUY,
        version=version,
        price_ticks=2_420_000_000_000,
        orig_qty_scaled=231_500,
    )


class FakeConnection:
    def __init__(self, ws: ServerConnection) -> None:
        self.ws = ws
        self.received: asyncio.Queue[pb.ClientMessage] = asyncio.Queue()
        self.log: list[pb.ClientMessage] = []
        self.close_code: int | None = None

    async def expect(self, kind: str) -> Any:
        """Next client message of ``kind``; other kinds stay in ``log``."""
        while True:
            msg = await asyncio.wait_for(self.received.get(), EVENT_TIMEOUT)
            if msg.WhichOneof("op") == kind:
                return getattr(msg, kind)

    def ops(self, kind: str) -> list[Any]:
        return [getattr(m, kind) for m in self.log if m.WhichOneof("op") == kind]

    async def send(self, sub: str = "", seq: int = 0, **frame: Any) -> None:
        await self.ws.send(pb.ServerMessage(sub=sub, seq=seq, **frame).SerializeToString())

    async def send_raw(self, data: bytes) -> None:
        await self.ws.send(data)

    async def close(self, code: int, reason: str = "") -> None:
        await self.ws.close(code, reason)

    async def confirm(self, sub: str = "s1") -> pb.Subscribe:
        request = await self.expect("subscribe")
        await self.send(sub, subscribed=pb.Subscribed(id=request.id, account=ACCOUNT))
        return request

    async def snapshot(self, sub: str, cursor: str, orders: list[orders_read_pb2.Order]) -> None:
        await self.send(sub, 1, snapshot_begin=pb.SnapshotBegin(epoch=1))
        await self.send(sub, 2, snapshot_page=pb.SnapshotPage(orders=orders))
        await self.send(sub, 3, snapshot_end=pb.SnapshotEnd(cursor=cursor, count=len(orders)))


class FakePrivateWsServer:
    """Serves ``/v1/ws/private`` plus the realtime token endpoints on one port."""

    def __init__(self) -> None:
        self.connections: asyncio.Queue[FakeConnection] = asyncio.Queue()
        self.all: list[FakeConnection] = []
        self.http_paths: list[str] = []
        self.ws_paths: list[str] = []
        self.subprotocols: list[str | None] = []
        self._server: Server | None = None
        self.port = 0

    async def start(self) -> None:
        self._server = await serve(
            self._handler,
            "127.0.0.1",
            0,
            subprotocols=[PRIVATE_WS_SUBPROTOCOL],  # type: ignore[list-item]
            process_request=self._process_request,
            ping_interval=None,
        )
        self.port = self._server.sockets[0].getsockname()[1]

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def aclose(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def _process_request(self, connection: ServerConnection, request: Request) -> Response | None:
        if request.path.startswith("/v1/rt/"):
            self.http_paths.append(request.path)
            assert request.headers.get("X-API-Key-ID") or request.headers.get("x-api-key-id")
            token = "connect-token" if request.path == "/v1/rt/token" else "sub-token"
            response = connection.respond(200, json.dumps({"token": token}))
            response.headers = Headers({"Content-Type": "application/json"})
            response.headers["Content-Length"] = str(len(response.body))
            return response
        self.ws_paths.append(request.path)
        return None

    async def _handler(self, ws: ServerConnection) -> None:
        conn = FakeConnection(ws)
        self.subprotocols.append(ws.subprotocol)
        self.all.append(conn)
        await self.connections.put(conn)
        try:
            async for raw in ws:
                assert isinstance(raw, bytes)
                msg = pb.ClientMessage()
                msg.ParseFromString(raw)
                conn.log.append(msg)
                await conn.received.put(msg)
        except Exception:
            pass
        finally:
            conn.close_code = ws.close_code

    async def next_connection(self) -> FakeConnection:
        return await asyncio.wait_for(self.connections.get(), EVENT_TIMEOUT)


class Tokens:
    def __init__(self) -> None:
        self.connect_calls = 0
        self.subscribe_channels: list[str] = []
        self.connect_error: Exception | None = None

    async def connect(self) -> str:
        self.connect_calls += 1
        if self.connect_error is not None:
            raise self.connect_error
        return f"connect-{self.connect_calls}"

    async def subscribe(self, channel: str) -> str:
        self.subscribe_channels.append(channel)
        return f"sub-{len(self.subscribe_channels)}"


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(private_orders, "RECONNECT_BASE_DELAY", 0.01)
    monkeypatch.setattr(private_orders, "RECONNECT_MAX_DELAY", 0.05)


@pytest_asyncio.fixture(loop_scope="function")
async def server() -> AsyncIterator[FakePrivateWsServer]:
    fake = FakePrivateWsServer()
    await fake.start()
    yield fake
    await fake.aclose()


@pytest.fixture
def tokens() -> Tokens:
    return Tokens()


@pytest_asyncio.fixture(loop_scope="function")
async def stream(server: FakePrivateWsServer, tokens: Tokens) -> AsyncIterator[PrivateOrderStream]:
    s = PrivateOrderStream(
        url=private_ws_url(server.api_url),
        fetch_connect_token=tokens.connect,
        fetch_subscribe_token=tokens.subscribe,
    )
    yield s
    await s.aclose()


async def next_event(sub: AsyncSubscription[Any]) -> Any:
    return await asyncio.wait_for(sub.__anext__(), EVENT_TIMEOUT)


async def open_stream(
    server: FakePrivateWsServer, stream: PrivateOrderStream, sub: str = "s1"
) -> tuple[AsyncSubscription[Any], FakeConnection]:
    task = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
    conn = await server.next_connection()
    await conn.expect("auth")
    await conn.confirm(sub)
    subscription = await asyncio.wait_for(task, EVENT_TIMEOUT)
    assert isinstance(await next_event(subscription), PrivateOrdersConnected)
    return subscription, conn


async def settle() -> None:
    await asyncio.sleep(0.05)


def test_private_ws_url_uses_the_api_host() -> None:
    assert private_ws_url("https://api.example.test") == "wss://api.example.test/v1/ws/private"
    assert private_ws_url("http://127.0.0.1:8080/") == "ws://127.0.0.1:8080/v1/ws/private"


async def test_auth_is_the_first_frame_and_subscribe_uses_the_base_channel_token(
    server: FakePrivateWsServer, stream: PrivateOrderStream, tokens: Tokens
) -> None:
    task = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
    conn = await server.next_connection()
    first = await asyncio.wait_for(conn.received.get(), EVENT_TIMEOUT)
    assert first.WhichOneof("op") == "auth"
    assert first.auth.token == "connect-1"
    request = await conn.confirm()
    assert request.channel == pb.ORDERS
    assert request.account == ACCOUNT
    assert request.token == "sub-1"
    assert request.cursor == ""
    assert tokens.subscribe_channels == [CHANNEL]
    assert not CHANNEL.endswith(":proto")
    assert server.subprotocols == [PRIVATE_WS_SUBPROTOCOL]
    assert server.ws_paths == ["/v1/ws/private"]
    sub = await asyncio.wait_for(task, EVENT_TIMEOUT)
    assert isinstance(await next_event(sub), PrivateOrdersConnected)


async def test_snapshot_is_staged_and_installed_only_at_snapshot_end(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.send("s1", 1, snapshot_begin=pb.SnapshotBegin(epoch=1))
    await conn.send("s1", 2, snapshot_page=pb.SnapshotPage(orders=[order(1)]))
    await conn.send("s1", 3, snapshot_page=pb.SnapshotPage(orders=[order(2)]))
    await settle()
    assert sub._queue.empty()
    await conn.send("s1", 4, snapshot_end=pb.SnapshotEnd(cursor="c1", count=2))

    event = await next_event(sub)
    assert isinstance(event, PrivateOrdersSnapshot)
    assert [o.order_id for o in event.orders] == [format_id(1), format_id(2)]
    # The same Order model the order reads return.
    assert all(isinstance(o, Order) for o in event.orders)
    assert event.orders[0] == order_from_proto(order(1))
    assert event.orders[0].price is not None
    assert event.orders[0].price.format() == "2420"


async def test_snapshot_whose_pages_disagree_with_its_count_is_retaken_fresh(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.send("s1", 1, snapshot_begin=pb.SnapshotBegin())
    await conn.send("s1", 2, snapshot_page=pb.SnapshotPage(orders=[order(1)]))
    await conn.send("s1", 3, snapshot_end=pb.SnapshotEnd(cursor="c1", count=2))

    assert (await conn.expect("unsubscribe")).sub == "s1"
    retry = await conn.expect("subscribe")
    assert retry.cursor == ""
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)


async def test_units_deliver_orders_removed_ids_and_events(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [order(1), order(2)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    await conn.send(
        "s1",
        4,
        unit=pb.Unit(
            prev_cursor="c1",
            next_cursor="c2",
            orders=[order(1, version=2)],
            removed_order_ids=[2],
            events=[
                pb.UnitEvent(
                    order=pb.OrderEvent(
                        order_id=1,
                        version=2,
                        kind=pb.OrderEvent.FILLED,
                        fill=pb.Fill(
                            match_id=77,
                            ordinal=1,
                            role=pb.Fill.TAKER,
                            qty_scaled=100_000,
                            price_ticks=2_420_000_000_000,
                        ),
                    )
                ),
                pb.UnitEvent(
                    outcome=pb.CommandOutcome(
                        kind=pb.CommandOutcome.CANCEL_REJECTED,
                        order_id=3,
                        reason=orders_pb2.ERROR_CODE_ORDER_ALREADY_TERMINAL,
                    )
                ),
            ],
        ),
    )
    unit = await next_event(sub)
    assert isinstance(unit, PrivateOrdersUnit)
    assert [(o.order_id, o.version) for o in unit.orders] == [(format_id(1), 2)]
    assert unit.removed_order_ids == [format_id(2)]
    filled, outcome = unit.events
    assert isinstance(filled, PrivateOrderEvent)
    assert filled.kind == "filled"
    assert filled.fill is not None
    assert filled.fill.match_id == "77"
    assert filled.fill.role == "taker"
    assert filled.fill.price is not None
    assert filled.fill.price.format() == "2420"
    assert isinstance(outcome, PrivateOrderCommandOutcome)
    assert outcome.kind == "cancel_rejected"
    assert outcome.order_id == format_id(3)
    assert outcome.reason == "order_already_terminal"


async def test_seq_gap_resubscribes_with_the_last_applied_cursor(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    await conn.send("s1", 5, unit=pb.Unit(prev_cursor="c1", next_cursor="c9"))
    assert (await conn.expect("unsubscribe")).sub == "s1"
    retry = await conn.expect("subscribe")
    assert retry.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    # Frames for the dropped subscription are ignored.
    await conn.send("s1", 6, unit=pb.Unit(next_cursor="c10", orders=[order(9)]))
    await conn.send("s2", subscribed=pb.Subscribed(id=retry.id, account=ACCOUNT))
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await conn.send("s2", 1, unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(1)]))
    unit = await next_event(sub)
    assert isinstance(unit, PrivateOrdersUnit)
    assert [o.order_id for o in unit.orders] == [format_id(1)]


async def test_seq_repeat_resubscribes(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await conn.send("s1", 3, covered=pb.Covered(cursor="c2"))
    assert (await conn.expect("subscribe")).cursor == "c1"


async def test_unknown_frame_kind_is_skipped_but_counts_in_seq(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    # seq 4 carries a frame kind this SDK does not know (field 99).
    unknown = pb.ServerMessage(sub="s1", seq=4).SerializeToString() + bytes([0x9A, 0x06, 0x00])
    await conn.send_raw(unknown)
    await conn.send("s1", 5, unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(3)]))

    unit = await next_event(sub)
    assert isinstance(unit, PrivateOrdersUnit)
    assert [o.order_id for o in unit.orders] == [format_id(3)]
    await settle()
    assert conn.ops("subscribe") and len(conn.ops("subscribe")) == 1
    assert conn.ops("unsubscribe") == []


async def test_resync_required_replaces_state_with_the_next_snapshot(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [order(1), order(2)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    await conn.send(
        "s1",
        4,
        resync_required=pb.ResyncRequired(reason=pb.ResyncRequired.CURSOR_EXPIRED),
    )
    await conn.send("s1", 5, snapshot_begin=pb.SnapshotBegin(epoch=2))
    await conn.send("s1", 6, snapshot_page=pb.SnapshotPage(orders=[order(3)]))
    await conn.send("s1", 7, snapshot_end=pb.SnapshotEnd(cursor="r1", count=1))
    event = await next_event(sub)
    assert isinstance(event, PrivateOrdersSnapshot)
    assert [o.order_id for o in event.orders] == [format_id(3)]

    # A consumer that joins now catches up on the replaced state only.
    late = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(late), PrivateOrdersConnected)
    catch_up = await next_event(late)
    assert isinstance(catch_up, PrivateOrdersSnapshot)
    assert [o.order_id for o in catch_up.orders] == [format_id(3)]
    # One server subscription is shared by both consumers.
    await settle()
    assert len(conn.ops("subscribe")) == 1


async def test_unavailable_and_available_toggle_the_stale_flag(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await conn.send("s1", 4, unavailable=pb.Unavailable(reason=pb.FAILOVER))
    await conn.send("s1", 5, available=pb.Available())
    first = await next_event(sub)
    second = await next_event(sub)
    assert isinstance(first, PrivateOrdersStale) and first.stale is True
    assert isinstance(second, PrivateOrdersStale) and second.stale is False


async def test_subscribe_expiring_sends_subscribe_refresh_with_a_fresh_token(
    server: FakePrivateWsServer, stream: PrivateOrderStream, tokens: Tokens
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.send("s1", subscribe_expiring=pb.SubscribeExpiring(expires_ts_sec=1))
    refresh = await conn.expect("subscribe_refresh")
    assert refresh.sub == "s1"
    assert refresh.token == "sub-2"
    assert tokens.subscribe_channels == [CHANNEL, CHANNEL]
    await conn.send("s1", subscribe_refreshed=pb.SubscribeRefreshed(id=refresh.id))

    # A refused refresh is surfaced; the stream keeps running.
    await conn.send("s1", subscribe_expiring=pb.SubscribeExpiring(expires_ts_sec=2))
    second = await conn.expect("subscribe_refresh")
    await conn.send(
        "s1",
        error=pb.RequestError(id=second.id, code=pb.RequestError.FORBIDDEN, message="denied"),
    )
    event = await next_event(sub)
    assert isinstance(event, PrivateOrdersError)
    assert event.kind == "refresh"
    assert isinstance(event.error, PolyesterRealtimeError)
    assert event.error.code == "FORBIDDEN"
    assert sub.is_alive


async def test_token_expiring_reauthenticates_with_a_fresh_connect_token(
    server: FakePrivateWsServer, stream: PrivateOrderStream, tokens: Tokens
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.send(token_expiring=pb.TokenExpiring(expires_ts_sec=1))
    auth = await conn.expect("auth")
    assert auth.token == "connect-2"
    assert tokens.connect_calls == 2
    assert len(server.all) == 1


async def test_token_expired_unsubscribe_resubscribes_from_the_cursor(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await conn.send(
        "s1", unsubscribed=pb.Unsubscribed(reason=pb.Unsubscribed.TOKEN_EXPIRED)
    )
    assert (await conn.expect("subscribe")).cursor == "c1"


async def test_heartbeat_timeout_reconnects_and_resubscribes_with_the_cursor(
    server: FakePrivateWsServer,
    stream: PrivateOrderStream,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(private_orders, "HEARTBEAT_TIMEOUT", 0.3)
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    # Heartbeats keep the connection.
    for _ in range(3):
        await asyncio.sleep(0.15)
        await first.send(heartbeat=pb.Heartbeat(server_ts_ns=1))
    assert len(server.all) == 1

    # Silence drops it.
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    second = await server.next_connection()
    assert (await second.expect("auth")).token == "connect-2"
    request = await second.confirm("s2")
    assert request.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await asyncio.sleep(0.05)
    assert first.close_code == 4000


@pytest.mark.parametrize("code", [4408, 1001, 4401])
async def test_reconnecting_close_codes_resume_from_the_cursor(
    server: FakePrivateWsServer, stream: PrivateOrderStream, code: int
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await first.close(code)
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)

    second = await server.next_connection()
    await second.expect("auth")
    assert (await second.confirm("s2")).cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await second.send("s2", 1, unit=pb.Unit(prev_cursor="c1", next_cursor="c2"))
    assert isinstance(await next_event(sub), PrivateOrdersUnit)


@pytest.mark.parametrize("code", [4403, 4400])
async def test_terminal_close_codes_end_the_stream(
    server: FakePrivateWsServer, stream: PrivateOrderStream, code: int
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.close(code, "bad token")
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    with pytest.raises(PolyesterRealtimeError) as excinfo:
        await next_event(sub)
    assert excinfo.value.close_code == code
    assert sub.error is excinfo.value
    await asyncio.sleep(0.2)
    assert len(server.all) == 1
    assert stream.active_accounts == 0


async def test_forbidden_subscribe_is_surfaced(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    task = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
    conn = await server.next_connection()
    request = await conn.expect("subscribe")
    await conn.send(
        error=pb.RequestError(id=request.id, code=pb.RequestError.FORBIDDEN, message="forbidden")
    )
    with pytest.raises(PolyesterRealtimeError, match="forbidden") as excinfo:
        await asyncio.wait_for(task, EVENT_TIMEOUT)
    assert excinfo.value.code == "FORBIDDEN"
    await asyncio.sleep(0.05)
    assert conn.close_code == 1000


async def test_forbidden_resubscribe_ends_a_running_stream(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await conn.send("s1", 9, covered=pb.Covered(cursor="c2"))
    request = await conn.expect("subscribe")
    await conn.send(
        error=pb.RequestError(id=request.id, code=pb.RequestError.FORBIDDEN, message="forbidden")
    )
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    with pytest.raises(PolyesterRealtimeError) as excinfo:
        await next_event(sub)
    assert excinfo.value.code == "FORBIDDEN"


async def test_invalid_cursor_retries_with_a_fresh_snapshot(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    await conn.send("s1", 9, covered=pb.Covered(cursor="c2"))
    request = await conn.expect("subscribe")
    assert request.cursor == "c1"
    await conn.send(error=pb.RequestError(id=request.id, code=pb.RequestError.CURSOR_INVALID))
    assert (await conn.expect("subscribe")).cursor == ""


async def test_refused_connect_token_fails_the_subscribe(
    server: FakePrivateWsServer, stream: PrivateOrderStream, tokens: Tokens
) -> None:
    tokens.connect_error = PolyesterAuthError("permission denied")
    with pytest.raises(PolyesterAuthError):
        await asyncio.wait_for(stream.subscribe(ACCOUNT_B58), EVENT_TIMEOUT)
    assert len(server.all) == 0


async def test_last_consumer_leaving_unsubscribes_and_closes_the_connection(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    other = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(other), PrivateOrdersConnected)
    await sub.aclose()
    await settle()
    assert conn.ops("unsubscribe") == []
    await other.aclose()
    assert (await conn.expect("unsubscribe")).sub == "s1"
    await asyncio.sleep(0.1)
    assert conn.close_code == 1000


async def test_ready_follows_the_snapshot_once_per_server_subscription(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [order(1)])
    await conn.send("s1", 4, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    assert isinstance(await next_event(sub), PrivateOrdersReady)

    # A repeated ready on the same server subscription is not delivered again.
    await conn.send("s1", 5, ready=pb.Ready())
    await conn.send("s1", 6, unit=pb.Unit(prev_cursor="c1", next_cursor="c2"))
    assert isinstance(await next_event(sub), PrivateOrdersUnit)

    # A resubscribe on the same connection starts a new server subscription.
    await conn.send("s1", 9, covered=pb.Covered(cursor="c3"))
    request = await conn.expect("subscribe")
    assert request.cursor == "c2"
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    await conn.send("s2", subscribed=pb.Subscribed(id=request.id, account=ACCOUNT))
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await conn.send("s2", 1, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersReady)


async def test_ready_is_delivered_again_after_a_reconnect(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [order(1)])
    await first.send("s1", 4, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    assert isinstance(await next_event(sub), PrivateOrdersReady)

    await first.close(1001)
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    second = await server.next_connection()
    await second.expect("auth")
    assert (await second.confirm("s2")).cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    # A resumed subscription sends no snapshot; ready still marks its read boundary.
    await second.send("s2", 1, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersReady)


async def test_late_joiner_of_a_ready_subscription_gets_snapshot_then_ready(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [order(1), order(2)])
    await conn.send("s1", 4, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    assert isinstance(await next_event(sub), PrivateOrdersReady)

    late = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(late), PrivateOrdersConnected)
    catch_up = await next_event(late)
    assert isinstance(catch_up, PrivateOrdersSnapshot)
    assert [o.order_id for o in catch_up.orders] == [format_id(1), format_id(2)]
    assert isinstance(await next_event(late), PrivateOrdersReady)
    assert late._queue.empty()


async def test_late_joiner_before_ready_gets_it_live(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, conn = await open_stream(server, stream)
    await conn.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    late = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(late), PrivateOrdersConnected)
    assert isinstance(await next_event(late), PrivateOrdersSnapshot)
    assert late._queue.empty()
    await conn.send("s1", 4, ready=pb.Ready())
    assert isinstance(await next_event(sub), PrivateOrdersReady)
    assert isinstance(await next_event(late), PrivateOrdersReady)


async def test_subscribe_right_after_the_last_consumer_left_opens_a_new_connection(
    server: FakePrivateWsServer, stream: PrivateOrderStream
) -> None:
    sub, first = await open_stream(server, stream)
    await sub.aclose()
    task = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
    second = await server.next_connection()
    await second.expect("auth")
    await second.confirm("s2")
    again = await asyncio.wait_for(task, EVENT_TIMEOUT)
    assert isinstance(await next_event(again), PrivateOrdersConnected)
    await asyncio.sleep(0.1)
    assert first.close_code == 1000
    assert len(server.all) == 2


async def test_orders_subscribe_routes_through_the_private_socket(
    server: FakePrivateWsServer,
) -> None:
    import httpx

    from polyester.realtime.client import AsyncRealtimeClient

    async with httpx.AsyncClient(timeout=5.0) as http:
        realtime = AsyncRealtimeClient(
            "ws://127.0.0.1:1",
            api_url=server.api_url,
            credentials=make_test_credentials(),
            http=http,
        )
        service = AsyncOrdersService(
            transport=None,
            catalogs=None,  # type: ignore[arg-type]
            default_sub_account_id=None,
            default_account_id=ACCOUNT_B58,
            realtime=realtime,
        )
        task = asyncio.create_task(service.subscribe())
        conn = await server.next_connection()
        assert (await conn.expect("auth")).token == "connect-token"
        request = await conn.confirm()
        assert request.token == "sub-token"
        sub = await asyncio.wait_for(task, EVENT_TIMEOUT)
        assert isinstance(await next_event(sub), PrivateOrdersConnected)
        assert server.ws_paths == ["/v1/ws/private"]
        assert server.http_paths == [
            "/v1/rt/token",
            f"/v1/rt/subscribe?channel=private%3Aspot%3Aorders%3A{ACCOUNT_B58}",
        ]
        await realtime.aclose()
        with pytest.raises(StopAsyncIteration):
            await next_event(sub)


async def test_unanswered_resubscribe_on_a_confirmed_stream_retries_and_recovers(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(private_orders, "SUBSCRIBE_ACK_TIMEOUT", 0.2)
    sub, conn = await open_stream(server, stream)
    # A snapshot end with no snapshot makes a confirmed stream subscribe again.
    await conn.send("s1", 1, snapshot_end=pb.SnapshotEnd(cursor="c1", count=1))
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    first_retry = await conn.expect("subscribe")

    # The server keeps the connection alive and never answers it.
    await conn.send(heartbeat=pb.Heartbeat(server_ts_ns=1))
    reported = await next_event(sub)
    assert isinstance(reported, PrivateOrdersError), reported
    assert reported.kind == "subscribe"
    assert "not confirmed" in str(reported.error)

    # The stream keeps its subscription, retries, and recovers.
    second_retry = await conn.expect("subscribe")
    assert second_retry.id != first_retry.id
    await conn.send("s3", subscribed=pb.Subscribed(id=second_retry.id, account=ACCOUNT))
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await conn.send("s3", 1, snapshot_begin=pb.SnapshotBegin(epoch=1))
    await conn.send("s3", 2, snapshot_end=pb.SnapshotEnd(cursor="c2", count=0))
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    assert sub.error is None

    # A late answer to the expired request is unsubscribed, not adopted.
    await conn.send("late", subscribed=pb.Subscribed(id=first_retry.id, account=ACCOUNT))
    assert (await conn.expect("unsubscribe")).sub == "late"


async def test_answered_resubscribe_within_the_deadline_is_not_retried(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(private_orders, "SUBSCRIBE_ACK_TIMEOUT", 0.2)
    sub, conn = await open_stream(server, stream)
    await conn.send("s1", 1, snapshot_end=pb.SnapshotEnd(cursor="c1", count=1))
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    await conn.confirm("s2")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await asyncio.sleep(0.4)
    assert len(conn.ops("subscribe")) == 2, "the initial subscribe and one resubscribe"
    assert sub.error is None


# --- unexpected failures inside the shared connection ----------------------
#
# The decoder maps orders one to one, so these inject the failures: a decoder
# that returns fewer orders than the frame carries, and handlers that raise.

ACCOUNT_B = 43
ACCOUNT_C = 44


def short_decoder(decode: Any) -> Any:
    """Wrap ``decode`` to drop the last decoded order."""

    def short(value: Any, *, scales: Any = None) -> Any:
        decoded = decode(value, scales=scales)
        if isinstance(decoded, list):
            return decoded[:-1]
        return dataclasses.replace(decoded, orders=decoded.orders[:-1])

    return short


def fail_on_unit(
    stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch, *, times: int
) -> None:
    """Make the next ``times`` unit frames raise inside the frame handler."""
    handle = stream._on_frame
    left = times

    def failing(ws: Any, raw: str | bytes) -> None:
        nonlocal left
        if left and isinstance(raw, bytes) and pb.ServerMessage.FromString(raw).HasField("unit"):
            left -= 1
            raise RuntimeError("injected internal handler failure")
        handle(ws, raw)

    monkeypatch.setattr(stream, "_on_frame", failing)


async def expect_internal_failure(sub: AsyncSubscription[Any]) -> PolyesterRealtimeError:
    """The connection dropped and said why; the consumer keeps running."""
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    reported = await next_event(sub)
    assert isinstance(reported, PrivateOrdersError), reported
    assert reported.kind == "internal"
    assert isinstance(reported.error, PolyesterRealtimeError)
    assert "private order stream failed" in str(reported.error)
    assert sub.is_alive
    assert sub.error is None
    return reported.error


async def reconnect(
    server: FakePrivateWsServer, sub_id: str
) -> tuple[FakeConnection, pb.Subscribe]:
    conn = await server.next_connection()
    await conn.expect("auth")
    return conn, await conn.confirm(sub_id)


async def test_unit_decoded_short_of_its_orders_applies_nothing_and_resumes_from_its_cursor(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    errors: list[BaseException] = []
    sub.set_on_error(errors.append)
    await first.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    decode_unit = private_orders.private_orders_unit_from_proto
    monkeypatch.setattr(
        private_orders, "private_orders_unit_from_proto", short_decoder(decode_unit)
    )
    unit = pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(1, version=2), order(2)])
    await first.send("s1", 4, unit=unit)

    error = await expect_internal_failure(sub)
    assert isinstance(error.__cause__, ValueError)
    assert errors == [error]
    # Nothing of the unit was applied: neither its cursor nor any of its orders.
    state = stream._subs[CHANNEL]
    assert state.cursor == "c1"
    assert state.orders == {format_id(1): order(1)}

    monkeypatch.setattr(private_orders, "private_orders_unit_from_proto", decode_unit)
    # A consumer joining during the recovery gets the last applied view.
    joining = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
    second, request = await reconnect(server, "s2")
    assert request.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    late = await asyncio.wait_for(joining, EVENT_TIMEOUT)
    assert isinstance(await next_event(late), PrivateOrdersConnected)
    view = await next_event(late)
    assert isinstance(view, PrivateOrdersSnapshot)
    assert [(o.order_id, o.version) for o in view.orders] == [(format_id(1), 1)]

    # The undelivered unit arrives again and is applied once.
    await second.send("s2", 1, unit=unit)
    for consumer in (sub, late):
        delivered = await next_event(consumer)
        assert isinstance(delivered, PrivateOrdersUnit)
        assert [(o.order_id, o.version) for o in delivered.orders] == [
            (format_id(1), 2),
            (format_id(2), 1),
        ]
    assert state.cursor == "c2"
    assert state.orders == {format_id(1): order(1, version=2), format_id(2): order(2)}
    await asyncio.sleep(0.05)
    assert first.close_code == 1011
    assert len(server.all) == 2


async def test_snapshot_decoded_short_of_its_orders_keeps_the_last_view_and_cursor(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    decode_orders = private_orders.private_orders_from_proto
    monkeypatch.setattr(private_orders, "private_orders_from_proto", short_decoder(decode_orders))
    await first.send("s1", 4, snapshot_begin=pb.SnapshotBegin(epoch=2))
    await first.send("s1", 5, snapshot_page=pb.SnapshotPage(orders=[order(1, 2), order(2)]))
    await first.send("s1", 6, snapshot_end=pb.SnapshotEnd(cursor="c2", count=2))

    error = await expect_internal_failure(sub)
    assert isinstance(error.__cause__, ValueError)
    state = stream._subs[CHANNEL]
    assert state.cursor == "c1"
    assert state.orders == {format_id(1): order(1)}

    monkeypatch.setattr(private_orders, "private_orders_from_proto", decode_orders)
    second, request = await reconnect(server, "s2")
    assert request.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await second.snapshot("s2", "c2", [order(1, 2), order(2)])
    snapshot = await next_event(sub)
    assert isinstance(snapshot, PrivateOrdersSnapshot)
    assert [o.order_id for o in snapshot.orders] == [format_id(1), format_id(2)]
    assert state.cursor == "c2"


async def test_internal_handler_failure_reconnects_from_the_last_applied_cursor(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [order(1)])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    fail_on_unit(stream, monkeypatch, times=1)
    await first.send("s1", 4, unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(2)]))
    error = await expect_internal_failure(sub)
    assert isinstance(error.__cause__, RuntimeError)
    assert stream._subs[CHANNEL].cursor == "c1"

    second, request = await reconnect(server, "s2")
    assert request.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await second.send("s2", 1, unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(2)]))
    unit = await next_event(sub)
    assert isinstance(unit, PrivateOrdersUnit)
    assert [o.order_id for o in unit.orders] == [format_id(2)]
    assert sub.error is None


async def test_repeated_internal_failures_end_the_stream_truthfully(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    limit = private_orders.MAX_INTERNAL_FAILURES
    sub, conn = await open_stream(server, stream)
    fail_on_unit(stream, monkeypatch, times=limit)
    for attempt in range(limit):
        if attempt:
            conn, request = await reconnect(server, f"s{attempt + 1}")
            assert request.cursor == "c1"
            assert isinstance(await next_event(sub), PrivateOrdersConnected)
        else:
            await conn.snapshot("s1", "c1", [order(1)])
            assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
        await conn.send(
            f"s{attempt + 1}",
            4 if attempt == 0 else 1,
            unit=pb.Unit(prev_cursor="c1", next_cursor="c2", orders=[order(2)]),
        )
        if attempt < limit - 1:
            await expect_internal_failure(sub)

    # The last failure ends the stream: no consumer is left looking alive.
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    with pytest.raises(PolyesterRealtimeError, match="private order stream failed") as excinfo:
        await next_event(sub)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert sub.error is excinfo.value
    assert not sub.is_alive
    assert stream.active_accounts == 0
    await asyncio.sleep(0.2)
    assert len(server.all) == limit


async def test_internal_failure_reaches_every_account_and_fails_pending_subscribes(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, conn = await open_stream(server, stream)
    shared = await stream.subscribe(ACCOUNT_B58)
    assert isinstance(await next_event(shared), PrivateOrdersConnected)
    opening = asyncio.create_task(stream.subscribe(format_id(ACCOUNT_B)))
    request = await conn.expect("subscribe")
    assert request.account == ACCOUNT_B
    await conn.send("s2", subscribed=pb.Subscribed(id=request.id, account=ACCOUNT_B))
    b = await asyncio.wait_for(opening, EVENT_TIMEOUT)
    assert isinstance(await next_event(b), PrivateOrdersConnected)
    await conn.snapshot("s1", "a1", [order(1)])
    await conn.snapshot("s2", "b1", [order(2)])
    for consumer in (a, shared, b):
        assert isinstance(await next_event(consumer), PrivateOrdersSnapshot)

    # A subscribe the server has not confirmed yet.
    pending = asyncio.create_task(stream.subscribe(format_id(ACCOUNT_C)))
    assert (await conn.expect("subscribe")).account == ACCOUNT_C

    fail_on_unit(stream, monkeypatch, times=1)
    await conn.send("s1", 4, unit=pb.Unit(prev_cursor="a1", next_cursor="a2"))
    errors = [await expect_internal_failure(consumer) for consumer in (a, shared, b)]
    assert errors[0] is errors[1] is errors[2]
    with pytest.raises(PolyesterRealtimeError) as excinfo:
        await asyncio.wait_for(pending, EVENT_TIMEOUT)
    assert excinfo.value is errors[0]
    assert stream.active_accounts == 2

    second = await server.next_connection()
    await second.expect("auth")
    requests = [await second.expect("subscribe") for _ in range(2)]
    assert {r.account: r.cursor for r in requests} == {ACCOUNT: "a1", ACCOUNT_B: "b1"}
    for index, r in enumerate(requests):
        await second.send(f"t{index}", subscribed=pb.Subscribed(id=r.id, account=r.account))
    for consumer in (a, shared, b):
        assert isinstance(await next_event(consumer), PrivateOrdersConnected)
        assert consumer.error is None


async def test_failure_in_a_connection_helper_task_is_supervised_too(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)

    async def broken(ws: Any) -> None:
        raise RuntimeError("injected reauthentication failure")

    monkeypatch.setattr(stream, "_reauthenticate", broken)
    await first.send(token_expiring=pb.TokenExpiring(expires_ts_sec=1))
    error = await expect_internal_failure(sub)
    assert isinstance(error.__cause__, RuntimeError)
    _, request = await reconnect(server, "s2")
    assert request.cursor == "c1"
    assert isinstance(await next_event(sub), PrivateOrdersConnected)


async def test_cancelled_subscribe_during_recovery_stays_a_cancellation(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    fail_on_unit(stream, monkeypatch, times=1)
    await first.send("s1", 4, unit=pb.Unit(prev_cursor="c1", next_cursor="c2"))
    await expect_internal_failure(sub)

    joining = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
    await settle()
    joining.cancel()
    with pytest.raises(asyncio.CancelledError):
        await joining
    assert len(stream._subs[CHANNEL].consumers) == 1

    await reconnect(server, "s2")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    await stream.aclose()
    with pytest.raises(StopAsyncIteration):
        await next_event(sub)
    assert sub.error is None
    assert not sub.is_alive


async def test_close_during_recovery_ends_consumers_without_an_error(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    await first.snapshot("s1", "c1", [])
    assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
    # The stream waits out its reconnect backoff when it is closed.
    monkeypatch.setattr(private_orders, "RECONNECT_BASE_DELAY", 5.0)
    monkeypatch.setattr(private_orders, "RECONNECT_MAX_DELAY", 10.0)
    fail_on_unit(stream, monkeypatch, times=1)
    await first.send("s1", 4, unit=pb.Unit(prev_cursor="c1", next_cursor="c2"))
    await expect_internal_failure(sub)

    await asyncio.wait_for(stream.aclose(), EVENT_TIMEOUT)
    with pytest.raises(StopAsyncIteration):
        await next_event(sub)
    assert sub.error is None
    assert not sub.is_alive
    assert stream.active_accounts == 0
    assert len(server.all) == 1


async def test_failure_outside_the_connection_handling_ends_the_stream_truthfully(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, conn = await open_stream(server, stream)

    def broken(attempt: int) -> float:
        raise RuntimeError("injected backoff failure")

    monkeypatch.setattr(private_orders, "_backoff_delay", broken)
    await conn.close(1001)
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    with pytest.raises(PolyesterRealtimeError, match="private order stream failed") as excinfo:
        await next_event(sub)
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert sub.error is excinfo.value
    assert not sub.is_alive
    assert stream.active_accounts == 0


async def test_helper_failing_after_its_connection_dropped_is_reported(
    server: FakePrivateWsServer, stream: PrivateOrderStream, monkeypatch: pytest.MonkeyPatch
) -> None:
    sub, first = await open_stream(server, stream)
    release = asyncio.Event()

    async def broken(ws: Any, s: Any) -> None:
        await release.wait()
        raise RuntimeError("injected refresh failure")

    monkeypatch.setattr(stream, "_refresh", broken)
    monkeypatch.setattr(private_orders, "RECONNECT_BASE_DELAY", 0.3)
    monkeypatch.setattr(private_orders, "RECONNECT_MAX_DELAY", 0.3)
    await first.send("s1", subscribe_expiring=pb.SubscribeExpiring(expires_ts_sec=1))
    await settle()
    await first.close(1001)
    assert isinstance(await next_event(sub), PrivateOrdersDisconnected)
    release.set()
    reported = await next_event(sub)
    assert isinstance(reported, PrivateOrdersError)
    assert reported.kind == "internal"
    assert isinstance(reported.error.__cause__, RuntimeError)
    # The stream reconnects as it was already doing.
    _, request = await reconnect(server, "s2")
    assert isinstance(await next_event(sub), PrivateOrdersConnected)
    assert sub.error is None
