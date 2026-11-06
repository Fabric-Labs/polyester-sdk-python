from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from websockets.asyncio.server import serve

from polyester import Polyester
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV
from polyester.catalogs import CatalogManager
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterRealtimeError, PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.privatews.v1 import private_ws_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.realtime import client as realtime_client
from polyester.realtime import private_orders
from polyester.realtime.client import (
    CENTRIFUGO_PROTOBUF_SUBPROTOCOL,
    AsyncRealtimeClient,
    AsyncSubscription,
)
from polyester.realtime.private_orders import PrivateOrderStream, private_ws_url
from polyester.services.internal_transfers import AsyncInternalTransfersService
from polyester.services.orderbook import AsyncOrderbookService
from polyester.services.orders import AsyncOrdersService
from polyester.services.withdraw import AsyncWithdrawService
from polyester.types.money import AssetAmount
from tests.hardening_support import make_test_credentials
from tests.unit.test_private_orders_stream import FakePrivateWsServer, Tokens
from tests.unit.test_request_builder_regressions import capture_transport


async def send_amount(transport, path, amount, scale):
    if path == "transfer":
        return await AsyncInternalTransfersService(transport, CatalogManager(), None).create(
            asset_id=7,
            quantity=amount,
            quantity_scale=scale,
            idempotency_key="amount-capture",
            destination_account_id=format_id(42),
        )
    service = AsyncWithdrawService(transport, None)
    kwargs = dict(
        asset_id=7,
        quantity=amount,
        idempotency_key="amount-capture",
        nonce=42,
        deadline_ts_sec=1_800_000_000,
    )
    if scale is not None:
        kwargs["amount_scale"] = scale
    if path == "wallet":
        kwargs["amount"] = kwargs.pop("quantity")
        return await service.create_wallet_trading_withdraw(
            **kwargs,
            action="to_funding",
            signer_wallet="0xlocal",
            payload_signature=b"capture",
        )
    if path == "prepare":
        return service.prepare_api_key_to_funding(**kwargs)
    if path == "external":
        return await service.create_to_external_chain(
            **kwargs,
            payload_signature=b"capture",
            destination_chain_id=1,
            destination_address="0xlocal",
        )
    return await service.create_to_funding(**kwargs, payload_signature=b"capture")


@pytest.mark.parametrize("path", ["transfer", "funding", "external", "prepare", "wallet"])
@pytest.mark.parametrize(
    ("scaled", "typed_scale", "argument_scale", "asset_id", "message"),
    [
        (1500000, None, None, 7, "scale"),
        (1500000, 6, 8, 7, "scale"),
        (1500000, 8, 6, 7, "scale"),
        (0, 6, 6, 7, "positive"),
        (1500000, 6, 6, 8, "asset_id"),
        (1, 19, 19, 7, "exact"),
    ],
)
async def test_ambiguous_or_invalid_amount_is_refused_before_dispatch(
    path,
    scaled,
    typed_scale,
    argument_scale,
    asset_id,
    message,
):
    amount = AssetAmount.from_scaled(scaled, scale=typed_scale, asset_id=asset_id)
    async with capture_transport() as (transport, requests):
        with pytest.raises(PolyesterValidationError, match=message):
            await send_amount(transport, path, amount, argument_scale)
        assert requests == []


