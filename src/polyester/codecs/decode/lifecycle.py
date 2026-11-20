from __future__ import annotations

from collections.abc import Callable
from typing import Any

from polyester.codecs.decode.balances import ledger_amount
from polyester.codecs.decode.common import require_id
from polyester.codecs.proto_helpers import has_field, proto_enum_name
from polyester.codecs.scalars import unix_ms_to_datetime
from polyester.errors import PolyesterResponseContractError, PolyesterTransportError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2, types_pb2
from polyester.gen.chain.zipper.v1 import reason_pb2
from polyester.models import (
    LifecycleFlowProgress,
    LifecycleFlowsList,
    LifecycleFlowSummary,
    LifecycleFlowTimelineItem,
    LifecycleRequestFee,
    ZipperReasonDetails,
)
from polyester.services._scope import lifecycle_account_fields
from polyester.types.money import AssetAmount

FlowDetailView = lifecycle_read_pb2.FlowDetailView
FlowSummaryView = lifecycle_read_pb2.FlowSummaryView
FlowTxMatchView = lifecycle_read_pb2.FlowTxMatchView

# Explicit catalog keyed by wire int (matches TS LifecycleFlowReasonCodec).
# Proto3 enums are open; unknown codes must not fail the whole flow payload.
_LIFECYCLE_REASON_BY_CODE: dict[int, str] = {
    int(types_pb2.REASON_UNSPECIFIED): "unspecified",
    int(types_pb2.ZIPPER_VALIDATION_REJECTED): "zipper_validation_rejected",
    int(types_pb2.ZIPPER_EXECUTION_REJECTED): "zipper_execution_rejected",
    int(types_pb2.ZIPPER_WITHDRAW_EXECUTION_FAILED): "zipper_withdraw_execution_failed",
    int(types_pb2.ZIPPER_DEPOSIT_REFUND_FAILED): "zipper_deposit_refund_failed",
    int(types_pb2.LEDGER_MIRROR_REJECTED): "ledger_mirror_rejected",
    int(types_pb2.LEDGER_MIRROR_TRANSFER_EXCEEDS_CREDITS): (
        "ledger_mirror_transfer_exceeds_credits"
    ),
    int(types_pb2.LEDGER_MIRROR_TRANSFER_EXISTS): "ledger_mirror_transfer_exists",
    int(types_pb2.LEDGER_MIRROR_PENDING_TRANSFER_NOT_FOUND): (
        "ledger_mirror_pending_transfer_not_found"
    ),
    int(types_pb2.LEDGER_MIRROR_TRANSFER_ID_ALREADY_FAILED): (
        "ledger_mirror_transfer_id_already_failed"
    ),
    int(types_pb2.TRADING_WITHDRAW_POLICY_DENIED): "trading_withdraw_policy_denied",
    int(types_pb2.TRADING_WITHDRAW_CONTRACT_REVERTED): (
        "trading_withdraw_contract_reverted"
    ),
    int(types_pb2.TRADING_WITHDRAW_EXECUTION_FAILED): (
        "trading_withdraw_execution_failed"
    ),
    int(types_pb2.DEPOSIT_SOURCE_NOT_CONFIRMED): "deposit_source_not_confirmed",
    int(types_pb2.ZIPPER_COMPLIANCE_TRANSFERRED): "zipper_compliance_transferred",
    # A completed outcome, not a failure: the deposit was delivered to the
    # account's own Polyester Chain wallet and no Funding or Trading balance
    # was credited.
    int(types_pb2.ZIPPER_DEPOSIT_DELIVERED_TO_WALLET): "zipper_deposit_delivered_to_wallet",
}


def lifecycle_reason_from_code(code: int) -> str:
    return _LIFECYCLE_REASON_BY_CODE.get(int(code), f"unknown_reason_{int(code)}")


def _flow_kind_label(code: int) -> str:
    return proto_enum_name(types_pb2.FlowKind, code) or "unspecified"


def _flow_step_label(code: int) -> str:
    return proto_enum_name(lifecycle_read_pb2.FlowStep, code) or "unspecified"


def _zipper_reason_from_proto(msg: reason_pb2.ZipperReasonDetails) -> ZipperReasonDetails:
    return ZipperReasonDetails(
        code=int(msg.code),
        reason_id=str(msg.reason_id or ""),
        message=str(msg.message or ""),
    )


