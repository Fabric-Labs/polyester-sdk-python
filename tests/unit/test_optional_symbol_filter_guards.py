"""Blank market filters, trigger cancel-all request IDs, policy cap errors,
candle timeframes and cancel result timestamps.

A blank market name passed where a market filter is optional used to be
dropped and so read as "every market": the dead-man switch armed for every
market, and with ``include_triggers`` its expiry stopped every trigger on every
pair. Every such call now refuses it before anything is awaited or sent, as
``orders.cancel_all`` does; leaving the market out still means every market.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf import json_format
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester
from polyester._wire import map_connect_error
from polyester.codecs.decode.orders import (
    batch_cancel_from_proto,
    cancel_all_after_from_proto,
    cancel_all_from_proto,
)
from polyester.codecs.orders import cancel_all_after_to_proto
from polyester.codecs.triggers import cancel_all_triggers_to_proto
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterCatalogHydrationError,
    PolyesterValidationError,
)
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services._symbols import resolve_optional_symbol_id
from polyester.services.market_data import (
    _candle_timeframe,
    _resolve_candle_channel_timeframe,
)
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()
_BLANKS = ["", "   ", " \t"]


@asynccontextmanager
async def _client(answer: Callable[[ParsedRequest], HttpScript] | None = None):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        if answer is None:
            return HttpScript.json(500, "{}")
        return answer(req)

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


def _catalog_wait(outcome: str, waits: list[str]) -> Callable[[], Awaitable[None]]:
    """A catalog wait that records each call, then fails or never ends."""

    async def wait() -> None:
        waits.append(outcome)
        if outcome == "failed":
            raise PolyesterCatalogHydrationError("spot config unavailable")
        await asyncio.Event().wait()

    return wait


def _proto_reply(reply: Any) -> Callable[[ParsedRequest], HttpScript]:
    def answer(req: ParsedRequest) -> HttpScript:
        if req.body.lstrip().startswith(b"{"):
            return HttpScript.json(200, json_format.MessageToJson(reply))
        return connect_proto_response(reply.SerializeToString())

    return answer


def _parse(req: ParsedRequest, message: Any) -> Any:
    if req.body.lstrip().startswith(b"{"):
        json_format.Parse(req.body, message)
    else:
        message.ParseFromString(req.body)
    return message


# --- optional market filters ----------------------------------------------------------------------

_CALLS: dict[str, Callable[[AsyncPolyester, str], Awaitable[Any]]] = {
    "orders.cancel_all_after": lambda c, s: c.orders.cancel_all_after(timeout_sec=30, symbol=s),
    "orders.cancel_all_after include_triggers": lambda c, s: c.orders.cancel_all_after(
        timeout_sec=30, symbol=s, include_triggers=True
    ),
    "orders.list_history": lambda c, s: c.orders.list_history(symbol=s),
    "orders.list_history with symbol_id": lambda c, s: c.orders.list_history(symbol=s, symbol_id=1),
    "pnl.get": lambda c, s: c.pnl.get(window="days_7", symbol=s),
    "pnl.get with symbol_id": lambda c, s: c.pnl.get(window="days_7", symbol=s, symbol_id=1),
    "pnl.get_trading_statistics": lambda c, s: c.pnl.get_trading_statistics(
        window="days_7", symbol=s
    ),
    "alerts.list": lambda c, s: c.alerts.list(symbol=s),
    "triggers.list": lambda c, s: c.triggers.list(symbol=s),
    "triggers.resume": lambda c, s: c.triggers.resume(trigger_id=9, symbol=s),
    "triggers.modify": lambda c, s: c.triggers.modify(trigger_id=9, symbol=s, max_slippage_bps=50),
}

_SERVICES = ("orders", "pnl", "alerts", "triggers")


@pytest.mark.parametrize("catalogs", ["failed", "pending"])
@pytest.mark.parametrize("blank", _BLANKS, ids=repr)
@pytest.mark.parametrize("call", list(_CALLS), ids=str)
async def test_optional_market_filter_refuses_a_blank_symbol_before_sending(
    call: str, blank: str, catalogs: str
) -> None:
    waits: list[str] = []
    async with _client() as (client, requests):
        for name in _SERVICES:
            getattr(client, name)._wait_for_catalogs = _catalog_wait(catalogs, waits)
        with pytest.raises(PolyesterValidationError, match="must not be blank"):
            await asyncio.wait_for(_CALLS[call](client, blank), 5)
    assert waits == []
    assert requests == []


@pytest.mark.parametrize("symbol_id", [None, 1])
@pytest.mark.parametrize("blank", _BLANKS, ids=repr)
def test_resolve_optional_symbol_id_refuses_a_blank_symbol(blank: str, symbol_id) -> None:
    with pytest.raises(PolyesterValidationError, match="must not be blank"):
        resolve_optional_symbol_id(
            None, symbol=blank, symbol_id=symbol_id, label="orders.cancel_all_after symbol"
        )
    assert resolve_optional_symbol_id(None, symbol=None, label="filter") is None


async def test_cancel_all_after_without_a_symbol_still_arms_every_market() -> None:
    reply = orders_pb2.CancelAllAfterResponse(
        status=orders_pb2.CancelAllAfterResponse.ARMED, effective_timeout_sec=30
    )
    async with _client(_proto_reply(reply)) as (client, requests):
        await client.orders.cancel_all_after(timeout_sec=30)
        await client.orders.cancel_all_after(timeout_sec=30, include_triggers=True)
    sent = [_parse(req, orders_pb2.CancelAllAfterRequest()) for req in requests]
    assert [r.symbol_id for r in sent] == [0, 0]
    assert [r.include_triggers for r in sent] == [False, True]
    # The codec the call uses still encodes an omitted market as every market.
    proto = cancel_all_after_to_proto(
        sub_account_id=None,
        timeout_sec=30,
        symbol_id=None,
        side=None,
        request_id=None,
        include_triggers=True,
    )
    assert proto.symbol_id == 0


# --- triggers.cancel_all request ID ---------------------------------------------------------------


@pytest.mark.parametrize("request_id", ["", "   ", " abc ", "abc ", "\tabc"], ids=repr)
async def test_triggers_cancel_all_refuses_a_request_id_it_would_change(request_id: str) -> None:
    # Already correct: sent exactly as given or refused, never trimmed or
    # replaced with a new random key on every call.
    waits: list[str] = []
    async with _client() as (client, requests):
        client.triggers._wait_for_catalogs = _catalog_wait("pending", waits)
        with pytest.raises(PolyesterValidationError, match="request_id"):
            await asyncio.wait_for(
                client.triggers.cancel_all(dry_run=True, request_id=request_id), 5
            )
    assert requests == []
    with pytest.raises(PolyesterValidationError, match="request_id"):
        cancel_all_triggers_to_proto(dry_run=True, request_id=request_id)


async def test_triggers_cancel_all_sends_a_request_id_as_given_and_generates_one_when_omitted() -> (
    None
):
    reply = triggers_pb2.CancelAllTriggersResponse(
        status=triggers_pb2.CancelAllTriggersResponse.DRY_RUN, matched_triggers=1
    )
    async with _client(_proto_reply(reply)) as (client, requests):
        for _ in range(2):
            await client.triggers.cancel_all(dry_run=True, request_id="abc")
            await client.triggers.cancel_all(dry_run=True)
    keys = [_parse(req, triggers_pb2.CancelAllTriggersRequest()).request_id for req in requests]
    assert keys[0] == keys[2] == "abc"
    assert keys[1] != keys[3]
    assert keys[1].startswith("trg-cancel-all-")


# --- sub-account policy refusals ------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [orders_pb2.ERROR_CODE_POLICY_MAX_NOTIONAL, orders_pb2.ERROR_CODE_POLICY_MAX_OPEN_ORDERS],
)
def test_policy_cap_refusal_is_an_api_error_that_keeps_its_code(code: int) -> None:
    # invalid_argument (HTTP 400): the order was too large or one too many,
    # not a credentials problem.
    err = map_connect_error(
        ConnectError(
            Code.INVALID_ARGUMENT,
            "Sub-account policy max order notional exceeded",
            details=[orders_pb2.ErrorDetail(code=code)],
        )
    )
    assert not isinstance(err, PolyesterAuthError)
    assert type(err) is PolyesterApiError
    assert err.code == orders_pb2.ErrorCode.Name(code)


@pytest.mark.parametrize("status", [Code.PERMISSION_DENIED, Code.UNAUTHENTICATED])
@pytest.mark.parametrize(
    "code",
    [
        orders_pb2.ERROR_CODE_POLICY_SPOT_TRADE_DENY,
        orders_pb2.ERROR_CODE_POLICY_MARKET_DENY,
        orders_pb2.ERROR_CODE_POLICY_SPOT_READ_DENY,
        orders_pb2.ERROR_CODE_POLICY_TRADING_HALTED,
    ],
)
def test_policy_permission_refusal_stays_an_auth_error(code: int, status: Code) -> None:
    err = map_connect_error(
        ConnectError(status, "denied", details=[orders_pb2.ErrorDetail(code=code)])
    )
    assert type(err) is PolyesterAuthError
    assert err.code == orders_pb2.ErrorCode.Name(code)


# --- candle timeframes ----------------------------------------------------------------------------

# Every accepted timeframe, exactly as written, with its enum and channel
# label; the Go and Rust SDKs accept the same set.
ACCEPTED_TIMEFRAMES = {
    "1s": ("SEC_1", "1s"),
    "1m": ("MIN_1", "1m"),
    "3m": ("MIN_3", "3m"),
    "5m": ("MIN_5", "5m"),
    "15m": ("MIN_15", "15m"),
    "30m": ("MIN_30", "30m"),
    "1h": ("HOUR_1", "1h"),
    "2h": ("HOUR_2", "2h"),
    "4h": ("HOUR_4", "4h"),
    "6h": ("HOUR_6", "6h"),
    "8h": ("HOUR_8", "8h"),
    "12h": ("HOUR_12", "12h"),
    "1d": ("DAY_1", "1d"),
    "3d": ("DAY_3", "3d"),
    "1w": ("WEEK_1", "1w"),
    "1mo": ("MONTH_1", "1mo"),
}

REFUSED_TIMEFRAMES = [
    "1M",
    "1H",
    "1D",
    "1S",
    "1W",
    "1MO",
    "1Mo",
    "15M",
    "min_1",
    "min1",
    "MIN1",
    "Min_1",
    "month_1",
    "month1",
    "sec1",
    "TIMEFRAME_UNSPECIFIED",
    "BUY",
    "SELL",
    "buy",
    "sell",
    " 1m",
    "1m ",
    "",
    "1",
    "60",
    "1min",
    "1month",
    "UNSPECIFIED",
    None,
    1,
]


@pytest.mark.parametrize("label", list(ACCEPTED_TIMEFRAMES))
def test_candle_timeframes_accept_labels_and_enum_names(label: str) -> None:
    enum_name, channel = ACCEPTED_TIMEFRAMES[label]
    for spelling in (label, enum_name):
        assert _candle_timeframe(spelling) == marketdata_pb2.Timeframe.Value(enum_name)
        assert _resolve_candle_channel_timeframe(spelling) == channel


@pytest.mark.parametrize("timeframe", REFUSED_TIMEFRAMES, ids=repr)
def test_candle_timeframes_refuse_everything_else(timeframe: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="Unknown candle timeframe"):
        _candle_timeframe(timeframe)
    with pytest.raises(PolyesterValidationError, match="Unknown candle timeframe"):
        _resolve_candle_channel_timeframe(timeframe)


_CANDLE_CALLS: dict[str, Callable[[AsyncPolyester, str], Awaitable[Any]]] = {
    "get_candles": lambda c, tf: c.market_data.get_candles(symbol="BTC-USDT", timeframe=tf),
    "get_candles_columns": lambda c, tf: c.market_data.get_candles_columns(
        symbol="BTC-USDT", timeframe=tf
    ),
    "get_index_price_candles": lambda c, tf: c.market_data.get_index_price_candles(
        symbol="BTC-USDT", timeframe=tf
    ),
    "get_current_candle": lambda c, tf: c.market_data.get_current_candle(
        symbol="BTC-USDT", timeframe=tf
    ),
    "subscribe_candles": lambda c, tf: c.market_data.subscribe_candles(
        symbol="BTC-USDT", timeframe=tf
    ),
}


@pytest.mark.parametrize("timeframe", ["1M", "buy", "sell", "min_1", "TIMEFRAME_UNSPECIFIED"])
@pytest.mark.parametrize("call", list(_CANDLE_CALLS))
async def test_candle_calls_refuse_an_unknown_timeframe_before_sending(
    call: str, timeframe: str
) -> None:
    waits: list[str] = []
    async with _client() as (client, requests):
        client.market_data._wait_for_catalogs = _catalog_wait("pending", waits)
        with pytest.raises(PolyesterValidationError, match="Unknown candle timeframe"):
            await asyncio.wait_for(_CANDLE_CALLS[call](client, timeframe), 5)
    assert waits == []
    assert requests == []


# --- cancel result timestamps ---------------------------------------------------------------------

_TS_NS = 1_700_000_000_123_456_789
_TS = Timestamp(seconds=1_700_000_000, nanos=5)


@pytest.mark.parametrize(
    ("ts_ns", "ts", "listing", "want"),
    [
        (_TS_NS, None, orders_pb2.CancelAllOrdersResponse.INCLUDED, _TS_NS),
        (_TS_NS, _TS, orders_pb2.CancelAllOrdersResponse.INCLUDED, _TS_NS),
        (0, _TS, orders_pb2.CancelAllOrdersResponse.INCLUDED, 1_700_000_000_000_000_005),
        # A retry with the same request_id: the server's original time.
        (_TS_NS, _TS, orders_pb2.CancelAllOrdersResponse.NOT_RETAINED_READ_OPEN_ORDERS, _TS_NS),
        (0, None, orders_pb2.CancelAllOrdersResponse.INCLUDED, None),
    ],
    ids=["ts_ns", "ts_ns and ts", "ts only", "retry", "absent"],
)
def test_cancel_results_read_the_server_timestamp(ts_ns, ts, listing, want) -> None:
    cancel_all = cancel_all_from_proto(
        orders_pb2.CancelAllOrdersResponse(
            status=orders_pb2.CancelAllOrdersResponse.SUBMITTED,
            matched_orders=1,
            submitted_cancels=1,
            listing_status=listing,
            ts_ns=ts_ns,
            ts=ts,
        )
    )
    assert cancel_all.ts_ns == want
    after = cancel_all_after_from_proto(
        orders_pb2.CancelAllAfterResponse(
            status=orders_pb2.CancelAllAfterResponse.ARMED,
            effective_timeout_sec=30,
            expires_at_ts_ns=42,
            ts_ns=ts_ns,
            ts=ts,
        )
    )
    assert after.ts_ns == want
    assert after.expires_at_ts_ns == "42"
    batch = batch_cancel_from_proto(orders_pb2.BatchCancelOrdersResponse(ts_ns=ts_ns, ts=ts))
    assert batch.ts_ns == want


async def test_cancel_all_returns_the_server_timestamp() -> None:
    reply = orders_pb2.CancelAllOrdersResponse(
        status=orders_pb2.CancelAllOrdersResponse.DRY_RUN, ts_ns=_TS_NS
    )
    async with _client(_proto_reply(reply)) as (client, _):
        result = await client.orders.cancel_all(dry_run=True, request_id="all-1")
    assert result.ts_ns == _TS_NS
