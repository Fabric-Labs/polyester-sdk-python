from __future__ import annotations

from polyester.codecs.ledger_amounts import LEDGER_SCALE
from polyester.errors import PolyesterResponseContractError
from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.models import (
    InternalTransferBatchLegResult,
    InternalTransferBatchResult,
    InternalTransferResult,
)
from polyester.types.money import AssetAmount, QuantityDomain


def _u128_scaled(msg) -> int:
    if msg is None:
        return 0
    return (int(getattr(msg, "hi", 0) or 0) << 64) + int(getattr(msg, "lo", 0) or 0)


_INTERNAL_TRANSFER_STATUS_LABELS = {
    internal_transfer_pb2.INTERNAL_TRANSFER_STATUS_UNSPECIFIED: "",
    internal_transfer_pb2.INTERNAL_TRANSFER_STATUS_ACCEPTED: "accepted",
    internal_transfer_pb2.INTERNAL_TRANSFER_STATUS_REJECTED: "rejected",
    internal_transfer_pb2.INTERNAL_TRANSFER_STATUS_FAILED: "failed",
}


def _internal_transfer_status_label(value: int) -> str:
    label = _INTERNAL_TRANSFER_STATUS_LABELS.get(value)  # type: ignore[call-overload]
    return f"UNKNOWN({value})" if label is None else label


def internal_transfer_from_proto(
    msg: internal_transfer_pb2.CreateInternalTransferResponse,
) -> InternalTransferResult:
    if not msg.request_id.strip() or not msg.transfer_id.strip():
        raise PolyesterResponseContractError(
            "CreateInternalTransfer", "missing request_id or transfer_id"
        )
    return InternalTransferResult(
        request_id=msg.request_id,
        transfer_id=msg.transfer_id,
        asset_id=int(msg.asset_id),
        asset_code=msg.asset_code,
        quantity=AssetAmount.from_scaled(
            _u128_scaled(msg.amount_e18) if msg.HasField("amount_e18") else 0,
            scale=LEDGER_SCALE,
            domain=QuantityDomain.LEDGER_E18,
            asset_id=int(msg.asset_id),
        ),
        status=_internal_transfer_status_label(int(msg.status)),
        flow_id=msg.flow_id,
    )


_BATCH_STATUS_LABELS = {
    internal_transfer_pb2.BATCH_SUBMITTED: "submitted",
    internal_transfer_pb2.BATCH_REFUSED: "refused",
}

_LEG_STATUS_LABELS = {
    internal_transfer_pb2.LEG_ACCEPTED: "accepted",
    internal_transfer_pb2.LEG_PENDING: "pending",
    internal_transfer_pb2.LEG_REFUSED: "refused",
    internal_transfer_pb2.LEG_NOT_SUBMITTED: "not_submitted",
}


def transfer_error_label(code: int) -> str:
    """A ``transfer.v1.ErrorCode`` as a lowercase label without its prefix
    (``"insufficient_funds"``); "" when unspecified, ``UNKNOWN_ERROR_CODE(n)``
    for a code this SDK does not know."""
    if code == 0:
        return ""
    try:
        name = internal_transfer_pb2.ErrorCode.Name(code)
    except ValueError:
        return f"UNKNOWN_ERROR_CODE({code})"
    return name.removeprefix("ERROR_CODE_").lower()


def _batch_leg_from_proto(
    msg: internal_transfer_pb2.InternalTransferBatchLegResult,
) -> InternalTransferBatchLegResult:
    operation = "BatchCreateInternalTransfers"
    status = _LEG_STATUS_LABELS.get(msg.status)  # type: ignore[call-overload]
    if status is None:
        raise PolyesterResponseContractError(
            operation, f"leg {msg.leg_index} has no known status ({int(msg.status)})"
        )
    if status in ("accepted", "pending") and not msg.request_id:
        raise PolyesterResponseContractError(
            operation, f"{status} leg {msg.leg_index} is missing request_id"
        )
    if status == "accepted" and not msg.transfer_id:
        raise PolyesterResponseContractError(
            operation, f"accepted leg {msg.leg_index} is missing transfer_id"
        )
    asset_id = int(msg.asset_id)
    return InternalTransferBatchLegResult(
        leg_index=int(msg.leg_index),
        status=status,
        request_id=msg.request_id,
        transfer_id=msg.transfer_id,
        flow_id=msg.flow_id,
        accepted_at_ts_ns=int(msg.accepted_at_ts_ns) or None,
        asset_id=asset_id,
        asset_code=msg.asset_code,
        quantity=AssetAmount.from_scaled(
            _u128_scaled(msg.amount_e18) if msg.HasField("amount_e18") else 0,
            scale=LEDGER_SCALE,
            domain=QuantityDomain.LEDGER_E18,
            asset_id=asset_id,
        ),
        error_code=transfer_error_label(int(msg.error_code)),
        error_message=msg.error_message,
    )


def internal_transfer_batch_from_proto(
    msg: internal_transfer_pb2.BatchCreateInternalTransfersResponse, *, leg_count: int
) -> InternalTransferBatchResult:
    """Decode a batch reply to a request of ``leg_count`` legs.

    It must name a known batch status, carry its ``request_id`` when
    submitted, and answer every requested leg once, in request order.
    """
    operation = "BatchCreateInternalTransfers"
    status = _BATCH_STATUS_LABELS.get(msg.status)  # type: ignore[call-overload]
    if status is None:
        raise PolyesterResponseContractError(
            operation, f"no known batch status ({int(msg.status)})"
        )
    if status == "submitted" and not msg.request_id:
        raise PolyesterResponseContractError(operation, "submitted batch is missing request_id")
    if len(msg.legs) != leg_count:
        raise PolyesterResponseContractError(
            operation, f"answered {len(msg.legs)} legs for {leg_count} requested"
        )
    for index, leg in enumerate(msg.legs):
        if leg.leg_index != index:
            raise PolyesterResponseContractError(
                operation, f"leg {index} answered as leg_index {leg.leg_index}"
            )
    legs = [_batch_leg_from_proto(leg) for leg in msg.legs]
    if status == "refused" and any(leg.status == "accepted" for leg in legs):
        raise PolyesterResponseContractError(operation, "refused batch has an accepted leg")
    return InternalTransferBatchResult(request_id=msg.request_id, status=status, legs=legs)
