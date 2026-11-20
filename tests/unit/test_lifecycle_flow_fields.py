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
from polyester.codecs.decode.lifecycle import flow_summary_from_proto, lifecycle_reason_from_code
from polyester.codecs.realtime_decode import decode_flow_detail_bytes, decode_flow_summary_bytes
from polyester.codecs.wire_decode import decode_lifecycle_flow, decode_lifecycle_flows_list
from polyester.errors import PolyesterResponseContractError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2 as lr
from polyester.gen.chain.lifecycle.v1 import types_pb2
from polyester.gen.chain.zipper.v1 import reason_pb2
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


def _delayed_withdraw() -> lr.FlowSummaryView:
    """A populated delayed flow: every summary field the contract sends, with
    no estimate, as the contract sends none while a flow is delayed."""
    view = _open_withdraw()
    view.is_delayed = True
    view.ClearField("estimated_completion_unix_ms")
    view.participation = lr.PARTICIPATION_OWNER
    view.lifecycle_reason = types_pb2.ZIPPER_VALIDATION_REJECTED
    view.zipper_reason.code = reason_pb2.DEPOSIT_AMOUNT_BELOW_MINIMUM
    view.zipper_reason.reason_id = "deposit_amount_below_minimum"
    view.zipper_reason.message = "amount below minimum"
    return view


def _check_delayed_withdraw(flow: LifecycleFlowSummary) -> None:
    assert flow.is_delayed is True and flow.is_open is True and flow.is_terminal is False
    assert flow.estimated_completion_at is None
    assert flow.smart_account_address == "0x00000000000000000000000000000000000000a1"
    assert flow.source_address == "0x00000000000000000000000000000000000000a1"
    assert flow.destination_address == "0x00000000000000000000000000000000000000b2"
    assert flow.participation == "owner"
    assert (flow.flow_kind, flow.latest_step) == ("withdraw", "validation")
    assert flow.lifecycle_reason == "zipper_validation_rejected"
    assert flow.zipper_reason is not None
    assert flow.zipper_reason.code == int(reason_pb2.DEPOSIT_AMOUNT_BELOW_MINIMUM)
    assert flow.zipper_reason.reason_id == "deposit_amount_below_minimum"
    assert (flow.source_domain, flow.destination_domain) == ("funding", "external_chain")
    _check_ledger_amount(flow.amount, 23446744073709551616, 1)


@pytest.mark.parametrize(
    "encoding",
    [
        {},
        {"preserving_proto_field_name": True},
        {"use_integers_for_enums": True},
        {"use_integers_for_enums": True, "preserving_proto_field_name": True},
    ],
    ids=["camel-names", "snake-names", "camel-numbers", "snake-numbers"],
)
def test_json_flow_matches_the_binary_decoder_field_for_field(encoding) -> None:
    view = _delayed_withdraw()
    binary = flow_summary_from_proto(view)
    _check_delayed_withdraw(binary)
    item = json_format.MessageToDict(view, **encoding)
    detail = json_format.MessageToDict(lr.FlowDetailView(summary=view), **encoding)
    listed = decode_lifecycle_flows_list({"flows": [item]}).flows[0]
    for flow in (decode_lifecycle_flow(item), decode_lifecycle_flow(detail), listed):
        _check_delayed_withdraw(flow)
        assert flow == binary


def test_json_flow_reads_an_empty_summary_as_the_binary_decoder_does() -> None:
    assert decode_lifecycle_flow({}) == flow_summary_from_proto(lr.FlowSummaryView())


