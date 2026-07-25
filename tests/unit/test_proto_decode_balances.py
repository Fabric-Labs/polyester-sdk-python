from polyester.codecs.decode.balances import (
    asset_balance_from_proto,
    balance_history_from_proto,
    equity_history_from_proto,
    holds_list_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2


def test_asset_balance_from_proto_preserves_uint64_revisions() -> None:
    msg = ledger_read_pb2.AssetBalance(
        asset_id=1,
        trading_revision=2**63 + 1,
        funding_revision=2**63 + 2,
    )
    result = asset_balance_from_proto(msg)
    assert result.trading_revision == 2**63 + 1
    assert result.funding_revision == 2**63 + 2


def test_balance_history_from_proto() -> None:
    msg = ledger_read_pb2.GetBalanceHistoryResponse(
        range=ledger_read_pb2.DAY_7,
        bucket="1h",
        start_ts_sec=100,
        end_ts_sec=200,
        points=2,
        series=[
            ledger_read_pb2.BalanceSeries(
                asset_id=1,
                account_code=10,
                balance_q=[100, 200],
            )
        ],
    )
    result = balance_history_from_proto(msg)
    assert result.range == "7d"
    assert result.bucket == "1h"
    assert len(result.series) == 1
    assert result.series[0].balance_q == [100, 200]


def test_equity_history_from_proto() -> None:
    msg = ledger_read_pb2.GetEquityHistorySeriesResponse(
        range=ledger_read_pb2.DAY_30,
        bucket="1d",
        start_ts_sec=1,
        end_ts_sec=2,
        quote_asset="USD",
        points=1,
        series=[
            ledger_read_pb2.EquitySeries(
                account=ledger_read_pb2.AccountGrouping(account_code=5, name="Trading"),
                equity_q=[999],
            )
        ],
    )
    result = equity_history_from_proto(msg)
    assert result.range == "30d"
    assert result.quote_asset == "USD"
    assert result.series[0].account_code == 5
    assert result.series[0].account_name == "Trading"


def test_holds_list_from_proto() -> None:
    msg = ledger_read_pb2.ListHoldsResponse(
        holds=[
            ledger_read_pb2.HoldRow(
                hold_id=42,
                asset_id=1,
                amount_reserved_e18=u128_pb2.U128(hi=0, lo=500),
                expires_at_ns=1_700_000_000_000,
            )
        ]
    )
    result = holds_list_from_proto(msg)
    assert len(result.holds) == 1
    assert result.holds[0].hold_id == format_id(42)
    assert result.holds[0].amount_reserved == "500"
