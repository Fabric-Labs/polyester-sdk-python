from __future__ import annotations

from types import SimpleNamespace

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.codecs.decode.market_data import candle_point_from_proto, candles_columns_from_proto
from polyester.codecs.decode.market_overview import (
    market_overview_entry_from_proto,
    spot_volume_history_from_proto,
)
from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.orders import cancel_all_orders_to_proto
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterApiError, PolyesterAuthError, PolyesterValidationError
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services._symbols import resolve_cancel_all_symbol_ids


def test_cancel_all_orders_to_proto_uses_repeated_symbol_ids() -> None:
    proto = cancel_all_orders_to_proto(symbol_ids=[3, 3, 7], dry_run=True)
    assert proto.dry_run is True
    assert list(proto.symbol_ids) == [3, 7]
    assert not proto.HasField("subaccount_id")


def test_cancel_all_orders_to_proto_empty_matches_all_symbols() -> None:
    proto = cancel_all_orders_to_proto()
    assert list(proto.symbol_ids) == []


def test_cancel_all_orders_to_proto_rejects_zero_and_over_limit() -> None:
    with pytest.raises(PolyesterValidationError, match="positive"):
        cancel_all_orders_to_proto(symbol_ids=[0])
    with pytest.raises(PolyesterValidationError, match="at most 100"):
        cancel_all_orders_to_proto(symbol_ids=list(range(1, 102)))


def test_resolve_cancel_all_symbol_ids_is_mutually_exclusive() -> None:
    catalogs = SimpleNamespace(
        symbol_id_for_symbol=lambda symbol: 1 if symbol == "BTC-USDT" else None
    )
    assert resolve_cancel_all_symbol_ids(catalogs, symbol="BTC-USDT") == [1]
    assert resolve_cancel_all_symbol_ids(catalogs, symbols=["BTC-USDT", "BTC-USDT"]) == [1]
    assert resolve_cancel_all_symbol_ids(catalogs, symbol_ids=[2, 2, 5]) == [2, 5]
    with pytest.raises(PolyesterValidationError, match="only one of"):
        resolve_cancel_all_symbol_ids(catalogs, symbol="BTC-USDT", symbol_ids=[2])


def test_twap_market_ioc_encodes_optional_slippage() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="twap",
        side="buy",
        qty="1",
        quantity_scale=8,
        twap_duration_ms=60_000,
        twap_slice_interval_ms=5_000,
        max_slippage_bps=25,
    )
    assert proto.trigger.twap.HasField("market_ioc")
    assert proto.trigger.twap.market_ioc.max_slippage_bps == 25
    with pytest.raises(PolyesterValidationError, match="1 and 10000"):
        create_trigger_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            trigger_type="twap",
            side="buy",
            qty="1",
            quantity_scale=8,
            max_slippage_bps=10_001,
        )


def test_ladder_details_decode_executed_fields() -> None:
    msg = triggers_pb2.Trigger(
        trigger_id=9,
        symbol_id=1,
        status=triggers_pb2.STATUS_RUNNING,
        qty_scaled=100_000_000,
        ladder=triggers_pb2.LadderTrigger(
            side=orders_pb2.BUY,
            price_min_ticks=1,
            price_max_ticks=2,
            levels=4,
        ),
        ladder_state=triggers_pb2.LadderDetails(
            ladder_price_min_ticks=1,
            ladder_price_max_ticks=2,
            ladder_levels=4,
            executed_qty_scaled=25_000_000,
            executed_levels=2,
        ),
    )
    trigger = trigger_from_proto(msg)
    assert trigger.details is not None
    assert trigger.details.case == "ladder"
    assert trigger.details.ladder is not None
    assert trigger.details.ladder.executed_levels == 2
    assert trigger.details.ladder.executed_qty is not None
    assert trigger.details.ladder.executed_qty.scaled == 25_000_000


