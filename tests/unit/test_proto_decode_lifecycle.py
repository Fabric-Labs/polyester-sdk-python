import pytest

from polyester.codecs.decode.lifecycle import (
    flow_detail_from_proto,
    flow_from_get_by_tx_response,
    flow_from_get_response,
    flow_summary_from_proto,
    flows_list_from_proto,
    lifecycle_reason_from_code,
)
from polyester.codecs.realtime_decode import decode_flow_detail_bytes
from polyester.errors import PolyesterRealtimeError, PolyesterTransportError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2
from polyester.gen.chain.zipper.v1 import reason_pb2


def test_flow_summary_from_proto() -> None:
    msg = lifecycle_read_pb2.FlowSummaryView(
        flow_id="flow-abc",
        flow_kind=types_pb2.KIND_DEPOSIT,
        current_step=lifecycle_read_pb2.FLOW_STEP_SETTLEMENT,
        is_open=False,
        is_terminal=True,
        owner_account_id=99,
        smart_account_address="0xabc",
    )
    flow = flow_summary_from_proto(msg)
    assert flow.intent_id == "flow-abc"
    assert flow.flow_kind == "deposit"
    assert flow.latest_step == "settlement"
    assert flow.is_terminal is True
    assert flow.owner_account_id
    assert flow.smart_account_address == "0xabc"
    assert flow.lifecycle_reason == "unspecified"
    assert flow.zipper_reason is None


def test_flow_summary_zipper_reason_and_lifecycle_reason() -> None:
    msg = lifecycle_read_pb2.FlowSummaryView(
        flow_id="flow-rej",
        flow_kind=types_pb2.KIND_WITHDRAW,
        current_step=lifecycle_read_pb2.FLOW_STEP_FAILED,
        is_open=False,
        is_terminal=True,
        lifecycle_reason=types_pb2.ZIPPER_VALIDATION_REJECTED,
        zipper_reason=reason_pb2.ZipperReasonDetails(
            code=reason_pb2.DEPOSIT_AMOUNT_BELOW_MINIMUM,
            reason_id="deposit_amount_below_minimum",
            message="amount below minimum",
        ),
    )
    flow = flow_summary_from_proto(msg)
    assert flow.lifecycle_reason == "zipper_validation_rejected"
    assert flow.zipper_reason is not None
    assert flow.zipper_reason.code == int(reason_pb2.DEPOSIT_AMOUNT_BELOW_MINIMUM)
    assert flow.zipper_reason.reason_id == "deposit_amount_below_minimum"
    assert flow.zipper_reason.message == "amount below minimum"


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (
            types_pb2.TRADING_WITHDRAW_POLICY_DENIED,
            "trading_withdraw_policy_denied",
        ),
        (
            types_pb2.TRADING_WITHDRAW_CONTRACT_REVERTED,
            "trading_withdraw_contract_reverted",
        ),
        (
            types_pb2.TRADING_WITHDRAW_EXECUTION_FAILED,
            "trading_withdraw_execution_failed",
        ),
    ],
)
def test_trading_withdraw_lifecycle_reasons(reason: int, expected: str) -> None:
    assert lifecycle_reason_from_code(reason) == expected
    msg = lifecycle_read_pb2.FlowSummaryView(
        flow_id="flow-trading-withdraw",
        flow_kind=types_pb2.KIND_WITHDRAW,
        current_step=lifecycle_read_pb2.FLOW_STEP_FAILED,
        is_open=False,
        is_terminal=True,
        lifecycle_reason=reason,
    )
    flow = flow_summary_from_proto(msg)
    assert flow.lifecycle_reason == expected


def test_lifecycle_reason_unknown_code_fallback() -> None:
    assert lifecycle_reason_from_code(2001) == "unknown_reason_2001"
    msg = lifecycle_read_pb2.FlowSummaryView(
        flow_id="flow-unknown",
        lifecycle_reason=2001,
    )
    flow = flow_summary_from_proto(msg)
    assert flow.flow_kind == "unspecified"
    assert flow.latest_step == "unspecified"
    assert flow.lifecycle_reason == "unknown_reason_2001"


def test_flow_from_get_response_unwraps_detail_summary() -> None:
    detail = lifecycle_read_pb2.FlowDetailView(
        summary=lifecycle_read_pb2.FlowSummaryView(
            flow_id="flow-detail",
            current_step=lifecycle_read_pb2.FLOW_STEP_REQUEST,
            is_open=True,
        )
    )
    msg = lifecycle_read_pb2.GetFlowResponse(flow=detail)
    flow = flow_from_get_response(msg)
    assert flow.intent_id == "flow-detail"
    assert flow.latest_step == "request"
    assert flow.is_open is True


def test_flows_list_from_proto() -> None:
    msg = lifecycle_read_pb2.ListFlowsResponse(
        flows=[
            lifecycle_read_pb2.FlowSummaryView(flow_id="a"),
            lifecycle_read_pb2.FlowSummaryView(flow_id="b"),
        ],
        next_page_token="next",
    )
    result = flows_list_from_proto(msg)
    assert len(result.flows) == 2
    assert result.next_page_token == "next"


def test_flow_detail_missing_summary_fails_closed() -> None:
    with pytest.raises(PolyesterTransportError, match="missing summary"):
        flow_detail_from_proto(lifecycle_read_pb2.FlowDetailView(from_live_state=True))


def test_get_by_transaction_missing_match_fails_closed() -> None:
    with pytest.raises(PolyesterTransportError, match="no matching flow"):
        flow_from_get_by_tx_response(lifecycle_read_pb2.ListFlowsByTxResponse())


def test_realtime_decoder_rejects_empty_payload() -> None:
    with pytest.raises(PolyesterRealtimeError, match="empty publication"):
        decode_flow_detail_bytes(b"")