def _zipper_reason_if_present(msg) -> ZipperReasonDetails | None:
    if has_field(msg, "zipper_reason"):
        return _zipper_reason_from_proto(msg.zipper_reason)
    return None


def _summary_from_detail(msg: FlowDetailView) -> FlowSummaryView:
    if msg.HasField("summary"):
        return msg.summary
    raise PolyesterTransportError("flow detail response is missing summary")


_PARTICIPATION_LABELS = {
    int(lifecycle_read_pb2.PARTICIPATION_UNSPECIFIED): "unspecified",
    int(lifecycle_read_pb2.PARTICIPATION_OWNER): "owner",
    int(lifecycle_read_pb2.PARTICIPATION_RECIPIENT): "recipient",
}


def flow_participation_label(code: int) -> str:
    """Name a ``FlowParticipation`` the way REST spells it, lowercased. A value
    newer than this SDK reads ``unknown_participation_<n>``, never unspecified."""
    return _PARTICIPATION_LABELS.get(int(code), f"unknown_participation_{int(code)}")


_DOMAIN_LABELS = {
    int(types_pb2.DOMAIN_UNSPECIFIED): "unspecified",
    int(types_pb2.DOMAIN_EXTERNAL_CHAIN): "external_chain",
    int(types_pb2.DOMAIN_ZIPPER): "zipper",
    int(types_pb2.DOMAIN_FUNDING): "funding",
    int(types_pb2.DOMAIN_TRADING): "trading",
    int(types_pb2.DOMAIN_LENDING): "lending",
}

_REQUEST_FEE_STATUS_LABELS = {
    int(types_pb2.REQUEST_FEE_STATUS_UNSPECIFIED): "unspecified",
    int(types_pb2.REQUEST_FEE_STATUS_LOCKED): "locked",
    int(types_pb2.REQUEST_FEE_STATUS_SETTLED): "settled",
    int(types_pb2.REQUEST_FEE_STATUS_KEPT): "kept",
}

_TIMELINE_STATUS_LABELS = {
    int(lifecycle_read_pb2.TIMELINE_STATUS_UNSPECIFIED): "unspecified",
    int(lifecycle_read_pb2.TIMELINE_STATUS_COMPLETED): "completed",
    int(lifecycle_read_pb2.TIMELINE_STATUS_CURRENT): "current",
    int(lifecycle_read_pb2.TIMELINE_STATUS_PLANNED): "planned",
}


def flow_domain_label(code: int) -> str:
    """Name a ``FlowDomain`` lowercased without its ``DOMAIN_`` prefix. A value
    newer than this SDK reads ``unknown_domain_<n>``, never unspecified."""
    return _DOMAIN_LABELS.get(int(code), f"unknown_domain_{int(code)}")


def _request_fee_status_label(code: int) -> str:
    return _REQUEST_FEE_STATUS_LABELS.get(int(code), f"unknown_fee_status_{int(code)}")


def _timeline_status_label(code: int) -> str:
    return _TIMELINE_STATUS_LABELS.get(int(code), f"unknown_timeline_status_{int(code)}")


def _optional_ledger_amount(msg, asset_id: int) -> AssetAmount | None:
    """The message's ``amount_e18``, exact ((hi << 64) | lo, never a float), in
    units of ``asset_id``; None when the server sends none."""
    if not has_field(msg, "amount_e18"):
        return None
    value = msg.amount_e18
    return ledger_amount((int(value.hi) << 64) | int(value.lo), asset_id or None)


def _request_fee(msg: lifecycle_read_pb2.FlowSummaryView) -> LifecycleRequestFee | None:
    if not has_field(msg, "request_fee"):
        return None
    fee = msg.request_fee
    unified_asset_id = int(fee.asset_ids.unified_asset_id)
    return LifecycleRequestFee(
        zipped_asset_id=int(fee.asset_ids.zipped_asset_id),
        unified_asset_id=unified_asset_id,
        amount=_optional_ledger_amount(fee, unified_asset_id),
        recipient_address=str(fee.recipient_address or ""),
        status=_request_fee_status_label(fee.status),
    )


