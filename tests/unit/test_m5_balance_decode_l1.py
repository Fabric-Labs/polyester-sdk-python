"""POLY-3746 M5 L1: direct decoder preserves scaled ledger integers (not L2)."""

from __future__ import annotations

from polyester.codecs.decode.balances import asset_balance_from_proto
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2


def test_l1_m5_balance_decode_lo_1e18_stays_string() -> None:
    msg = ledger_read_pb2.AssetBalance(
        asset_id=1,
        trading=u128_pb2.U128(hi=0, lo=10**18),
        funding=u128_pb2.U128(hi=0, lo=0),
        reserved=u128_pb2.U128(hi=0, lo=0),
        available=u128_pb2.U128(hi=0, lo=10**18),
    )
    result = asset_balance_from_proto(msg)
    assert result.trading == "1000000000000000000"
    assert isinstance(result.trading, str)
    assert result.available == "1000000000000000000"
