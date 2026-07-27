import pytest

from polyester.codecs.decode.lifecycle import (
    flow_detail_from_proto,
    flow_from_get_by_tx_response,
    flow_from_get_response,
    flow_summary_from_proto,
    flows_list_from_proto,
)
from polyester.codecs.realtime_decode import decode_flow_detail_bytes
from polyester.errors import PolyesterRealtimeError, PolyesterTransportError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2


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
