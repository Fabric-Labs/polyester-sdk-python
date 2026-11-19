"""Every candle path keeps the contract's ``is_closed`` flag.

``CandlePoint.is_closed`` is true for a closed bucket (historical rows and a
live terminal update) and false only while the bucket is still open. Each path
that builds a :class:`~polyester.models.Candle` from a ``CandlePoint`` must
carry it through, both ways.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.realtime_decode import decode_candle_point_bytes
from polyester.codecs.wire_decode import decode_candles_list
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.services.market_data import AsyncMarketDataService
from tests.unit.support import CaptureUnary

SYMBOL_ID = 1


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": SYMBOL_ID,
                    "base_asset": "BTC",
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                    "reference_price_scale": 8,
                }
            ],
            "assets": [{"asset": "BTC", "market_data_volume_scale": 8}],
        }
    )
    return catalogs


def _point(ts_sec: int, *, is_closed: bool) -> marketdata_pb2.CandlePoint:
    return marketdata_pb2.CandlePoint(
        ts_sec=ts_sec,
        open=2_000_000_000,
        high=2_000_000_000,
        low=2_000_000_000,
        close=2_000_000_000,
        volume=10_000_000,
        is_closed=is_closed,
    )


@pytest.mark.parametrize("is_closed", [True, False])
@pytest.mark.asyncio
async def test_get_candles_rows_keep_is_closed(is_closed: bool) -> None:
    capture = CaptureUnary(
        marketdata_pb2.GetCandlesResponse(
            symbol_id=SYMBOL_ID,
            timeframe=marketdata_pb2.MIN_1,
            candles=[_point(120, is_closed=is_closed)],
            reference_candles=[_point(120, is_closed=is_closed)],
        )
    )
    service = AsyncMarketDataService(MagicMock(), _catalogs())
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await service.get_candles(symbol="BTC-USDT", include_reference=True)

    assert [candle.is_closed for candle in result.candles] == [is_closed]
    assert [candle.is_closed for candle in result.reference_candles] == [is_closed]


@pytest.mark.asyncio
async def test_get_current_candle_keeps_is_closed_of_open_and_closed_rows() -> None:
    open_row = _point(180, is_closed=False)
    closed_row = _point(120, is_closed=True)
    service = AsyncMarketDataService(MagicMock(), _catalogs())

    capture = CaptureUnary(
        marketdata_pb2.GetCandlesResponse(
            symbol_id=SYMBOL_ID, timeframe=marketdata_pb2.MIN_1, candles=[open_row, closed_row]
        )
    )
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        forming = await service.get_current_candle(symbol="BTC-USDT")
    assert forming is not None
    assert (forming.ts_sec, forming.is_closed) == (180, False)

    # Once the bucket has closed and no open one exists yet, the newest row is closed.
    capture = CaptureUnary(
        marketdata_pb2.GetCandlesResponse(
            symbol_id=SYMBOL_ID, timeframe=marketdata_pb2.MIN_1, candles=[closed_row]
        )
    )
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        finished = await service.get_current_candle(symbol="BTC-USDT")
    assert finished is not None
    assert (finished.ts_sec, finished.is_closed) == (120, True)


@pytest.mark.parametrize("is_closed", [True, False])
def test_live_candle_update_keeps_is_closed(is_closed: bool) -> None:
    decode = decode_candle_point_bytes(symbol_id=SYMBOL_ID, timeframe="1m", volume_scale=8)

    candle = decode(_point(180, is_closed=is_closed).SerializeToString())

    assert candle.ts_sec == 180
    assert candle.is_closed is is_closed


@pytest.mark.parametrize("is_closed", [True, False])
def test_json_candle_rows_keep_is_closed(is_closed: bool) -> None:
    data = {
        "symbolId": SYMBOL_ID,
        "timeframe": "MIN_1",
        "candles": [{"tsSec": "120", "close": "2000000000", "isClosed": is_closed}],
    }

    result = decode_candles_list(data, volume_scale=8)

    assert [candle.is_closed for candle in result.candles] == [is_closed]


def test_columnar_candles_have_no_closed_flag_in_the_contract() -> None:
    # GetCandlesColumnsResponse carries no closed column, so columnar candles
    # can't report it. When the contract adds one, decode it in
    # candles_columns_from_proto and replace this check with a decode test.
    fields = marketdata_pb2.GetCandlesColumnsResponse.DESCRIPTOR.fields_by_name
    assert not [name for name in fields if "closed" in name]
