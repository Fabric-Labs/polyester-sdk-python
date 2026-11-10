"""POLY-9127: methods that name a market wait for construction-time catalog hydration.

A local Connect server holds ``GetSpotConfig`` open until the test releases it, so
each call is made while hydration is still running. No timing is involved: the call
must still be pending once the server holds the request, and must reach the wire
with the catalog's ``symbol_id`` once hydration ends.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from google.protobuf import descriptor_pool, message_factory

from polyester import AsyncPolyester, errors
from polyester.errors import PolyesterError, PolyesterValidationError
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models import OrderId
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


def _hydration_error() -> type[Exception]:
    # Looked up at run time so that, before the fix, the tests fail on behaviour.
    return getattr(errors, "PolyesterCatalogHydrationError")  # noqa: B009


class _Reached(Exception):
    """A realtime subscribe was attempted: the call got past symbol resolution."""


class _Harness:
    """A client whose construction-time hydration waits for :meth:`release`."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.spot_requested = asyncio.Event()
        self.fail_spot = False
        self.symbol_ids: list[int] = []
        self.http: MockHttpServer | None = None
        self.client: AsyncPolyester | None = None

    async def __aenter__(self) -> _Harness:
        self.http = await MockHttpServer.spawn(self._handle)
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
        for part in channel.split(":"):
            if part.isdigit():
                self.symbol_ids.append(int(part))

    async def _handle(self, req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/GetSpotConfig"):
            self.spot_requested.set()
            await self.gate.wait()
            if self.fail_spot:
                return HttpScript.json(500, b'{"code":"internal","message":"spot down"}')
            return connect_proto_response(_spot_config_body())
        if req.path.endswith("/GetDepositWithdrawConfig"):
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
        for name in ("symbol_id", "symbol_ids"):
            if name not in input_type.fields_by_name:
                continue
            self.symbol_ids.extend(_ids(getattr(request, name)))

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


def _ids(value: Any) -> list[int]:
    if isinstance(value, int):
        return [value] if value else []
    return [int(item) for item in value]


def _market_overview_subscription(c: AsyncPolyester, s: str) -> Awaitable[Any]:
    return c.market_overview.create_subscription(symbols=[s])


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
    ("orders.cancel_all", lambda c, s: c.orders.cancel_all(symbol=s)),
    (
        "orders.cancel_all_after",
        lambda c, s: c.orders.cancel_all_after(timeout_sec=10, symbol=s),
    ),
    ("orders.create", lambda c, s: c.orders.create(**_LIMIT_ORDER, symbol=s)),
    ("orders.preview_order", lambda c, s: c.orders.preview_order(**_LIMIT_ORDER, symbol=s)),
    (
        "orders.batch_create",
        lambda c, s: c.orders.batch_create(items=[{**_LIMIT_ORDER, "symbol": s}]),
    ),
    (
        "orders.modify",
        lambda c, s: c.orders.modify(key=OrderId(1), symbol=s, new_qty="1"),
    ),
    ("triggers.list", lambda c, s: c.triggers.list(symbol=s)),
    ("triggers.resume", lambda c, s: c.triggers.resume(trigger_id=1, symbol=s)),
    ("triggers.modify", lambda c, s: c.triggers.modify(trigger_id=1, symbol=s)),
]


def _assert_sent_to_server(name: str, exc: BaseException | None) -> None:
    """The call got past symbol resolution: the stub server or stream refused it."""
    assert isinstance(exc, (PolyesterError, _Reached)), f"{name} raised {exc!r}"
    assert not isinstance(exc, (PolyesterValidationError, _hydration_error())), (
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
        assert SYMBOL_ID in harness.symbol_ids, f"{name} sent {harness.symbol_ids}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "probe"), PROBES, ids=[name for name, _ in PROBES])
async def test_symbol_call_raises_typed_error_when_hydration_fails(name: str, probe: Probe) -> None:
    async with _Harness() as harness:
        task = await harness.start(probe)
        assert not task.done(), f"{name} ended while hydration was still running"
        harness.release(fail=True)
        with pytest.raises(_hydration_error(), match="catalog hydration failed") as info:
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
async def test_caller_cancelled_while_waiting_does_not_cancel_hydration() -> None:
    async with _Harness() as harness:
        task = await harness.start(lambda c, s: c.orderbook.get(symbol=s))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        harness.release()
        client = harness.client
        assert client is not None
        await client.wait_for_catalogs()
        assert client.catalogs.symbol_id_for_symbol(SYMBOL) == SYMBOL_ID


@pytest.mark.asyncio
async def test_market_overview_list_without_symbols_waits_but_tolerates_failure() -> None:
    async with _Harness() as harness:
        task = await harness.start(lambda c, _s: c.market_overview.list())
        assert not task.done(), "market_overview.list decoded rows before the catalog loaded"
        harness.release(fail=True)
        # A failed catalog only costs the display enrichment; the read itself goes out.
        done, _ = await asyncio.wait((task,), timeout=10)
        assert done
        _assert_sent_to_server("market_overview.list", task.exception())


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
