from __future__ import annotations

from google.protobuf.message import Message

from polyester.codecs.ledger_amounts import LEDGER_SCALE
from polyester.codecs.proto_helpers import format_uint64_id, has_field, proto_enum_name, u128_to_str
from polyester.errors import PolyesterResponseContractError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.v1 import catalog_pb2
from polyester.models import (
    AssetBalance,
    BalanceHistory,
    BalanceHistorySeries,
    BalancesList,
    BalanceUpdate,
    EquityHistory,
    EquityHistorySeries,
)
from polyester.types.money import AssetAmount, QuantityDomain

_BALANCE_RANGE_LABELS: dict[int, str] = {
    ledger_read_pb2.DAY_1: "1d",
    ledger_read_pb2.DAY_7: "7d",
    ledger_read_pb2.DAY_30: "30d",
    ledger_read_pb2.DAY_90: "90d",
    ledger_read_pb2.DAY_180: "180d",
    ledger_read_pb2.DAY_365: "365d",
}


def u128_from_proto(msg: Message) -> str:
    return u128_to_str(int(getattr(msg, "hi", 0)), int(getattr(msg, "lo", 0)))


def _balance_range_label(value: int) -> str:
    if value in _BALANCE_RANGE_LABELS:
        return _BALANCE_RANGE_LABELS[value]
    name = proto_enum_name(ledger_read_pb2.BalanceRange, value)
    return name.replace("day_", "") + "d" if name.startswith("day_") else name


def asset_balance_from_proto(msg: ledger_read_pb2.AssetBalance) -> AssetBalance:
    return AssetBalance(
        asset_id=int(msg.asset_id),
        trading=u128_from_proto(msg.trading),
        funding=u128_from_proto(msg.funding),
        reserved=u128_from_proto(msg.reserved),
        available=u128_from_proto(msg.available),
        funding_revision=int(msg.funding_revision),
    )


def balances_list_from_proto(msg: ledger_read_pb2.GetBalancesResponse) -> BalancesList:
    return BalancesList(
        balances=[asset_balance_from_proto(item) for item in msg.balances],
        trading_epoch=int(msg.trading_epoch),
        trading_sequence=int(msg.trading_sequence),
        trading_applied_through_ts_ns=int(msg.trading_applied_through_ts_ns),
    )


def balance_update_from_proto(msg: ledger_read_pb2.BalanceUpdate) -> BalanceUpdate:
    """One balance stream publication, field for field: no buffering, ordering
    or merging; a client applies it as the README's reload loop says."""
    # Imported here: the transfer decoder imports this module.
    from polyester.codecs.decode.transfers import ledger_transfer_from_proto

    return BalanceUpdate(
        account=proto_enum_name(catalog_pb2.AccountCode, int(msg.account)),
        trading_epoch=int(msg.trading_epoch),
        trading_sequence=int(msg.trading_sequence),
        complete=bool(msg.complete),
        balances=[asset_balance_from_proto(item) for item in msg.balances],
        transfers=[ledger_transfer_from_proto(item) for item in msg.transfers],
        trading_applied_through_ts_ns=int(msg.trading_applied_through_ts_ns),
    )


def ledger_amount(scaled: int, asset_id: int | None) -> AssetAmount:
    """An exact 18-decimal ledger amount, as ``AssetAmount`` (domain ``ledger_e18``)."""
    return AssetAmount(
        scaled=scaled, scale=LEDGER_SCALE, domain=QuantityDomain.LEDGER_E18, asset_id=asset_id
    )


def balance_history_series_from_proto(msg: ledger_read_pb2.BalanceSeries) -> BalanceHistorySeries:
    asset_id = int(msg.asset_id)
    return BalanceHistorySeries(
        asset_id=asset_id,
        account_code=int(msg.account_code),
        # Exact integers: (hi << 64) | lo, never a float.
        balance=[ledger_amount((int(v.hi) << 64) | int(v.lo), asset_id) for v in msg.balance],
    )


def balance_history_from_proto(msg: ledger_read_pb2.GetBalanceHistoryResponse) -> BalanceHistory:
    points = int(msg.points)
    series = [balance_history_series_from_proto(item) for item in msg.series]
    for item in series:
        # Each series holds one balance per point. A server on an older
        # contract sends its balances in a field this SDK no longer reads, so
        # an empty series must not read as a history without balances.
        if len(item.balance) != points:
            raise PolyesterResponseContractError(
                "GetBalanceHistory",
                f"series of asset {item.asset_id} has {len(item.balance)} balances "
                f"for {points} points",
            )
    return BalanceHistory(
        range=_balance_range_label(msg.range),
        bucket=msg.bucket,
        start_ts_sec=int(msg.start_ts_sec),
        end_ts_sec=int(msg.end_ts_sec),
        points=points,
        series=series,
    )


def equity_history_series_from_proto(msg: ledger_read_pb2.EquitySeries) -> EquityHistorySeries:
    account_code = 0
    account_name = ""
    asset_id = 0
    asset_symbol = ""
    portfolio_account_id = ""
    portfolio_remaining = False
    if msg.HasField("account"):
        account_code = int(msg.account.account_code)
        account_name = msg.account.name
    elif msg.HasField("asset"):
        asset_id = int(msg.asset.id)
        asset_symbol = msg.asset.symbol
    elif msg.HasField("portfolio_account"):
        grouping = msg.portfolio_account
        if has_field(grouping, "account_id"):
            portfolio_account_id = format_uint64_id(int(grouping.account_id))
        portfolio_remaining = bool(grouping.remaining)
    return EquityHistorySeries(
        account_code=account_code,
        account_name=account_name,
        asset_id=asset_id,
        asset_symbol=asset_symbol,
        portfolio_account_id=portfolio_account_id,
        portfolio_remaining=portfolio_remaining,
        equity_q=[int(v) for v in msg.equity_q],
    )


def equity_history_from_proto(
    msg: ledger_read_pb2.GetEquityHistorySeriesResponse,
) -> EquityHistory:
    return EquityHistory(
        range=_balance_range_label(msg.range),
        bucket=msg.bucket,
        start_ts_sec=int(msg.start_ts_sec),
        end_ts_sec=int(msg.end_ts_sec),
        quote_asset=msg.quote_asset,
        points=int(msg.points),
        series=[equity_history_series_from_proto(item) for item in msg.series],
        btc_prices_q=[int(v) for v in msg.btc_prices_q],
    )
