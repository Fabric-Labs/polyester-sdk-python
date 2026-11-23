"""Public contract c35662b (0.93.5): all-or-nothing internal transfer batches and their
read, statement export cancel and download URL, the server time and the
timestamp window of a skew refusal, route supply status, partial wallet
reads, ladder outcomes, preview price band limits, asset market datapoints,
account activity and the refusal codes the API
now answers for triggers, OCOs and attached exits."""

from __future__ import annotations

import asyncio
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
from polyester.models import (
    ActivityActor,
    ActivityItem,
    CreateOrderRequest,
    ServerTime,
    ZippedAssetSupplyUpdate,
)
from polyester.types.money import Quantity
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)
from tests.unit.support import btc_market

_CREDS = make_test_credentials()
Answer = Callable[[ParsedRequest], HttpScript]
_OBSERVED = datetime(2026, 11, 17, 6, 30, 0, 123000, tzinfo=UTC)


def _ts(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


@asynccontextmanager
async def _client(answer: Answer, *, signed: bool = True, delay: float = 0.0):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        if delay:
            await asyncio.sleep(delay)
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
        it_pb2.GetInternalTransferBatchResponse(
            request_id="1234",
            status=it_pb2.BATCH_ACCEPTED,
            legs=[
                it_pb2.InternalTransferBatchLegResult(
                    leg_index=0,
                    status=it_pb2.LEG_CREDITED,
                    transfer_id="t0",
                    credited_at_ts_ns=1,
                )
            ],
        ),
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
    assert requests == []


async def test_wait_batch_never_returns_a_read_that_ends_after_its_deadline() -> None:
    # The batch is accepted, but the read only answers after the deadline.
    answer = _ok(_batch(it_pb2.BATCH_ACCEPTED, it_pb2.LEG_CREDITED))
    async with _client(answer, delay=0.3) as (client, _requests):
        started = asyncio.get_running_loop().time()
        with pytest.raises(PolyesterTimeoutError):
            await client.internal_transfers.wait_batch(request_id="1234", timeout=0.05)
        assert asyncio.get_running_loop().time() - started < 0.25


async def test_wait_batch_bounds_its_wait_between_reads(monkeypatch) -> None:
    monkeypatch.setattr("polyester.services.internal_transfers._BATCH_POLL_INITIAL", 5.0)
    answer = _ok(_batch(it_pb2.BATCH_PROCESSING, it_pb2.LEG_PROCESSING))
    async with _client(answer) as (client, requests):
        started = asyncio.get_running_loop().time()
        with pytest.raises(PolyesterTimeoutError):
            await client.internal_transfers.wait_batch(request_id="1234", timeout=0.2)
        assert asyncio.get_running_loop().time() - started < 1.0
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


@pytest.mark.parametrize(
    "reply",
    [
        export_pb2.GetStatementExportDownloadUrlResponse(
            expires_at=_ts(_OBSERVED), filename="statement-AAo.csv"
        ),
        export_pb2.GetStatementExportDownloadUrlResponse(
            url="https://files.example.test/s.csv", filename="statement-AAo.csv"
        ),
        export_pb2.GetStatementExportDownloadUrlResponse(
            url="https://files.example.test/s.csv", expires_at=_ts(_OBSERVED)
        ),
    ],
)
async def test_download_url_answer_missing_a_guaranteed_field_is_refused(reply) -> None:
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
    async with _client(_ok(reply)) as (client, requests):
        with pytest.raises(PolyesterTimeoutError):
            await client.statements.wait_export(export_id=format_id(77), timeout=0)
    assert requests == []


async def test_wait_export_never_returns_a_read_that_ends_after_its_deadline() -> None:
    reply = export_pb2.GetStatementExportResponse(
        export=_export(export_pb2.STATEMENT_EXPORT_STATUS_READY)
    )
    async with _client(_ok(reply), delay=0.3) as (client, _requests):
        started = asyncio.get_running_loop().time()
        with pytest.raises(PolyesterTimeoutError):
            await client.statements.wait_export(export_id=format_id(77), timeout=0.05)
        assert asyncio.get_running_loop().time() - started < 0.25


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
        ({"serverTimeMs": "9" * 5000}, None),
        ({"serverTimeMs": str(2**63)}, None),
        ({"serverTimeMs": 2**63}, None),
        ({"serverTimeMs": -5}, None),
        ({"serverTimeMs": 1.5}, None),
        (
            {"serverTimeMs": "1763361000123", "recvWindowMs": 2**32, "maxFutureMs": -1},
            ServerTime(server_time_ms=1_763_361_000_123),
        ),
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
    assert raised.value.status_code == 401


_HUGE_WINDOW = (
    b'{"code":"TIMESTAMP_SKEW","status":401,"detail":"d",'
    b'"timestampWindow":{"serverTimeMs":' + b"9" * 5000 + b',"recvWindowMs":5000}}'
)


async def test_unreadable_timestamp_window_keeps_the_skew_refusal_and_its_answer() -> None:
    # A number too long for Python to convert must not cost the refusal its
    # code, status or retry delay.
    answer = lambda _req: HttpScript.raw(  # noqa: E731
        401,
        headers=[("Content-Type", "application/problem+json"), ("Retry-After", "7")],
        body=_HUGE_WINDOW,
    )
    async with _client(answer) as (client, _):
        with pytest.raises(PolyesterTimestampSkewError) as raised:
            await client.statements.get_export(export_id=format_id(77))
    assert raised.value.timestamp_window is None
    assert (raised.value.status_code, raised.value.retry_after) == (401, 7)


@pytest.mark.parametrize(
    "body",
    [
        _HUGE_WINDOW,
        b'{"code":"TIMESTAMP_SKEW","timestampWindow":{"serverTimeMs":"' + b"9" * 5000 + b'"}}',
    ],
)
def test_realtime_login_skew_refusal_survives_unreadable_metadata(body: bytes) -> None:
    from polyester.realtime.auth import _auth_http_error

    error = _auth_http_error(status_code=401, label="realtime token", endpoint="/x", body=body)
    assert isinstance(error, PolyesterTimestampSkewError)
    assert (error.status_code, error.timestamp_window) == (401, None)


def test_realtime_login_skew_refusal_reads_its_window() -> None:
    from polyester.realtime.auth import _auth_http_error

    body = json.dumps(
        {"code": "TIMESTAMP_SKEW", "timestampWindow": {"serverTimeMs": "1763361000123"}}
    ).encode()
    error = _auth_http_error(status_code=401, label="realtime token", endpoint="/x", body=body)
    assert isinstance(error, PolyesterTimestampSkewError)
    assert error.timestamp_window == ServerTime(server_time_ms=1_763_361_000_123)


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


@pytest.mark.parametrize("status", [zipper_pb2.AVAILABLE, zipper_pb2.STALE])
def test_known_supply_without_its_observation_time_is_refused(status) -> None:
    with pytest.raises(PolyesterResponseContractError):
        deposit_withdraw_config_from_proto(_config(supply_q=1_500_000, supply_status=status))
    batch = zipper_pb2.ZippedAssetSupplyBatch(
        updates=[zipper_pb2.ZippedAssetSupplyUpdate(zipped_asset_id=7, supply_q=1, status=status)]
    )
    with pytest.raises(PolyesterResponseContractError):
        zipped_asset_supply_batch_from_proto(
            batch, quantity_scale_for_zipped_asset_id=lambda _zid: 6
        )


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

    config = _config(
        supply_q=1_000_000, supply_status=zipper_pb2.AVAILABLE, supply_observed_at=_ts(_OBSERVED)
    )
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
    preview = preview_order_from_proto(reply, market=btc_market())
    assert preview.rejection is not None
    assert preview.rejection.code == "PRICE_BAND_VIOLATION"
    assert preview.rejection.price_band_limit is not None
    assert preview.rejection.price_band_limit.ticks == 1_837_500_000_000
    reply.rejection.ClearField("price_band_limit_ticks")
    cleared = preview_order_from_proto(reply, market=btc_market())
    assert cleared.rejection is not None
    assert cleared.rejection.price_band_limit is None


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
            max_supply_unlimited=asset_info_pb2.AssetMarketFlag(
                source=asset_info_pb2.POLYESTER, as_of=_ts(_OBSERVED)
            ),
            rank=value(value="1", source=asset_info_pb2.COINMARKETCAP, as_of=_ts(_OBSERVED)),
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


_VALUE = dict(value="1", source=asset_info_pb2.COINMARKETCAP, as_of=_ts(_OBSERVED))


@pytest.mark.parametrize(
    "stats",
    [
        {"rank": asset_info_pb2.AssetMarketValue(**{**_VALUE, "value": ""})},
        {"rank": asset_info_pb2.AssetMarketValue(**{**_VALUE, "source": 0})},
        {"total_supply": asset_info_pb2.AssetMarketValue(value="1", source=1)},
        {"max_supply_unlimited": asset_info_pb2.AssetMarketFlag(as_of=_ts(_OBSERVED))},
        {"max_supply_unlimited": asset_info_pb2.AssetMarketFlag(source=1)},
    ],
)
def test_present_market_datapoint_without_its_provenance_is_refused(stats) -> None:
    market_stats = asset_info_pb2.AssetMarketStats(**stats)
    msg = asset_info_pb2.AssetInfo(asset_id=3, market_stats=market_stats)
    with pytest.raises(PolyesterResponseContractError):
        asset_info_from_proto(msg)


def test_activity_event_exposes_every_published_field() -> None:
    created = datetime(2026, 11, 17, 6, 30, 0, 123456, tzinfo=UTC)
    event = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(
            created_at=_ts(created),
            entity_kind=subaccounts_pb2.ACTIVITY_ENTITY_SESSION,
            event_action=subaccounts_pb2.ACTIVITY_ACTION_FAILED,
            source=subaccounts_pb2.ACTIVITY_SOURCE_API,
            ip="203.0.113.7",
            user_agent="wallet/1.0",
            subaccount_id=12,
            actor=subaccounts_pb2.ActivityActor(
                kind=subaccounts_pb2.ACTIVITY_ACTOR_UNAUTHENTICATED
            ),
            item=subaccounts_pb2.ActivityItem(name="sign-in"),
            details=subaccounts_pb2.ActivityDetails(
                session=subaccounts_pb2.ActivitySessionDetails(
                    failure=subaccounts_pb2.ACTIVITY_SIGN_IN_FAILURE_INVALID_SIGNATURE
                )
            ),
        )
    )
    assert event.created_at == created
    assert (event.entity_kind, event.event_action, event.source) == ("session", "failed", "api")
    assert (event.ip, event.user_agent) == ("203.0.113.7", "wallet/1.0")
    assert event.subaccount_id == format_id(12)
    assert event.actor == ActivityActor(kind="unauthenticated")
    assert event.item == ActivityItem(name="sign-in")
    assert event.details == {
        "session": {"failure": "ACTIVITY_SIGN_IN_FAILURE_INVALID_SIGNATURE"}
    }
    published = set(subaccounts_pb2.ActivityEvent.DESCRIPTOR.fields_by_name)
    assert published <= set(type(event).__struct_fields__)
    assert set(subaccounts_pb2.ActivityActor.DESCRIPTOR.fields_by_name) <= set(
        ActivityActor.__struct_fields__
    )


