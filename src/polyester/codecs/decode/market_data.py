from __future__ import annotations

from polyester.codecs.decode.invariants import ts_ns_string_from_response
from polyester.codecs.proto_helpers import proto_enum_name
from polyester.codecs.scalars import format_price_ticks, format_qty_scaled
from polyester.errors import PolyesterTransportError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models.market import (
    Candle,
    CandlesResult,
    MarketTrade,
    MarketTradesResult,
)

_TIMEFRAME_LABELS: dict[int, str] = {
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


def market_trade_from_proto(
    msg: marketdata_pb2.MarketTrade,
    *,
    quantity_scale: int | None = None,
) -> MarketTrade:
    from polyester.types.money import Price, Quantity

    symbol_id = int(msg.symbol_id)
    return MarketTrade(
        symbol_id=symbol_id,
        match_id=str(msg.match_id),
        is_buy=bool(msg.is_buy),
        price=Price.from_ticks(int(msg.price_ticks)),
        qty=Quantity.from_scaled(int(msg.qty_scaled), scale=quantity_scale, symbol_id=symbol_id),
        ts_ns=ts_ns_string_from_response(
            msg.ts_ns,
            context="MarketTrade",
            empty_when_zero=True,
        ),
    )


def market_trades_from_proto(
    msg: marketdata_pb2.GetTradesResponse, *, quantity_scale: int
) -> MarketTradesResult:
    return MarketTradesResult(
        trades=[
            market_trade_from_proto(item, quantity_scale=quantity_scale) for item in msg.trades
        ],
        next_match_id=msg.next_page_token,
    )


def _decode_price_field(value: object) -> str:
    if value is None or value == "":
        return ""
    text = str(value)
    if "." in text:
        return text
    return format_price_ticks(int(text))


def _decode_volume_field(value: object, *, scale: int) -> str:
    if value is None or value == "":
        return ""
    text = str(value)
    if "." in text:
        return text
    return format_qty_scaled(int(text), scale)


def candle_point_from_proto(
    msg: marketdata_pb2.CandlePoint,
    *,
    volume_scale: int,
) -> Candle:
    return Candle(
        ts_sec=int(msg.ts_sec),
        open=_decode_price_field(msg.open),
        high=_decode_price_field(msg.high),
        low=_decode_price_field(msg.low),
        close=_decode_price_field(msg.close),
        volume=_decode_volume_field(msg.volume, scale=volume_scale),
        is_closed=bool(msg.is_closed),
    )


def candles_from_proto(
    msg: marketdata_pb2.GetCandlesResponse,
    *,
    volume_scale: int,
) -> CandlesResult:
    return CandlesResult(
        symbol_id=int(msg.symbol_id),
        timeframe=_timeframe_label(msg.timeframe),
        candles=[candle_point_from_proto(item, volume_scale=volume_scale) for item in msg.candles],
    )


def candles_columns_from_proto(
    msg: marketdata_pb2.GetCandlesColumnsResponse,
    *,
    volume_scale: int,
) -> CandlesResult:
    row_count = len(msg.ts_sec)
    lengths = {
        "open": len(msg.open),
        "high": len(msg.high),
        "low": len(msg.low),
        "close": len(msg.close),
        "volume": len(msg.volume),
    }
    if any(length != row_count for length in lengths.values()):
        rendered = ", ".join(
            [f"ts_sec={row_count}", *(f"{name}={length}" for name, length in lengths.items())]
        )
        raise PolyesterTransportError(f"invalid GetCandlesColumns response lengths: {rendered}")

    candles: list[Candle] = []
    for index, ts in enumerate(msg.ts_sec):
        candles.append(
            Candle(
                ts_sec=int(ts),
                open=_decode_price_field(msg.open[index]),
                high=_decode_price_field(msg.high[index]),
                low=_decode_price_field(msg.low[index]),
                close=_decode_price_field(msg.close[index]),
                volume=_decode_volume_field(
                    msg.volume[index],
                    scale=volume_scale,
                ),
            )
        )
    return CandlesResult(
        symbol_id=int(msg.symbol_id),
        timeframe=_timeframe_label(msg.timeframe),
        candles=candles,
    )
