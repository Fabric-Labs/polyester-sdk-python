from __future__ import annotations

from polyester.codecs.ledger_amounts import LEDGER_SCALE
from polyester.errors import PolyesterResponseContractError
from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.models import (
    InternalTransferBatchLegResult,
    InternalTransferBatchResult,
    InternalTransferResult,
    ResolvedDestination,
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
    internal_transfer_pb2.BATCH_REFUSED: "refused",
    internal_transfer_pb2.BATCH_PROCESSING: "processing",
    internal_transfer_pb2.BATCH_ACCEPTED: "accepted",
}

_LEG_STATUS_LABELS = {
    internal_transfer_pb2.LEG_PROCESSING: "processing",
    internal_transfer_pb2.LEG_CREDITED: "credited",
    internal_transfer_pb2.LEG_NOT_MOVED: "not_moved",
}

# The only leg status each batch status admits: a batch moves as one.
_LEG_STATUS_OF_BATCH = {
    "refused": "not_moved",
    "processing": "processing",
    "accepted": "credited",
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
    msg: internal_transfer_pb2.InternalTransferBatchLegResult, *, operation: str
) -> InternalTransferBatchLegResult:
    status = _LEG_STATUS_LABELS.get(msg.status)  # type: ignore[call-overload]
    if status is None:
        raise PolyesterResponseContractError(
            operation, f"leg {msg.leg_index} has no known status ({int(msg.status)})"
        )
    if status in ("processing", "credited") and not msg.transfer_id:
        raise PolyesterResponseContractError(
            operation, f"{status} leg {msg.leg_index} is missing transfer_id"
        )
    # The contract sets a leg's lifecycle flow and credit time once it is
    # credited: a credited leg without them is not a receipt of a credit.
    if status == "credited" and not msg.flow_id:
        raise PolyesterResponseContractError(
            operation, f"credited leg {msg.leg_index} is missing flow_id"
        )
    if status == "credited" and not msg.credited_at_ts_ns:
        raise PolyesterResponseContractError(
            operation, f"credited leg {msg.leg_index} is missing credited_at_ts_ns"
        )
    asset_id = int(msg.asset_id)
    return InternalTransferBatchLegResult(
        leg_index=int(msg.leg_index),
        status=status,
        transfer_id=msg.transfer_id,
        flow_id=msg.flow_id,
        credited_at_ts_ns=int(msg.credited_at_ts_ns) or None,
        asset_id=asset_id,
        asset_code=msg.asset_code,
        quantity=AssetAmount.from_scaled(
            _u128_scaled(msg.amount_e18) if msg.HasField("amount_e18") else 0,
            scale=LEDGER_SCALE,
            domain=QuantityDomain.LEDGER_E18,
            asset_id=asset_id,
        ),
        destination=(
            ResolvedDestination(
                root_account_public_id=msg.destination.root_account_public_id,
                subaccount_public_id=msg.destination.subaccount_public_id,
                smart_account_address=msg.destination.smart_account_address,
            )
            if msg.HasField("destination")
            else None
        ),
        error_code=transfer_error_label(int(msg.error_code)),
        error_message=msg.error_message,
    )


def internal_transfer_batch_from_proto(
    msg: internal_transfer_pb2.BatchCreateInternalTransfersResponse
    | internal_transfer_pb2.GetInternalTransferBatchResponse,
    *,
    leg_count: int | None = None,
    request_id: str | None = None,
    operation: str = "BatchCreateInternalTransfers",
) -> InternalTransferBatchResult:
    """Decode a batch answer, from a create of ``leg_count`` legs or a read
    of the batch ``request_id``.

    It must name a known batch status and carry its ``request_id`` unless
    refused (a read must answer the batch it named), answer every requested
    leg once in request order, give a processing or credited leg its
    ``transfer_id`` and a credited leg its ``flow_id`` and
    ``credited_at_ts_ns``, and give every leg the one status its batch
    status admits: ``"credited"`` for an accepted batch, ``"processing"`` for
    a processing one and ``"not_moved"`` for a refused one.
    """
    status = _BATCH_STATUS_LABELS.get(msg.status)  # type: ignore[call-overload]
    if status is None:
        raise PolyesterResponseContractError(
            operation, f"no known batch status ({int(msg.status)})"
        )
    if status != "refused" and not msg.request_id:
        raise PolyesterResponseContractError(operation, f"{status} batch is missing request_id")
    if request_id is not None and msg.request_id != request_id:
        raise PolyesterResponseContractError(
            operation, f"answered batch {msg.request_id!r} for {request_id!r}"
        )
    if leg_count is not None and len(msg.legs) != leg_count:
        raise PolyesterResponseContractError(
            operation, f"answered {len(msg.legs)} legs for {leg_count} requested"
        )
    if not msg.legs:
        raise PolyesterResponseContractError(operation, "batch has no legs")
    for index, leg in enumerate(msg.legs):
        if leg.leg_index != index:
            raise PolyesterResponseContractError(
                operation, f"leg {index} answered as leg_index {leg.leg_index}"
            )
    legs = [_batch_leg_from_proto(leg, operation=operation) for leg in msg.legs]
    expected = _LEG_STATUS_OF_BATCH[status]
    for leg in legs:
        if leg.status != expected:
            raise PolyesterResponseContractError(
                operation, f"{status} batch has a {leg.status} leg {leg.leg_index}"
            )
    return InternalTransferBatchResult(request_id=msg.request_id, status=status, legs=legs)