def _flow_progress(msg: lifecycle_read_pb2.FlowSummaryView) -> LifecycleFlowProgress | None:
    if not has_field(msg, "current_progress"):
        return None
    progress = msg.current_progress
    return LifecycleFlowProgress(
        current_step_started_at=unix_ms_to_datetime(progress.current_step_started_at_unix_ms),
        current_step_expected_duration_ms=int(progress.current_step_expected_duration_ms),
        current_confirmations=int(progress.current_confirmations),
        required_confirmations=int(progress.required_confirmations),
        approve_count=int(progress.approve_count),
        reject_count=int(progress.reject_count),
        validator_count=int(progress.validator_count),
        required_approvals=int(progress.required_approvals),
        required_rejections=int(progress.required_rejections),
    )


def _flow_timeline(msg: lifecycle_read_pb2.FlowSummaryView) -> list[LifecycleFlowTimelineItem]:
    return [
        LifecycleFlowTimelineItem(
            sequence=int(item.sequence),
            step=_flow_step_label(item.step),
            status=_timeline_status_label(item.status),
            expected_duration_ms=int(item.expected_duration_ms),
        )
        for item in msg.progress_timeline
    ]


def _flow_tx_fields(msg: FlowSummaryView | FlowTxMatchView) -> dict[str, Any]:
    """The asset, chain, amount, transaction and route fields a flow summary
    and a transaction match both carry, and the time lists order by."""
    unified_asset_id = int(msg.asset_ids.unified_asset_id)
    return {
        "zipped_asset_id": int(msg.asset_ids.zipped_asset_id),
        "unified_asset_id": unified_asset_id,
        "polyester_chain_id": int(msg.polyester_chain_id),
        "amount": _optional_ledger_amount(msg, unified_asset_id),
        "source_tx_hash": str(msg.source_tx_hash or ""),
        "tx_occurrence_index": int(msg.tx_occurrence_index),
        "latest_tx_ref": str(msg.latest_tx_ref or ""),
        "source_domain": flow_domain_label(msg.source_domain),
        "destination_domain": flow_domain_label(msg.destination_domain),
        "last_activity_at": unix_ms_to_datetime(msg.last_activity_at_unix_ms),
    }


def _flow_summary_detail_fields(msg: FlowSummaryView) -> dict[str, Any]:
    """Every ``LifecycleFlowSummary`` field a ``FlowSummaryView`` carries beyond
    its kind, step, state, account, reasons, participation and addresses.
    ``latest_lifecycle_source`` (server provenance) is not modelled."""
    return {
        **_flow_tx_fields(msg),
        "request_fee": _request_fee(msg),
        "started_at": unix_ms_to_datetime(msg.started_at_unix_ms),
        "updated_at": unix_ms_to_datetime(msg.updated_at_unix_ms),
        "terminal_at": unix_ms_to_datetime(msg.terminal_at_unix_ms),
        "estimated_completion_at": unix_ms_to_datetime(msg.estimated_completion_unix_ms),
        "current_step_sequence": int(msg.current_step_sequence),
        "current_progress": _flow_progress(msg),
        "progress_timeline": _flow_timeline(msg),
    }


# The label each lifecycle flow enum reads as on LifecycleFlowSummary and its
# nested models, by enum name, so a JSON decoder can read those labels back.
FLOW_ENUM_LABELS: dict[str, Callable[[int], str]] = {
    types_pb2.FlowKind.DESCRIPTOR.full_name: _flow_kind_label,
    lifecycle_read_pb2.FlowStep.DESCRIPTOR.full_name: _flow_step_label,
    types_pb2.LifecycleReason.DESCRIPTOR.full_name: lifecycle_reason_from_code,
    lifecycle_read_pb2.FlowParticipation.DESCRIPTOR.full_name: flow_participation_label,
    types_pb2.FlowDomain.DESCRIPTOR.full_name: flow_domain_label,
    types_pb2.RequestFeeStatus.DESCRIPTOR.full_name: _request_fee_status_label,
    lifecycle_read_pb2.FlowTimelineStatus.DESCRIPTOR.full_name: _timeline_status_label,
}


