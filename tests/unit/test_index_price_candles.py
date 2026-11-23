"""``market_data.get_index_price_candles`` wraps ``GetIndexPriceCandles``.

The request carries exactly the symbol, timeframe, limit, bounds and token the
caller gave, in the body of a POST with no query string. The column reply
decodes into rows, newest first as sent, with prices at the pair's
``reference_price_scale`` and each row's source. A malformed reply, a pair
without a reference price scale and arguments the contract refuses fail
without a decoded page.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from google.protobuf.json_format import MessageToDict, ParseDict
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, Polyester
from polyester.codecs.decode.market_data import index_price_candles_from_proto
from polyester.errors import PolyesterTransportError, PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models import IndexPriceCandle, IndexPriceCandlesResult
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)

_PATH = "/marketdata.v1.MarketDataService/GetIndexPriceCandles"
_SPOT_CONFIG = {
    "pairs": [
        {
            "symbol": "BTC-USDT",
            "symbol_id": 1,
            "base_asset": "BTC",
            "base_quantity_scale": 8,
            "quote_quantity_scale": 6,
            "reference_price_scale": 2,
        },
        # A pair whose reference price scale is not known.
        {
            "symbol": "ETH-USDT",
            "symbol_id": 2,
            "base_asset": "ETH",
            "base_quantity_scale": 8,
            "quote_quantity_scale": 6,
        },
    ],
    "assets": [
        {"asset": "BTC", "market_data_volume_scale": 8},
        {"asset": "ETH", "market_data_volume_scale": 8},
    ],
}
_START = datetime(2026, 1, 1, tzinfo=UTC)
# 2026-02-01T00:00:00.25Z written at +02:00: the offset is kept, not dropped.
_END = (datetime(2026, 2, 1, tzinfo=UTC) + timedelta(milliseconds=250)).astimezone(
    timezone(timedelta(hours=2))
)
_REPLY = marketdata_pb2.GetIndexPriceCandlesResponse(
    symbol_id=1,
    timeframe=marketdata_pb2.HOUR_1,
    ts_sec=[1_769_904_000, 1_769_900_400, 1_769_896_800],
    open=[9_501_250, 9_499_000, 9_400_000],
    high=[9_512_000, 9_502_000, 9_400_001],
    low=[9_498_025, 9_497_500, 9_399_999],
    close=[9_510_100, 9_501_250, 9_400_000],
    source=[
        marketdata_pb2.INDEX_PRICE_CANDLE_SOURCE_INDEX,
        marketdata_pb2.INDEX_PRICE_CANDLE_SOURCE_REFERENCE,
        # A source this SDK does not know reads as its number.
        7,
    ],
    next_page_token="older",
)
_EXPECTED = IndexPriceCandlesResult(
    symbol_id=1,
    timeframe="1h",
    candles=[
        IndexPriceCandle(
            ts_sec=1_769_904_000,
            open="95012.5",
            high="95120",
            low="94980.25",
            close="95101",
            source="index",
        ),
        IndexPriceCandle(
            ts_sec=1_769_900_400,
            open="94990",
            high="95020",
            low="94975",
            close="95012.5",
            source="reference",
        ),
        IndexPriceCandle(
            ts_sec=1_769_896_800,
            open="94000",
            high="94000.01",
            low="93999.99",
            close="94000",
            source="7",
        ),
    ],
    next_page_token="older",
)


def _check_request(sent: marketdata_pb2.GetIndexPriceCandlesRequest) -> None:
    assert sent == marketdata_pb2.GetIndexPriceCandlesRequest(
        symbol_id=1,
        timeframe=marketdata_pb2.HOUR_1,
        limit=745,
        start_time={"seconds": int(_START.timestamp())},
        end_time={"seconds": 1_769_904_000, "nanos": 250_000_000},
        page_token="tok",
    )


async def _serve(json_wire: bool) -> tuple[MockHttpServer, list[Any]]:
    seen: list[Any] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        # Every field is in the body; a POST carries no query parameters.
        assert req.method == "POST" and req.path == _PATH
        seen.append(
            ParseDict(json.loads(req.body), marketdata_pb2.GetIndexPriceCandlesRequest())
            if json_wire
            else marketdata_pb2.GetIndexPriceCandlesRequest.FromString(req.body)
        )
        if json_wire:
            return HttpScript.json(200, MessageToDict(_REPLY))
        return connect_proto_response(_REPLY.SerializeToString())

    return await MockHttpServer.spawn(handler), seen


@pytest.mark.parametrize("json_wire", [False, True])
async def test_async_sends_exactly_the_arguments_and_decodes_the_columns(json_wire: bool) -> None:
    http, seen = await _serve(json_wire)
    client = AsyncPolyester(
        api_url=http.base_url,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
    try:
        page = await client.market_data.get_index_price_candles(
            symbol="BTC-USDT",
            timeframe="1h",
            limit=745,
            start_time=_START,
            end_time=_END,
            page_token="tok",
        )
    finally:
        await client.aclose()
        await http.aclose()
    (sent,) = seen
    _check_request(sent)
    assert page == _EXPECTED


def test_sync_sends_exactly_the_arguments_and_decodes_the_columns(httpserver: HTTPServer) -> None:
    seen: list[Request] = []

    def handler(request: Request) -> Response:
        seen.append(request)
        return Response(_REPLY.SerializeToString(), status=200, content_type="application/proto")

    httpserver.expect_request(_PATH, method="POST").respond_with_handler(handler)
    with Polyester(api_url=httpserver.url_for("").rstrip("/"), hydrate_catalogs=False) as client:
        client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
        page = client.market_data.get_index_price_candles(
            symbol_id=1,
            timeframe="HOUR_1",
            limit=745,
            start_time=_START,
            end_time=_END,
            page_token="tok",
        )
    (request,) = seen
    assert request.query_string == b""
    _check_request(marketdata_pb2.GetIndexPriceCandlesRequest.FromString(request.get_data()))
    assert page == _EXPECTED


async def test_defaults_send_only_the_market_timeframe_and_limit() -> None:
    http, seen = await _serve(False)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
    try:
        await client.market_data.get_index_price_candles(symbol="BTC-USDT")
    finally:
        await client.aclose()
        await http.aclose()
    (sent,) = seen
    assert sent == marketdata_pb2.GetIndexPriceCandlesRequest(
        symbol_id=1, timeframe=marketdata_pb2.MIN_1, limit=100
    )
    assert not sent.HasField("start_time") and not sent.HasField("end_time")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"symbol": "BTC-USDT", "limit": 10_001}, "limit 10001 is outside 0..10000"),
        ({"symbol": "BTC-USDT", "limit": True}, "limit must be an integer"),
        ({"symbol": "BTC-USDT", "timeframe": "1M"}, "Unknown candle timeframe"),
        ({"symbol": "BTC-USDT", "start_time": datetime(2026, 1, 1)}, "timezone-aware"),
        ({"symbol": "ETH-USDT"}, "index price candles require reference_price_scale"),
        ({"symbol": "NOPE-USDT"}, "NOPE-USDT"),
    ],
)
async def test_refused_arguments_send_nothing(kwargs: dict[str, Any], message: str) -> None:
    http, seen = await _serve(False)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    client.catalogs.hydrate_spot_config(_SPOT_CONFIG)
    try:
        with pytest.raises(PolyesterValidationError, match=message):
            await client.market_data.get_index_price_candles(**kwargs)
    finally:
        await client.aclose()
        await http.aclose()
    assert seen == []


@pytest.mark.parametrize("column", ["open", "high", "low", "close", "source"])
def test_a_column_of_another_length_is_a_contract_violation(column: str) -> None:
    reply = marketdata_pb2.GetIndexPriceCandlesResponse()
    reply.CopyFrom(_REPLY)
    del getattr(reply, column)[-1]
    with pytest.raises(PolyesterTransportError, match=f"{column}=2"):
        index_price_candles_from_proto(reply, reference_price_scale=2)


def test_an_empty_page_decodes_to_no_candles() -> None:
    page = index_price_candles_from_proto(
        marketdata_pb2.GetIndexPriceCandlesResponse(symbol_id=1, timeframe=marketdata_pb2.DAY_1),
        reference_price_scale=2,
    )
    assert page == IndexPriceCandlesResult(symbol_id=1, timeframe="1d", candles=[])
