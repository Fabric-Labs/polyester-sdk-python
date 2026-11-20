"""Every candle path reports ``is_closed``.

``CandlePoint.is_closed`` is true for a closed bucket (historical rows and a
live terminal update) and false only while the bucket is still open. Each path
that builds a :class:`~polyester.models.Candle` from a ``CandlePoint`` must
carry it through, both ways. The columnar response has no closed column: only
the newest primary row of a first page asked with ``include_incomplete`` is not
known to be closed; continuation pages and reference rows are closed.
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
    # derive is_closed from include_incomplete (tests below). When the contract
    # adds one, decode it in candles_columns_from_proto and replace this check.
    fields = marketdata_pb2.GetCandlesColumnsResponse.DESCRIPTOR.fields_by_name
    assert not [name for name in fields if "closed" in name]


def _columns() -> marketdata_pb2.GetCandlesColumnsResponse:
    # Oldest-first, as the contract orders both series.
    return marketdata_pb2.GetCandlesColumnsResponse(
        symbol_id=SYMBOL_ID,
        timeframe=marketdata_pb2.MIN_1,
        ts_sec=[60, 120, 180],
        open=[2_000_000_000] * 3,
        high=[2_000_000_000] * 3,
        low=[2_000_000_000] * 3,
        close=[2_000_000_000] * 3,
        volume=[10_000_000] * 3,
        reference_ts_sec=[60, 120, 180],
        reference_open=[200_000_000] * 3,
        reference_high=[200_000_000] * 3,
        reference_low=[200_000_000] * 3,
        reference_close=[200_000_000] * 3,
        reference_volume=[10_000_000] * 3,
    )


@pytest.mark.parametrize(
    ("include_incomplete", "page_token", "expected"),
    [
        # Without include_incomplete every row is a closed candle.
        (False, "", [True, True, True]),
        (False, "eyJ2IjoxfQ==", [True, True, True]),
        # A first page with include_incomplete may end with the open candle.
        (True, "", [True, True, False]),
        # A continuation page holds only older closed candles.
        (True, "eyJ2IjoxfQ==", [True, True, True]),
    ],
)
@pytest.mark.asyncio
async def test_get_candles_columns_is_closed_follows_the_request(
    include_incomplete: bool, page_token: str, expected: list[bool]
) -> None:
    capture = CaptureUnary(_columns())
    service = AsyncMarketDataService(MagicMock(), _catalogs())
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await service.get_candles_columns(
            symbol="BTC-USDT",
            include_incomplete=include_incomplete,
            include_reference=True,
            page_token=page_token,
        )

    assert capture.request is not None
    assert capture.request.include_incomplete is include_incomplete
    assert capture.request.page_token == page_token
    rows = list(zip([60, 120, 180], expected, strict=True))
    assert [(c.ts_sec, c.is_closed) for c in result.candles] == rows
    # Reference rows are always closed buckets, the newest included.
    assert [(c.ts_sec, c.is_closed) for c in result.reference_candles] == [
        (60, True),
        (120, True),
        (180, True),
    ]


def test_columnar_decoder_marks_only_a_first_pages_newest_primary_row() -> None:
    from polyester.codecs.decode.market_data import candles_columns_from_proto

    closed = candles_columns_from_proto(_columns(), volume_scale=8, reference_price_scale=8)
    assert [c.is_closed for c in closed.candles] == [True, True, True]
    assert [c.is_closed for c in closed.reference_candles] == [True, True, True]

    # A single row is the newest one; an empty page has no rows to mark.
    single = marketdata_pb2.GetCandlesColumnsResponse(
        ts_sec=[180], open=[1], high=[1], low=[1], close=[1], volume=[1]
    )
    only = candles_columns_from_proto(single, volume_scale=8, include_incomplete=True)
    assert [c.is_closed for c in only.candles] == [False]
    continued = candles_columns_from_proto(
        single, volume_scale=8, include_incomplete=True, page_token="eyJ2IjoxfQ=="
    )
    assert [c.is_closed for c in continued.candles] == [True]
    tip = candles_columns_from_proto(
        _columns(), volume_scale=8, reference_price_scale=8, include_incomplete=True
    )
    assert [c.is_closed for c in tip.candles] == [True, True, False]
    assert [c.is_closed for c in tip.reference_candles] == [True, True, True]
    empty = candles_columns_from_proto(
        marketdata_pb2.GetCandlesColumnsResponse(), volume_scale=8, include_incomplete=True
    )
    assert empty.candles == []


@pytest.mark.parametrize(
    ("include_incomplete", "page_token", "expected"),
    [
        (False, "", [True, True]),
        (True, "", [True, False]),
        (True, "eyJ2IjoxfQ==", [True, True]),
    ],
)
def test_json_columnar_candles_is_closed_follows_the_request(
    include_incomplete: bool, page_token: str, expected: list[bool]
) -> None:
    data = {
        "symbolId": SYMBOL_ID,
        "timeframe": "MIN_1",
        "tsSec": ["120", "180"],
        "open": ["2000000000"] * 2,
        "high": ["2000000000"] * 2,
        "low": ["2000000000"] * 2,
        "close": ["2000000000"] * 2,
        "volume": ["10000000"] * 2,
    }

    result = decode_candles_list(
        data, volume_scale=8, include_incomplete=include_incomplete, page_token=page_token
    )

    assert [c.is_closed for c in result.candles] == expected