@pytest.mark.parametrize("path", ["transfer", "funding", "external", "prepare", "wallet"])
@pytest.mark.parametrize(
    ("amount", "scale", "expected"),
    [
        (AssetAmount.from_scaled(1500000, scale=6, asset_id=7), None, 15 * 10**17),
        (AssetAmount.from_scaled(1500000, scale=6, asset_id=7), 6, 15 * 10**17),
        (AssetAmount.from_scaled(1500000, scale=8, asset_id=7), 8, 15 * 10**15),
        (AssetAmount.from_scaled(1500000, asset_id=7), 6, 15 * 10**17),
        ("1.5", None, 15 * 10**17),
        ("1.5", 6, 15 * 10**17),
        (AssetAmount.from_scaled(15 * 10**17, scale=18, asset_id=7), 18, 15 * 10**17),
    ],
)
async def test_declared_amount_scale_controls_round_trip(path, amount, scale, expected):
    async with capture_transport() as (transport, requests):
        result = await send_amount(transport, path, amount, scale)
        if path == "prepare":
            assert requests == []
            request = withdraw_pb2.CreateTradingWithdrawRequest.FromString(result.request_bytes)
            encoded = request.payload.amount_e18
        else:
            assert len(requests) == 1
            if path == "transfer":
                request = internal_transfer_pb2.CreateInternalTransferRequest.FromString(
                    requests[0].body
                )
                encoded = request.amount_e18
            else:
                request_type = (
                    withdraw_pb2.CreateWalletTradingWithdrawRequest
                    if path == "wallet"
                    else withdraw_pb2.CreateTradingWithdrawRequest
                )
                request = request_type.FromString(requests[0].body)
                encoded = request.payload.amount_e18
        assert (encoded.hi << 64) | encoded.lo == expected


@pytest.mark.parametrize(
    ("symbol", "bid", "ask", "coarse", "fine"),
    [
        ("DOGE-USDT", 71600000, 71700000, "0.1", "0.001"),
        ("LTC-USDT", 51750000000, 51760000000, "100", "0.1"),
        ("BNB-USDT", 650100000000, 650200000000, "100", "1"),
    ],
)
async def test_managed_book_coarse_buckets_snapshot_change_and_delta(
    monkeypatch,
    symbol,
    bid,
    ask,
    coarse,
    fine,
):
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": symbol, "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    queue = asyncio.Queue()
    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(
        return_value=AsyncSubscription(queue=queue, close=asyncio.Event())
    )
    fetch = AsyncMock(
        return_value=orderbook_pb2.GetOrderBookResponse(
            book_seq=1,
            available=True,
            bids=[orderbook_pb2.PriceLevel(price_ticks=bid, qty_scaled=3)],
            asks=[orderbook_pb2.PriceLevel(price_ticks=ask, qty_scaled=4)],
        )
    )
    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fetch)
    service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=realtime)
    sub = await service.create_subscription(symbol=symbol, bucket=coarse)
    try:
        for index, bucket in enumerate([coarse, fine, coarse, None]):
            # Every bucket change must produce a view, including a zero bid boundary.
            if index:
                sub.set_bucket(bucket)
            view = await asyncio.wait_for(anext(sub), 3)
            ticks = int(Decimal(bucket) * 10**9) if bucket else 1
            assert len(view.bids) == len(view.asks) == 1
            assert view.bids[0].price.ticks == bid // ticks * ticks
            assert view.asks[0].price.ticks == (ask + ticks - 1) // ticks * ticks
            assert view.bids[0].qty.scaled == 3
            assert view.asks[0].qty.scaled == 4
        sub.set_bucket(coarse)
        await asyncio.wait_for(anext(sub), 3)
        await queue.put(
            OrderBookDeltaUpdate(
                symbol_id=1,
                book_seq_start="2",
                book_seq_end="2",
                bids=[[str(bid), "5"]],
                asks=[[str(ask), "0"]],
            )
        )
        delta = await asyncio.wait_for(anext(sub), 3)
        assert delta.book_seq == "2"
        assert delta.bids[0].qty.scaled == 5
        assert delta.asks == []
        assert sub.last_error is None
        fetch.assert_awaited_once()
        realtime.subscribe_proto.assert_awaited_once()
    finally:
        await sub.aclose()


@pytest.mark.parametrize("mode", ["setup", "iteration", "success"])
def test_sync_subscription_delivers_setup_and_iteration_errors_once(monkeypatch, mode):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    attempted = threading.Event()
    delivered = threading.Event()
    closed = threading.Event()
    events, errors = [], []
    failure = ValueError(f"{mode}-proof")

    class Stream:
        async def __aiter__(self):
            if mode == "iteration":
                raise failure
            yield "event-proof"
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    async def subscribe(self, **kwargs):
        attempted.set()
        if mode == "setup":
            raise failure
        return Stream()

    def on_event(event):
        events.append(event)
        delivered.set()

    def on_error(error):
        errors.append(error)
        delivered.set()

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    handle = client.orders.subscribe_sync(on_event=on_event, on_error=on_error)
    try:
        assert attempted.wait(3), "subscription setup was never attempted"
        assert delivered.wait(3), "background failure was never delivered"
        handle.close()
        handle.close()
        assert events == (["event-proof"] if mode == "success" else [])
        assert errors == ([] if mode == "success" else [failure])
        assert closed.is_set() == (mode != "setup")
    finally:
        with contextlib.suppress(ValueError):
            handle.close()
        client.close()