def test_activity_event_names_its_sub_account() -> None:
    event = subaccount_activity_event_from_proto(subaccounts_pb2.ActivityEvent(subaccount_id=12))
    assert event.subaccount_id == format_id(12)
    main = subaccount_activity_event_from_proto(subaccounts_pb2.ActivityEvent())
    assert main.subaccount_id == ""
    assert (main.actor, main.item, main.details) == (None, None, None)


_KEY_ID = "ak_" + "0123456789abcdef" * 2


def test_activity_actor_names_the_account_and_key_that_acted() -> None:
    event = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(
            actor=subaccounts_pb2.ActivityActor(
                kind=subaccounts_pb2.ACTIVITY_ACTOR_API_KEY,
                account_id=56,
                username="ada",
                api_key_id=_KEY_ID,
                api_key_kind=subaccounts_pb2.ACTIVITY_KEY_STRATEGY_BOT,
                api_key_label="grid bot",
            )
        )
    )
    assert event.actor == ActivityActor(
        kind="api_key",
        account_id=format_id(56),
        username="ada",
        api_key_id=_KEY_ID,
        api_key_kind="strategy_bot",
        api_key_label="grid bot",
    )
    system = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(
            actor=subaccounts_pb2.ActivityActor(
                kind=subaccounts_pb2.ACTIVITY_ACTOR_SYSTEM,
                system_reason=subaccounts_pb2.ACTIVITY_SYSTEM_ASSISTANT_PRESET_UPDATED,
            )
        )
    )
    assert system.actor == ActivityActor(
        kind="system", system_reason="assistant_preset_updated"
    )
    unknown = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(actor=subaccounts_pb2.ActivityActor(kind=99))
    )
    assert unknown.actor == ActivityActor(kind="99")


