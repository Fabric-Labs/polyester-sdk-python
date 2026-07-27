from __future__ import annotations

from polyester.codecs.proto_helpers import proto_enum_name
from polyester.errors import PolyesterTransportError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2
from polyester.models import LifecycleFlowsList, LifecycleFlowSummary
from polyester.services._scope import lifecycle_account_fields

FlowDetailView = lifecycle_read_pb2.FlowDetailView
FlowSummaryView = lifecycle_read_pb2.FlowSummaryView
FlowTxMatchView = lifecycle_read_pb2.FlowTxMatchView


def _summary_from_detail(msg: FlowDetailView) -> FlowSummaryView:
    if msg.HasField("summary"):
        return msg.summary
    raise PolyesterTransportError("flow detail response is missing summary")


def flow_summary_from_proto(msg: lifecycle_read_pb2.FlowSummaryView) -> LifecycleFlowSummary:
    return LifecycleFlowSummary(
        intent_id=msg.flow_id,
        flow_kind=proto_enum_name(types_pb2.FlowKind, msg.flow_kind),
        latest_step=proto_enum_name(lifecycle_read_pb2.FlowStep, msg.current_step),
        is_open=bool(msg.is_open),
        is_terminal=bool(msg.is_terminal),
        **lifecycle_account_fields(msg),
    )


def flow_tx_match_from_proto(msg: FlowTxMatchView) -> LifecycleFlowSummary:
    return LifecycleFlowSummary(
        intent_id=msg.flow_id,
        flow_kind=proto_enum_name(types_pb2.FlowKind, msg.flow_kind),
        latest_step=proto_enum_name(lifecycle_read_pb2.FlowStep, msg.current_step),
        is_open=bool(msg.is_open),
        is_terminal=bool(msg.is_terminal),
        **lifecycle_account_fields(msg),
    )


def flow_detail_from_proto(msg: lifecycle_read_pb2.FlowDetailView) -> LifecycleFlowSummary:
    return flow_summary_from_proto(_summary_from_detail(msg))


def flows_list_from_proto(msg: lifecycle_read_pb2.ListFlowsResponse) -> LifecycleFlowsList:
    return LifecycleFlowsList(
        flows=[flow_summary_from_proto(item) for item in msg.flows],
        next_page_token=msg.next_page_token,
    )


def flows_by_tx_list_from_proto(
    msg: lifecycle_read_pb2.ListFlowsByTxResponse,
) -> LifecycleFlowsList:
    return LifecycleFlowsList(
        flows=[flow_tx_match_from_proto(item) for item in msg.matches],
        next_page_token=msg.next_page_token,
    )


def flow_from_get_response(msg: lifecycle_read_pb2.GetFlowResponse) -> LifecycleFlowSummary:
    if msg.HasField("flow"):
        return flow_detail_from_proto(msg.flow)
    raise PolyesterTransportError("get flow response is missing flow")


def flow_from_get_by_tx_response(
    msg: lifecycle_read_pb2.ListFlowsByTxResponse,
) -> LifecycleFlowSummary:
    if msg.matches:
        return flow_tx_match_from_proto(msg.matches[0])
    raise PolyesterTransportError("get flow by transaction response has no matching flow")
