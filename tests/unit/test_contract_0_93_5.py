"""Public contract 0.93.5: all-or-nothing internal transfer batches and their
read, statement export cancel and download URL, the server time and the
timestamp window of a skew refusal, route supply status, partial wallet
reads, ladder outcomes, preview price band limits, asset market datapoints,
account activity and the refusal codes the API
now answers for triggers, OCOs and attached exits."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp
from websockets.datastructures import Headers
from websockets.exceptions import InvalidStatus
from websockets.http11 import Response

from polyester import AsyncPolyester
from polyester._answer import refused_upgrade
from polyester._wire import map_connect_error
from polyester.catalogs.zipper import build_zipper_catalog_data
from polyester.catalogs.zipper_supply import patch_zipper_catalog_supply
from polyester.codecs.decode.asset_info import asset_info_from_proto
from polyester.codecs.decode.orders import preview_order_from_proto
from polyester.codecs.decode.sub_accounts import subaccount_activity_event_from_proto
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.decode.withdraw import wallet_balances_from_proto
from polyester.codecs.decode.zipper import (
    deposit_withdraw_config_from_proto,
    zipped_asset_supply_batch_from_proto,
)
from polyester.codecs.oco import create_oco_to_proto
from polyester.codecs.orders import create_order_to_proto
from polyester.codecs.scalars import format_id
from polyester.codecs.triggers import modify_trigger_to_proto
from polyester.errors import (
    PolyesterRealtimeError,
    PolyesterResponseContractError,
    PolyesterTimeoutError,
    PolyesterTimestampSkewError,
    PolyesterValidationError,
)
from polyester.gen.auth.v1 import auth_pb2, subaccounts_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.ledger.read.v1 import statement_export_pb2 as export_pb2
from polyester.gen.marketdata.v1 import asset_info_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.system.v1 import system_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as it_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import CreateOrderRequest, ServerTime, ZippedAssetSupplyUpdate
from polyester.types.money import Quantity
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()
Answer = Callable[[ParsedRequest], HttpScript]
_OBSERVED = datetime(2026, 11, 17, 6, 30, 0, 123000, tzinfo=UTC)


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


@asynccontextmanager
async def _client(answer: Answer, *, signed: bool = True):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return answer(req)

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id if signed else None,
        api_private_key=_CREDS.private_key if signed else None,
        hydrate_catalogs=False,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


def _ok(message: Message) -> Answer:
    return lambda _req: connect_proto_response(message.SerializeToString())


def _sequence(*messages: Message) -> Answer:
    pending = list(messages)

    def answer(_req: ParsedRequest) -> HttpScript:
        message = pending.pop(0) if len(pending) > 1 else pending[0]
        return connect_proto_response(message.SerializeToString())

    return answer


# --- internal transfer batches -------------------------------------------------------------------


def _batch(status: int, leg_status: int, *, request_id: str = "1234", legs: int = 2):
    return it_pb2.GetInternalTransferBatchResponse(
        request_id=request_id,
        status=status,
        legs=[
            it_pb2.InternalTransferBatchLegResult(
                leg_index=i,
                status=leg_status,
                transfer_id=f"t{i}",
                flow_id=f"f{i}" if leg_status == it_pb2.LEG_CREDITED else "",
                credited_at_ts_ns=1_763_000_000_000_000_001
                if leg_status == it_pb2.LEG_CREDITED
                else 0,
            )
            for i in range(legs)
        ],
    )


async def test_get_batch_reads_the_batch_it_names() -> None:
    reply = _batch(it_pb2.BATCH_ACCEPTED, it_pb2.LEG_CREDITED)
    async with _client(_ok(reply)) as (client, requests):
        batch = await client.internal_transfers.get_batch(request_id="1234")
    (request,) = requests
    assert request.path == "/transfer.v1.InternalTransferService/GetInternalTransferBatch"
    assert request.headers.get("x-api-signature")
    assert it_pb2.GetInternalTransferBatchRequest.FromString(request.body).request_id == "1234"
    assert (batch.request_id, batch.status) == ("1234", "accepted")
    assert [(leg.status, leg.flow_id) for leg in batch.legs] == [
        ("credited", "f0"),
        ("credited", "f1"),
    ]
    assert batch.legs[0].credited_at_ts_ns == 1_763_000_000_000_000_001


@pytest.mark.parametrize(
    "request_id", ["", "0", "0123", "12a", "１２", "1" * 40, " 12", 12, None, True]
)
async def test_get_batch_refuses_a_request_id_the_contract_refuses(request_id: Any) -> None:
    async with _client(_ok(it_pb2.GetInternalTransferBatchResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.internal_transfers.get_batch(request_id=request_id)
    assert requests == []


@pytest.mark.parametrize(
    "reply",
    [
        _batch(it_pb2.BATCH_ACCEPTED, it_pb2.LEG_CREDITED, request_id="999"),
        _batch(it_pb2.BATCH_ACCEPTED, it_pb2.LEG_CREDITED, request_id=""),
        _batch(it_pb2.BATCH_ACCEPTED, it_pb2.LEG_CREDITED, legs=0),
        _batch(it_pb2.BATCH_PROCESSING, it_pb2.LEG_CREDITED),
    ],
)
async def test_get_batch_refuses_an_answer_that_breaks_the_contract(reply) -> None:
    async with _client(_ok(reply)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            await client.internal_transfers.get_batch(request_id="1234")


async def test_wait_batch_reads_until_the_batch_is_final(monkeypatch) -> None:
    monkeypatch.setattr("polyester.services.internal_transfers._BATCH_POLL_INITIAL", 0.0)
    answer = _sequence(
        _batch(it_pb2.BATCH_PROCESSING, it_pb2.LEG_PROCESSING),
        _batch(it_pb2.BATCH_PROCESSING, it_pb2.LEG_PROCESSING),
        _batch(it_pb2.BATCH_REFUSED, it_pb2.LEG_NOT_MOVED),
    )
    async with _client(answer) as (client, requests):
        batch = await client.internal_transfers.wait_batch(request_id="1234")
    assert batch.status == "refused"
    assert [leg.status for leg in batch.legs] == ["not_moved", "not_moved"]
    assert len(requests) == 3


async def test_wait_batch_gives_up_after_its_timeout() -> None:
    answer = _ok(_batch(it_pb2.BATCH_PROCESSING, it_pb2.LEG_PROCESSING))
    async with _client(answer) as (client, requests):
        with pytest.raises(PolyesterTimeoutError):
            await client.internal_transfers.wait_batch(request_id="1234", timeout=0)
    assert len(requests) == 1


# --- statement exports ---------------------------------------------------------------------------


def _export(status: int, **fields) -> export_pb2.StatementExport:
    return export_pb2.StatementExport(export_id=77, status=status, **fields)


async def test_cancel_export_returns_the_canceled_export() -> None:
    reply = export_pb2.CancelStatementExportResponse(
        export=_export(export_pb2.STATEMENT_EXPORT_STATUS_CANCELED)
    )
    async with _client(_ok(reply)) as (client, requests):
        export = await client.statements.cancel_export(export_id=format_id(77))
    (request,) = requests
    assert request.path == "/ledger.read.v1.StatementExportService/CancelStatementExport"
    assert export_pb2.CancelStatementExportRequest.FromString(request.body).export_id == 77
    assert (export.export_id, export.status) == (format_id(77), "canceled")


async def test_cancel_export_refuses_an_answer_without_its_export() -> None:
    async with _client(_ok(export_pb2.CancelStatementExportResponse())) as (client, _):
        with pytest.raises(PolyesterResponseContractError):
            await client.statements.cancel_export(export_id=format_id(77))


async def test_download_url_is_a_secret_that_never_prints() -> None:
    url = "https://files.example.test/statement-77.csv?signature=abc"
    reply = export_pb2.GetStatementExportDownloadUrlResponse(
        url=url, expires_at=_ts(_OBSERVED), filename="statement-AAo.csv"
    )
    async with _client(_ok(reply)) as (client, requests):
        link = await client.statements.get_export_download_url(export_id=format_id(77))
    assert requests[0].path.endswith("/GetStatementExportDownloadUrl")
    assert link.url.reveal() == url
    assert url not in repr(link) and url not in str(link.url) and url not in f"{link.url}"
    assert (link.expires_at, link.filename) == (_OBSERVED, "statement-AAo.csv")


async def test_download_url_answer_without_a_url_is_refused() -> None:
    reply = export_pb2.GetStatementExportDownloadUrlResponse(filename="statement-AAo.csv")
    async with _client(_ok(reply)) as (client, _):
        with pytest.raises(PolyesterResponseContractError):
            await client.statements.get_export_download_url(export_id=format_id(77))


async def test_list_exports_reads_the_root_accounts_exports_in_progress() -> None:
    reply = export_pb2.ListStatementExportsResponse(
        exports=[_export(export_pb2.STATEMENT_EXPORT_STATUS_QUEUED)],
        in_progress_exports=3,
        max_in_progress_exports=5,
    )
    async with _client(_ok(reply)) as (client, _):
        page = await client.statements.list_exports()
    assert (page.in_progress_exports, page.max_in_progress_exports) == (3, 5)


@pytest.mark.parametrize(
    ("final", "label"),
    [
        (export_pb2.STATEMENT_EXPORT_STATUS_READY, "ready"),
        (export_pb2.STATEMENT_EXPORT_STATUS_FAILED, "failed"),
        (export_pb2.STATEMENT_EXPORT_STATUS_EXPIRED, "expired"),
        (export_pb2.STATEMENT_EXPORT_STATUS_CANCELED, "canceled"),
    ],
)
async def test_wait_export_stops_at_every_final_status(monkeypatch, final, label) -> None:
    monkeypatch.setattr("polyester.services.statements._EXPORT_POLL_INITIAL", 0.0)
    answer = _sequence(
        export_pb2.GetStatementExportResponse(
            export=_export(export_pb2.STATEMENT_EXPORT_STATUS_QUEUED)
        ),
        export_pb2.GetStatementExportResponse(
            export=_export(export_pb2.STATEMENT_EXPORT_STATUS_PROCESSING)
        ),
        export_pb2.GetStatementExportResponse(export=_export(final)),
    )
    async with _client(answer) as (client, requests):
        export = await client.statements.wait_export(export_id=format_id(77))
    assert export.status == label
    assert len(requests) == 3


async def test_wait_export_gives_up_after_its_timeout() -> None:
    reply = export_pb2.GetStatementExportResponse(
        export=_export(export_pb2.STATEMENT_EXPORT_STATUS_PROCESSING)
    )
    async with _client(_ok(reply)) as (client, _):
        with pytest.raises(PolyesterTimeoutError):
            await client.statements.wait_export(export_id=format_id(77), timeout=0)


def test_statements_no_longer_offer_the_removed_paged_export() -> None:
    from polyester.services.statements import AsyncStatementsService

    assert not hasattr(AsyncStatementsService, "export")
    assert not hasattr(AsyncStatementsService, "export_page")


# --- server time and the timestamp window --------------------------------------------------------


async def test_get_time_is_public_and_reads_the_server_clock() -> None:
    reply = system_pb2.GetTimeResponse(server_time_ms=1_763_361_000_123)
    async with _client(_ok(reply), signed=False) as (client, requests):
        server = await client.get_time()
    (request,) = requests
    assert request.path == "/system.v1.SystemService/GetTime"
    assert not request.headers.get("x-api-signature")
    assert server == ServerTime(server_time_ms=1_763_361_000_123)
    assert server.server_time == datetime(2025, 11, 17, 6, 30, 0, 123000, tzinfo=UTC)


async def test_get_time_refuses_an_answer_without_a_time() -> None:
    async with _client(_ok(system_pb2.GetTimeResponse()), signed=False) as (client, _):
        with pytest.raises(PolyesterResponseContractError):
            await client.get_time()


def test_skew_refusal_carries_the_servers_timestamp_window() -> None:
    detail = auth_pb2.AuthErrorDetail(
        code=auth_pb2.AUTH_TIMESTAMP_SKEW,
        timestamp_window=auth_pb2.TimestampWindow(
            server_time_ms=1_763_361_000_123, recv_window_ms=5000, max_future_ms=1000
        ),
    )
    error = map_connect_error(
        ConnectError(Code.UNAUTHENTICATED, "timestamp skew", details=[detail])
    )
    assert isinstance(error, PolyesterTimestampSkewError)
    assert error.timestamp_window == ServerTime(
        server_time_ms=1_763_361_000_123, recv_window_ms=5000, max_future_ms=1000
    )
    without = map_connect_error(
        ConnectError(
            Code.UNAUTHENTICATED,
            "timestamp skew",
            details=[auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_TIMESTAMP_SKEW)],
        )
    )
    assert isinstance(without, PolyesterTimestampSkewError)
    assert without.timestamp_window is None


@pytest.mark.parametrize(
    ("window", "expected"),
    [
        (
            {"serverTimeMs": "1763361000123", "recvWindowMs": 5000, "maxFutureMs": 1000},
            ServerTime(server_time_ms=1_763_361_000_123, recv_window_ms=5000, max_future_ms=1000),
        ),
        ({"serverTimeMs": 1_763_361_000_123}, ServerTime(server_time_ms=1_763_361_000_123)),
        ({"serverTimeMs": "abc"}, None),
        ({"serverTimeMs": "١٢"}, None),
        ({"serverTimeMs": True}, None),
        ("not an object", None),
    ],
)
async def test_rest_skew_problem_carries_its_timestamp_window(window, expected) -> None:
    problem = {
        "type": "https://polyester.dev/problems/timestamp-skew",
        "title": "Unauthorized",
        "status": 401,
        "code": "TIMESTAMP_SKEW",
        "detail": "timestamp outside the receive window",
        "timestampWindow": window,
    }
    async with _client(lambda _req: HttpScript.json(401, problem)) as (client, _):
        with pytest.raises(PolyesterTimestampSkewError) as raised:
            await client.statements.get_export(export_id=format_id(77))
    assert raised.value.timestamp_window == expected


# --- route supply status -------------------------------------------------------------------------


def _config(**variant) -> zipper_pb2.GetDepositWithdrawConfigResponse:
    return zipper_pb2.GetDepositWithdrawConfigResponse(
        assets=[
            zipper_pb2.AssetConfig(
                asset="USDT",
                ledger_id=42,
                quantity_scale=6,
                variants=[zipper_pb2.AssetChainVariant(zipped_asset_id=7, chain_id=1, **variant)],
            )
        ]
    )


@pytest.mark.parametrize(
    ("variant", "supply", "status", "observed"),
    [
        (
            dict(
                supply_q=1_500_000,
                supply_status=zipper_pb2.AVAILABLE,
                supply_observed_at=_ts(_OBSERVED),
            ),
            "1.5",
            "available",
            _OBSERVED,
        ),
        (
            dict(supply_q=0, supply_status=zipper_pb2.STALE, supply_observed_at=_ts(_OBSERVED)),
            "0",
            "stale",
            _OBSERVED,
        ),
        (dict(supply_status=zipper_pb2.MISSING), None, "missing", None),
        # A status the contract never sends, or none, names no known supply.
        (dict(supply_q=1_500_000), None, "", None),
    ],
)
def test_route_supply_is_set_only_while_known(variant, supply, status, observed) -> None:
    (asset,) = deposit_withdraw_config_from_proto(_config(**variant)).assets
    (route,) = asset.variants
    assert (route.supply, route.supply_status, route.supply_observed_at) == (
        supply,
        status,
        observed,
    )
    assert route.known_supply() == supply


def test_supply_stream_update_carries_its_status_and_patches_the_catalog() -> None:
    batch = zipper_pb2.ZippedAssetSupplyBatch(
        updates=[
            zipper_pb2.ZippedAssetSupplyUpdate(
                zipped_asset_id=7,
                supply_q=1_500_000,
                status=zipper_pb2.STALE,
                observed_at=_ts(_OBSERVED),
            )
        ]
    )
    (update,) = zipped_asset_supply_batch_from_proto(
        batch, quantity_scale_for_zipped_asset_id=lambda _zid: 6
    ).updates
    assert update == ZippedAssetSupplyUpdate(
        zipped_asset_id=7, supply="1.5", status="stale", observed_at=_OBSERVED
    )

    config = _config(supply_q=1_000_000, supply_status=zipper_pb2.AVAILABLE)
    config.chains.add(chain_id=1, code="ETH")
    catalog = build_zipper_catalog_data(deposit_withdraw_config_from_proto(config))
    assert catalog.assets[0].chains[0].supply_status == "available"
    patched = patch_zipper_catalog_supply(catalog, [update])
    (chain,) = patched.assets[0].chains
    assert (chain.supply, chain.supply_status, chain.supply_observed_at) == (
        "1.5",
        "stale",
        _OBSERVED,
    )


# --- wallet balances -----------------------------------------------------------------------------


def test_wallet_read_lists_the_assets_it_could_not_read() -> None:
    reply = withdraw_pb2.GetWalletBalancesResponse(
        smart_account_address="0xabc",
        unavailable_assets=[
            withdraw_pb2.UnavailableWalletAsset(
                zipped_asset_id=3,
                unified_asset_id=4,
                chain_id=5,
                ztoken_address="0xz",
                reason=withdraw_pb2.READ_FAILED,
            ),
            withdraw_pb2.UnavailableWalletAsset(zipped_asset_id=9, reason=99),
        ],
    )
    balances = wallet_balances_from_proto(reply)
    assert not balances.is_complete
    first, future = balances.unavailable_assets
    assert (first.zipped_asset_id, first.unified_asset_id, first.chain_id) == (3, 4, 5)
    assert (first.ztoken_address, first.reason) == ("0xz", "read_failed")
    assert future.reason == "99"
    assert wallet_balances_from_proto(withdraw_pb2.GetWalletBalancesResponse()).is_complete


# --- ladder outcome ------------------------------------------------------------------------------


def test_ladder_reads_its_level_counts_and_outcome() -> None:
    trigger = triggers_pb2.Trigger(
        trigger_id=5,
        symbol_id=1,
        ladder_state=triggers_pb2.LadderDetails(
            ladder_levels=5,
            requested_levels=5,
            placed_levels=4,
            rejected_levels=1,
            canceled_levels=2,
            outcome=triggers_pb2.MIXED_REJECTIONS,
        ),
    )
    ladder = trigger_from_proto(trigger).details.ladder  # type: ignore[union-attr]
    assert ladder is not None
    assert (
        ladder.requested_levels,
        ladder.placed_levels,
        ladder.rejected_levels,
        ladder.canceled_levels,
        ladder.outcome,
    ) == (5, 4, 1, 2, "mixed_rejections")
    trigger.ladder_state.outcome = 0
    assert trigger_from_proto(trigger).details.ladder.outcome == ""  # type: ignore[union-attr]
    trigger.ladder_state.outcome = 42
    assert trigger_from_proto(trigger).details.ladder.outcome == "42"  # type: ignore[union-attr]


# --- preview price band --------------------------------------------------------------------------


def test_refused_preview_names_the_price_band_limit() -> None:
    reply = orders_pb2.PreviewOrderResponse(
        admissible=False,
        rejection=orders_pb2.ErrorDetail(
            code=orders_pb2.ERROR_CODE_PRICE_BAND_VIOLATION,
            price_band_limit_ticks=1_837_500_000_000,
        ),
        evaluated_at=_ts(_OBSERVED),
    )
    preview = preview_order_from_proto(reply)
    assert preview.rejection is not None
    assert preview.rejection.code == "PRICE_BAND_VIOLATION"
    assert preview.rejection.price_band_limit is not None
    assert preview.rejection.price_band_limit.ticks == 1_837_500_000_000
    reply.rejection.ClearField("price_band_limit_ticks")
    assert preview_order_from_proto(reply).rejection.price_band_limit is None  # type: ignore[union-attr]


# --- asset market datapoints and account activity ------------------------------------------------


def test_asset_info_reads_its_market_datapoints() -> None:
    value = asset_info_pb2.AssetMarketValue
    msg = asset_info_pb2.AssetInfo(
        asset_id=3,
        market_stats=asset_info_pb2.AssetMarketStats(
            circulating_supply=value(
                value="19800000.123456789",
                source=asset_info_pb2.COINMARKETCAP,
                as_of=_ts(_OBSERVED),
            ),
            max_supply_unlimited=asset_info_pb2.AssetMarketFlag(source=asset_info_pb2.POLYESTER),
            rank=value(value="1", source=asset_info_pb2.COINMARKETCAP),
        ),
    )
    info = asset_info_from_proto(msg)
    stats = info.market_stats
    assert stats is not None
    assert stats.circulating_supply is not None
    assert stats.circulating_supply.value == "19800000.123456789"
    assert (stats.circulating_supply.source, stats.circulating_supply.as_of) == (
        "coinmarketcap",
        _OBSERVED,
    )
    assert stats.max_supply is None and stats.total_supply is None
    assert stats.max_supply_unlimited is not None
    assert stats.max_supply_unlimited.source == "polyester"
    assert stats.rank is not None and stats.rank.value == "1"
    assert asset_info_from_proto(asset_info_pb2.AssetInfo(asset_id=3)).market_stats is None


def test_activity_event_names_its_sub_account_and_acting_key() -> None:
    event = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(subaccount_id=12, actor_api_key_id=34)
    )
    assert (event.subaccount_id, event.actor_api_key_id) == (format_id(12), format_id(34))
    main = subaccount_activity_event_from_proto(subaccounts_pb2.ActivityEvent())
    assert (main.subaccount_id, main.actor_api_key_id) == ("", "")


# --- refusal codes for trigger, OCO and attached exit fields -------------------------------------


def _code(call: Callable[[], Any]) -> str | None:
    with pytest.raises(PolyesterValidationError) as refused:
        call()
    return refused.value.code


def test_empty_trigger_modify_carries_trigger_patch_empty() -> None:
    assert _code(lambda: modify_trigger_to_proto(trigger_id="9")) == (
        "ERROR_CODE_TRIGGER_PATCH_EMPTY"
    )


def _oco(**overrides: Any):
    args: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "sell",
        "qty": "0.1",
        "take_profit": {"trigger_price": "110"},
        "stop_loss": {"trigger_price": "90"},
        "quantity_scale": 8,
    }
    args.update(overrides)
    return create_oco_to_proto(**args)


@pytest.mark.parametrize("client_list_id", ["", " a", "a" * 37, "a b", "é", 7])
def test_bad_client_list_id_carries_client_list_id_invalid(client_list_id: Any) -> None:
    assert _code(lambda: _oco(client_list_id=client_list_id)) == (
        "ERROR_CODE_CLIENT_LIST_ID_INVALID"
    )


async def test_list_filter_with_a_bad_client_list_id_is_refused_before_sending() -> None:
    async with _client(_ok(triggers_pb2.ListTriggersResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError) as refused:
            await client.triggers.list(client_list_id="bad id")
    assert refused.value.code == "ERROR_CODE_CLIENT_LIST_ID_INVALID"
    assert requests == []


@pytest.mark.parametrize("qty", ["0", "-1"])
def test_oco_quantity_carries_trigger_qty_invalid(qty: str) -> None:
    assert _code(lambda: _oco(qty=qty)) == "ERROR_CODE_TRIGGER_QTY_INVALID"


def _order_with(risk: dict[str, Any], *, side: str = "buy"):
    request = CreateOrderRequest(
        symbol="BTC-USDT",
        symbol_id=1,
        side=side,
        order_type="limit",
        price="100",
        qty=Quantity.from_scaled(1, scale=8),
        attached_risk=risk,  # type: ignore[arg-type]
    )
    return create_order_to_proto(request, quantity_scale=8)


_TRAIL = {"trailing_distance_bps": 100}
_TICKS = "ERROR_CODE_SLIPPAGE_TICKS_INVALID"
_BPS = "ERROR_CODE_SLIPPAGE_BPS_INVALID"
_MAX = "ERROR_CODE_MAX_SLIPPAGE_INVALID"
_DISTANCE = "ERROR_CODE_TRAILING_DISTANCE_INVALID"


@pytest.mark.parametrize(
    ("risk", "code"),
    [
        (
            {"trailing_stop": {**_TRAIL, "max_slippage_ticks": -1}},
            "ERROR_CODE_SLIPPAGE_TICKS_INVALID",
        ),
        ({"trailing_stop": {**_TRAIL, "max_slippage_bps": 0}}, _BPS),
        ({"trailing_stop": {**_TRAIL, "max_slippage_bps": -5}}, _BPS),
        (
            {"trailing_stop": {**_TRAIL, "max_slippage_bps": 10_000}},
            "ERROR_CODE_MAX_SLIPPAGE_INVALID",
        ),
        (
            {"trailing_stop": {**_TRAIL, "activation_price_ticks": -1}},
            "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_INVALID",
        ),
        (
            {"trailing_stop": {**_TRAIL, "activation_price": "-1"}},
            "ERROR_CODE_TRIGGER_ACTIVATION_PRICE_INVALID",
        ),
        ({"trailing_stop": {"trailing_distance_bps": 0}}, _DISTANCE),
        (
            {"trailing_stop": {"trailing_distance_ticks": -1}},
            "ERROR_CODE_TRAILING_DISTANCE_INVALID",
        ),
        ({"take_profit": {"trigger_price": "-1"}}, "ERROR_CODE_TRIGGER_PRICE_INVALID"),
        ({"stop_loss": {"trigger_price_ticks": 0}}, "ERROR_CODE_TRIGGER_PRICE_INVALID"),
        (
            {"take_profit": {"trigger_price": "110", "order_type": "limit", "limit_price": "-1"}},
            "ERROR_CODE_BAD_PRICE",
        ),
    ],
)
def test_attached_exit_refusal_carries_the_apis_code(risk, code) -> None:
    assert _code(lambda: _order_with(risk)) == code


# --- refused WebSocket upgrades ------------------------------------------------------------------


def test_refused_upgrade_reads_the_problem_code() -> None:
    body = {
        "type": "https://polyester.dev/problems/too-many-sessions-api-key",
        "title": "Too Many Requests",
        "status": 429,
        "code": "TOO_MANY_SESSIONS_API_KEY",
        "detail": "too many sessions for this API key",
    }
    refused = InvalidStatus(
        Response(
            429,
            "Too Many Requests",
            Headers({"Retry-After": "5", "Content-Type": "application/problem+json"}),
            json.dumps(body).encode(),
        )
    )
    error = refused_upgrade(refused, "trade WebSocket connection failed")
    assert isinstance(error, PolyesterRealtimeError)
    assert (error.code, error.status_code, error.retry_after) == (
        "TOO_MANY_SESSIONS_API_KEY",
        429,
        5,
    )
    assert error.problem is not None and error.problem.code == "TOO_MANY_SESSIONS_API_KEY"


@pytest.mark.parametrize("body", [b"", b"plain text", b"{}", b"[1]", b"\xff"])
def test_refused_upgrade_without_a_problem_keeps_only_its_status(body: bytes) -> None:
    error = refused_upgrade(
        InvalidStatus(Response(426, "Upgrade Required", Headers(), body)), "failed"
    )
    assert isinstance(error, PolyesterRealtimeError)
    assert (error.code, error.problem, error.status_code) == (None, None, 426)


# --- account activity ----------------------------------------------------------------------------


async def test_list_account_activity_sends_every_filter_exactly() -> None:
    from polyester.gen.auth.v1 import activity_pb2

    reply = activity_pb2.ListAccountActivityResponse(
        events=[subaccounts_pb2.ActivityEvent(subaccount_id=12, actor_api_key_id=34)],
        next_page_token="next",
    )
    start = datetime(2026, 11, 1, tzinfo=UTC)
    end = datetime(2026, 11, 17, 0, 0, 0, 123456, tzinfo=UTC)
    async with _client(_ok(reply)) as (client, requests):
        page = await client.sub_accounts.list_account_activity(
            sub_account_ids=[format_id(12), 13],
            include_main_account=True,
            entity_kinds=["session", "ACTIVITY_ENTITY_API_KEY"],
            event_actions=["created", "failed"],
            sources=["api"],
            api_key_id=format_id(34),
            start_time=start,
            end_time=end,
            limit=200,
            page_token="tok",
        )
    (request,) = requests
    assert request.path == "/auth.v1.AccountActivityService/ListAccountActivity"
    assert request.headers.get("x-api-signature")
    sent = activity_pb2.ListAccountActivityRequest.FromString(request.body)
    assert list(sent.subaccount_ids) == [12, 13] and sent.include_main_account
    assert list(sent.entity_kinds) == [
        subaccounts_pb2.ACTIVITY_ENTITY_SESSION,
        subaccounts_pb2.ACTIVITY_ENTITY_API_KEY,
    ]
    assert list(sent.event_actions) == [
        subaccounts_pb2.ACTIVITY_ACTION_CREATED,
        subaccounts_pb2.ACTIVITY_ACTION_FAILED,
    ]
    assert list(sent.sources) == [subaccounts_pb2.ACTIVITY_SOURCE_API]
    assert sent.api_key_id == 34
    assert sent.start_time.ToDatetime(tzinfo=UTC) == start
    assert sent.end_time.ToDatetime(tzinfo=UTC) == end
    assert (sent.limit, sent.page_token) == (200, "tok")
    (event,) = page.events
    assert (event.subaccount_id, event.actor_api_key_id) == (format_id(12), format_id(34))
    assert page.next_page_token == "next"


async def test_list_account_activity_sends_no_filter_when_none_is_given() -> None:
    from polyester.gen.auth.v1 import activity_pb2

    async with _client(_ok(activity_pb2.ListAccountActivityResponse())) as (client, requests):
        await client.sub_accounts.list_account_activity()
    sent = activity_pb2.ListAccountActivityRequest.FromString(requests[0].body)
    assert sent == activity_pb2.ListAccountActivityRequest()


_START = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sub_account_ids": [0]},
        {"sub_account_ids": [""]},
        {"sub_account_ids": ["12", "12"]},
        {"sub_account_ids": [12, 12]},
        {"sub_account_ids": list(range(1, 102))},
        {"sub_account_ids": "abc"},
        {"include_main_account": 1},
        {"entity_kinds": ["unspecified"]},
        {"entity_kinds": ["nope"]},
        {"entity_kinds": ["session", "SESSION"]},
        {"entity_kinds": "session"},
        {"event_actions": [""]},
        {"sources": ["ápi"]},
        {"api_key_id": 0},
        {"api_key_id": ""},
        {"start_time": datetime(2026, 11, 1)},
        {"start_time": _START, "end_time": _START},
        {"limit": 0},
        {"limit": 201},
        {"limit": True},
        {"page_token": "x" * 513},
    ],
)
async def test_list_account_activity_refuses_what_the_contract_refuses(kwargs) -> None:
    from polyester.gen.auth.v1 import activity_pb2

    async with _client(_ok(activity_pb2.ListAccountActivityResponse())) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.sub_accounts.list_account_activity(**kwargs)
    assert requests == []


async def test_iter_account_activity_follows_pages_with_the_same_filters() -> None:
    from polyester.gen.auth.v1 import activity_pb2

    pages = {
        "": activity_pb2.ListAccountActivityResponse(
            events=[subaccounts_pb2.ActivityEvent(subaccount_id=1)], next_page_token="p2"
        ),
        "p2": activity_pb2.ListAccountActivityResponse(
            events=[subaccounts_pb2.ActivityEvent(subaccount_id=2)]
        ),
    }

    def answer(req: ParsedRequest) -> HttpScript:
        sent = activity_pb2.ListAccountActivityRequest.FromString(req.body)
        return connect_proto_response(pages[sent.page_token].SerializeToString())

    async with _client(answer) as (client, requests):
        events = [
            event
            async for event in client.sub_accounts.iter_account_activity(sources=["api"])
        ]
    assert [event.subaccount_id for event in events] == [format_id(1), format_id(2)]
    sent = [activity_pb2.ListAccountActivityRequest.FromString(r.body) for r in requests]
    assert [list(s.sources) for s in sent] == [[subaccounts_pb2.ACTIVITY_SOURCE_API]] * 2
