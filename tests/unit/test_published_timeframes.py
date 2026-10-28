import pytest

from polyester.codecs.decode.market_data import _timeframe_label
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.services.market_data import _resolve_candle_channel_timeframe


@pytest.mark.parametrize(
    ("alias", "label"),
    [("3m", "3m"), ("MIN_3", "3m"), ("2h", "2h"), ("HOUR_6", "6h"), ("8h", "8h"), ("DAY_3", "3d")],
)
def test_candle_channel_accepts_published_intervals(alias: str, label: str) -> None:
    assert _resolve_candle_channel_timeframe(alias) == label


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (marketdata_pb2.MIN_3, "3m"),
        (marketdata_pb2.HOUR_2, "2h"),
        (marketdata_pb2.HOUR_6, "6h"),
        (marketdata_pb2.HOUR_8, "8h"),
        (marketdata_pb2.DAY_3, "3d"),
    ],
)
def test_decode_labels_published_intervals(value: int, label: str) -> None:
    assert _timeframe_label(value) == label
