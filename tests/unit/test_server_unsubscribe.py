"""Subscriptions the server ends: no silent stall, bounded resume, typed stops."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import MagicMock

import httpx
import pytest
import websockets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester import PolyesterSubscriptionEndedError
from polyester.auth import ApiKeyCredentials
from polyester.catalogs import CatalogManager
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterAuthError, PolyesterRealtimeError
from polyester.gen.auth.v1 import subaccounts_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.realtime.client import AsyncRealtimeClient
from polyester.realtime.resubscribe import (
    ResubscribeTiming,
    SubaccountAccess,
    subaccount_channel_id,
)
from polyester.services.orderbook import AsyncOrderbookService

ACK_CONNECT = bytes.fromhex("020801")
ACK_SUBSCRIBE = bytes.fromhex("020802")


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _field(number: int, payload: bytes) -> bytes:
    return _varint((number << 3) | 2) + _varint(len(payload)) + payload


def _frame(reply: bytes) -> bytes:
    return _varint(len(reply)) + reply


def publication(data: bytes) -> bytes:
    return _frame(_field(4, _field(4, _field(4, data))))


def unsubscribe(channel: str, code: int = 2000, reason: str = "server unsubscribe") -> bytes:
    body = _varint(2 << 3) + _varint(code) + _field(3, reason.encode())
    return _frame(_field(4, _field(2, channel.encode()) + _field(7, body)))


class CentrifugoServer:
    """Real socket answering connect and subscribe, then pushing frames per channel."""

    def __init__(self) -> None:
        self.conns: dict[str, list[websockets.ServerConnection]] = {}
        self.subscribed: asyncio.Queue[str] = asyncio.Queue()
        self.on_subscribed = None
        self.url = ""
        self._server = None

    async def __aenter__(self) -> CentrifugoServer:
        self._server = await websockets.serve(
            self._handle, "127.0.0.1", 0, subprotocols=["centrifuge-protobuf"]
        )
        self.url = f"ws://127.0.0.1:{self._server.sockets[0].getsockname()[1]}"
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self._server.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._server.wait_closed(), timeout=2)

    async def _handle(self, ws) -> None:
        await ws.recv()
        await ws.send(ACK_CONNECT)
        command = await ws.recv()
        start = min(i for i in (command.find(b"private:"), command.find(b"public:")) if i >= 0)
        channel = command[start : start + command[start - 1]].decode()
        await ws.send(ACK_SUBSCRIBE)
        self.conns.setdefault(channel, []).append(ws)
        self.subscribed.put_nowait(channel)
        if self.on_subscribed is not None:
            await self.on_subscribed(channel, ws)
        await ws.wait_closed()

    async def wait_subscribed(self, channel: str, timeout: float = 10) -> None:
        async with asyncio.timeout(timeout):
            while await self.subscribed.get() != channel:
                pass

    async def push(self, channel: str, frame: bytes) -> None:
        await self.conns[channel][-1].send(frame)


async def _drain(sub, timeout: float = 5) -> list:
    """Queued rows until the stream ends; a raw iterator raises its terminal error last."""
    rows = []
    with contextlib.suppress(PolyesterSubscriptionEndedError):
        async with asyncio.timeout(timeout):
            async for row in sub:
                rows.append(row)
    return rows


async def test_server_unsubscribe_ends_subscription_instead_of_stalling() -> None:
    channel = "public:spot:trades:1:proto"
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        sub = await rt.subscribe_proto(channel, decode=lambda data: data)
        reported = []
        sub.set_on_error(reported.append)
        await server.wait_subscribed(channel)
        await server.push(channel, publication(b"live"))
        async with asyncio.timeout(5):
            assert await anext(sub) == b"live"
        assert sub.error is None, "live control"

        await server.push(channel, publication(b"last") + unsubscribe(channel))
        try:
            rows = await _drain(sub)
        except TimeoutError:
            pytest.fail("subscription stayed open and silent after the server ended it")
        assert rows == [b"last"]
        assert isinstance(sub.error, PolyesterSubscriptionEndedError)
        assert sub.error.channel == channel
        assert sub.error.unsubscribe_code == 2000
        assert sub.error.server_reason == "server unsubscribe"
        assert sub.error.reason == "not_resubscribable"
        assert reported == [sub.error]
        await rt.aclose()


async def test_unsubscribe_of_another_channel_is_ignored() -> None:
    channel = "public:spot:trades:1:proto"
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        sub = await rt.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        await server.push(channel, unsubscribe("public:spot:trades:2:proto"))
        await server.push(channel, publication(b"after"))
        async with asyncio.timeout(5):
            assert await anext(sub) == b"after"
        assert sub.error is None
        await rt.aclose()


def _book(seq: int, *, available: bool) -> orderbook_pb2.GetOrderBookResponse:
    response = orderbook_pb2.GetOrderBookResponse(symbol_id=1, book_seq=seq, available=available)
    if available:
        response.bids.add(price_ticks=100, qty_scaled=5)
        response.asks.add(price_ticks=101, qty_scaled=5)
    return response


def _book_service(rt, respond, monkeypatch) -> tuple[AsyncOrderbookService, list[int]]:
    calls: list[int] = []

    async def fake_unary(_transport, _client, _call, _request, decode):
        calls.append(1)
        return decode(respond(len(calls)))

    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fake_unary)
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=rt), calls


async def test_available_snapshot_cancels_pending_request(monkeypatch) -> None:
    # A newer available snapshot makes the pending request obsolete: it must not
    # fire, or a failure there could end a healthy stream.
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, calls = _book_service(
            rt,
            lambda n: _book(0, available=False) if n == 1 else _book(10, available=True),
            monkeypatch,
        )
        sub = await service.create_subscription(symbol="BTC-USDT", depth=10)
        async with asyncio.timeout(5):
            assert (await anext(sub)).available is False
        await sub.refresh_snapshot()
        async with asyncio.timeout(5):
            assert (await anext(sub)).available is True
        assert len(calls) == 2, "before the old timer is due"
        # Past the 1 s delay the unavailable snapshot scheduled.
        await asyncio.sleep(1.5)
        assert len(calls) == 2, "an obsolete request fired"
        assert sub.last_error is None
        await sub.aclose()
        await rt.aclose()


async def test_reconnect_with_an_available_snapshot_cancels_pending_request(monkeypatch) -> None:
    channel = "public:spot:orderbook:deltas:depth:10:1:proto"
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, calls = _book_service(
            rt,
            lambda n: _book(0, available=False) if n == 1 else _book(10, available=True),
            monkeypatch,
        )
        sub = await service.create_subscription(symbol="BTC-USDT", depth=10)
        await server.wait_subscribed(channel)
        async with asyncio.timeout(5):
            assert (await anext(sub)).available is False
        await server.conns[channel][-1].close()
        async with asyncio.timeout(5):
            assert (await anext(sub)).available is True
        await server.wait_subscribed(channel)
        assert len(calls) == 2
        await asyncio.sleep(1.5)
        assert len(calls) == 2, "an obsolete request fired"
        await sub.aclose()
        await rt.aclose()


async def test_first_view_is_the_fetched_snapshot(monkeypatch) -> None:
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, _ = _book_service(rt, lambda _n: _book(10, available=True), monkeypatch)
        events = []
        sub = await service.create_subscription(symbol="BTC-USDT", depth=10, on_event=events.append)
        async with asyncio.timeout(5):
            first = await anext(sub)
        assert first.book_seq == "10" and first.available and len(first.bids) == 1
        assert events[0].book_seq == "10"
        await sub.aclose()
        await rt.aclose()


async def test_unavailable_snapshot_is_requested_again(monkeypatch) -> None:
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, calls = _book_service(
            rt,
            lambda n: _book(0, available=False) if n < 3 else _book(10, available=True),
            monkeypatch,
        )
        sub = await service.create_subscription(symbol="BTC-USDT", depth=10)
        async with asyncio.timeout(5):
            first = await anext(sub)
        assert first.available is False and first.bids == []
        # A repeated unavailable answer adds no view: the next one is the book.
        try:
            async with asyncio.timeout(15):
                second = await anext(sub)
        except TimeoutError:
            pytest.fail("the unavailable snapshot was never requested again")
        assert second.available is True and second.book_seq == "10" and len(second.bids) == 1
        assert len(calls) == 3
        await asyncio.sleep(1.5)
        assert len(calls) == 3, "requests stop once the book is available"
        await sub.aclose()
        await rt.aclose()


async def test_available_snapshot_is_not_requested_again(monkeypatch) -> None:
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, calls = _book_service(rt, lambda _n: _book(10, available=True), monkeypatch)
        sub = await service.create_subscription(symbol="BTC-USDT", depth=10)
        async with asyncio.timeout(5):
            await anext(sub)
        await asyncio.sleep(1.5)
        assert len(calls) == 1
        await sub.aclose()
        await rt.aclose()


async def test_close_stops_requests_for_an_unavailable_book(monkeypatch) -> None:
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, calls = _book_service(rt, lambda _n: _book(0, available=False), monkeypatch)
        sub = await service.create_subscription(symbol="BTC-USDT", depth=10)
        async with asyncio.timeout(5):
            assert (await anext(sub)).available is False
        await sub.aclose()
        await asyncio.sleep(1.5)
        assert len(calls) == 1
        await rt.aclose()


async def test_managed_book_the_server_ends_releases_consumers(monkeypatch) -> None:
    channel = "public:spot:orderbook:deltas:depth:10:1:proto"
    async with CentrifugoServer() as server:
        rt = AsyncRealtimeClient(server.url)
        service, _ = _book_service(rt, lambda _n: _book(10, available=True), monkeypatch)
        reported = []
        sub = await service.create_subscription(
            symbol="BTC-USDT", depth=10, on_error=reported.append
        )
        await server.wait_subscribed(channel)
        async with asyncio.timeout(5):
            assert (await anext(sub)).book_seq == "10"
        await server.push(channel, unsubscribe(channel))
        try:
            assert await _drain(sub) == []
        except TimeoutError:
            pytest.fail("consumers not released after the server ended the book")
        assert isinstance(sub.last_error, PolyesterSubscriptionEndedError)
        assert sub.last_error.channel == channel
        assert reported == [sub.last_error]
        await sub.aclose()
        await rt.aclose()


SUB_ID = 2305843009213693953
FAST = ResubscribeTiming(
    max_attempts=3,
    initial_backoff=0.01,
    stable_after=3600,
    attempt_spacing=0.001,
    read_interval=0.001,
)


class ResumeApi:
    """Token and list API. Counters only count the operation they name."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.token_calls = 0
        self.connection_tokens = 0
        self.list_response = self.listed(SUB_ID)
        self.token_refusal: httpx.Response | None = None
        # Holds list answers open while set, and marks that one arrived.
        self.list_gate: asyncio.Event | None = None
        self.list_arrived = asyncio.Event()
        self.transport = httpx.MockTransport(self._handle)

    @staticmethod
    def listed(*ids: int) -> httpx.Response:
        return httpx.Response(
            200, json={"subaccounts": [{"id": str(i), "role": "VIEWER"} for i in ids]}
        )

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/rt/token":
            self.connection_tokens += 1
            return httpx.Response(200, json={"token": "connection"})
        if path == "/v1/rt/subscribe":
            self.token_calls += 1
            if self.token_refusal is not None:
                return self.token_refusal
            return httpx.Response(200, json={"token": "subscribe"})
        if path == "/v1/auth/subaccounts":
            self.list_calls += 1
            self.list_arrived.set()
            if self.list_gate is not None:
                await self.list_gate.wait()
            return (
                self.list_response(self.list_calls)
                if callable(self.list_response)
                else self.list_response
            )
        return httpx.Response(404)