def test_sync_private_subscription_missing_credentials_reports_once(monkeypatch):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    errors = []
    delivered = threading.Event()

    def report(error):
        errors.append(error)
        delivered.set()

    client = Polyester(hydrate_catalogs=False)
    try:
        handle = client.orders.subscribe_sync(
            account_id=format_id(42), on_event=lambda _: None, on_error=report
        )
        assert delivered.wait(3), "private subscription failure was never delivered"
        handle.close()
        handle.close()
        assert len(errors) == 1
        assert "credentials" in str(errors[0]).lower() or "api key" in str(errors[0]).lower()
    finally:
        client.close()


@pytest.mark.parametrize("bucket", [None, "0.001", "0.1"])
@pytest.mark.parametrize("side", ["bids", "asks"])
@pytest.mark.parametrize("quantity", [9, 0])
async def test_raw_zero_delta_never_becomes_a_display_bucket(monkeypatch, bucket, side, quantity):
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "DOGE-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    queue = asyncio.Queue()
    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(
        return_value=AsyncSubscription(queue=queue, close=asyncio.Event())
    )
    fetch = AsyncMock(
        return_value=orderbook_pb2.GetOrderBookResponse(
            book_seq=1,
            available=True,
            bids=[orderbook_pb2.PriceLevel(price_ticks=71600000, qty_scaled=3)],
            asks=[orderbook_pb2.PriceLevel(price_ticks=71700000, qty_scaled=4)],
        )
    )
    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fetch)
    service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=realtime)
    errors = []
    sub = await service.create_subscription(
        symbol="DOGE-USDT", bucket=bucket, on_error=errors.append
    )
    try:
        initial = await asyncio.wait_for(anext(sub), 3)
        assert initial.book_seq == "1"
        assert len(initial.bids) == len(initial.asks) == 1
        wire = orderbook_pb2.OrderBookDelta(symbol_id=1, book_seq_start=2, book_seq_end=2)
        # An omitted proto3 price is zero; positive quantity must never materialize it.
        getattr(wire, side).add(qty_scaled=quantity)
        decode = realtime.subscribe_proto.call_args.kwargs["decode"]
        delta = decode(wire.SerializeToString())
        assert list(getattr(delta, side)) == [("0", str(quantity))]
        await queue.put(delta)
        if quantity:
            with pytest.raises(StopAsyncIteration):
                await asyncio.wait_for(anext(sub), 3)
            assert sub.last_error is not None
            assert "invalid or missing price" in str(sub.last_error)
            assert len(errors) == 1
        else:
            view = await asyncio.wait_for(anext(sub), 3)
            assert view.book_seq == "2"
            assert view.bids == initial.bids
            assert view.asks == initial.asks
            assert sub.last_error is None
            assert errors == []
        fetch.assert_awaited_once()
        realtime.subscribe_proto.assert_awaited_once()
    finally:
        await sub.aclose()


