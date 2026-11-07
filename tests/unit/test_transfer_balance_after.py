"""Transfer rows keep the post-transfer balance and link ID the server sends."""

from __future__ import annotations

from typing import Any

import msgspec

from polyester.codecs.decode.transfers import ledger_transfer_from_proto, transfers_list_from_proto
from polyester.codecs.realtime_decode import decode_ledger_transfer_batch_bytes
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.models import LedgerTransfer


def _populated_row() -> ledger_read_pb2.TransferRow:
    # Both values lie beyond float64's exact integer range: 2**64 + 5 and 2**63 + 1.
    return ledger_read_pb2.TransferRow(
        asset_id=2,
        amount_e18=u128_pb2.U128(lo=1000),
        balance_after_e18=u128_pb2.U128(hi=1, lo=5),
        link_id=9223372036854775809,
        ts_us=999,
        transfer_id="42",
    )


def _as_builtins(transfer: LedgerTransfer) -> dict[str, Any]:
    # Serialised as a caller would see it, independent of the field types.
    value = msgspec.to_builtins(transfer)
    assert isinstance(value, dict)
    return value


def test_transfer_read_and_stream_keep_balance_after_and_link_id() -> None:
    row = _populated_row()
    batch = ledger_read_pb2.TransferRowBatch(events=[row]).SerializeToString()
    streamed = decode_ledger_transfer_batch_bytes(batch)
    listed = transfers_list_from_proto(ledger_read_pb2.ListTransfersResponse(transfers=[row]))
    assert isinstance(streamed[0], LedgerTransfer)
    for path, transfer in (("list", listed.transfers[0]), ("stream", streamed[0])):
        got = _as_builtins(transfer)
        assert got.get("balance_after") == "18446744073709551621", path
        assert got.get("link_id") == "9223372036854775809", path


def test_transfer_balance_after_zero_is_not_absent() -> None:
    zero = _populated_row()
    zero.balance_after_e18.CopyFrom(u128_pb2.U128())
    zero.link_id = 0
    got = _as_builtins(ledger_transfer_from_proto(zero))
    assert got.get("balance_after") == "0", "a zero post-transfer balance must read '0'"
    # The contract sends link_id 0 when no correlation ID exists.
    assert "link_id" not in got

    absent = _populated_row()
    absent.ClearField("balance_after_e18")
    got = _as_builtins(ledger_transfer_from_proto(absent))
    assert "balance_after" not in got
