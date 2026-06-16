from __future__ import annotations

from polyester.codecs.proto_helpers import u128_to_str
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.models import (
    AssetBalance,
    BalancesList,
    LedgerHealth,
)


def u128_from_proto(msg: ledger_read_pb2.U128) -> str:
    return u128_to_str(msg.hi, msg.lo)


def asset_balance_from_proto(msg: ledger_read_pb2.AssetBalance) -> AssetBalance:
    return AssetBalance(
        asset_id=int(msg.asset_id),
        trading=u128_from_proto(msg.trading),
        funding=u128_from_proto(msg.funding),
        reserved=u128_from_proto(msg.reserved),
        available=u128_from_proto(msg.available),
    )


def balances_list_from_proto(msg: ledger_read_pb2.GetBalancesResponse) -> BalancesList:
    return BalancesList(balances=[asset_balance_from_proto(item) for item in msg.balances])


def ledger_health_from_proto(msg: ledger_read_pb2.GetHealthResponse) -> LedgerHealth:
    return LedgerHealth(ok=bool(msg.ok), version=msg.version)