@pytest.mark.parametrize(
    ("item", "kind", "item_id"),
    [
        (subaccounts_pb2.ActivityItem(api_policy_id=99), "api_policy_id", format_id(99)),
        (subaccounts_pb2.ActivityItem(subaccount_id=12), "subaccount_id", format_id(12)),
        (subaccounts_pb2.ActivityItem(api_key_id=_KEY_ID), "api_key_id", _KEY_ID),
        (subaccounts_pb2.ActivityItem(mfa_factor_id="mfa_1"), "mfa_factor_id", "mfa_1"),
        (subaccounts_pb2.ActivityItem(name="recovery codes"), "", ""),
    ],
)
def test_activity_item_names_the_id_that_is_set(item, kind: str, item_id: str) -> None:
    item.name = item.name or "label"
    event = subaccount_activity_event_from_proto(subaccounts_pb2.ActivityEvent(item=item))
    assert event.item == ActivityItem(kind=kind, id=item_id, name=item.name)


def test_activity_details_show_opaque_ids_as_public_ids() -> None:
    details = subaccounts_pb2.ActivityDetails()
    details.policy.source_template_id = 7
    details.policy.source_template_revision = 3
    details.policy.strategy_bot_id = 8
    details.policy.actions.added.append(1)
    details.policy.subaccount_policy_id.to_id = 9
    event = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(details=details)
    )
    assert event.details is not None
    policy = event.details["policy"]
    assert policy["sourceTemplateId"] == format_id(7)
    assert policy["strategyBotId"] == format_id(8)
    # A revision is a count, not an ID: it stays protobuf JSON's decimal string.
    assert policy["sourceTemplateRevision"] == "3"
    assert set(policy["actions"]) == {"added"}
    # Only the side the event set is shown.
    assert policy["subaccountPolicyId"] == {"toId": format_id(9)}

    tags = subaccounts_pb2.ActivityDetails()
    tags.destination.tag_ids.added_ids.extend([12, 13])
    tags.destination.tag_ids.removed_ids.append(14)
    event = subaccount_activity_event_from_proto(subaccounts_pb2.ActivityEvent(details=tags))
    assert event.details == {
        "destination": {
            "tagIds": {
                "addedIds": [format_id(12), format_id(13)],
                "removedIds": [format_id(14)],
            }
        }
    }


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
        events=[subaccounts_pb2.ActivityEvent(subaccount_id=12)],
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
            api_key_id=_KEY_ID,
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
    assert sent.api_key_id == _KEY_ID
    assert sent.start_time.ToDatetime(tzinfo=UTC) == start
    assert sent.end_time.ToDatetime(tzinfo=UTC) == end
    assert (sent.limit, sent.page_token) == (200, "tok")
    (event,) = page.events
    assert event.subaccount_id == format_id(12)
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
        {"api_key_id": 34},
        {"api_key_id": ""},
        {"api_key_id": format_id(34)},
        {"api_key_id": "ak_" + "0" * 31},
        {"api_key_id": "AK_" + "0" * 32},
        {"api_key_id": "ak_" + "A" * 32},
        {"api_key_id": "ak_" + "0" * 32 + "\n"},
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


