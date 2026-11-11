"""POLY-9127: methods that name a market wait for construction-time catalog hydration.

A local Connect server holds ``GetSpotConfig`` open until the test releases it, so
each call is made while hydration is still running. No timing is involved: the call
must still be pending once the server holds the request, and must reach the wire
with the catalog's ``symbol_id`` once hydration ends.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from google.protobuf import descriptor_pool, message_factory
from google.protobuf.message import Message

from polyester import AsyncPolyester, Polyester
from polyester.errors import (
    PolyesterCatalogHydrationError,
    PolyesterError,
    PolyesterValidationError,
)
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models import BatchReplaceItem, OrderId
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

SYMBOL = "DOGE-USDT"
SYMBOL_ID = 6


def _spot_config_body() -> bytes:
    spot = marketdata_pb2.GetSpotConfigResponse()
    for code, scale in (("DOGE", 8), ("USDT", 6)):
        asset = spot.assets.add()
        asset.asset = code
        asset.quantity_scale = scale
        asset.market_data_volume_scale = scale
    pair = spot.pairs.add()
    pair.symbol = SYMBOL
    pair.symbol_id = SYMBOL_ID
    pair.base_asset = "DOGE"
    pair.quote_asset = "USDT"
    pair.base_quantity_scale = 8
    pair.quote_quantity_scale = 6
    pair.reference_price_scale = 9
    return spot.SerializeToString()


Probe = Callable[[AsyncPolyester, str], Awaitable[Any]]


class _Reached(Exception):
    """A realtime subscribe was attempted: the call got past symbol resolution."""


class _Harness:
    """A client whose construction-time hydration waits for :meth:`release`."""

    def __init__(self, *, with_client: bool = True) -> None:
        self.with_client = with_client
        self.gate = asyncio.Event()
        self.spot_requested = asyncio.Event()
        # For a client on another thread, as the sync client is.
        self.spot_requested_sync = threading.Event()
        self.fail_spot = False
        # Hold the funding config too, behind the same gate.
        self.hold_funding = False
        self.reached = False
        self.symbol_ids: list[int] = []
        self.http: MockHttpServer | None = None
        self.client: AsyncPolyester | None = None

    async def __aenter__(self) -> _Harness:
        self.http = await MockHttpServer.spawn(self._handle)
        if not self.with_client:
            return self
        creds = make_test_credentials()
        self.client = AsyncPolyester(
            api_url=self.http.base_url,
            ws_url="ws://127.0.0.1:9/unused",
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            default_account_id=1,
            hydrate_catalogs=True,
            timeout=5.0,
        )
        realtime = self.client.realtime

        async def subscribe(channel: str, *args: Any, **kwargs: Any) -> Any:
            self._record_channel(channel)
            raise _Reached(channel)

        realtime.subscribe_proto = subscribe  # type: ignore[method-assign]
        realtime.subscribe_proto_batch = subscribe  # type: ignore[method-assign]
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.gate.set()
        if self.client is not None:
            await self.client.aclose()
        if self.http is not None:
            await self.http.aclose()

    def release(self, *, fail: bool = False) -> None:
        self.fail_spot = fail
        self.gate.set()

    def _record_channel(self, channel: str) -> None:
        self.reached = True
        for part in channel.split(":"):
            if part.isdigit():
                self.symbol_ids.append(int(part))

    async def _handle(self, req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/GetSpotConfig"):
            self.spot_requested.set()
            self.spot_requested_sync.set()
            await self.gate.wait()
            if self.fail_spot:
                return HttpScript.json(500, b'{"code":"internal","message":"spot down"}')
            return connect_proto_response(_spot_config_body())
        if req.path.endswith("/GetDepositWithdrawConfig"):
            if self.hold_funding:
                await self.gate.wait()
                if self.fail_spot:
                    return HttpScript.json(500, b'{"code":"internal","message":"funding down"}')
            return connect_proto_response(
                zipper_pb2.GetDepositWithdrawConfigResponse().SerializeToString()
            )
        self._record_request(req)
        # Not retried, so the call ends as soon as the stub answers.
        return HttpScript.json(400, b'{"code":"failed_precondition","message":"stub"}')

    def _record_request(self, req: ParsedRequest) -> None:
        service_name, _, method_name = req.path.strip("/").rpartition("/")
        method = descriptor_pool.Default().FindServiceByName(service_name)
        input_type = method.FindMethodByName(method_name).input_type
        request = message_factory.GetMessageClass(input_type)()
        request.ParseFromString(req.body)
        self.reached = True
        self.symbol_ids.extend(_symbol_ids(request))

    async def start(self, probe: Probe, symbol: str = SYMBOL) -> asyncio.Task[Any]:
        """Start ``probe`` once ``GetSpotConfig`` is held and let it run as far as it can."""
        assert self.client is not None
        client = self.client

        async def run() -> Any:
            return await probe(client, symbol)

        await self.spot_requested.wait()
        task = asyncio.create_task(run())
        # Every step the call can take without the held response runs here.
        for _ in range(50):
            await asyncio.sleep(0)
        return task


def _symbol_ids(message: Message) -> list[int]:
    """Every ``symbol_id`` set anywhere in ``message``, nested items included."""
    found: list[int] = []
    for field, value in message.ListFields():
        values = value if field.is_repeated else [value]
        for item in values:
            if field.message_type is not None:
                found.extend(_symbol_ids(item))
            elif field.name in ("symbol_id", "symbol_ids"):
                found.append(int(item))
    return found


def _market_overview_subscription(c: AsyncPolyester, s: str) -> Awaitable[Any]:
    return c.market_overview.create_subscription(symbols=[s])


# The overview channel carries every market; the subscription filters by symbol_id itself.
_FILTERED_LOCALLY = {"market_overview.create_subscription"}

_LIMIT_ORDER: dict[str, Any] = {
    "side": "buy",
    "order_type": "limit",
    "tif": "gtc",
    "qty": "1",
    "price": "0.1",
}

# Every public method that turns a display symbol into a symbol_id, or needs the
# pair's catalog scales, with the display symbol the issue was reported with.
PROBES: list[tuple[str, Probe]] = [
    (
        "orderbook.create_subscription",
        lambda c, s: c.orderbook.create_subscription(symbol=s, depth=10),
    ),
    ("orderbook.subscribe", lambda c, s: c.orderbook.subscribe(symbol=s, depth=10)),
    ("orderbook.get", lambda c, s: c.orderbook.get(symbol=s, depth=10)),
    ("market_data.get_trades", lambda c, s: c.market_data.get_trades(symbol=s)),
    ("market_data.get_candles", lambda c, s: c.market_data.get_candles(symbol=s)),
    (
        "market_data.get_candles_columns",
        lambda c, s: c.market_data.get_candles_columns(symbol=s),
    ),
    (
        "market_data.get_current_candle",
        lambda c, s: c.market_data.get_current_candle(symbol=s),
    ),
    ("market_data.subscribe_trades", lambda c, s: c.market_data.subscribe_trades(symbol=s)),
    (
        "market_data.subscribe_candles",
        lambda c, s: c.market_data.subscribe_candles(symbol=s),
    ),
    ("heatmap.get", lambda c, s: c.heatmap.get(symbol=s)),
    ("heatmap.subscribe_live", lambda c, s: c.heatmap.subscribe_live(symbol=s)),
    ("market_overview.list", lambda c, s: c.market_overview.list(symbols=[s])),
    (
        "market_overview.get_spot_volume_history",
        lambda c, s: c.market_overview.get_spot_volume_history(symbols=[s]),
    ),
    ("market_overview.create_subscription", _market_overview_subscription),
    ("trades.list", lambda c, s: c.trades.list(symbol=s)),
    ("orders.list_history", lambda c, s: c.orders.list_history(symbol=s)),
    ("orders.cancel", lambda c, s: c.orders.cancel(key=OrderId(1), symbol=s)),
    ("orders.cancel_all", lambda c, s: c.orders.cancel_all(symbol=s, dry_run=True)),
    (
        "orders.cancel_all_after",
        lambda c, s: c.orders.cancel_all_after(timeout_sec=10, symbol=s),
    ),
    ("orders.create", lambda c, s: c.orders.create(**_LIMIT_ORDER, symbol=s)),
    ("orders.preview", lambda c, s: c.orders.preview(**_LIMIT_ORDER, symbol=s)),
    (
        "orders.batch_create",
        lambda c, s: c.orders.batch_create(items=[{**_LIMIT_ORDER, "symbol": s}]),
    ),
    (
        "orders.modify",
        lambda c, s: c.orders.modify(key=OrderId(1), symbol=s, new_qty="1"),
    ),
    (
        "orders.batch_replace",
        lambda c, s: c.orders.batch_replace(
            symbol=s, items=[BatchReplaceItem(key=OrderId(1), new_qty="1")]
        ),
    ),
    (
        "triggers.create",
        lambda c, s: c.triggers.create(
            symbol=s, trigger_type="stop_loss", side="sell", qty="1", trigger_price="0.1"
        ),
    ),
    ("triggers.list", lambda c, s: c.triggers.list(symbol=s)),
    ("triggers.resume", lambda c, s: c.triggers.resume(trigger_id=1, symbol=s)),
    (
        "triggers.modify",
        lambda c, s: c.triggers.modify(trigger_id=1, symbol=s, max_slippage_bps=10),
    ),
]


def _assert_sent_to_server(name: str, exc: BaseException | None) -> None:
    """The call got past symbol resolution: the stub server or stream refused it."""
    assert isinstance(exc, (PolyesterError, _Reached)), f"{name} raised {exc!r}"
    assert not isinstance(exc, (PolyesterValidationError, PolyesterCatalogHydrationError)), (
        f"{name} refused the symbol: {exc!r}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "probe"), PROBES, ids=[name for name, _ in PROBES])
async def test_symbol_call_waits_for_in_flight_hydration(name: str, probe: Probe) -> None:
    async with _Harness() as harness:
        task = await harness.start(probe)
        assert not task.done(), (
            f"{name} ended while hydration was still running: "
            f"{task.exception() if not task.cancelled() else 'cancelled'!r}"
        )
        harness.release()
        done, _ = await asyncio.wait((task,), timeout=10)
        assert done, f"{name} did not end after hydration"
        _assert_sent_to_server(name, task.exception())
        assert harness.reached, f"{name} sent nothing"
        if name not in _FILTERED_LOCALLY:
            assert SYMBOL_ID in harness.symbol_ids, f"{name} sent {harness.symbol_ids}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "probe"), PROBES, ids=[name for name, _ in PROBES])
async def test_symbol_call_raises_typed_error_when_hydration_fails(name: str, probe: Probe) -> None:
    async with _Harness() as harness:
        task = await harness.start(probe)
        assert not task.done(), f"{name} ended while hydration was still running"
        harness.release(fail=True)
        with pytest.raises(
            PolyesterCatalogHydrationError, match="catalog hydration failed"
        ) as info:
            await asyncio.wait_for(task, 10)
        assert harness.client is not None
        assert info.value.__cause__ is harness.client.catalogs_last_error
        assert "spot down" in str(info.value)
        assert harness.symbol_ids == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "probe"), PROBES, ids=[name for name, _ in PROBES])
async def test_unknown_symbol_after_hydration_is_refused_as_unknown(
    name: str, probe: Probe
) -> None:
    async with _Harness() as harness:
        harness.release()
        assert harness.client is not None
        await harness.client.wait_for_catalogs()
        task = await harness.start(probe, "NOPE-USDT")
        with pytest.raises(PolyesterValidationError, match=r"Unknown symbol 'NOPE-USDT'"):
            await asyncio.wait_for(task, 10)
        assert harness.symbol_ids == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "probe",
    [
        lambda c, s: c.orderbook.get(symbol=s),
        lambda c, _s: c.wait_for_catalogs(),
        lambda c, _s: asyncio.wait_for(c.orderbook.get(symbol=SYMBOL), timeout=0),
    ],
    ids=["cancelled-call", "cancelled-wait_for_catalogs", "timed-out-call"],
)
async def test_caller_cancelled_while_waiting_does_not_cancel_hydration(probe: Probe) -> None:
    async with _Harness() as harness:
        task = await harness.start(probe)
        task.cancel()
        with pytest.raises((asyncio.CancelledError, TimeoutError)):
            await task
        harness.release()
        client = harness.client
        assert client is not None
        await client.wait_for_catalogs()
        assert client.catalogs.symbol_id_for_symbol(SYMBOL) == SYMBOL_ID
        with pytest.raises(PolyesterError, match="stub"):
            await client.orderbook.get(symbol=SYMBOL)
        assert SYMBOL_ID in harness.symbol_ids


# Reads that only label or scale their rows from the catalogs: they wait for
# hydration, and a failed one costs the labels, not the read.
LABELLED_READS: list[tuple[str, Probe]] = [
    ("market_overview.list", lambda c, _s: c.market_overview.list()),
    (
        "market_overview.get_spot_volume_history",
        lambda c, _s: c.market_overview.get_spot_volume_history(symbol_ids=[SYMBOL_ID]),
    ),
    ("market_overview.subscribe", lambda c, _s: c.market_overview.subscribe()),
    ("fees.get_spot_fee_rates", lambda c, _s: c.fees.get_spot_fee_rates()),
    # Orders and triggers are decoded at their pair's catalog quantity scales.
    ("orders.get", lambda c, _s: c.orders.get(key=OrderId(7))),
    ("orders.list_open", lambda c, _s: c.orders.list_open()),
    ("orders.list_history", lambda c, _s: c.orders.list_history()),
    ("triggers.get", lambda c, _s: c.triggers.get(trigger_id=7)),
    ("triggers.list", lambda c, _s: c.triggers.list()),
    ("trades.list", lambda c, _s: c.trades.list()),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True], ids=["loaded", "failed"])
@pytest.mark.parametrize(
    ("name", "probe"), LABELLED_READS, ids=[name for name, _ in LABELLED_READS]
)
async def test_labelled_read_waits_for_hydration_but_tolerates_failure(
    name: str, probe: Probe, fail: bool
) -> None:
    async with _Harness() as harness:
        task = await harness.start(probe)
        assert not task.done(), f"{name} read before the catalogs loaded"
        harness.release(fail=fail)
        done, _ = await asyncio.wait((task,), timeout=10)
        assert done, f"{name} did not end after hydration"
        _assert_sent_to_server(name, task.exception())
        assert harness.reached


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True], ids=["loaded", "failed"])
async def test_zipped_asset_supply_waits_for_the_scales_it_decodes_with(fail: bool) -> None:
    async with _Harness() as harness:
        harness.hold_funding = True
        task = await harness.start(lambda c, _s: c.zipper.subscribe_zipped_asset_supply())
        assert not task.done(), "the supply stream started before the funding config loaded"
        harness.release(fail=fail)
        # POLY-9228: the stream waits for the funding config, not the spot config.
        expected = PolyesterCatalogHydrationError if fail else _Reached
        with pytest.raises(expected, match="funding config" if fail else ""):
            await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_zipped_asset_supply_does_not_need_the_spot_config() -> None:
    async with _Harness() as harness:
        task = await harness.start(lambda c, _s: c.zipper.subscribe_zipped_asset_supply())
        harness.release(fail=True)
        with pytest.raises(_Reached):
            await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_hydration_disabled_keeps_todays_refusals() -> None:
    client = AsyncPolyester(api_url="http://127.0.0.1:9", hydrate_catalogs=False)
    try:
        with pytest.raises(
            PolyesterValidationError,
            match=r"symbol_id is required for orderbook subscriptions \('DOGE-USDT'\)",
        ):
            await client.orderbook.create_subscription(symbol=SYMBOL, depth=10)
        with pytest.raises(PolyesterValidationError, match=r"Unknown symbol 'DOGE-USDT'"):
            await client.orderbook.get(symbol=SYMBOL)
    finally:
        await client.aclose()


def test_sync_client_waits_for_hydration_and_refuses_waits_from_callbacks() -> None:
    server_loop = asyncio.new_event_loop()
    server_thread = threading.Thread(target=server_loop.run_forever, daemon=True)
    server_thread.start()
    harness = _Harness(with_client=False)

    def on_server(coro: Awaitable[Any]) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, server_loop).result(10)  # type: ignore[arg-type]

    on_server(harness.__aenter__())
    try:
        assert harness.http is not None
        built: dict[str, Any] = {}

        def build() -> None:
            try:
                built["client"] = Polyester(
                    api_url=harness.http.base_url,
                    ws_url="ws://127.0.0.1:9/unused",
                    hydrate_catalogs=True,
                    timeout=5.0,
                )
            except BaseException as exc:
                built["error"] = exc

        builder = threading.Thread(target=build)
        builder.start()
        assert harness.spot_requested_sync.wait(10)
        assert builder.is_alive(), "Polyester() returned before the catalogs loaded"
        server_loop.call_soon_threadsafe(harness.release)
        builder.join(10)
        assert "error" not in built, built.get("error")
        client: Polyester = built["client"]
        try:
            with pytest.raises(PolyesterError, match="stub"):
                client.orderbook.get(symbol=SYMBOL)
            assert SYMBOL_ID in harness.symbol_ids

            # A callback runs on the client loop: a sync call there is refused, not hung.
            outcome: dict[str, BaseException] = {}
            done = threading.Event()

            def callback() -> None:
                try:
                    client.orderbook.get(symbol=SYMBOL)
                except BaseException as exc:
                    outcome["error"] = exc
                finally:
                    done.set()

            client._loop.call_soon_threadsafe(callback)
            assert done.wait(10)
            assert isinstance(outcome.get("error"), PolyesterError)
            assert "client callback" in str(outcome["error"])
        finally:
            client.close()
    finally:
        on_server(harness.__aexit__(None, None, None))
        server_loop.call_soon_threadsafe(server_loop.stop)
        server_thread.join(5)


_MISSING_SCALE = (
    r"quantity scale for 'NOPE-USDT' is unavailable; "
    r"await client\.wait_for_catalogs\(\) before placing orders"
)


def _scale_first_calls(client: Any) -> list[tuple[str, Callable[[], Any]]]:
    return [
        (
            "orders.modify",
            lambda: client.orders.modify(key=OrderId(1), symbol="NOPE-USDT", new_qty="1"),
        ),
        (
            "triggers.create",
            lambda: client.triggers.create(
                symbol="NOPE-USDT",
                trigger_type="stop_loss",
                side="sell",
                qty="1",
                trigger_price="0.1",
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_hydration_disabled_keeps_missing_scale_refusals() -> None:
    # Without hydration these check the quantity scale before the symbol, as before.
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url="http://127.0.0.1:9",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        for name, call in _scale_first_calls(client):
            with pytest.raises(PolyesterValidationError, match=_MISSING_SCALE):
                await call()
            assert name
    finally:
        await client.aclose()


def test_sync_hydration_disabled_keeps_missing_scale_refusals() -> None:
    creds = make_test_credentials()
    client = Polyester(
        api_url="http://127.0.0.1:9",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        for name, call in _scale_first_calls(client):
            with pytest.raises(PolyesterValidationError, match=_MISSING_SCALE):
                call()
            assert name
    finally:
        client.close()