def _client(server: CentrifugoServer, api: ResumeApi, timing=FAST) -> AsyncRealtimeClient:
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    client = AsyncRealtimeClient(
        server.url,
        api_url="https://api.test",
        credentials=ApiKeyCredentials(key_id="ak_test", private_key=private),
        http=httpx.AsyncClient(transport=api.transport),
    )
    client._access = SubaccountAccess(client, timing)
    return client


def _channel(account: int = SUB_ID) -> str:
    return f"private:ledger:balances:{format_id(account)}:proto"


async def _ended(sub, timeout: float = 5) -> PolyesterSubscriptionEndedError:
    try:
        await _drain(sub, timeout)
    except TimeoutError:
        pytest.fail("subscription stayed open after the server ended it")
    assert isinstance(sub.error, PolyesterSubscriptionEndedError), sub.error
    return sub.error


async def test_stale_unsubscribe_while_listed_resumes_with_fresh_token() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        assert api.token_calls == 1
        assert api.list_calls == 0, "a healthy subscribe must not read the list"

        await server.push(channel, unsubscribe(channel))
        await server.wait_subscribed(channel)
        assert api.token_calls == 2
        assert api.list_calls == 1
        await server.push(channel, publication(b"live again"))
        async with asyncio.timeout(5):
            assert await anext(sub) == b"live again"
        assert sub.take_resubscribed() is True
        assert sub.error is None
        await client.aclose()


