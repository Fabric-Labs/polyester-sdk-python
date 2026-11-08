"""POLY-8824: an internal transfer receipt keeps the status the service sent."""

from __future__ import annotations

import pytest

from polyester.codecs.decode.internal_transfers import internal_transfer_from_proto
from polyester.errors import PolyesterResponseContractError
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as pb


def _receipt(status: int) -> pb.CreateInternalTransferResponse:
    return pb.CreateInternalTransferResponse(
        request_id="req",
        transfer_id="xfer",
        asset_id=7,
        asset_code="USDT",
        amount_e18=u128_pb2.U128(lo=1_000_000_000_000_000_000),
        status=status,  # type: ignore[arg-type]
    )


def test_poly_8824_receipts_that_differ_only_in_status_decode_differently() -> None:
    accepted, rejected, failed = (
        internal_transfer_from_proto(_receipt(status))
        for status in (
            pb.INTERNAL_TRANSFER_STATUS_ACCEPTED,
            pb.INTERNAL_TRANSFER_STATUS_REJECTED,
            pb.INTERNAL_TRANSFER_STATUS_FAILED,
        )
    )
    assert accepted != rejected
    assert accepted != failed
    assert rejected != failed
    assert (accepted.status, rejected.status, failed.status) == ("accepted", "rejected", "failed")
    assert rejected.quantity is not None
    assert rejected.quantity.scaled == 1_000_000_000_000_000_000
    assert (rejected.request_id, rejected.transfer_id) == ("req", "xfer")


def test_poly_8824_unspecified_and_future_statuses() -> None:
    assert internal_transfer_from_proto(_receipt(0)).status == ""
    assert internal_transfer_from_proto(_receipt(42)).status == "UNKNOWN(42)"


def test_poly_8824_missing_ids_still_fail_whatever_the_status() -> None:
    receipt = _receipt(pb.INTERNAL_TRANSFER_STATUS_REJECTED)
    receipt.transfer_id = ""
    with pytest.raises(PolyesterResponseContractError):
        internal_transfer_from_proto(receipt)