def test_json_flow_keeps_reading_legacy_names_and_labels() -> None:
    flow = decode_lifecycle_flow(
        {
            "intentId": "flow_legacy",
            "flowKind": "withdraw",
            "latestStep": "validation",
            "participation": "recipient",
            "sourceDomain": "trading",
            "reasonCode": "zipper_execution_rejected",
            "isDelayed": True,
        }
    )
    assert (flow.intent_id, flow.flow_kind, flow.latest_step) == (
        "flow_legacy",
        "withdraw",
        "validation",
    )
    assert (flow.participation, flow.source_domain) == ("recipient", "trading")
    assert flow.lifecycle_reason == "zipper_execution_rejected"
    assert flow.is_delayed is True
    newer = decode_lifecycle_flow({"flowId": "f", "lifecycleReason": "unknown_reason_2001"})
    assert newer.lifecycle_reason == "unknown_reason_2001"
    numbered = decode_lifecycle_flow({"flowId": "f", "flowKind": "2", "currentStep": " 4 "})
    assert (numbered.flow_kind, numbered.latest_step) == (
        flow_summary_from_proto(lr.FlowSummaryView(flow_kind=2, current_step=4)).flow_kind,  # type: ignore[arg-type]
        flow_summary_from_proto(lr.FlowSummaryView(flow_kind=2, current_step=4)).latest_step,  # type: ignore[arg-type]
    )
    assert numbered.flow_kind == "withdraw"
    for bad in ({"flowKind": "not a kind"}, {"isDelayed": "yes"}, {"flowKind": "\u00b2"}):
        with pytest.raises(PolyesterResponseContractError):
            decode_lifecycle_flow({"flowId": "f", **bad})
    # The contract name wins over a legacy alias.
    both = decode_lifecycle_flow({"flowId": "flow_new", "intentId": "flow_old"})
    assert both.intent_id == "flow_new"


def test_json_flow_reads_enum_names_newer_than_the_sdk_by_name() -> None:
    flow = decode_lifecycle_flow(
        {
            "flowId": "flow_newer",
            "flowKind": "KIND_SWAP",
            "sourceDomain": "DOMAIN_LIQUIDITY",
            "destinationDomain": "DOMAIN_TRADING",
            "requestFee": {"status": "REQUEST_FEE_STATUS_WAIVED"},
            "progressTimeline": [
                {"sequence": 1, "step": "FLOW_STEP_REQUEST", "status": "TIMELINE_STATUS_SKIPPED"},
                {"sequence": 2, "step": "FLOW_STEP_TELEPORT", "status": "TIMELINE_STATUS_PLANNED"},
            ],
            "latestLifecycleSource": "SOURCE_SOMETHING_NEW",
        }
    )
    assert (flow.flow_kind, flow.source_domain, flow.destination_domain) == (
        "swap",
        "liquidity",
        "trading",
    )
    assert flow.request_fee is not None and flow.request_fee.status == "waived"
    assert flow.progress_timeline == [
        LifecycleFlowTimelineItem(sequence=1, step="request", status="skipped"),
        LifecycleFlowTimelineItem(sequence=2, step="teleport", status="planned"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"progressTimeline": [{"status": "TIMELINE_STATUS_NEW"}], "progress_timeline": []},
        {"sourceDomain": "DOMAIN_FUTURE", "source_domain": "DOMAIN_FUNDING"},
        {"requestFee": {"status": "REQUEST_FEE_STATUS_NEW"}, "request_fee": {}},
        {"progressTimeline": [{"expectedDurationMs": "1", "expected_duration_ms": "2"}]},
    ],
    ids=["timeline", "scalar-enum", "fee", "nested-scalar"],
)
def test_json_flow_refuses_a_field_spelled_twice(payload) -> None:
    with pytest.raises(PolyesterResponseContractError):
        decode_lifecycle_flow({"flowId": "flow_twice", **payload})


@pytest.mark.parametrize("number", [-1, -(2**31), 2**31 - 1, 7, 2001])
def test_json_flow_reads_back_every_label_the_binary_decoder_returns(number) -> None:
    binary = flow_summary_from_proto(
        lr.FlowSummaryView(
            flow_id="flow_signed",
            flow_kind=number,  # type: ignore[arg-type]
            current_step=number,  # type: ignore[arg-type]
            lifecycle_reason=number,  # type: ignore[arg-type]
            participation=number,  # type: ignore[arg-type]
            source_domain=number,  # type: ignore[arg-type]
            request_fee=types_pb2.RequestFee(status=number),  # type: ignore[arg-type]
            progress_timeline=[lr.FlowTimelineItemView(sequence=1, status=number)],  # type: ignore[arg-type]
        )
    )
    assert binary.lifecycle_reason == lifecycle_reason_from_code(number)
    assert binary.request_fee is not None
    labelled = {
        "flowId": "flow_signed",
        "flowKind": binary.flow_kind,
        "currentStep": binary.latest_step,
        "lifecycleReason": binary.lifecycle_reason,
        "participation": binary.participation,
        "sourceDomain": binary.source_domain,
        "requestFee": {"status": binary.request_fee.status},
        "progressTimeline": [{"sequence": 1, "status": binary.progress_timeline[0].status}],
    }
    assert decode_lifecycle_flow(labelled) == binary