@pytest.mark.parametrize("bucket", [None, "0.001", "0.1"])
async def test_raw_zero_bid_outside_the_requested_depth_still_fails_closed(monkeypatch, bucket):
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "DOGE-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    queue = asyncio.Queue()
    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(
        return_value=AsyncSubscription(queue=queue, close=asyncio.Event())
    )
    fetch = AsyncMock(
        return_value=orderbook_pb2.GetOrderBookResponse(
            book_seq=1,
            available=True,
            bids=[orderbook_pb2.PriceLevel(price_ticks=71600000, qty_scaled=3)],
            asks=[orderbook_pb2.PriceLevel(price_ticks=71700000, qty_scaled=4)],
        )
    )
    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fetch)
    service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=realtime)
    errors = []
    # A zero bid sorts last, so depth 1 alone would never render it.
    sub = await service.create_subscription(
        symbol="DOGE-USDT", depth=1, bucket=bucket, on_error=errors.append
    )
    try:
        initial = await asyncio.wait_for(anext(sub), 3)
        assert len(initial.bids) == 1
        await queue.put(
            OrderBookDeltaUpdate(
                symbol_id=1,
                book_seq_start="2",
                book_seq_end="2",
                bids=[["0", "9"]],
                asks=[],
            )
        )
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(sub), 3)
        assert "invalid or missing price" in str(sub.last_error)
        assert len(errors) == 1
    finally:
        await sub.aclose()


def assert_clean_shutdown(client):
    # Cleanup must not surface the setup error or leave the loop running.
    close_error = None
    try:
        client.close()
    except Exception as error:
        close_error = error
    thread_alive = client._loop_thread.is_alive()
    if thread_alive:
        client._loop.call_soon_threadsafe(client._loop.stop)
        client._loop_thread.join(3)
    assert close_error is None
    assert not thread_alive


def test_sync_setup_failure_without_callback_raises_once_and_does_not_register(monkeypatch):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    attempts = []
    failure = ValueError("setup-proof")

    async def subscribe(self, **kwargs):
        attempts.append("setup")
        raise failure

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    try:
        with pytest.raises(ValueError) as raised:
            client.orders.subscribe_sync(on_event=lambda _: pytest.fail("unexpected event"))
        assert raised.value is failure
        assert attempts == ["setup"]
        assert client._active_sync_subscriptions == []
    finally:
        assert_clean_shutdown(client)


def test_sync_missing_credentials_without_callback_raises_once_and_does_not_register(monkeypatch):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    client = Polyester(hydrate_catalogs=False)
    try:
        with pytest.raises(Exception, match="(?i)credentials|api key"):
            client.orders.subscribe_sync(
                account_id=format_id(42), on_event=lambda _: pytest.fail("unexpected event")
            )
        assert client._active_sync_subscriptions == []
    finally:
        assert_clean_shutdown(client)


def test_sync_without_callback_returns_a_live_handle_after_setup(monkeypatch):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    delivered = threading.Event()
    closed = threading.Event()
    events = []

    class Stream:
        async def __aiter__(self):
            yield "event-proof"
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    async def subscribe(self, **kwargs):
        return Stream()

    def on_event(event):
        events.append(event)
        delivered.set()

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    try:
        handle = client.orders.subscribe_sync(on_event=on_event)
        assert delivered.wait(3), "event was never delivered"
        assert events == ["event-proof"]
        assert client._active_sync_subscriptions == [handle]
        handle.close()
        assert closed.is_set()
    finally:
        assert_clean_shutdown(client)


def test_sync_setup_wait_ends_when_the_client_closes(monkeypatch):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    attempted = threading.Event()
    outcome = []

    async def subscribe(self, **kwargs):
        attempted.set()
        await asyncio.Event().wait()

    def call():
        try:
            client.orders.subscribe_sync(on_event=lambda _: pytest.fail("unexpected event"))
        except Exception as error:
            outcome.append(error)

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    caller = threading.Thread(target=call, daemon=True)
    caller.start()
    assert attempted.wait(3), "subscription setup was never attempted"
    assert_clean_shutdown(client)
    caller.join(5)
    assert not caller.is_alive(), "subscribe_sync kept waiting after the client closed"
    assert len(outcome) == 1
    assert isinstance(outcome[0], PolyesterRealtimeError)
    assert "closed during subscription setup" in str(outcome[0])
    assert client._active_sync_subscriptions == []


