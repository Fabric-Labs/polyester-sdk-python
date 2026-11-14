"""Public contract ebbbeac: account statements, status events, asset
information, route status and the statement permission."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester, Polyester
from polyester.catalogs.zipper import build_zipper_catalog_data
from polyester.catalogs.zipper_supply import patch_zipper_catalog_supply
from polyester.codecs.decode.api_keys import api_key_from_get_proto
from polyester.codecs.decode.asset_info import asset_info_list_from_proto
from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
from polyester.codecs.decode.system import status_events_page_from_proto
from polyester.codecs.decode.zipper import deposit_withdraw_config_from_proto
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.auth.v1 import api_keys_pb2, policies_pb2, subaccounts_pb2
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.marketdata.v1 import asset_info_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.system.v1 import system_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import (
    AssetIssuePrice,
    Statement,
    StatementRow,
    ZippedAssetSupplyUpdate,
    parse_statement_csv,
)
from polyester.services.statements import AsyncStatementsService
from polyester.transport import TransportConfig, TransportFactory
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

START = datetime(2026, 10, 1, 0, 0, 0, 123456, tzinfo=UTC)
END = datetime(2026, 11, 1, tzinfo=UTC)
HEADER = "time,entry_id,type,account,asset,amount,fee,balance,link_id,flow_id\r\n"
ROW_1 = "2026-10-02T14:03:11.000000Z,27419385013475392777,deposit,funding,USDT,100,0,100,,f1\r\n"
ROW_2 = "2026-10-03T08:12:45.123456Z,27419385013475392811,trade,trading,BTC,0.1,0,1.1,77,\r\n"


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


_PRIVATE_KEY = make_test_credentials().private_key

Responder = Callable[[ParsedRequest], Message]


@asynccontextmanager
async def _server(respond: Responder, *, signed: bool = True):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest):
        requests.append(req)
        return connect_proto_response(respond(req).SerializeToString())

    http = await MockHttpServer.spawn(handler)
    transport = TransportFactory(
        TransportConfig(api_url=http.base_url),
        credentials=make_test_credentials() if signed else None,
    )
    try:
        yield http.base_url, transport, requests
    finally:
        await transport.aclose()
        await http.aclose()


# --- account statements --------------------------------------------------------------------------


def _statement_pages(req: ParsedRequest) -> Message:
    sent = ledger_read_pb2.ExportStatementRequest.FromString(req.body)
    pages = {
        "": ledger_read_pb2.ExportStatementResponse(csv=HEADER + ROW_1, next_page_token="p2"),
        "p2": ledger_read_pb2.ExportStatementResponse(csv=ROW_2, next_page_token=""),
    }
    return pages[sent.page_token]


async def test_export_follows_every_page_with_the_same_request_and_concatenates() -> None:
    async with _server(_statement_pages) as (_, transport, requests):
        statement = await AsyncStatementsService(transport, None).export(
            start_time=START, end_time=END, asset_id=7
        )
    assert statement == Statement(csv=HEADER + ROW_1 + ROW_2)
    sent = [ledger_read_pb2.ExportStatementRequest.FromString(r.body) for r in requests]
    assert [r.path for r in requests] == ["/ledger.read.v1.LedgerReadService/ExportStatement"] * 2
    assert [s.page_token for s in sent] == ["", "p2"]
    for request in sent:
        # Exact to the microsecond, the same fields on every page.
        assert request.start_time == _ts(START)
        assert request.start_time.nanos == 123_456_000
        assert request.end_time == _ts(END)
        assert request.asset_id == 7
        assert not request.HasField("subaccount_id")
    # Signed like the other ledger reads.
    assert all(r.headers.get("x-api-key-id") == "ak_test" for r in requests)
    assert all(r.headers.get("x-api-signature") for r in requests)
    rows = statement.rows()
    assert [row.flow_id for row in rows] == ["f1", ""]
    assert rows[1] == StatementRow(
        time=datetime(2026, 10, 3, 8, 12, 45, 123456, tzinfo=UTC),
        entry_id="27419385013475392811",
        type="trade",
        account="trading",
        asset="BTC",
        amount="0.1",
        fee="0",
        balance="1.1",
        link_id="77",
    )


async def test_export_page_applies_the_default_sub_account_unless_named() -> None:
    sub = format_id(9_000_000_001)
    other = format_id(9_000_000_002)
    async with _server(_statement_pages) as (_, transport, requests):
        service = AsyncStatementsService(transport, sub)
        await service.export_page(start_time=START, end_time=END)
        await service.export_page(start_time=START, end_time=END, sub_account_id=other)
        await service.export_page(start_time=START, end_time=END, account="main")
    sent = [ledger_read_pb2.ExportStatementRequest.FromString(r.body) for r in requests]
    assert [s.subaccount_id for s in sent] == [9_000_000_001, 9_000_000_002, 9_000_000_001]
    assert all(s.asset_id == 0 for s in sent)


async def test_export_page_returns_one_page_as_sent() -> None:
    async with _server(_statement_pages) as (_, transport, _requests):
        page = await AsyncStatementsService(transport, None).export_page(
            start_time=START, end_time=END
        )
    assert page.csv == HEADER + ROW_1
    assert page.next_page_token == "p2"


async def test_client_statements_use_the_configured_default_sub_account() -> None:
    sub = format_id(9_000_000_001)
    async with _server(_statement_pages) as (url, _transport, requests):
        client = AsyncPolyester(
            api_url=url,
            hydrate_catalogs=False,
            api_key_id="ak_test",
            api_private_key=_PRIVATE_KEY,
            default_sub_account_id=sub,
        )
        try:
            await client.statements.export_page(start_time=START, end_time=END)
        finally:
            await client.aclose()
    (sent,) = requests
    assert ledger_read_pb2.ExportStatementRequest.FromString(sent.body).subaccount_id == (
        9_000_000_001
    )
    assert sent.headers.get("x-api-key-id") == "ak_test"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"start_time": None, "end_time": END},
        {"start_time": START, "end_time": None},
        {"start_time": "2026-10-01T00:00:00Z", "end_time": END},
        {"start_time": START.replace(tzinfo=None), "end_time": END},
        {"start_time": START, "end_time": END, "asset_id": -1},
        {"start_time": START, "end_time": END, "asset_id": True},
    ],
)
async def test_export_refuses_what_it_cannot_send_before_sending(kwargs) -> None:
    async with _server(_statement_pages) as (_, transport, requests):
        with pytest.raises(PolyesterValidationError):
            await AsyncStatementsService(transport, None).export(**kwargs)
    assert requests == []


async def test_export_rejects_a_repeated_page_token() -> None:
    def respond(req: ParsedRequest) -> Message:
        return ledger_read_pb2.ExportStatementResponse(csv=HEADER, next_page_token="again")

    async with _server(respond) as (_, transport, requests):
        with pytest.raises(PolyesterResponseContractError):
            await AsyncStatementsService(transport, None).export(start_time=START, end_time=END)
    assert len(requests) == 2


def test_statement_csv_reads_columns_by_header_name() -> None:
    text = (
        "asset,future_column,balance,fee,amount,account,type,entry_id,time,link_id\r\n"
        'USDT,"x,y",4997.5,2.5,-5000,trading,trade,274,2026-10-03T08:12:45.123456Z,77\r\n'
    )
    (row,) = parse_statement_csv(text)
    assert row.asset == "USDT"
    assert row.amount == "-5000"
    assert row.fee == "2.5"
    assert row.balance == "4997.5"
    assert row.entry_id == "274"
    assert row.link_id == "77"
    # A statement without the flow_id column reads it as "".
    assert row.flow_id == ""
    assert row.time == datetime(2026, 10, 3, 8, 12, 45, 123456, tzinfo=UTC)


def test_statement_with_only_the_header_has_no_rows() -> None:
    assert parse_statement_csv(HEADER) == []
    assert parse_statement_csv("") == []


@pytest.mark.parametrize(
    "text",
    [
        "time,entry_id,type,account,asset,amount,fee,balance\r\n",
        HEADER + "2026-10-03T08:12:45Z,1,trade\r\n",
        HEADER + "yesterday,1,trade,trading,BTC,0.1,0,1.1,77,\r\n",
        HEADER + "2026-10-03T08:12:45,1,trade,trading,BTC,0.1,0,1.1,77,\r\n",
    ],
)
def test_statement_csv_refuses_what_it_cannot_read(text: str) -> None:
    with pytest.raises(PolyesterResponseContractError):
        parse_statement_csv(text)


@pytest.mark.parametrize(
    "text",
    [
        # Content after a closing quote; a lenient reader reads 1000.
        HEADER + '2026-10-03T08:12:45Z,1,trade,trading,BTC,"100"0,0,1.1,77,\r\n',
        # An unterminated quoted field; a lenient reader swallows the rest.
        HEADER + '2026-10-03T08:12:45Z,1,trade,trading,BTC,"0.1,0,1.1,77,\r\n',
    ],
)
def test_statement_csv_refuses_malformed_quoting(text: str) -> None:
    with pytest.raises(PolyesterResponseContractError, match="not valid CSV"):
        parse_statement_csv(text)


def test_statement_csv_reads_an_escaped_quote() -> None:
    (row,) = parse_statement_csv(
        HEADER + '2026-10-03T08:12:45Z,1,trade,trading,"B""TC",0.1,0,"1,1",77,\r\n'
    )
    assert row.asset == 'B"TC'
    assert row.balance == "1,1"


def test_sync_client_exports_statements() -> None:
    from polyester._sync_services import SyncStatementsService

    with Polyester(api_url="http://127.0.0.1:9", hydrate_catalogs=False) as client:
        assert isinstance(client.statements, SyncStatementsService)


# --- statement permission ------------------------------------------------------------------------


def test_read_statements_permission_values_read_by_name() -> None:
    assert policies_pb2.READ_STATEMENTS == 38
    assert subaccounts_pb2.SUBACCOUNT_PERMISSION_READ_STATEMENTS == 29
    actions = [policies_pb2.READ_BALANCES, policies_pb2.READ_STATEMENTS]
    api = api_policy_from_proto(policies_pb2.ApiPolicyView(id=1, actions=actions))
    sub = subaccount_policy_from_proto(policies_pb2.SubaccountPolicyView(id=1, actions=actions))
    assert api.actions == sub.actions == ["read_balances", "read_statements"]


def test_api_key_reads_keep_policy_public_key_creator_and_microseconds() -> None:
    created = datetime(2026, 11, 12, 16, 48, 15, 912958, tzinfo=UTC)
    key = api_key_from_get_proto(
        api_keys_pb2.GetApiKeyResponse(
            api_key=api_keys_pb2.ApiKey(
                key_id="ak_1",
                policy_id=42,
                public_key_ed25519=bytes(range(32)),
                created_by_actor="desk",
                created_at=_ts(created),
            )
        )
    )
    assert key is not None
    assert key.policy_id == format_id(42)
    assert key.public_key_ed25519 == bytes(range(32)).hex()
    assert key.created_by_actor == "desk"
    assert key.created_at == created


def test_quote_size_renames_have_not_regressed() -> None:
    assert orders_pb2.ERROR_CODE_QUOTE_SIZE_TOO_SMALL == 68
    assert triggers_pb2.TRIGGER_FAILURE_REASON_QUOTE_SIZE_TOO_SMALL == 24
    assert not hasattr(orders_pb2, "ERROR_CODE_MAX_QUOTE_DEBIT_TOO_SMALL")
    assert not hasattr(triggers_pb2, "TRIGGER_FAILURE_REASON_MAX_QUOTE_DEBIT_TOO_SMALL")


# --- status events -------------------------------------------------------------------------------

T0 = datetime(2026, 11, 12, 19, 30, tzinfo=UTC)


def _event(event_id: int, **kwargs) -> system_pb2.StatusEvent:
    return system_pb2.StatusEvent(id=event_id, title=f"event {event_id}", **kwargs)


def test_status_event_decodes_every_field_and_keeps_omissions_none() -> None:
    page = status_events_page_from_proto(
        system_pb2.ListStatusEventsResponse(
            events=[
                _event(
                    7433029815562201289,
                    kind=system_pb2.INCIDENT,
                    state=system_pb2.IN_PROGRESS,
                    message="SOL deposits are slow.",
                    start_time=_ts(T0),
                    services=[system_pb2.DEPOSITS, system_pb2.MARKET_DATA, 42],
                    assets=["SOL"],
                    markets=["SOL-USDT"],
                    impact=system_pb2.DEGRADED,
                    details_url="https://example.com/a",
                    updates=[
                        system_pb2.StatusEventUpdate(
                            id=1, message="identified", created_at=_ts(T0 + timedelta(minutes=15))
                        )
                    ],
                    updated_at=_ts(T0 + timedelta(minutes=15)),
                ),
                _event(
                    2,
                    kind=system_pb2.MAINTENANCE,
                    state=system_pb2.CANCELLED,
                    start_time=_ts(T0),
                    end_time=_ts(T0 + timedelta(hours=1)),
                    cancelled_at=_ts(T0 - timedelta(hours=1)),
                    services=[system_pb2.TRADING, system_pb2.APP],
                    details_url="",
                ),
            ],
            next_page_token="next",
        )
    )
    incident, maintenance = page.events
    assert page.next_page_token == "next"
    assert incident.id == format_id(7433029815562201289)
    assert (incident.kind, incident.state, incident.impact) == (
        "incident",
        "in_progress",
        "degraded",
    )
    # A service newer than this SDK reads as its number.
    assert incident.services == ["deposits", "market_data", "42"]
    assert incident.assets == ["SOL"]
    assert incident.markets == ["SOL-USDT"]
    assert incident.start_time == T0
    assert incident.end_time is None
    assert incident.cancelled_at is None
    assert incident.details_url == "https://example.com/a"
    assert incident.updates[0].id == 1
    assert incident.updates[0].created_at == T0 + timedelta(minutes=15)
    assert incident.updated_at == T0 + timedelta(minutes=15)
    assert (maintenance.kind, maintenance.state, maintenance.impact) == (
        "maintenance",
        "cancelled",
        "",
    )
    assert maintenance.services == ["trading", "app"]
    assert maintenance.end_time == T0 + timedelta(hours=1)
    assert maintenance.cancelled_at == T0 - timedelta(hours=1)
    # A present empty link is kept apart from an omitted one.
    assert maintenance.details_url == ""
    assert (
        status_events_page_from_proto(system_pb2.ListStatusEventsResponse(events=[_event(3)]))
        .events[0]
        .details_url
        is None
    )


def _status_pages(req: ParsedRequest) -> Message:
    sent = system_pb2.ListStatusEventsRequest.FromString(req.body)
    pages = {
        "": system_pb2.ListStatusEventsResponse(events=[_event(1), _event(2)], next_page_token="b"),
        "b": system_pb2.ListStatusEventsResponse(events=[_event(3)]),
    }
    return pages[sent.page_token]


async def test_iter_status_events_resends_the_same_filters_unsigned() -> None:
    async with _server(_status_pages) as (url, _transport, requests):
        client = AsyncPolyester(
            api_url=url,
            hydrate_catalogs=False,
            api_key_id="ak_test",
            api_private_key=_PRIVATE_KEY,
        )
        try:
            events = [
                event
                async for event in client.iter_status_events(
                    states=["Scheduled", "in_progress"], kinds=["maintenance"], limit=2
                )
            ]
        finally:
            await client.aclose()
    assert [event.id for event in events] == [format_id(1), format_id(2), format_id(3)]
    sent = [system_pb2.ListStatusEventsRequest.FromString(r.body) for r in requests]
    assert [r.path for r in requests] == ["/system.v1.SystemService/ListStatusEvents"] * 2
    assert [s.page_token for s in sent] == ["", "b"]
    for request in sent:
        assert list(request.states) == [system_pb2.SCHEDULED, system_pb2.IN_PROGRESS]
        assert list(request.kinds) == [system_pb2.MAINTENANCE]
        assert request.limit == 2
    # Public: never signed, even by a client that holds an API key.
    assert not any(r.headers.get("x-api-key-id") for r in requests)
    assert not any(r.headers.get("x-api-signature") for r in requests)


async def test_list_status_events_sends_no_states_when_none_are_given() -> None:
    async with _server(_status_pages, signed=False) as (url, _transport, requests):
        client = AsyncPolyester(api_url=url, hydrate_catalogs=False)
        try:
            page = await client.list_status_events()
        finally:
            await client.aclose()
    assert page.next_page_token == "b"
    (sent,) = requests
    request = system_pb2.ListStatusEventsRequest.FromString(sent.body)
    # The server applies the current-and-upcoming default; it is not expanded here.
    assert list(request.states) == []
    assert list(request.kinds) == []
    assert request.limit == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"states": ["upcoming"]},
        {"states": ["state_unspecified"]},
        {"kinds": ["outage"]},
        {"kinds": "maintenance"},
    ],
)
async def test_list_status_events_refuses_labels_it_cannot_send(kwargs) -> None:
    async with _server(_status_pages, signed=False) as (url, _transport, requests):
        client = AsyncPolyester(api_url=url, hydrate_catalogs=False)
        try:
            with pytest.raises(PolyesterValidationError):
                await client.list_status_events(**kwargs)
        finally:
            await client.aclose()
    assert requests == []


def test_sync_client_iterates_status_events() -> None:
    import asyncio
    import threading

    from tests.hardening_support import MockHttpServer as _Mock

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    holder: dict[str, object] = {}

    async def start() -> None:
        async def handler(req: ParsedRequest):
            return connect_proto_response(_status_pages(req).SerializeToString())

        holder["http"] = await _Mock.spawn(handler)
        ready.set()

    thread = threading.Thread(target=lambda: (loop.run_until_complete(start()), loop.run_forever()))
    thread.start()
    ready.wait(5)
    http = holder["http"]
    try:
        with Polyester(api_url=http.base_url, hydrate_catalogs=False) as client:  # type: ignore[attr-defined]
            ids = [event.id for event in client.iter_status_events(kinds=["incident"])]
            page = client.list_status_events(page_token="b")
    finally:
        asyncio.run_coroutine_threadsafe(http.aclose(), loop).result(5)  # type: ignore[attr-defined]
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
        loop.close()
    assert ids == [format_id(1), format_id(2), format_id(3)]
    assert [event.id for event in page.events] == [format_id(3)]


# --- asset information ---------------------------------------------------------------------------


def test_asset_info_decodes_editorial_and_keeps_unknowns_apart() -> None:
    updated = datetime(2026, 11, 12, 21, 11, 5, 250000, tzinfo=UTC)
    infos = asset_info_list_from_proto(
        asset_info_pb2.ListAssetInfoResponse(
            asset_info=[
                asset_info_pb2.AssetInfo(
                    asset_id=1,
                    editorial=asset_info_pb2.AssetEditorialInfo(
                        description="Bitcoin",
                        website_url="https://bitcoin.org",
                        whitepaper_url="https://bitcoin.org/bitcoin.pdf",
                        explorer_urls=["https://b.example", "https://a.example"],
                        x_url="https://x.com/b",
                        telegram_url="https://t.me/b",
                        discord_url="https://discord.gg/b",
                        github_url="https://github.com/b",
                        issue_date="2009-01-03",
                        issue_price=asset_info_pb2.AssetIssuePrice(amount="0", currency="USD"),
                    ),
                    editorial_updated_at=_ts(updated),
                ),
                asset_info_pb2.AssetInfo(
                    asset_id=2,
                    editorial=asset_info_pb2.AssetEditorialInfo(description="cleared later"),
                ),
                asset_info_pb2.AssetInfo(asset_id=3),
            ]
        )
    )
    btc, other, bare = infos
    assert btc.asset_id == 1
    assert btc.editorial.explorer_urls == ["https://b.example", "https://a.example"]
    assert btc.editorial.issue_date == "2009-01-03"
    # A known zero launch price is kept apart from an unknown one.
    assert btc.editorial.issue_price == AssetIssuePrice(amount="0", currency="USD")
    assert btc.editorial.github_url == "https://github.com/b"
    assert btc.editorial_updated_at == updated
    assert other.editorial.issue_price is None
    assert other.editorial_updated_at is None
    assert bare.editorial.description == ""
    assert bare.editorial.explorer_urls == []


async def test_list_asset_info_is_public_and_sends_the_ids() -> None:
    def respond(req: ParsedRequest) -> Message:
        sent = asset_info_pb2.ListAssetInfoRequest.FromString(req.body)
        return asset_info_pb2.ListAssetInfoResponse(
            asset_info=[asset_info_pb2.AssetInfo(asset_id=i) for i in sent.asset_ids or [9]]
        )

    async with _server(respond) as (url, _transport, requests):
        client = AsyncPolyester(
            api_url=url,
            hydrate_catalogs=False,
            api_key_id="ak_test",
            api_private_key=_PRIVATE_KEY,
        )
        try:
            some = await client.market_data.list_asset_info([1, 2])
            every = await client.market_data.list_asset_info()
            with pytest.raises(PolyesterValidationError):
                await client.market_data.list_asset_info([-1])
            with pytest.raises(PolyesterValidationError):
                await client.market_data.list_asset_info("1")  # type: ignore[arg-type]
        finally:
            await client.aclose()
    assert [info.asset_id for info in some] == [1, 2]
    assert [info.asset_id for info in every] == [9]
    assert len(requests) == 2
    assert [r.path for r in requests] == ["/marketdata.v1.MarketDataService/ListAssetInfo"] * 2
    assert list(asset_info_pb2.ListAssetInfoRequest.FromString(requests[1].body).asset_ids) == []
    assert not any(r.headers.get("x-api-key-id") for r in requests)


# --- route status --------------------------------------------------------------------------------


def _config() -> zipper_pb2.GetDepositWithdrawConfigResponse:
    return zipper_pb2.GetDepositWithdrawConfigResponse(
        chains=[zipper_pb2.ChainConfig(chain_id=2, code="ethereum")],
        assets=[
            zipper_pb2.AssetConfig(
                asset="USDT",
                ledger_id=3,
                quantity_scale=6,
                variants=[
                    zipper_pb2.AssetChainVariant(
                        zipped_asset_id=3,
                        chain_id=2,
                        deposit_status=zipper_pb2.NORMAL,
                        withdrawal_status=zipper_pb2.SUSPENDED,
                    ),
                    zipper_pb2.AssetChainVariant(zipped_asset_id=4, chain_id=2),
                    zipper_pb2.AssetChainVariant(
                        zipped_asset_id=5,
                        chain_id=2,
                        deposit_status=9,  # type: ignore[arg-type]
                        withdrawal_status=zipper_pb2.NORMAL,
                    ),
                ],
            )
        ],
    )


def test_route_status_reads_by_label_and_only_normal_accepts() -> None:
    config = deposit_withdraw_config_from_proto(_config())
    split, unknown, newer = config.assets[0].variants
    assert (split.deposit_status, split.withdrawal_status) == ("normal", "suspended")
    assert split.accepts_deposits() and not split.accepts_withdrawals()
    # STATUS_UNSPECIFIED is not known yet, which is not available.
    assert (unknown.deposit_status, unknown.withdrawal_status) == ("", "")
    assert not unknown.accepts_deposits() and not unknown.accepts_withdrawals()
    # A status newer than this SDK reads as its number and is not available.
    assert newer.deposit_status == "9"
    assert not newer.accepts_deposits() and newer.accepts_withdrawals()


def test_route_status_survives_the_catalog_and_supply_updates() -> None:
    catalog = build_zipper_catalog_data(deposit_withdraw_config_from_proto(_config()))
    chains = catalog.assets[0].chains
    assert [(c.deposit_status, c.withdrawal_status) for c in chains] == [
        ("normal", "suspended"),
        ("", ""),
        ("9", "normal"),
    ]
    assert chains[0].accepts_deposits() and not chains[0].accepts_withdrawals()
    updated = patch_zipper_catalog_supply(
        catalog, [ZippedAssetSupplyUpdate(zipped_asset_id=3, supply="5")]
    )
    chain = updated.assets[0].chains[0]
    assert chain.supply == "5"
    assert (chain.deposit_status, chain.withdrawal_status) == ("normal", "suspended")


def test_offset_timestamps_are_read_in_utc() -> None:
    (row,) = parse_statement_csv(
        HEADER + "2026-10-03T12:12:45.5+04:00,1,trade,trading,BTC,0.1,0,1.1,77,\r\n"
    )
    assert row.time == datetime(2026, 10, 3, 8, 12, 45, 500000, tzinfo=UTC)
    assert row.time.tzinfo == UTC