# --- refused WebSocket upgrades over a real socket -----------------------------------------------

_SESSIONS_PROBLEM = (
    b'{"type":"https://polyester.dev/problems/too-many-sessions-api-key",'
    b'"title":"Too Many Requests","status":429,"code":"TOO_MANY_SESSIONS_API_KEY",'
    b'"detail":"too many sessions for this API key","unrelated":' + b"9" * 5000 + b"}"
)


@asynccontextmanager
async def _refusing_ws_server(body: bytes):
    """A local WebSocket endpoint refusing every upgrade with HTTP 429."""
    from websockets.asyncio.server import ServerConnection, serve
    from websockets.http11 import Request

    def refuse(_connection: ServerConnection, _request: Request) -> Response:
        return Response(
            429,
            "Too Many Requests",
            Headers(
                {
                    "Content-Type": "application/problem+json",
                    "Retry-After": "7",
                    "Content-Length": str(len(body)),
                }
            ),
            body,
        )

    async def handler(_connection: ServerConnection) -> None:
        return None

    import logging

    async with serve(
        handler,
        "127.0.0.1",
        0,
        process_request=refuse,
        logger=logging.getLogger("tests.fake_ws_server"),
    ) as server:
        yield f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/ws"


async def _subscribe_generic(url: str) -> None:
    from polyester.realtime.client import AsyncRealtimeClient

    client = AsyncRealtimeClient(url)
    try:
        await client.subscribe_proto("trades:BTC-USDT", decode=lambda b: b, auto_reconnect=False)
    finally:
        await client.aclose()


