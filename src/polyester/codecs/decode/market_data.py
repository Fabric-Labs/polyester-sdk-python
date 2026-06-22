from __future__ import annotations

from polyester.codecs.proto_helpers import proto_enum_name
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models.market import (
    Candle,
    CandlesResult,
    MarketTrade,
    MarketTradesResult,
)

_TIMEFRAME_LABELS = {
    marketdata_pb2.SEC_1: "1s",
    marketdata_pb2.MIN_1: "1m",
    marketdata_pb2.MIN_5: "5m",
    marketdata_pb2.MIN_15: "15m",
    marketdata_pb2.MIN_30: "30m",
    marketdata_pb2.HOUR_1: "1h",
    marketdata_pb2.HOUR_4: "4h",
    marketdata_pb2.HOUR_12: "12h",
    marketdata_pb2.DAY_1: "1d",
    marketdata_pb2.WEEK_1: "1w",
    marketdata_pb2.MONTH_1: "1mo",
}


def _timeframe_label(value: int) -> str:
    if value in _TIMEFRAME_LABELS:
        return _TIMEFRAME_LABELS[value]
    return proto_enum_name(marketdata_pb2.Timeframe, value)


def market_trade_from_proto(msg: marketdata_pb2.MarketTrade) -> MarketTrade:
    return MarketTrade(
        symbol_id=int(msg.symbol_id),
        match_id=str(msg.match_id),
        is_buy=bool(msg.is_buy),
        price_ticks=str(msg.price_ticks),
        qty_scaled=str(msg.qty_scaled),
        ts_ns=str(msg.ts_ns),
    )


def market_trades_from_proto(msg: marketdata_pb2.GetTradesResponse) -> MarketTradesResult:
    return MarketTradesResult(
        trades=[market_trade_from_proto(item) for item in msg.trades],
        next_match_id=msg.next_page_token,
    )


def candle_point_from_proto(msg: marketdata_pb2.CandlePoint) -> Candle:
    return Candle(
        ts_sec=int(msg.ts_sec),
        open=str(msg.open),
        high=str(msg.high),
        low=str(msg.low),
        close=str(msg.close),
        volume=str(msg.volume),
        is_closed=bool(msg.is_closed),
    )


def candles_from_proto(msg: marketdata_pb2.GetCandlesResponse) -> CandlesResult:
    return CandlesResult(
        symbol_id=int(msg.symbol_id),
        timeframe=_timeframe_label(msg.timeframe),
        candles=[candle_point_from_proto(item) for item in msg.candles],
    )


def candles_columns_from_proto(msg: marketdata_pb2.GetCandlesColumnsResponse) -> CandlesResult:
    candles: list[Candle] = []
    for index, ts in enumerate(msg.ts_sec):
        candles.append(
            Candle(
                ts_sec=int(ts),
                open=str(msg.open[index]) if index < len(msg.open) else "",
                high=str(msg.high[index]) if index < len(msg.high) else "",
                low=str(msg.low[index]) if index < len(msg.low) else "",
                close=str(msg.close[index]) if index < len(msg.close) else "",
                volume=str(msg.volume[index]) if index < len(msg.volume) else "",
            )
        )
    return CandlesResult(
        symbol_id=int(msg.symbol_id),
        timeframe=_timeframe_label(msg.timeframe),
        candles=candles,
    )