async def test_removed_from_the_list_does_not_resubscribe() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        api.list_response = api.listed(SUB_ID + 1)
        await server.push(channel, unsubscribe(channel))
        ended = await _ended(sub)
        assert ended.reason == "not_listed"
        assert (ended.channel, ended.unsubscribe_code) == (channel, 2000)
        assert api.list_calls == 1
        assert api.token_calls == 1
        await client.aclose()


async def test_listed_without_a_role_does_not_resubscribe() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        api.list_response = httpx.Response(
            200, json={"subaccounts": [{"id": str(SUB_ID), "role": "SUBACCOUNT_ROLE_UNSPECIFIED"}]}
        )
        await server.push(channel, unsubscribe(channel))
        assert (await _ended(sub)).reason == "not_listed"
        await client.aclose()


async def test_seen_removal_stops_without_calls_and_a_later_grant_clears_it() -> None:
    channel = _channel()
    updates = "private:auth:subaccounts:root:proto"
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        stream = await client.subscribe_proto(updates, decode=lambda data: data)
        await server.wait_subscribed(updates)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        tokens = api.token_calls

        async def publish(message) -> None:
            await server.push(updates, publication(message.SerializeToString()))
            async with asyncio.timeout(5):
                await anext(stream)

        await publish(subaccounts_pb2.Subaccount(id=SUB_ID, removed=True))
        await server.push(channel, unsubscribe(channel))
        assert (await _ended(sub)).reason == "access_removed"
        assert api.list_calls == 0
        assert api.token_calls == tokens

        await publish(subaccounts_pb2.Subaccount(id=SUB_ID, role=subaccounts_pb2.VIEWER))
        again = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        await server.push(channel, unsubscribe(channel))
        await server.wait_subscribed(channel)
        assert api.list_calls == 1
        assert again.error is None
        await client.aclose()