@pytest.mark.parametrize(
    "value",
    ["9" * 4301, "-" + "9" * 4301, str(2**31), str(-(2**31) - 1), "unknown_reason_" + "9" * 4301],
)
def test_json_flow_refuses_an_enum_number_out_of_range_with_a_typed_error(value) -> None:
    for key in ("flowKind", "lifecycleReason"):
        with pytest.raises(PolyesterResponseContractError):
            decode_lifecycle_flow({"flowId": "flow_big", key: value})


def test_json_flow_refuses_a_fallback_label_of_another_field() -> None:
    with pytest.raises(PolyesterResponseContractError):
        decode_lifecycle_flow({"flowId": "flow_x", "lifecycleReason": "unknown_domain_3"})


def _decode_both_ways(summary: dict) -> list[LifecycleFlowSummary]:
    """``summary`` through both JSON helpers: as a detail view and as a list row."""
    item = {"flowId": "flow_typed", **summary}
    return [
        decode_lifecycle_flow({"summary": item, "steps": []}),
        decode_lifecycle_flows_list({"flows": [item]}).flows[0],
    ]


_BAD_ENUM_VALUES = [
    True,
    False,
    2.9,
    1.5,
    float("inf"),
    float("-inf"),
    float("nan"),
    2**31,
    -(2**31) - 1,
    [],
    {},
]


@pytest.mark.parametrize("value", _BAD_ENUM_VALUES, ids=repr)
@pytest.mark.parametrize(
    "where",
    [
        lambda v: {"requestFee": {"status": v}},
        lambda v: {"progressTimeline": [{"sequence": 1, "status": v}]},
        lambda v: {"progressTimeline": [{"sequence": 1, "step": v}]},
        lambda v: {"sourceDomain": v},
        lambda v: {"flowKind": v},
        lambda v: {"participation": v},
        lambda v: {"lifecycleReason": v},
        lambda v: {"zipperReason": {"code": v}},
    ],
    ids=[
        "fee-status",
        "timeline-status",
        "timeline-step",
        "domain",
        "kind",
        "participation",
        "reason",
        "zipper-code",
    ],
)
def test_json_flow_refuses_an_enum_value_that_is_not_an_int32(where, value) -> None:
    item = {"flowId": "flow_typed", **where(value)}
    with pytest.raises(PolyesterResponseContractError):
        decode_lifecycle_flow({"summary": item, "steps": []})
    with pytest.raises(PolyesterResponseContractError):
        decode_lifecycle_flows_list({"flows": [item]})


def test_json_flow_reads_null_and_int32_enum_numbers() -> None:
    summary = {
        "requestFee": {"status": 2},
        "progressTimeline": [
            {"sequence": 1, "step": 1, "status": 1},
            {"sequence": 2, "step": None, "status": -1},
        ],
        "sourceDomain": None,
        "destinationDomain": 2.0,
        "lifecycleReason": -(2**31),
        "zipperReason": {"code": 1003},
    }
    for flow in _decode_both_ways(summary):
        assert flow.request_fee is not None and flow.request_fee.status == "settled"
        assert [(i.step, i.status) for i in flow.progress_timeline] == [
            ("source", "completed"),
            ("unspecified", "unknown_timeline_status_-1"),
        ]
        assert (flow.source_domain, flow.destination_domain) == ("unspecified", "zipper")
        assert flow.lifecycle_reason == lifecycle_reason_from_code(-(2**31))
        assert flow.zipper_reason is not None and flow.zipper_reason.code == 1003