def test_candle_point_preserves_quote_volume() -> None:
    candle = candle_point_from_proto(
        marketdata_pb2.CandlePoint(
            ts_sec=1,
            open=1_000_000,
            high=2_000_000,
            low=500_000,
            close=1_500_000,
            volume=10,
            quote_volume="150.25",
            is_closed=True,
        ),
        volume_scale=8,
    )
    assert candle.quote_volume == "150.25"
    columns = candles_columns_from_proto(
        marketdata_pb2.GetCandlesColumnsResponse(
            symbol_id=1,
            timeframe=marketdata_pb2.MIN_1,
            ts_sec=[1],
            open=[1_000_000],
            high=[2_000_000],
            low=[500_000],
            close=[1_500_000],
            volume=[10],
            quote_volume=["150.25"],
        ),
        volume_scale=8,
    )
    assert columns.candles[0].quote_volume == "150.25"


def test_market_overview_optional_volume_fields() -> None:
    present = market_overview_entry_from_proto(
        marketoverview_pb2.MarketOverview(
            symbol_id=1,
            volume_24h_base_scaled=10,
            volume_24h_quote_scaled=20,
            volume_24h_usd_scaled=30,
        )
    )
    assert present.volume_24h_base_scaled == "10"
    assert present.volume_24h_quote_scaled == "20"
    assert present.volume_24h_usd_scaled == "30"

    absent = market_overview_entry_from_proto(marketoverview_pb2.MarketOverview(symbol_id=2))
    assert absent.volume_24h_base_scaled is None
    assert absent.volume_24h_quote_scaled is None
    assert absent.volume_24h_usd_scaled is None


def test_spot_volume_history_from_proto() -> None:
    result = spot_volume_history_from_proto(
        marketoverview_pb2.GetSpotVolumeHistoryResponse(
            bucket="15m",
            start_ts_sec=100,
            end_ts_sec=200,
            points=2,
            pairs=[
                marketoverview_pb2.SpotPairVolumeSeries(
                    symbol_id=7,
                    volume_usd_scaled=[1, 2],
                )
            ],
            total_volume_usd_scaled=[3, 4],
        )
    )
    assert result.bucket == "15m"
    assert result.points == 2
    assert result.pairs[0].symbol_id == 7
    assert result.pairs[0].volume_usd_scaled == [1, 2]
    assert result.total_volume_usd_scaled == [3, 4]


def test_empty_orderbook_with_zero_sequence_is_success() -> None:
    result = orderbook_from_proto(
        orderbook_pb2.GetOrderBookResponse(symbol_id=1, book_seq=0),
        symbol="BTC-USDT",
        depth=50,
        quantity_scale=8,
    )
    assert result.book_seq == "0"
    assert result.bids == []
    assert result.asks == []


def test_withdraw_and_transfer_error_details() -> None:
    withdraw = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "insufficient",
            details=[withdraw_pb2.ErrorDetail(code=withdraw_pb2.ERROR_CODE_INSUFFICIENT_FUNDS)],
        )
    )
    assert isinstance(withdraw, PolyesterApiError)
    assert withdraw.code == "ERROR_CODE_INSUFFICIENT_FUNDS"

    transfer = map_connect_error(
        ConnectError(
            Code.PERMISSION_DENIED,
            "denied",
            details=[transfer_pb2.ErrorDetail(code=transfer_pb2.ERROR_CODE_PERMISSION_DENIED)],
        )
    )
    assert isinstance(transfer, PolyesterAuthError)

    expired = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "expired",
            details=[orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_CANCEL_REQUEST_EXPIRED)],
        )
    )
    assert isinstance(expired, PolyesterApiError)
    assert expired.code == "ERROR_CODE_CANCEL_REQUEST_EXPIRED"


def test_auth_terms_not_accepted_is_surfaced() -> None:
    mapped = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "accept terms",
            details=[
                auth_pb2.AuthErrorDetail(
                    code=auth_pb2.AUTH_TERMS_NOT_ACCEPTED, message="terms"
                )
            ],
        )
    )
    assert isinstance(mapped, PolyesterApiError)
    assert mapped.code == "AUTH_TERMS_NOT_ACCEPTED"
    assert str(mapped) == "terms"