async def test_refused_token_stops_with_the_refusal() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        api.token_refusal = httpx.Response(
            403, json={"code": "SUBACCOUNT_READ_FORBIDDEN", "message": "no access"}
        )
        await server.push(channel, unsubscribe(channel))
        ended = await _ended(sub)
        assert ended.reason == "token_refused"
        assert isinstance(ended.__cause__, PolyesterAuthError)
        assert ended.__cause__.status_code == 403
        assert api.token_calls == 2, "exactly one refused attempt"
        await client.aclose()


@pytest.mark.parametrize("status", [401, 403])
async def test_refused_list_stops_and_says_why(status: int) -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        api.list_response = httpx.Response(
            status, json={"code": "AUTH_SUBACCOUNT_ACCESS_DENIED", "message": "forbidden"}
        )
        await server.push(channel, unsubscribe(channel))
        ended = await _ended(sub)
        assert ended.reason == "list_refused"
        assert isinstance(ended.__cause__, PolyesterAuthError)
        assert ended.__cause__.status_code == status
        assert ended.__cause__.code == "AUTH_SUBACCOUNT_ACCESS_DENIED"
        assert "server ended realtime subscription" in str(ended)
        assert "list_refused" in str(ended)
        assert api.list_calls == 1
        assert api.token_calls == 1
        await client.aclose()