@pytest.mark.parametrize("nested_on_error", [None, lambda _: None])
def test_sync_subscribe_from_a_client_callback_is_refused(monkeypatch, nested_on_error):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    finished = threading.Event()
    outcome = []

    class Stream:
        async def __aiter__(self):
            yield "event-proof"
            await asyncio.Event().wait()

        async def aclose(self):
            pass

    async def subscribe(self, **kwargs):
        return Stream()

    def on_event(_):
        try:
            client.orders.subscribe_sync(on_event=lambda _: None, on_error=nested_on_error)
        except Exception as error:
            outcome.append(error)
        finally:
            finished.set()

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    try:
        handle = client.orders.subscribe_sync(on_event=on_event, on_error=outcome.append)
        assert finished.wait(5), "nested subscribe_sync blocked the client loop"
        assert len(outcome) == 1
        assert isinstance(outcome[0], PolyesterRealtimeError)
        assert "client callback" in str(outcome[0])
        assert client._active_sync_subscriptions == [handle]
    finally:
        client.close()


def test_sync_without_callback_waits_for_setup_longer_than_ten_seconds(monkeypatch):
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    ready = threading.Event()
    closed = threading.Event()

    class Stream:
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield "unreachable"

        async def aclose(self):
            closed.set()

    async def subscribe(self, **kwargs):
        await asyncio.sleep(10.05)
        ready.set()
        return Stream()

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    try:
        handle = client.orders.subscribe_sync(on_event=lambda _: pytest.fail("unexpected event"))
        assert ready.is_set(), "sync subscribe returned before setup completed"
        handle.close()
        assert closed.is_set()
    finally:
        client.close()
    assert not client._loop_thread.is_alive()


class HeartbeatOnlyPrivateServer:
    """Answers tokens and sends valid heartbeats, but never confirms a subscribe."""

    def __init__(self) -> None:
        self.server = FakePrivateWsServer()
        self.subscribes = []
        self.unsubscribes = []
        self.heartbeats = 0
        # Seconds before confirming, per account; an absent account is never confirmed.
        self.confirm_after = {}
        self._tasks = []

    async def __aenter__(self):
        await self.server.start()
        self._tasks.append(asyncio.create_task(self._serve()))
        return self

    async def __aexit__(self, *exc_info):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.server.aclose()

    async def _serve(self):
        while True:
            conn = await self.server.connections.get()
            self._tasks.append(asyncio.create_task(self._beat(conn)))
            self._tasks.append(asyncio.create_task(self._read(conn)))

    async def _beat(self, conn):
        with contextlib.suppress(Exception):
            while True:
                await conn.send(heartbeat=private_ws_pb2.Heartbeat(server_ts_ns=1))
                self.heartbeats += 1
                await asyncio.sleep(0.02)

    async def _read(self, conn):
        while True:
            msg = await conn.received.get()
            kind = msg.WhichOneof("op")
            if kind == "unsubscribe":
                self.unsubscribes.append(msg.unsubscribe)
            elif kind == "subscribe":
                self.subscribes.append(msg.subscribe)
                delay = self.confirm_after.get(msg.subscribe.account)
                if delay is not None:
                    confirm = self._confirm(conn, msg.subscribe, delay)
                    self._tasks.append(asyncio.create_task(confirm))

    async def _confirm(self, conn, request, delay):
        await asyncio.sleep(delay)
        with contextlib.suppress(Exception):
            await conn.send(
                f"s{request.account}",
                subscribed=private_ws_pb2.Subscribed(id=request.id, account=request.account),
            )


def private_sync_client(server):
    credentials = make_test_credentials()
    return Polyester(
        api_url=server.server.api_url,
        api_key_id=credentials.key_id,
        api_private_key=credentials.private_key,
        default_account_id=format_id(42),
        hydrate_catalogs=False,
    )


async def test_sync_setup_without_callback_times_out_when_heartbeats_never_confirm(monkeypatch):
    monkeypatch.setattr(private_orders, "SUBSCRIBE_ACK_TIMEOUT", 0.3)
    async with HeartbeatOnlyPrivateServer() as server:
        client = private_sync_client(server)
        try:
            with pytest.raises(PolyesterRealtimeError, match="not confirmed") as raised:
                await asyncio.wait_for(
                    asyncio.to_thread(
                        client.orders.subscribe_sync,
                        on_event=lambda _: pytest.fail("unexpected event"),
                    ),
                    5,
                )
            assert "timed out" in str(raised.value)
            assert len(server.subscribes) == 1, "subscribe was never sent"
            assert server.heartbeats > 3, "the connection was not kept alive by heartbeats"
            assert client._active_sync_subscriptions == []
            assert client._client.realtime._private_orders.active_accounts == 0
        finally:
            await asyncio.to_thread(assert_clean_shutdown, client)


