"""Public contract 74b89c5: the balance stream's ``BalanceUpdate`` and the
Trading position of ``GetBalances``, profit and loss, cancel-all for triggers,
the columnar candles' closed flag (see test_candle_is_closed.py), the market
overview's live price band and strategy bot keys."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from google.protobuf import json_format

from polyester import AsyncPolyester
from polyester.auth import ApiKeyCredentials
from polyester.codecs.decode.api_keys import api_key_from_proto
from polyester.codecs.decode.market_overview import market_overview_entry_from_proto
from polyester.codecs.decode.pnl import profit_and_loss_from_proto
from polyester.codecs.decode.transfers import ledger_transfer_from_proto
from polyester.codecs.decode.triggers import cancel_all_triggers_from_proto
from polyester.codecs.scalars import format_id
from polyester.codecs.triggers import cancel_all_triggers_to_proto
from polyester.errors import (
    PolyesterResponseContractError,
    PolyesterServerError,
    PolyesterValidationError,
)
from polyester.gen.auth.v1 import api_keys_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.v1 import catalog_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.pnl.v1 import pnl_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import AssetBalance
from polyester.realtime.client import AsyncRealtimeClient
from polyester.realtime.resubscribe import SubaccountAccess
from polyester.services import _retry
from polyester.services.balances import AsyncBalancesService
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)
from tests.unit.test_server_unsubscribe import (
    FAST,
    SUB_ID,
    CentrifugoServer,
    ResumeApi,
    publication,
    unsubscribe,
)

_CREDS = make_test_credentials()

Answer = Callable[[ParsedRequest], HttpScript]

_UNAVAILABLE = HttpScript.json(503, {"code": "unavailable", "message": "catching up"})


@asynccontextmanager
async def _client(answer: Answer, *, wire_format: str = "binary"):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return answer(req)

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
        wire_format=wire_format,  # type: ignore[arg-type]
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


def _reply(message, req: ParsedRequest) -> HttpScript:
    """The reply in the wire format the request used."""
    if req.body.lstrip().startswith(b"{"):
        return HttpScript.json(200, json_format.MessageToJson(message))
    return connect_proto_response(message.SerializeToString())


def _request(req: ParsedRequest, message_type):
    message = message_type()
    if req.body.lstrip().startswith(b"{"):
        json_format.Parse(req.body, message)
    else:
        message.ParseFromString(req.body)
    return message


@pytest.fixture
def no_sleep(monkeypatch):
    async def instant(_delay: float) -> None:
        return None

    monkeypatch.setattr(_retry, "_sleep", instant)


# --- GetBalances: the Trading position -------------------------------------------------------

_EPOCH = 4_294_967_303
_SEQUENCE = 42
_APPLIED_NS = 1_767_225_600_123_456_789
_E18 = 10**18


def _u128(value: int) -> u128_pb2.U128:
    return u128_pb2.U128(hi=value >> 64, lo=value & (2**64 - 1))


def _balances_reply() -> ledger_read_pb2.GetBalancesResponse:
    return ledger_read_pb2.GetBalancesResponse(
        balances=[
            ledger_read_pb2.AssetBalance(
                asset_id=1,
                trading=_u128(250 * _E18),
                reserved=_u128(25 * _E18),
                available=_u128(225 * _E18),
                funding=_u128(1000 * _E18),
                funding_revision=81,
            )
        ],
        trading_epoch=_EPOCH,
        trading_sequence=_SEQUENCE,
        trading_applied_through_ts_ns=_APPLIED_NS,
    )


@pytest.mark.parametrize("wire_format", ["binary", "json"])
async def test_balances_list_returns_the_trading_position(wire_format) -> None:
    def answer(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/ledger.read.v1.LedgerReadService/GetBalances")
        return _reply(_balances_reply(), req)

    async with _client(answer, wire_format=wire_format) as (client, _):
        result = await client.balances.list()

    assert (
        result.trading_epoch,
        result.trading_sequence,
        result.trading_applied_through_ts_ns,
    ) == (_EPOCH, _SEQUENCE, _APPLIED_NS)
    assert result.balances == [
        AssetBalance(
            asset_id=1,
            trading=str(250 * _E18),
            reserved=str(25 * _E18),
            available=str(225 * _E18),
            funding=str(1000 * _E18),
            funding_revision=81,
        )
    ]
    assert "trading_revision" not in AssetBalance.__struct_fields__


async def test_balances_list_retries_unavailable_with_the_same_request(no_sleep) -> None:
    answers = iter([_UNAVAILABLE, _UNAVAILABLE])

    def answer(req: ParsedRequest) -> HttpScript:
        return next(answers, None) or _reply(_balances_reply(), req)

    sub = format_id(SUB_ID)
    async with _client(answer) as (client, requests):
        result = await client.balances.list(sub_account_id=sub)

    assert result.trading_sequence == _SEQUENCE
    assert len(requests) == 3
    assert len({req.body for req in requests}) == 1
    assert _request(requests[0], ledger_read_pb2.GetBalancesRequest).subaccount_id == SUB_ID


async def test_balances_list_raises_unavailable_after_the_retry_budget(
    no_sleep, monkeypatch
) -> None:
    clock = iter(range(1000))
    monkeypatch.setattr(_retry, "_monotonic", lambda: float(next(clock)))
    async with _client(lambda _req: _UNAVAILABLE) as (client, requests):
        with pytest.raises(PolyesterServerError):
            await client.balances.list()
    # Each attempt advances the clock a second, past the 2-second budget.
    assert 1 <= len(requests) <= 3


# --- the balance stream: the generated BalanceUpdate as published ---------------------------


def _trading_update(sequence: int, *, complete: bool = True) -> ledger_read_pb2.BalanceUpdate:
    return ledger_read_pb2.BalanceUpdate(
        account=catalog_pb2.TRADING,
        trading_epoch=_EPOCH,
        trading_sequence=sequence,
        complete=complete,
        balances=[
            ledger_read_pb2.AssetBalance(
                asset_id=1,
                trading=_u128(250 * _E18),
                reserved=_u128(25 * _E18),
                available=_u128(225 * _E18),
            )
        ],
        transfers=[
            ledger_read_pb2.TransferRow(
                asset_id=1,
                amount_e18=_u128(25 * _E18),
                transfer_code=catalog_pb2.TransferCode.Value("FUNDING_OPENING_BALANCE"),
                account_code=catalog_pb2.TRADING,
                ts_us=_APPLIED_NS // 1000,
                ts_ns=_APPLIED_NS,
                is_debit=True,
                transfer_id="340282366920938463463374607431768211455",
                balance_after_e18=_u128(250 * _E18),
            )
        ],
        trading_applied_through_ts_ns=_APPLIED_NS,
    )


def _funding_update() -> ledger_read_pb2.BalanceUpdate:
    return ledger_read_pb2.BalanceUpdate(
        account=catalog_pb2.FUNDING,
        balances=[
            ledger_read_pb2.AssetBalance(
                asset_id=1, funding=_u128(1000 * _E18), funding_revision=81
            )
        ],
    )


def _realtime(server: CentrifugoServer, api: ResumeApi) -> AsyncRealtimeClient:
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    client = AsyncRealtimeClient(
        server.url,
        api_url="https://api.test",
        credentials=ApiKeyCredentials(key_id="ak_test", private_key=private),
        http=httpx.AsyncClient(transport=api.transport),
    )
    client._access = SubaccountAccess(client, FAST)
    return client


async def test_balance_stream_yields_each_update_as_published() -> None:
    account = format_id(SUB_ID)
    channel = f"private:ledger:balances:{account}:proto"
    api = ResumeApi()
    async with CentrifugoServer() as server:
        realtime = _realtime(server, api)
        service = AsyncBalancesService(None, realtime=realtime)
        sub = await service.subscribe(account_id=account)
        await server.wait_subscribed(channel)
        # Out of order and repeated, as a reconnect can deliver them: the SDK
        # passes them through without buffering, reordering or dropping.
        for message in (
            _trading_update(44, complete=False),
            _funding_update(),
            _trading_update(43),
            _trading_update(43),
        ):
            await server.push(channel, publication(message.SerializeToString()))
        async with asyncio.timeout(5):
            received = [await anext(sub) for _ in range(4)]

        # The generated message as published, not an SDK model.
        assert all(type(u) is ledger_read_pb2.BalanceUpdate for u in received)
        assert [(u.account, u.trading_sequence, u.complete) for u in received] == [
            (catalog_pb2.TRADING, 44, False),
            (catalog_pb2.FUNDING, 0, False),
            (catalog_pb2.TRADING, 43, True),
            (catalog_pb2.TRADING, 43, True),
        ]
        trading = received[0]
        assert trading == _trading_update(44, complete=False)
        (balance,) = trading.balances
        # Presence is kept: a Trading update sets no Funding field.
        assert balance.HasField("trading") and not balance.HasField("funding")
        assert (balance.trading.hi << 64) | balance.trading.lo == 250 * _E18
        (leg,) = trading.transfers
        assert (leg.transfer_id, leg.is_debit, leg.ts_ns) == (
            "340282366920938463463374607431768211455",
            True,
            _APPLIED_NS,
        )
        funding = received[1]
        assert funding == _funding_update()
        assert funding.trading_epoch == 0
        (funding_balance,) = funding.balances
        assert funding_balance.HasField("funding") and not funding_balance.HasField("trading")
        assert sub.take_resubscribed() is False

        # The reconnect signal is unchanged: clients reload on it.
        await server.push(channel, unsubscribe(channel))
        await server.wait_subscribed(channel)
        await server.push(channel, publication(_trading_update(45).SerializeToString()))
        async with asyncio.timeout(5):
            assert (await anext(sub)).trading_sequence == 45
        assert sub.take_resubscribed() is True
        await realtime.aclose()


def test_sync_balance_handle_reports_reconnects_without_an_update(monkeypatch) -> None:
    from polyester import Polyester
    from polyester.realtime.client import AsyncSubscription

    made: list[AsyncSubscription] = []

    async def subscribe(self, **kwargs):
        sub: AsyncSubscription = AsyncSubscription(queue=asyncio.Queue(), close=asyncio.Event())
        made.append(sub)
        return sub

    monkeypatch.setattr(AsyncBalancesService, "subscribe", subscribe)
    events: list[object] = []
    client = Polyester(hydrate_catalogs=False)
    try:
        handle = client.balances.subscribe_sync(on_event=events.append)
        assert handle.take_resubscribed() is False
        assert handle.resubscribed == 0
        # A reconnect with no update after it: the account is idle.
        reconnected = threading.Event()

        def reconnect() -> None:
            made[0]._mark_resubscribed()
            reconnected.set()

        client._loop.call_soon_threadsafe(reconnect)
        assert reconnected.wait(5)
        assert handle.resubscribed == 1
        assert handle.take_resubscribed() is True
        assert handle.take_resubscribed() is False
        assert events == []
        handle.close()
    finally:
        client.close()


def test_sync_handle_take_never_loses_or_repeats_a_reconnect() -> None:
    from polyester.realtime.client import AsyncSubscription
    from polyester.sync_subscribe import SyncSubscription

    loop = asyncio.new_event_loop()
    try:
        sub: AsyncSubscription = AsyncSubscription(queue=asyncio.Queue(), close=asyncio.Event())

        async def close() -> None:
            return None

        handle = SyncSubscription(loop, close_coro=close, holder={"sub": sub, "closed": False})
        marks = 20_000
        taken = 0
        done = threading.Event()

        def mark() -> None:
            for _ in range(marks):
                sub._mark_resubscribed()
            done.set()

        marker = threading.Thread(target=mark)
        marker.start()
        while not done.is_set():
            taken += handle.take_resubscribed()
        marker.join()
        taken += handle.take_resubscribed()
        assert handle.resubscribed == marks
        # Each take saw a distinct pending reconnect, and the last one was not lost.
        assert 1 <= taken <= marks
        assert handle.take_resubscribed() is False
    finally:
        loop.close()


def test_balance_update_keeps_unknown_values_and_fields() -> None:
    from polyester.codecs.realtime_decode import decode_balance_update_bytes

    # An account this SDK's contract does not name, and a field it does not
    # know (15, a varint), reach the caller as published.
    payload = (
        ledger_read_pb2.BalanceUpdate(account=302, trading_epoch=7).SerializeToString()  # type: ignore[arg-type]
        + bytes([15 << 3 | 0, 1])
    )
    update = decode_balance_update_bytes(payload)
    assert type(update) is ledger_read_pb2.BalanceUpdate
    assert update.account == 302
    assert update.trading_epoch == 7
    assert update.SerializeToString() == payload


def test_ledger_transfer_keeps_its_exact_time() -> None:
    row = ledger_read_pb2.TransferRow(transfer_id="7", ts_us=1_700_000_000_123_456)
    assert ledger_transfer_from_proto(row).ts_ns == 0
    row.ts_ns = 1_700_000_000_123_456_789
    assert ledger_transfer_from_proto(row).ts_ns == 1_700_000_000_123_456_789


# --- profit and loss ----------------------------------------------------------------------------

_AS_OF = datetime(2026, 11, 21, 9, 0, 5, tzinfo=UTC)


def _ts(value: datetime):
    from google.protobuf.timestamp_pb2 import Timestamp

    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


def _pnl_reply() -> pnl_pb2.GetProfitAndLossResponse:
    return pnl_pb2.GetProfitAndLossResponse(
        window_start=_ts(datetime(2026, 11, 15, tzinfo=UTC)),
        as_of=_ts(_AS_OF),
        mark_time=_ts(datetime(2026, 11, 21, 9, 0, tzinfo=UTC)),
        realized_pnl_usd="-12.500000000000000001",
        fees_usd="-0.25",
        volume_usd="1000",
        products=[
            pnl_pb2.ProductProfitAndLoss(
                product=pnl_pb2.PROFIT_AND_LOSS_PRODUCT_SPOT,
                realized_pnl_usd="-12.500000000000000001",
                fees_usd="-0.25",
                volume_usd="1000",
            )
        ],
        markets=[
            pnl_pb2.MarketProfitAndLoss(
                symbol_id=1,
                product=pnl_pb2.PROFIT_AND_LOSS_PRODUCT_SPOT,
                realized_pnl_usd="-12.500000000000000001",
                fees_usd="-0.25",
                volume_usd="1000",
                trade_count=3,
            )
        ],
        holdings=[
            pnl_pb2.HoldingProfitAndLoss(
                asset_id=2,
                position_quantity="1.5",
                untracked_quantity="0.5",
                cost_usd="60000",
                entry_price_usd="60000",
            )
        ],
        notices=[pnl_pb2.PROFIT_AND_LOSS_NOTICE_MARK_UNAVAILABLE, 99],  # type: ignore[list-item]
    )


@pytest.mark.parametrize("wire_format", ["binary", "json"])
async def test_pnl_get_sends_the_selection_and_keeps_exact_figures(wire_format) -> None:
    def answer(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/pnl.v1.ProfitAndLossService/GetProfitAndLoss")
        reply = _pnl_reply()
        if wire_format == "json":
            # ProtoJSON cannot name an enum number it does not know.
            del reply.notices[1:]
        return _reply(reply, req)

    async with _client(answer, wire_format=wire_format) as (client, requests):
        result = await client.pnl.get(
            window="7d", product="spot", symbol_id=1, sub_account_id=format_id(SUB_ID)
        )

    request = _request(requests[0], pnl_pb2.GetProfitAndLossRequest)
    assert (request.window, request.product, request.symbol_id, request.subaccount_id) == (
        pnl_pb2.PROFIT_AND_LOSS_WINDOW_DAYS_7,
        pnl_pb2.PROFIT_AND_LOSS_PRODUCT_SPOT,
        1,
        SUB_ID,
    )
    assert result.realized_pnl_usd == Decimal("-12.500000000000000001")
    assert result.fees_usd == Decimal("-0.25")
    # Figures that need an unavailable price are unknown, never zero.
    assert (result.pnl_usd, result.unrealized_pnl_usd, result.unrealized_pnl_change_usd) == (
        None,
        None,
        None,
    )
    assert result.as_of == _AS_OF
    assert result.products[0].product == "spot"
    (market,) = result.markets
    assert (market.symbol_id, market.symbol, market.trade_count) == (1, "", 3)
    (holding,) = result.holdings
    assert holding.position_quantity == Decimal("1.5")
    assert holding.entry_price_usd == Decimal("60000")
    assert (holding.mark_price_usd, holding.unrealized_pnl_usd) == (None, None)
    expected_notices = ["mark_unavailable"] + (["99"] if wire_format == "binary" else [])
    assert result.notices == expected_notices


async def test_pnl_main_account_selection_sends_no_sub_account() -> None:
    def answer(req: ParsedRequest) -> HttpScript:
        return _reply(_pnl_reply(), req)

    async with _client(answer) as (client, requests):
        await client.pnl.get(window="lifetime", account="main")
        await client.pnl.get(window="TODAY")

    for req, window in zip(
        requests,
        (pnl_pb2.PROFIT_AND_LOSS_WINDOW_LIFETIME, pnl_pb2.PROFIT_AND_LOSS_WINDOW_TODAY),
        strict=True,
    ):
        request = _request(req, pnl_pb2.GetProfitAndLossRequest)
        assert not request.HasField("subaccount_id")
        assert request.window == window
        assert request.product == pnl_pb2.PROFIT_AND_LOSS_PRODUCT_UNSPECIFIED
        assert request.symbol_id == 0


@pytest.mark.parametrize("text", ["", "1e3", "NaN", "1.", ".5", "+1", "1,5", " 1"], ids=repr)
def test_pnl_figure_that_is_not_a_decimal_is_a_contract_violation(text: str) -> None:
    reply = _pnl_reply()
    reply.fees_usd = text
    with pytest.raises(PolyesterResponseContractError, match="fees_usd"):
        profit_and_loss_from_proto(reply)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"window": "week"}, "window"),
        ({"window": ""}, "window"),
        ({"window": "7d", "product": "perp"}, "product"),
    ],
)
async def test_pnl_refuses_a_bad_selection_before_sending(kwargs, match) -> None:
    async with _client(lambda _req: HttpScript.not_found()) as (client, requests):
        with pytest.raises(PolyesterValidationError, match=match):
            await client.pnl.get(**kwargs)
        with pytest.raises(PolyesterValidationError, match=match):
            await client.pnl.get_trading_statistics(**kwargs)
    assert requests == []


def _stats_reply() -> pnl_pb2.GetTradingStatisticsResponse:
    return pnl_pb2.GetTradingStatisticsResponse(
        window_start=_ts(datetime(2026, 10, 23, tzinfo=UTC)),
        as_of=_ts(_AS_OF),
        trade_count=12,
        volume_usd="12000.5",
        fees_usd="6",
        realized_pnl_usd="40",
        notices=[pnl_pb2.PROFIT_AND_LOSS_NOTICE_SHARPE_INSUFFICIENT_DAYS],
        return_pct="9.95",
        max_drawdown_pct="0",
        return_days=2,
    )


async def test_pnl_trading_statistics_keep_unknown_ratios_unknown(no_sleep) -> None:
    answers = iter([_UNAVAILABLE])

    def answer(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/pnl.v1.ProfitAndLossService/GetTradingStatistics")
        return next(answers, None) or _reply(_stats_reply(), req)

    async with _client(answer) as (client, requests):
        stats = await client.pnl.get_trading_statistics(window="30d")

    assert len(requests) == 2
    request = _request(requests[1], pnl_pb2.GetTradingStatisticsRequest)
    assert request.window == pnl_pb2.PROFIT_AND_LOSS_WINDOW_DAYS_30
    assert stats.return_pct == Decimal("9.95")
    assert stats.max_drawdown_pct == Decimal(0)
    assert stats.sharpe is None
    assert stats.return_days == 2
    assert stats.notices == ["sharpe_insufficient_days"]
    assert stats.volume_usd == Decimal("12000.5")


def _day(day: int, **fields: Any) -> pnl_pb2.DailyProfitAndLoss:
    return pnl_pb2.DailyProfitAndLoss(
        day=_ts(datetime(2026, 11, day, tzinfo=UTC)),
        realized_pnl_usd="0",
        fees_usd="0",
        volume_usd="0",
        **fields,
    )


async def test_pnl_iter_daily_walks_every_page_of_the_same_days() -> None:
    pages = {
        "": pnl_pb2.ListDailyProfitAndLossResponse(
            days=[_day(1, start_equity_usd="100", end_equity_usd="110", net_flow_usd="5")],
            next_page_token="p2",
            as_of=_ts(_AS_OF),
        ),
        "p2": pnl_pb2.ListDailyProfitAndLossResponse(days=[_day(2), _day(3)]),
    }

    def answer(req: ParsedRequest) -> HttpScript:
        request = _request(req, pnl_pb2.ListDailyProfitAndLossRequest)
        return _reply(pages[request.page_token], req)

    async with _client(answer) as (client, requests):
        days = [
            day
            async for day in client.pnl.iter_daily(
                start=date(2026, 11, 1), end=datetime(2026, 11, 4, tzinfo=UTC), limit=2
            )
        ]

    assert [d.day for d in days] == [datetime(2026, 11, n, tzinfo=UTC) for n in (1, 2, 3)]
    first = days[0]
    assert (first.start_equity_usd, first.end_equity_usd, first.net_flow_usd) == (
        Decimal(100),
        Decimal(110),
        Decimal(5),
    )
    assert (days[1].start_equity_usd, days[1].pnl_usd) == (None, None)
    sent = [_request(req, pnl_pb2.ListDailyProfitAndLossRequest) for req in requests]
    assert [s.page_token for s in sent] == ["", "p2"]
    for request in sent:
        assert request.start_time.ToDatetime(tzinfo=UTC) == datetime(2026, 11, 1, tzinfo=UTC)
        assert request.end_time.ToDatetime(tzinfo=UTC) == datetime(2026, 11, 4, tzinfo=UTC)
        assert request.limit == 2


async def test_pnl_iter_daily_refuses_a_repeated_page_token() -> None:
    reply = pnl_pb2.ListDailyProfitAndLossResponse(days=[_day(1)], next_page_token="again")

    async with _client(lambda req: _reply(reply, req)) as (client, _):
        with pytest.raises(PolyesterResponseContractError, match="repeats"):
            async for _day_row in client.pnl.iter_daily(
                start=date(2026, 11, 1), end=date(2026, 11, 2)
            ):
                pass


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"start": datetime(2026, 11, 1, 12, tzinfo=UTC), "end": date(2026, 11, 2)}, "00:00"),
        ({"start": datetime(2026, 11, 1), "end": date(2026, 11, 2)}, "timezone-aware"),
        ({"start": "2026-11-01", "end": date(2026, 11, 2)}, "date"),
        ({"start": date(2026, 11, 2), "end": date(2026, 11, 2)}, "after start"),
        ({"start": date(2025, 1, 1), "end": date(2026, 1, 3)}, "366 days"),
        ({"start": date(2026, 1, 1), "end": date(2026, 1, 2), "limit": 367}, "limit"),
        ({"start": date(2026, 1, 1), "end": date(2026, 1, 2), "page_token": "x" * 513}, "page"),
    ],
)
async def test_pnl_list_daily_refuses_what_the_contract_refuses(kwargs, match) -> None:
    async with _client(lambda _req: HttpScript.not_found()) as (client, requests):
        with pytest.raises(PolyesterValidationError, match=match):
            await client.pnl.list_daily(**kwargs)
    assert requests == []


async def test_pnl_list_daily_accepts_the_last_representable_days() -> None:
    reply = pnl_pb2.ListDailyProfitAndLossResponse()
    async with _client(lambda req: _reply(reply, req)) as (client, requests):
        await client.pnl.list_daily(start=date(9999, 12, 30), end=date(9999, 12, 31))
        await client.pnl.list_daily(start=date(9998, 12, 30), end=date(9999, 12, 31))
    first, second = (_request(req, pnl_pb2.ListDailyProfitAndLossRequest) for req in requests)
    assert first.start_time.ToDatetime(tzinfo=UTC) == datetime(9999, 12, 30, tzinfo=UTC)
    assert first.end_time.ToDatetime(tzinfo=UTC) == datetime(9999, 12, 31, tzinfo=UTC)
    assert second.start_time.ToDatetime(tzinfo=UTC) == datetime(9998, 12, 30, tzinfo=UTC)


async def test_pnl_list_daily_refuses_a_range_one_day_too_long_at_the_last_date() -> None:
    async with _client(lambda _req: HttpScript.not_found()) as (client, requests):
        with pytest.raises(PolyesterValidationError, match="366 days"):
            await client.pnl.list_daily(start=date(9998, 12, 29), end=date(9999, 12, 31))
        with pytest.raises(PolyesterValidationError, match="date range"):
            await client.pnl.list_daily(
                start=date(9999, 12, 30),
                end=datetime(9999, 12, 31, 23, tzinfo=timezone(timedelta(hours=-2))),
            )
    assert requests == []


# --- cancel-all for triggers --------------------------------------------------------------------


def test_cancel_all_triggers_encodes_the_criteria() -> None:
    request = cancel_all_triggers_to_proto(
        sub_account_id=format_id(SUB_ID),
        symbol_ids=[2, 1, 2],
        side="SELL",
        trigger_types=["stop_loss", "take-profit", "stop_loss"],
        dry_run=True,
        request_id="ui-tpsl-cancel-all-7f3a",
    )
    assert request == triggers_pb2.CancelAllTriggersRequest(
        subaccount_id=SUB_ID,
        symbol_ids=[2, 1],
        side=orders_pb2.SELL,
        trigger_types=[triggers_pb2.STOP_LOSS, triggers_pb2.TAKE_PROFIT],
        dry_run=True,
        request_id="ui-tpsl-cancel-all-7f3a",
    )


def test_cancel_all_triggers_matches_everything_and_generates_a_request_id() -> None:
    request = cancel_all_triggers_to_proto()
    assert not request.HasField("subaccount_id")
    assert list(request.symbol_ids) == []
    assert list(request.trigger_types) == []
    assert request.side == orders_pb2.SIDE_UNSPECIFIED
    assert request.dry_run is False
    assert request.request_id.startswith("trg-cancel-all-")
    assert len(request.request_id) <= 64


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"symbol_ids": [0]}, "positive"),
        ({"symbol_ids": list(range(1, 102))}, "at most 100"),
        ({"side": "both"}, "side"),
        ({"trigger_types": "twap"}, "list"),
        ({"trigger_types": ["oco"]}, "trigger_type"),
        ({"request_id": "has space"}, "request_id"),
        ({"request_id": "x" * 65}, "request_id"),
        ({"request_id": ""}, "request_id"),
        ({"request_id": "  "}, "request_id"),
        ({"request_id": " twap-1"}, "request_id"),
        ({"request_id": 7}, "request_id"),
        ({"symbol_ids": b"\x01"}, "list of integer market IDs"),
        ({"symbol_ids": "1"}, "list of integer market IDs"),
        ({"trigger_types": {"twap": 1}}, "list"),
        ({"dry_run": "yes"}, "dry_run"),
    ],
)
def test_cancel_all_triggers_refuses_what_the_contract_refuses(kwargs, match) -> None:
    with pytest.raises(PolyesterValidationError, match=match):
        cancel_all_triggers_to_proto(**kwargs)


_TWAP: dict[str, Any] = {"trigger_types": ["twap"], "request_id": "twap-1"}


@pytest.mark.parametrize("wire_format", ["binary", "json"])
async def test_triggers_cancel_all_round_trip(wire_format) -> None:
    reply = triggers_pb2.CancelAllTriggersResponse(
        status=triggers_pb2.CancelAllTriggersResponse.DRY_RUN,
        matched_triggers=7,
        ts=_ts(_AS_OF),
        ts_ns=1_795_000_000_123_456_789,
    )

    def answer(req: ParsedRequest) -> HttpScript:
        assert req.path.endswith("/triggers.v1.TriggersService/CancelAllTriggers")
        return _reply(reply, req)

    async with _client(answer, wire_format=wire_format) as (client, requests):
        result = await client.triggers.cancel_all(dry_run=True, symbol_ids=[1], **_TWAP)

    request = _request(requests[0], triggers_pb2.CancelAllTriggersRequest)
    assert list(request.symbol_ids) == [1]
    assert list(request.trigger_types) == [triggers_pb2.TWAP]
    assert (request.dry_run, request.request_id) == (True, "twap-1")
    assert (result.status, result.matched_triggers, result.ts_ns) == (
        "dry_run",
        7,
        1_795_000_000_123_456_789,
    )


def test_cancel_all_triggers_decoder() -> None:
    submitted = cancel_all_triggers_from_proto(
        triggers_pb2.CancelAllTriggersResponse(
            status=triggers_pb2.CancelAllTriggersResponse.SUBMITTED,
            matched_triggers=3,
            ts=_ts(datetime(2026, 1, 1, tzinfo=UTC)),
        )
    )
    # Without the exact time, the paired Timestamp gives it.
    assert (submitted.status, submitted.matched_triggers, submitted.ts_ns) == (
        "submitted",
        3,
        1_767_225_600 * 10**9,
    )
    with pytest.raises(PolyesterResponseContractError, match="unknown status"):
        cancel_all_triggers_from_proto(triggers_pb2.CancelAllTriggersResponse())


async def test_triggers_cancel_all_resolves_symbol_names_before_sending() -> None:
    async with _client(lambda _req: HttpScript.not_found()) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.triggers.cancel_all(symbol="BTC-USDT", symbol_ids=[1], dry_run=True)
    assert requests == []


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"symbol": ""}, "symbol must not be blank"),
        ({"symbol": "   "}, "symbol must not be blank"),
        ({"symbols": ["BTC-USDT", " "]}, r"symbols\[1\] must not be blank"),
        ({"symbols": [""]}, r"symbols\[0\] must not be blank"),
    ],
)
async def test_triggers_cancel_all_refuses_a_blank_symbol_filter(kwargs, match) -> None:
    # A blank filter must never widen the cancel to every pair.
    async with _client(lambda _req: HttpScript.not_found()) as (client, requests):
        with pytest.raises(PolyesterValidationError, match=match):
            await client.triggers.cancel_all(dry_run=True, **kwargs)
    assert requests == []


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"symbols": ""}, "list of pair names"),
        ({"symbols": "BTC-USDT"}, "list of pair names"),
        ({"symbols": b""}, "list of pair names"),
        ({"symbols": {"BTC-USDT": 1}}, "list of pair names"),
        ({"symbols": 7}, "list of pair names"),
        ({"symbol": b"BTC-USDT"}, "must be a pair name"),
        ({"symbol_ids": b""}, "list of integer market IDs"),
        ({"symbol_ids": b"\x01"}, "list of integer market IDs"),
        ({"symbol_ids": "12"}, "list of integer market IDs"),
        ({"symbol_ids": {1: 1}}, "list of integer market IDs"),
        ({"symbol_ids": 1}, "list of integer market IDs"),
        ({"symbol_ids": [True]}, "symbol_ids"),
        ({"trigger_types": b"twap"}, "list of trigger types"),
        ({"trigger_types": {"twap": 1}}, "list of trigger types"),
        ({"request_id": ""}, "request_id"),
        ({"request_id": "   "}, "request_id"),
        ({"request_id": "twap-1 "}, "request_id"),
    ],
    ids=repr,
)
async def test_triggers_cancel_all_refuses_malformed_filters_before_sending(kwargs, match) -> None:
    # A malformed filter must never reach the server as an account-wide cancel.
    async with _client(lambda _req: HttpScript.not_found()) as (client, requests):
        with pytest.raises(PolyesterValidationError, match=match):
            await client.triggers.cancel_all(dry_run=True, **kwargs)
    assert requests == []


async def test_triggers_cancel_all_empty_lists_match_every_pair() -> None:
    reply = triggers_pb2.CancelAllTriggersResponse(
        status=triggers_pb2.CancelAllTriggersResponse.DRY_RUN, matched_triggers=2
    )
    async with _client(lambda req: _reply(reply, req)) as (client, requests):
        await client.triggers.cancel_all(dry_run=True, symbols=[], request_id="all-1")
        await client.triggers.cancel_all(dry_run=True, symbol_ids=(), request_id="all-2")
        await client.triggers.cancel_all(dry_run=True, trigger_types=[], request_id="all-3")
    sent = [_request(req, triggers_pb2.CancelAllTriggersRequest) for req in requests]
    assert [(list(r.symbol_ids), list(r.trigger_types), r.request_id) for r in sent] == [
        ([], [], "all-1"),
        ([], [], "all-2"),
        ([], [], "all-3"),
    ]


# --- the market overview's live price band ------------------------------------------------------


def test_market_overview_row_keeps_its_live_price_band() -> None:
    band = marketdata_pb2.LivePriceBand(
        symbol_id=1,
        state=marketdata_pb2.ACTIVE,
        reference_price_ticks=61_000_250_000_000,
        reference_source=marketdata_pb2.LAST_TRADE,
        max_buy_price_ticks=64_050_250_000_000,
        min_sell_price_ticks=57_950_250_000_000,
        updated_ts_ns=10,
        reanchor_eligible_ts_ns=0,
        parameters=marketdata_pb2.PriceBand(lower_bps=500, upper_bps=500),
        epoch=3,
        update_id=41,
        as_of_ts_ns=1_000,
        valid_until_ts_ns=5_000,
    )
    row = market_overview_entry_from_proto(
        marketoverview_pb2.MarketOverview(symbol_id=1, price_band=band)
    )
    live = row.price_band
    assert live is not None
    assert (live.state, live.reference_source, live.epoch, live.update_id) == (
        "active",
        "last_trade",
        3,
        41,
    )
    assert live.reference_price is not None
    assert live.reference_price.as_decimal() == Decimal("61000.25")
    assert live.max_buy_price is not None and live.min_sell_price is not None
    assert (live.min_buy_price, live.max_sell_price) == (None, None)
    # A sent zero is kept, an absent time is None.
    assert live.reanchor_eligible_ts_ns == 0
    assert live.parameters is not None and live.parameters.lower_bps == 500
    assert live.is_fresh(now_ns=5_000) is True
    assert live.is_fresh(now_ns=5_001) is False

    assert (
        market_overview_entry_from_proto(marketoverview_pb2.MarketOverview(symbol_id=1)).price_band
        is None
    )
    unknown = market_overview_entry_from_proto(
        marketoverview_pb2.MarketOverview(
            symbol_id=1,
            price_band=marketdata_pb2.LivePriceBand(
                symbol_id=1, state=marketdata_pb2.UNKNOWN, valid_until_ts_ns=5_000
            ),
        )
    ).price_band
    assert unknown is not None
    assert unknown.is_fresh(now_ns=1) is False
    assert unknown.reanchor_eligible_ts_ns is None


# --- strategy bot keys --------------------------------------------------------------------------


def test_api_key_names_its_strategy_bot() -> None:
    bot_key = api_key_from_proto(
        api_keys_pb2.ApiKey(
            key_id="ak_3f2a9c1b8e7d6f5a4c3b2a1f0e9d8c7b",
            purpose=api_keys_pb2.STRATEGY_BOT,
            strategy_bot_id=9_223_372_036_854_775_808,
        )
    )
    assert bot_key.purpose == "strategy_bot"
    assert bot_key.strategy_bot_id == format_id(9_223_372_036_854_775_808)
    standard = api_key_from_proto(api_keys_pb2.ApiKey(key_id="ak_1", purpose=api_keys_pb2.STANDARD))
    assert standard.strategy_bot_id == ""


def test_strategy_bot_access_calls_stay_out_of_the_sdk() -> None:
    import tomllib
    from pathlib import Path

    coverage = tomllib.loads((Path(__file__).parents[2] / "sdk-coverage.toml").read_text())
    reasons = {
        entry.get("procedure"): entry["reason"]
        for entry in coverage["allowlist"]
        if "procedure" in entry
    }
    for method in ("SetStrategyBotAccess", "EndStrategyBotAccess"):
        assert "web app" in reasons[f"/auth.v1.ApiKeyService/{method}"]