async def test_temporary_list_failure_retries_then_resumes() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        api.list_response = lambda call: (
            httpx.Response(503, json={}) if call == 1 else api.listed(SUB_ID)
        )
        await server.push(channel, unsubscribe(channel))
        await server.wait_subscribed(channel)
        assert api.list_calls == 2
        assert sub.error is None
        await client.aclose()


async def test_list_failures_have_a_hard_limit() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        api.list_response = httpx.Response(503, json={})
        await server.push(channel, unsubscribe(channel))
        ended = await _ended(sub, 10)
        assert ended.reason == "retries_exhausted"
        assert isinstance(ended.__cause__, PolyesterRealtimeError)
        assert api.list_calls == FAST.max_attempts
        await client.aclose()


async def test_repeated_stale_unsubscribes_have_a_hard_limit() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        unsubscribes = 0

        async def end_immediately(_channel_name, ws) -> None:
            nonlocal unsubscribes
            unsubscribes += 1
            await ws.send(unsubscribe(channel))

        server.on_subscribed = end_immediately
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        ended = await _ended(sub, 10)
        assert ended.reason == "retries_exhausted"
        assert api.token_calls == FAST.max_attempts + 1
        assert unsubscribes == FAST.max_attempts + 1, "the scenario must repeat to the limit"
        await client.aclose()


async def test_revocation_burst_cannot_flood_requests() -> None:
    timing = ResubscribeTiming(
        max_attempts=6,
        initial_backoff=0.005,
        stable_after=3600,
        attempt_spacing=0.04,
        read_interval=0.2,
    )
    burst = 25
    ids = [SUB_ID + i for i in range(burst)]
    api = ResumeApi()
    api.list_response = api.listed(*ids)
    async with CentrifugoServer() as server:
        client = _client(server, api, timing)
        subs = []
        for account in ids:
            subs.append(await client.subscribe_proto(_channel(account), decode=lambda data: data))
            await server.wait_subscribed(_channel(account))
        tokens = api.connection_tokens + api.token_calls
        started = asyncio.get_running_loop().time()
        for account in ids:
            await server.push(_channel(account), unsubscribe(_channel(account)))
        async with asyncio.timeout(30):
            for _ in range(burst):
                await server.subscribed.get()
        elapsed = asyncio.get_running_loop().time() - started
        assert all(sub.error is None for sub in subs)
        assert api.list_calls <= elapsed / timing.read_interval + 2
        assert api.list_calls < burst
        assert elapsed >= (burst - 1) * timing.attempt_spacing, "attempts must be paced"
        assert api.connection_tokens + api.token_calls - tokens == 2 * burst
        await client.aclose()


async def test_one_read_cannot_answer_a_later_decision() -> None:
    api = ResumeApi()
    release = asyncio.Event()
    started = asyncio.Event()

    class SlowRead(SubaccountAccess):
        async def _fetch_listed(self):
            api.list_calls += 1
            started.set()
            await release.wait()
            return set()

    async with CentrifugoServer() as server:
        client = _client(server, api)
        access = SlowRead(client, ResubscribeTiming(read_interval=0.05))
        first = asyncio.create_task(access._read())
        await started.wait()
        second = asyncio.create_task(access._read())
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
        assert api.list_calls == 2
        await client.aclose()


@pytest.mark.parametrize(
    "channel", ["private:auth:api-keys:root:proto", "public:spot:trades:1:proto"]
)
async def test_channels_no_access_governs_stop_without_requests(channel: str) -> None:
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        lists, tokens = api.list_calls, api.token_calls
        await server.push(channel, unsubscribe(channel))
        assert (await _ended(sub)).reason == "not_resubscribable"
        assert (api.list_calls, api.token_calls) == (lists, tokens)
        await client.aclose()


