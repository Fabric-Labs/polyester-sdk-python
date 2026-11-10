"""POLY-9238: a method given both ``symbol`` and ``symbol_id`` must not let one win.

``orders.list_history(symbol="LTC-USDT", symbol_id=1)`` sent ``symbol_id=[1]`` and
returned BTC-USDT history under the LTC-USDT label; so did an unknown name paired with
ID 1. Every method that takes both selectors now resolves them through the shared
resolver ``trades.list`` uses, which refuses the conflict before anything is sent.

A local Connect server answers in the wire format the client speaks, so each case runs
in binary and JSON, and records every ``symbol_id`` a request or a realtime channel
carries. The catalog maps BTC-USDT to 1 and LTC-USDT to 8.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

import pytest
from google.protobuf import descriptor_pool, json_format, message_factory
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.errors import PolyesterError, PolyesterValidationError
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

BTC, BTC_ID = "BTC-USDT", 1
LTC, LTC_ID = "LTC-USDT", 8

WireFormat = Literal["binary", "json"]


def _spot_config() -> marketdata_pb2.GetSpotConfigResponse:
    spot = marketdata_pb2.GetSpotConfigResponse()
    for code, scale in (("BTC", 8), ("LTC", 8), ("USDT", 6)):
        asset = spot.assets.add()
        asset.asset = code
        asset.quantity_scale = scale
        asset.market_data_volume_scale = scale
    for symbol, symbol_id, base in ((BTC, BTC_ID, "BTC"), (LTC, LTC_ID, "LTC")):
        pair = spot.pairs.add()
        pair.symbol = symbol
        pair.symbol_id = symbol_id
        pair.base_asset = base
        pair.quote_asset = "USDT"
        pair.base_quantity_scale = 8
        pair.quote_quantity_scale = 6
        pair.reference_price_scale = 9
    return spot


def _answer(req: ParsedRequest, message: Message) -> HttpScript:
    if "json" in req.headers.get("content-type", ""):
        return HttpScript.raw(
            200,
            headers=[("Content-Type", "application/json")],
            body=json_format.MessageToJson(message).encode(),
        )
    return HttpScript.raw(
        200, headers=[("Content-Type", "application/proto")], body=message.SerializeToString()
    )


class _Reached(Exception):
    """A realtime subscribe was attempted: the call got past symbol resolution."""


class _Harness:
    def __init__(self, wire_format: WireFormat) -> None:
        self.wire_format = wire_format
        self.sent: list[int] = []
        self.reached = False
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
            wire_format=self.wire_format,
            timeout=5.0,
        )

        async def subscribe(channel: str, *args: Any, **kwargs: Any) -> Any:
            self.reached = True
            # The market is the last number of a channel (after a depth tier, if any).
            self.sent.append([int(part) for part in channel.split(":") if part.isdigit()][-1])
            raise _Reached(channel)

        realtime = self.client.realtime
        realtime.subscribe_proto = subscribe  # type: ignore[method-assign]
        realtime.subscribe_proto_batch = subscribe  # type: ignore[method-assign]
        await self.client.wait_for_catalogs()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self.client is not None:
            await self.client.aclose()
        if self.http is not None:
            await self.http.aclose()

    async def _handle(self, req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/GetSpotConfig"):
            return _answer(req, _spot_config())
        if req.path.endswith("/GetDepositWithdrawConfig"):
            return _answer(req, zipper_pb2.GetDepositWithdrawConfigResponse())
        service_name, _, method_name = req.path.strip("/").rpartition("/")
        service = descriptor_pool.Default().FindServiceByName(service_name)
        input_type = service.FindMethodByName(method_name).input_type
        request = message_factory.GetMessageClass(input_type)()
        if "json" in req.headers.get("content-type", ""):
            json_format.Parse(req.body, request, ignore_unknown_fields=True)
        else:
            request.ParseFromString(req.body)
        self.reached = True
        self.sent.extend(_symbol_ids(request))
        # Refused without retry, so the call ends as soon as the stub answers.
        return HttpScript.json(400, b'{"code":"failed_precondition","message":"stub"}')


def _symbol_ids(message: Message) -> list[int]:
    found: list[int] = []
    for field, value in message.ListFields():
        values = value if field.is_repeated else [value]
        for item in values:
            if field.message_type is not None:
                found.extend(_symbol_ids(item))
            elif field.name in ("symbol_id", "symbol_ids"):
                found.append(int(item))
    return found


Call = Callable[[AsyncPolyester, dict[str, Any]], Awaitable[Any]]

# Every public method that takes both ``symbol`` and ``symbol_id``.
METHODS: list[tuple[str, Call]] = [
    ("orders.list_history", lambda c, s: c.orders.list_history(limit=3, **s)),
    ("trades.list", lambda c, s: c.trades.list(limit=3, **s)),
    ("market_data.get_trades", lambda c, s: c.market_data.get_trades(**s)),
    ("market_data.get_candles", lambda c, s: c.market_data.get_candles(**s)),
    ("market_data.get_candles_columns", lambda c, s: c.market_data.get_candles_columns(**s)),
    ("market_data.get_current_candle", lambda c, s: c.market_data.get_current_candle(**s)),
    ("market_data.subscribe_candles", lambda c, s: c.market_data.subscribe_candles(**s)),
    ("heatmap.get", lambda c, s: c.heatmap.get(**s)),
    ("heatmap.subscribe_live", lambda c, s: c.heatmap.subscribe_live(**s)),
    (
        "orderbook.create_subscription",
        lambda c, s: c.orderbook.create_subscription(depth=10, **s),
    ),
    ("orderbook.subscribe", lambda c, s: c.orderbook.subscribe(depth=10, **s)),
    ("triggers.modify", lambda c, s: c.triggers.modify(trigger_id=1, max_slippage_bps=10, **s)),
    ("triggers.resume", lambda c, s: c.triggers.resume(trigger_id=1, **s)),
]
_IDS = [name for name, _ in METHODS]
# A name is required here, so these have no ID-only form.
_NAME_REQUIRED = {"orderbook.create_subscription", "orderbook.subscribe"}

CONFLICTS = [
    pytest.param({"symbol": LTC, "symbol_id": BTC_ID}, id="other-market-name"),
    pytest.param({"symbol": "NOPE-USDT", "symbol_id": BTC_ID}, id="unknown-name"),
]


async def _sent_by(harness: _Harness, call: Call, selectors: dict[str, Any]) -> list[int]:
    assert harness.client is not None
    try:
        await call(harness.client, selectors)
    except (_Reached, PolyesterError) as exc:
        assert not isinstance(exc, PolyesterValidationError), f"refused {selectors}: {exc!r}"
    assert harness.reached, f"nothing was sent for {selectors}"
    return harness.sent


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["binary", "json"])
@pytest.mark.parametrize("selectors", CONFLICTS)
@pytest.mark.parametrize(("name", "call"), METHODS, ids=_IDS)
async def test_conflicting_selectors_are_refused_before_sending(
    name: str, call: Call, selectors: dict[str, Any], wire_format: WireFormat
) -> None:
    async with _Harness(wire_format) as harness:
        assert harness.client is not None
        with pytest.raises(PolyesterValidationError, match="symbol mismatch") as info:
            await call(harness.client, selectors)
        assert f"does not match symbol_id {BTC_ID} ({BTC})" in str(info.value)
        assert harness.sent == [], f"{name} sent {harness.sent}"
        assert not harness.reached


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["binary", "json"])
async def test_list_history_refuses_conflicts_as_trades_list_does(
    wire_format: WireFormat,
) -> None:
    async with _Harness(wire_format) as harness:
        client = harness.client
        assert client is not None
        for selectors in (
            {"symbol": LTC, "symbol_id": BTC_ID},
            {"symbol": "NOPE-USDT", "symbol_id": 1},
        ):
            with pytest.raises(PolyesterValidationError) as trades_error:
                await client.trades.list(**selectors)
            with pytest.raises(PolyesterValidationError) as history_error:
                await client.orders.list_history(**selectors)
            assert str(history_error.value) == str(trades_error.value).replace(
                "trades.list", "orders.list_history"
            )
        assert harness.sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize("wire_format", ["binary", "json"])
@pytest.mark.parametrize(
    ("selectors", "expected"),
    [
        pytest.param({"symbol": LTC, "symbol_id": LTC_ID}, LTC_ID, id="matching"),
        pytest.param({"symbol": LTC}, LTC_ID, id="name-only"),
        pytest.param({"symbol_id": BTC_ID}, BTC_ID, id="id-only"),
    ],
)
@pytest.mark.parametrize(("name", "call"), METHODS, ids=_IDS)
async def test_matching_and_single_selectors_still_select_their_market(
    name: str,
    call: Call,
    selectors: dict[str, Any],
    expected: int,
    wire_format: WireFormat,
) -> None:
    if name in _NAME_REQUIRED and "symbol" not in selectors:
        selectors = {**selectors, "symbol": BTC}
    async with _Harness(wire_format) as harness:
        sent = await _sent_by(harness, call, selectors)
        assert sent and set(sent) == {expected}, f"{name} sent {sent}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "call"), METHODS, ids=_IDS)
async def test_unknown_name_alone_is_refused_as_unknown(name: str, call: Call) -> None:
    async with _Harness("binary") as harness:
        assert harness.client is not None
        with pytest.raises(PolyesterValidationError, match=r"Unknown symbol 'NOPE-USDT'"):
            await call(harness.client, {"symbol": "NOPE-USDT"})
        assert harness.sent == []
