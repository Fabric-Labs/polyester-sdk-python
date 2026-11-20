"""A lifecycle flow keeps its amount, asset, transactions, route, times and
progress on every read and update: list_flows, get_flow, the account flows,
the transaction lookups, the realtime flow updates and the JSON decoders."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from google.protobuf import json_format
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.codecs.decode.lifecycle import flow_summary_from_proto
from polyester.codecs.realtime_decode import decode_flow_detail_bytes, decode_flow_summary_bytes
from polyester.codecs.wire_decode import decode_lifecycle_flow, decode_lifecycle_flows_list
from polyester.errors import PolyesterResponseContractError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2 as lr
from polyester.gen.chain.lifecycle.v1 import types_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.models import (
    LifecycleFlowProgress,
    LifecycleFlowSummary,
    LifecycleFlowTimelineItem,
    LifecycleRequestFee,
)
from polyester.types.money import AssetAmount, QuantityDomain
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()

# A flow summary in the shape of the API's JSON answer: an open withdrawal with
# its amount, fee, transactions, route, times, current progress and timeline.
OPEN_WITHDRAW_JSON = """{
 "smartAccountAddress": "0x00000000000000000000000000000000000000a1",
 "flowId": "flow_UZBpp6Kx7uX",
 "flowKind": "KIND_WITHDRAW",
 "currentStep": "FLOW_STEP_VALIDATION",
 "assetIds": {"zippedAssetId": 3, "unifiedAssetId": 1},
 "polyesterChainId": 2,
 "amountE18": {"hi": "1", "lo": "5000000000000000000"},
 "requestFee": {
  "assetIds": {"zippedAssetId": 3, "unifiedAssetId": 1},
  "amountE18": {"lo": "720000000000000000"},
  "recipientAddress": "0x00000000000000000000000000000000000000f1",
  "status": "REQUEST_FEE_STATUS_LOCKED"
 },
 "sourceTxHash": "0x6bb813ce477bf3aa09eb66315f10b2ae365a4d78285eba5e5cb6e09067f3a9b0",
 "txOccurrenceIndex": "8",
 "sourceAddress": "0x00000000000000000000000000000000000000a1",
 "destinationAddress": "0x00000000000000000000000000000000000000b2",
 "latestTxRef": "11455311618482410803791580314813518967",
 "sourceDomain": "DOMAIN_FUNDING",
 "destinationDomain": "DOMAIN_EXTERNAL_CHAIN",
 "latestLifecycleSource": "SOURCE_LEDGER",
 "startedAtUnixMs": "1795113306000",
 "updatedAtUnixMs": "1795113325000",
 "lastActivityAtUnixMs": "1795113325500",
 "isOpen": true,
 "currentStepSequence": 2,
 "currentProgress": {
  "currentStepStartedAtUnixMs": "1795113310000",
  "currentStepExpectedDurationMs": "11000",
  "currentConfirmations": 1,
  "requiredConfirmations": 12,
  "approveCount": 2,
  "rejectCount": 1,
  "validatorCount": 5,
  "requiredApprovals": 3,
  "requiredRejections": 3
 },
 "progressTimeline": [
  {"sequence": 1, "step": "FLOW_STEP_REQUEST", "status": "TIMELINE_STATUS_COMPLETED",
   "expectedDurationMs": "3000"},
  {"sequence": 2, "step": "FLOW_STEP_VALIDATION", "status": "TIMELINE_STATUS_CURRENT"},
  {"sequence": 3, "step": "FLOW_STEP_EXECUTION", "status": "TIMELINE_STATUS_PLANNED",
   "expectedDurationMs": "2000"}
 ],
 "estimatedCompletionUnixMs": "1795113347903"
}"""


def _open_withdraw() -> lr.FlowSummaryView:
    return json_format.Parse(OPEN_WITHDRAW_JSON, lr.FlowSummaryView())


def _ms(value: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=value)


def _check_time(got: datetime | None, want_ms: int) -> None:
    assert got == _ms(want_ms)
    assert got is not None and got.tzinfo is UTC


def _check_ledger_amount(got: AssetAmount | None, scaled: int, asset_id: int) -> None:
    assert got is not None
    assert got.scaled == scaled and isinstance(got.scaled, int)
    assert got.scale == 18
    assert got.domain is QuantityDomain.LEDGER_E18
    assert got.asset_id == asset_id


def _check_open_withdraw(flow: LifecycleFlowSummary) -> None:
    """Every field OPEN_WITHDRAW_JSON sets."""
    assert (flow.intent_id, flow.flow_kind, flow.latest_step, flow.is_open) == (
        "flow_UZBpp6Kx7uX",
        "withdraw",
        "validation",
        True,
    )
    assert (flow.zipped_asset_id, flow.unified_asset_id, flow.polyester_chain_id) == (3, 1, 2)
    # hi=1, lo=5e18: 2**64 + 5e18, past 64 bits, exact.
    _check_ledger_amount(flow.amount, 23446744073709551616, 1)
    assert flow.source_tx_hash == (
        "0x6bb813ce477bf3aa09eb66315f10b2ae365a4d78285eba5e5cb6e09067f3a9b0"
    )
    assert flow.tx_occurrence_index == 8
    assert flow.latest_tx_ref == "11455311618482410803791580314813518967"
    assert (flow.source_domain, flow.destination_domain) == ("funding", "external_chain")
    _check_time(flow.started_at, 1795113306000)
    _check_time(flow.updated_at, 1795113325000)
    _check_time(flow.last_activity_at, 1795113325500)
    _check_time(flow.estimated_completion_at, 1795113347903)
    assert flow.terminal_at is None
    fee = flow.request_fee
    assert isinstance(fee, LifecycleRequestFee)
    assert (fee.zipped_asset_id, fee.unified_asset_id) == (3, 1)
    assert fee.recipient_address == "0x00000000000000000000000000000000000000f1"
    assert fee.status == "locked"
    _check_ledger_amount(fee.amount, 720000000000000000, 1)
    assert flow.current_step_sequence == 2
    progress = flow.current_progress
    assert isinstance(progress, LifecycleFlowProgress)
    _check_time(progress.current_step_started_at, 1795113310000)
    assert (
        progress.current_step_expected_duration_ms,
        progress.current_confirmations,
        progress.required_confirmations,
        progress.approve_count,
        progress.reject_count,
        progress.validator_count,
        progress.required_approvals,
        progress.required_rejections,
    ) == (11000, 1, 12, 2, 1, 5, 3, 3)
    assert flow.progress_timeline == [
        LifecycleFlowTimelineItem(
            sequence=1, step="request", status="completed", expected_duration_ms=3000
        ),
        LifecycleFlowTimelineItem(sequence=2, step="validation", status="current"),
        LifecycleFlowTimelineItem(
            sequence=3, step="execution", status="planned", expected_duration_ms=2000
        ),
    ]
    assert not hasattr(flow, "latest_lifecycle_source")


Answer = Callable[[ParsedRequest], HttpScript]


def _ok(message: Message) -> Answer:
    return lambda _req: connect_proto_response(message.SerializeToString())


@asynccontextmanager
async def _client(answer: Answer):
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
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


async def test_list_flows_keeps_amount_transactions_and_times() -> None:
    async with _client(_ok(lr.ListFlowsResponse(flows=[_open_withdraw()]))) as (client, _):
        page = await client.lifecycle.list_flows(limit=1)
    assert len(page.flows) == 1
    _check_open_withdraw(page.flows[0])


async def test_get_flow_keeps_amount_transactions_and_times() -> None:
    reply = lr.GetFlowResponse(flow=lr.FlowDetailView(summary=_open_withdraw()))
    async with _client(_ok(reply)) as (client, _):
        flow = await client.lifecycle.get_flow(flow_id="flow_UZBpp6Kx7uX")
    _check_open_withdraw(flow)


async def test_account_flows_keep_amount_transactions_and_times() -> None:
    reply = lr.ListAccountFlowsResponse(flows=[_open_withdraw()])
    async with _client(_ok(reply)) as (client, _):
        page = await client.lifecycle.list_account_flows()
        flows = [flow async for flow in client.lifecycle.iter_account_flows()]
    assert len(page.flows) == 1
    _check_open_withdraw(page.flows[0])
    assert len(flows) == 1
    _check_open_withdraw(flows[0])


async def test_get_account_flow_keeps_amount_transactions_and_times() -> None:
    reply = lr.GetAccountFlowResponse(flow=lr.FlowDetailView(summary=_open_withdraw()))
    async with _client(_ok(reply)) as (client, _):
        flow = await client.lifecycle.get_account_flow(flow_id="flow_UZBpp6Kx7uX")
    _check_open_withdraw(flow)


def test_realtime_flow_update_keeps_amount_transactions_and_times() -> None:
    _check_open_withdraw(decode_flow_summary_bytes(_open_withdraw().SerializeToString()))


def test_realtime_flow_detail_keeps_amount_transactions_and_times() -> None:
    payload = lr.FlowDetailView(summary=_open_withdraw()).SerializeToString()
    _check_open_withdraw(decode_flow_detail_bytes(payload))


def test_json_flow_keeps_amount_transactions_and_times() -> None:
    item = json.loads(OPEN_WITHDRAW_JSON)
    _check_open_withdraw(decode_lifecycle_flow(item))
    _check_open_withdraw(decode_lifecycle_flow({"summary": item, "steps": []}))
    page = decode_lifecycle_flows_list({"flows": [item], "nextPageToken": "n"})
    assert page.next_page_token == "n"
    _check_open_withdraw(page.flows[0])


def test_json_flow_reads_snake_case_field_names() -> None:
    item = json_format.MessageToDict(_open_withdraw(), preserving_proto_field_name=True)
    _check_open_withdraw(decode_lifecycle_flow(item))


def test_json_flow_refuses_an_amount_that_breaks_the_contract() -> None:
    with pytest.raises(PolyesterResponseContractError):
        decode_lifecycle_flow({"flowId": "flow_x", "amountE18": {"lo": "not a number"}})


async def test_flows_by_tx_keep_amount_transactions_and_activity() -> None:
    match = lr.FlowTxMatchView(
        flow_id="flow_m",
        flow_kind=types_pb2.KIND_DEPOSIT,
        source_tx_hash="0xabc",
        latest_tx_ref="0xdef",
        tx_occurrence_index=4,
        source_domain=types_pb2.DOMAIN_EXTERNAL_CHAIN,
        destination_domain=types_pb2.DOMAIN_TRADING,
        asset_ids=types_pb2.AssetIds(zipped_asset_id=11, unified_asset_id=5),
        polyester_chain_id=2,
        amount_e18=u128_pb2.U128(lo=110000000000000),
        last_activity_at_unix_ms=1795113314313,
    )
    reply = lr.ListFlowsByTxResponse(matches=[match])
    async with _client(_ok(reply)) as (client, _):
        listed = await client.lifecycle.list_flows_by_tx(tx_hash="0xabc")
        looked_up = await client.lifecycle.get_flow_by_tx(tx_hash="0xabc")
    for page in (listed, looked_up):
        assert len(page.flows) == 1
        flow = page.flows[0]
        assert (flow.source_tx_hash, flow.latest_tx_ref, flow.tx_occurrence_index) == (
            "0xabc",
            "0xdef",
            4,
        )
        assert (flow.source_domain, flow.destination_domain) == ("external_chain", "trading")
        assert (flow.zipped_asset_id, flow.unified_asset_id, flow.polyester_chain_id) == (
            11,
            5,
            2,
        )
        _check_ledger_amount(flow.amount, 110000000000000, 5)
        _check_time(flow.last_activity_at, 1795113314313)
        # A transaction match carries no fee, progress or other times.
        assert flow.request_fee is None and flow.current_progress is None
        assert flow.progress_timeline == [] and flow.current_step_sequence == 0
        assert flow.started_at is None and flow.updated_at is None
        assert flow.terminal_at is None and flow.estimated_completion_at is None


def test_terminal_flow_reads_its_terminal_time_and_kept_fee() -> None:
    flow = flow_summary_from_proto(
        lr.FlowSummaryView(
            flow_id="flow_t",
            is_terminal=True,
            terminal_at_unix_ms=1795113340254,
            request_fee=types_pb2.RequestFee(status=types_pb2.REQUEST_FEE_STATUS_KEPT),
        )
    )
    _check_time(flow.terminal_at, 1795113340254)
    assert flow.request_fee is not None
    assert flow.request_fee.status == "kept" and flow.request_fee.amount is None


def test_a_flow_without_optional_fields_leaves_them_unset() -> None:
    for flow in (
        flow_summary_from_proto(
            lr.FlowSummaryView(flow_id="flow_d", is_open=True, is_delayed=True)
        ),
        decode_lifecycle_flow({"flowId": "flow_d", "isOpen": True, "isDelayed": True}),
    ):
        assert flow.amount is None and flow.request_fee is None
        assert flow.current_progress is None and flow.progress_timeline == []
        assert flow.started_at is None and flow.updated_at is None
        assert flow.terminal_at is None and flow.last_activity_at is None
        # The contract sends no estimate while a flow is delayed.
        assert flow.estimated_completion_at is None
        assert (flow.source_domain, flow.destination_domain) == ("unspecified", "unspecified")
        assert (flow.zipped_asset_id, flow.unified_asset_id, flow.polyester_chain_id) == (0, 0, 0)
        assert (flow.source_tx_hash, flow.latest_tx_ref, flow.tx_occurrence_index) == ("", "", 0)
        assert flow.current_step_sequence == 0


def test_a_zero_amount_is_kept_and_a_time_past_datetime_reads_none() -> None:
    flow = flow_summary_from_proto(
        lr.FlowSummaryView(
            flow_id="flow_z",
            amount_e18=u128_pb2.U128(),
            started_at_unix_ms=(1 << 64) - 1,
        )
    )
    assert flow.amount is not None and flow.amount.scaled == 0
    assert flow.started_at is None


def test_flow_enums_newer_than_the_sdk_keep_their_number() -> None:
    flow = flow_summary_from_proto(
        lr.FlowSummaryView(
            flow_id="flow_n",
            source_domain=42,  # type: ignore[arg-type]
            request_fee=types_pb2.RequestFee(status=9),  # type: ignore[arg-type]
            progress_timeline=[lr.FlowTimelineItemView(sequence=1, status=7)],  # type: ignore[arg-type]
        )
    )
    assert flow.source_domain == "unknown_domain_42"
    assert flow.request_fee is not None and flow.request_fee.status == "unknown_fee_status_9"
    assert flow.progress_timeline[0].status == "unknown_timeline_status_7"
    assert flow.progress_timeline[0].step == "unspecified"
