from polyester.codecs.decode.market_data import candle_point_from_proto, candles_from_proto
from polyester.gen.marketdata.v1 import marketdata_pb2


def test_candle_point_from_proto_converts_price_ticks_to_decimal() -> None:
    point = marketdata_pb2.CandlePoint(
        ts_sec=1_700_000_000,
        open=1_000_000_000,
        high=1_100_000_000,
        low=900_000_000,
        close=1_050_000_000,
        volume=250_000_000,
        is_closed=True,
    )

    candle = candle_point_from_proto(point, volume_scale=8)

    assert candle.open == "1000"
    assert candle.high == "1100"
    assert candle.low == "900"
    assert candle.close == "1050"
    assert candle.volume == "2.5"
    assert candle.is_closed is True


def test_candles_from_proto_uses_volume_scale() -> None:
    response = marketdata_pb2.GetCandlesResponse(
        symbol_id=42,
        timeframe=marketdata_pb2.MIN_1,
        candles=[
            marketdata_pb2.CandlePoint(
                ts_sec=1,
                open=2_000_000,
                high=2_000_000,
                low=2_000_000,
                close=2_000_000,
                volume=10_000_000,
            )
        ],
    )

    result = candles_from_proto(response, volume_scale=6)

    assert result.symbol_id == 42
    assert result.timeframe == "1m"
    assert result.candles[0].close == "2"
    assert result.candles[0].volume == "10"