async def _subscribe_private_orders(url: str) -> None:
    from polyester.realtime.private_orders import PrivateOrderStream

    async def token(*_args: object) -> str:
        return "fake-token"

    stream = PrivateOrderStream(url=url, fetch_connect_token=token, fetch_subscribe_token=token)
    try:
        await asyncio.wait_for(stream.subscribe(42), 5)
    finally:
        await stream.aclose()


@pytest.mark.parametrize(
    "dial", [_subscribe_generic, _subscribe_private_orders], ids=["generic", "private_orders"]
)
async def test_refused_upgrade_keeps_its_problem_despite_an_unreadable_integer(dial) -> None:
    # An unrelated integer too long to convert must not cost the refusal its
    # code, problem, status or retry delay.
    async with _refusing_ws_server(_SESSIONS_PROBLEM) as url:
        with pytest.raises(PolyesterRealtimeError) as raised:
            await dial(url)
    error = raised.value
    assert (error.code, error.status_code, error.retry_after) == (
        "TOO_MANY_SESSIONS_API_KEY",
        429,
        7,
    )
    assert error.problem is not None
    assert error.problem.code == "TOO_MANY_SESSIONS_API_KEY"
    assert error.problem.detail == "too many sessions for this API key"


def test_jsonrpc_answer_with_an_unconvertible_integer_is_a_typed_error() -> None:
    from polyester.chain.rpc import JsonRpcError, _decode_jsonrpc_envelope

    raw = b'{"jsonrpc":"2.0","id":1,"result":' + b"9" * 5000 + b"}"
    with pytest.raises(JsonRpcError):
        _decode_jsonrpc_envelope(raw, expected_id=1)