async def test_temporary_unsubscribe_code_reconnects_without_reading_the_list() -> None:
    channel = _channel()
    api = ResumeApi()
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        await server.push(channel, unsubscribe(channel, 2500, "insufficient state"))
        await server.wait_subscribed(channel)
        assert api.list_calls == 0
        assert sub.error is None
        await client.aclose()


async def test_listed_decimal_id_without_a_zero_digit_still_matches() -> None:
    # Such a decimal is also valid base58: it must read as the decimal the list reports.
    account = 2305843111111111111
    channel = _channel(account)
    api = ResumeApi()
    api.list_response = api.listed(account)
    async with CentrifugoServer() as server:
        client = _client(server, api)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        await server.push(channel, unsubscribe(channel))
        await server.wait_subscribed(channel)
        assert sub.error is None
        await client.aclose()


@pytest.mark.parametrize(
    ("barrier", "removed"),
    [("list", True), ("list", False), ("pacing", True), ("pacing", False)],
)
async def test_removal_while_deciding_stops_before_any_token(barrier: str, removed: bool) -> None:
    """A removal during the list or the pacing wait must win over the older answer.

    The removed false controls prove the same barriers still resume.
    """
    channel = _channel()
    updates = "private:auth:subaccounts:root:proto"
    api = ResumeApi()
    timing = FAST
    if barrier == "pacing":
        timing = ResubscribeTiming(
            max_attempts=3,
            initial_backoff=0.01,
            stable_after=3600,
            attempt_spacing=0.4,
            read_interval=0.001,
        )
    async with CentrifugoServer() as server:
        client = _client(server, api, timing)
        stream = await client.subscribe_proto(updates, decode=lambda data: data)
        await server.wait_subscribed(updates)
        sub = await client.subscribe_proto(channel, decode=lambda data: data)
        await server.wait_subscribed(channel)
        tokens = api.token_calls
        access = client._access
        occupied = 0.0
        if barrier == "list":
            api.list_gate = asyncio.Event()
        else:
            # Occupy the slot so the resume must wait for the next one.
            access._reserve_attempt()
            occupied = access._next_attempt_at

        await server.push(channel, unsubscribe(channel))
        async with asyncio.timeout(5):
            if barrier == "list":
                await api.list_arrived.wait()
            else:
                while access._next_attempt_at <= occupied:
                    await asyncio.sleep(0.001)
        assert api.token_calls == tokens, "no token before the barrier opens"

        update = (
            subaccounts_pb2.Subaccount(id=SUB_ID, removed=True)
            if removed
            else subaccounts_pb2.Subaccount(id=SUB_ID, role=subaccounts_pb2.VIEWER)
        )
        await server.push(updates, publication(update.SerializeToString()))
        async with asyncio.timeout(5):
            await anext(stream)
        if api.list_gate is not None:
            api.list_gate.set()

        if removed:
            assert (await _ended(sub)).reason == "access_removed"
            assert api.token_calls == tokens, "no token after the removal"
        else:
            await server.wait_subscribed(channel)
            assert api.token_calls == tokens + 1
            assert sub.error is None
        await client.aclose()


def test_subaccount_channel_id() -> None:
    public_id = format_id(SUB_ID)
    for channel in (
        f"private:ledger:balances:{public_id}",
        f"private:ledger:balances:{public_id}:proto",
        f"private:ledger:transfers:{public_id}:proto",
        f"private:spot:trades:{public_id}:proto",
        f"private:spot:triggers:events:{public_id}:proto",
        f"private:spot:triggers:{public_id}:proto",
        f"private:chain:lifecycle:flows:{public_id}:proto",
    ):
        assert subaccount_channel_id(channel) == SUB_ID, channel
    for channel in (
        f"private:auth:subaccounts:{public_id}:proto",
        f"private:spot:orders:{public_id}",
        "public:spot:trades:1:proto",
        "private:ledger:balances:",
        f"private:ledger:balances:{public_id}:other",
    ):
        assert subaccount_channel_id(channel) is None, channel