def flow_summary_from_proto(msg: lifecycle_read_pb2.FlowSummaryView) -> LifecycleFlowSummary:
    account_fields = lifecycle_account_fields(msg)
    return LifecycleFlowSummary(
        intent_id=msg.flow_id,
        flow_kind=_flow_kind_label(msg.flow_kind),
        latest_step=_flow_step_label(msg.current_step),
        is_open=bool(msg.is_open),
        is_terminal=bool(msg.is_terminal),
        smart_account_address=account_fields.get("smart_account_address", ""),
        lifecycle_reason=lifecycle_reason_from_code(int(msg.lifecycle_reason)),
        zipper_reason=_zipper_reason_if_present(msg),
        is_delayed=bool(msg.is_delayed),
        participation=flow_participation_label(msg.participation),
        source_address=str(msg.source_address or ""),
        destination_address=str(msg.destination_address or ""),
        **_flow_summary_detail_fields(msg),
    )


def flow_tx_match_from_proto(msg: FlowTxMatchView) -> LifecycleFlowSummary:
    account_fields = lifecycle_account_fields(msg)
    return LifecycleFlowSummary(
        intent_id=msg.flow_id,
        flow_kind=_flow_kind_label(msg.flow_kind),
        latest_step=_flow_step_label(msg.current_step),
        is_open=bool(msg.is_open),
        is_terminal=bool(msg.is_terminal),
        smart_account_address=account_fields.get("smart_account_address", ""),
        lifecycle_reason=lifecycle_reason_from_code(int(msg.lifecycle_reason)),
        zipper_reason=_zipper_reason_if_present(msg),
        source_address=str(msg.source_address or ""),
        destination_address=str(msg.destination_address or ""),
        # A transaction match carries no fee, progress, timeline or other times.
        **_flow_tx_fields(msg),
    )


def flow_detail_from_proto(msg: lifecycle_read_pb2.FlowDetailView) -> LifecycleFlowSummary:
    return flow_summary_from_proto(_summary_from_detail(msg))


def flows_list_from_proto(msg: lifecycle_read_pb2.ListFlowsResponse) -> LifecycleFlowsList:
    for item in msg.flows:
        require_id("ListFlows", "flow_id", item.flow_id)
    return LifecycleFlowsList(
        flows=[flow_summary_from_proto(item) for item in msg.flows],
        next_page_token=msg.next_page_token,
    )


def flows_by_tx_list_from_proto(
    msg: lifecycle_read_pb2.ListFlowsByTxResponse,
) -> LifecycleFlowsList:
    for item in msg.matches:
        require_id("ListFlowsByTx", "flow_id", item.flow_id)
    return LifecycleFlowsList(
        flows=[flow_tx_match_from_proto(item) for item in msg.matches],
        next_page_token=msg.next_page_token,
    )


def flow_from_get_response(msg: lifecycle_read_pb2.GetFlowResponse) -> LifecycleFlowSummary:
    # The flow detail decoder is shared with the flow stream: check here.
    if not msg.HasField("flow"):
        raise PolyesterResponseContractError("GetFlowById", "missing flow")
    if not msg.flow.HasField("summary"):
        raise PolyesterResponseContractError("GetFlowById", "missing flow summary")
    require_id("GetFlowById", "flow_id", msg.flow.summary.flow_id)
    return flow_detail_from_proto(msg.flow)


def flow_from_get_by_tx_response(
    msg: lifecycle_read_pb2.ListFlowsByTxResponse,
) -> LifecycleFlowsList:
    """Decode every flow in a transaction lookup response.

    The legacy helper name is retained for compatibility, but transaction
    lookups are one-to-many and must not silently discard bundled flows.
    """
    return flows_by_tx_list_from_proto(msg)


def account_flows_list_from_proto(
    msg: lifecycle_read_pb2.ListAccountFlowsResponse,
) -> LifecycleFlowsList:
    for item in msg.flows:
        require_id("ListAccountFlows", "flow_id", item.flow_id)
    return LifecycleFlowsList(
        flows=[flow_summary_from_proto(item) for item in msg.flows],
        next_page_token=msg.next_page_token,
    )


def flow_from_get_account_flow_response(
    msg: lifecycle_read_pb2.GetAccountFlowResponse,
) -> LifecycleFlowSummary:
    if not msg.HasField("flow"):
        raise PolyesterResponseContractError("GetAccountFlow", "missing flow")
    if not msg.flow.HasField("summary"):
        raise PolyesterResponseContractError("GetAccountFlow", "missing flow summary")
    require_id("GetAccountFlow", "flow_id", msg.flow.summary.flow_id)
    return flow_detail_from_proto(msg.flow)