async def test_sync_setup_with_callback_reports_an_unconfirmed_subscribe_once(monkeypatch):
    monkeypatch.setattr(private_orders, "SUBSCRIBE_ACK_TIMEOUT", 0.3)
    errors = []
    delivered = threading.Event()

    def report(error):
        errors.append(error)
        delivered.set()

    async with HeartbeatOnlyPrivateServer() as server:
        client = private_sync_client(server)
        try:
            handle = await asyncio.to_thread(
                client.orders.subscribe_sync,
                on_event=lambda _: pytest.fail("unexpected event"),
                on_error=report,
            )
            assert await asyncio.to_thread(delivered.wait, 5), "timeout was never reported"
            await asyncio.to_thread(handle.close)
            assert len(errors) == 1
            assert "not confirmed" in str(errors[0])
            assert len(server.subscribes) == 1
        finally:
            await asyncio.to_thread(assert_clean_shutdown, client)


async def test_late_confirmation_after_the_ack_timeout_is_unsubscribed(monkeypatch):
    monkeypatch.setattr(private_orders, "SUBSCRIBE_ACK_TIMEOUT", 0.2)
    tokens = Tokens()
    async with HeartbeatOnlyPrivateServer() as server:
        # A confirmed account keeps the shared connection open past the timeout.
        server.confirm_after = {43: 0, 42: 0.4}
        stream = PrivateOrderStream(
            url=private_ws_url(server.server.api_url),
            fetch_connect_token=tokens.connect,
            fetch_subscribe_token=tokens.subscribe,
        )
        healthy = await asyncio.wait_for(stream.subscribe(format_id(43)), 3)
        with pytest.raises(PolyesterRealtimeError, match="not confirmed"):
            await asyncio.wait_for(stream.subscribe(format_id(42)), 3)
        assert stream.active_accounts == 1
        for _ in range(100):
            if server.unsubscribes:
                break
            await asyncio.sleep(0.02)
        assert [item.sub for item in server.unsubscribes] == ["s42"]
        assert healthy.error is None
        await stream.aclose()


async def test_sync_setup_waits_past_ten_seconds_for_a_slow_confirmation(monkeypatch):
    async with HeartbeatOnlyPrivateServer() as server:
        server.confirm_after = {42: 10.05}
        client = private_sync_client(server)
        try:
            handle = await asyncio.to_thread(
                client.orders.subscribe_sync, on_event=lambda _: None
            )
            assert len(server.subscribes) == 1
            assert client._active_sync_subscriptions == [handle]
            await asyncio.to_thread(handle.close)
        finally:
            await asyncio.to_thread(assert_clean_shutdown, client)


async def test_public_handshake_times_out_when_only_pings_arrive(monkeypatch):
    monkeypatch.setattr(realtime_client, "CENTRIFUGO_REPLY_DEADLINE", 0.3)
    pings = []

    async def handler(ws):
        with contextlib.suppress(Exception):
            while True:
                await ws.send(b"\x00")
                pings.append(1)
                await asyncio.sleep(0.02)

    async with serve(
        handler, "127.0.0.1", 0, subprotocols=[CENTRIFUGO_PROTOBUF_SUBPROTOCOL]
    ) as server:
        port = server.sockets[0].getsockname()[1]
        realtime = AsyncRealtimeClient(f"ws://127.0.0.1:{port}")
        try:
            started = time.monotonic()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(
                    realtime.subscribe_proto(
                        "public:spot:market:trades:1:proto", decode=lambda raw: raw
                    ),
                    5,
                )
            # The outer limit raises the same type, so only the elapsed time proves the deadline.
            assert time.monotonic() - started < 3
            assert len(pings) > 3, "the handshake was not kept alive by pings"
        finally:
            await realtime.aclose()
