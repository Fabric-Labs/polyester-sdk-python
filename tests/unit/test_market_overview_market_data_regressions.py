from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from google.protobuf.json_format import MessageToDict

from polyester import AsyncPolyester
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.market_overview import market_overview_list_from_proto
from polyester.codecs.realtime_decode import decode_market_overview_batch_bytes
from polyester.codecs.wire_decode import decode_market_overview_list
from polyester.errors import PolyesterValidationError
from polyester.gen.marketoverview.v1 import marketoverview_pb2 as mo
from polyester.models.market import MarketOverviewEntry
from polyester.services import market_overview
from polyester.services.market_overview import AsyncMarketOverviewService
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)

BONK_BUCKETS = [1e-09, 1e-08, 1e-07, 1e-06, 1e-05]


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "assets": [
                {"asset": "BTC", "quantityScale": 8, "marketDataVolumeScale": 8},
                {"asset": "BONK", "quantityScale": 0, "marketDataVolumeScale": 0},
                {"asset": "USDT", "quantityScale": 6, "marketDataVolumeScale": 6},
            ],
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbolId": 1,
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "baseQuantityScale": 8,
                    "tickSize": "0.01",
                    "marketdata": {"orderbookPriceBuckets": [0.01, 0.1, 1, 10, 100]},
                },
                {
                    "symbol": "BONK-USDT",
                    "symbolId": 7,
                    "baseAsset": "BONK",
                    "quoteAsset": "USDT",
                    "baseQuantityScale": 0,
                    "tickSize": "0.000000001",
                    "marketdata": {"orderbookPriceBuckets": BONK_BUCKETS},
                },
            ],
        }
    )
    return catalogs


# POLY-8785
def test_orderbook_price_buckets_keep_sub_micro_increments() -> None:
    catalogs = _catalogs()
    assert catalogs.orderbook_price_buckets_for_symbol("BONK-USDT") == [
        "0.000000001",
        "0.00000001",
        "0.0000001",
        "0.000001",
        "0.00001",
    ]
    assert catalogs.orderbook_price_buckets_for_symbol("BTC-USDT") == [
        "0.01",
        "0.1",
        "1",
        "10",
        "100",
    ]


# POLY-8784
class _VolumeCapture:
    def __init__(self) -> None:
        self.ids: list[list[int]] = []

    async def handler(self, req: ParsedRequest) -> HttpScript:
        message = mo.GetSpotVolumeHistoryRequest.FromString(req.body)
        self.ids.append(list(message.symbol_id))
        return connect_proto_response(mo.GetSpotVolumeHistoryResponse().SerializeToString())


@pytest.mark.parametrize("copies", [2, 2_001])
@pytest.mark.parametrize("form", ["symbols", "symbol_ids"])
async def test_volume_history_sends_each_selected_pair_once(form: str, copies: int) -> None:
    capture = _VolumeCapture()
    http = await MockHttpServer.spawn(capture.handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    client.catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    selector: dict[str, Any] = (
        {"symbols": ["BTC-USDT"] * copies} if form == "symbols" else {"symbol_ids": [1] * copies}
    )
    try:
        await client.market_overview.get_spot_volume_history(**selector)
    finally:
        await client.aclose()
        await http.aclose()
    assert capture.ids == [[1]]


async def test_volume_history_still_refuses_more_than_2000_distinct_pairs() -> None:
    client = AsyncPolyester(api_url="http://127.0.0.1:9", hydrate_catalogs=False)
    try:
        with pytest.raises(PolyesterValidationError, match="at most 2000"):
            await client.market_overview.get_spot_volume_history(
                symbol_ids=list(range(1, 2_002))
            )
    finally:
        await client.aclose()


def _overview_response() -> mo.ListMarketOverviewResponse:
    return mo.ListMarketOverviewResponse(
        markets=[
            mo.MarketOverview(symbol_id=1, last_price_ticks=100, change_24h_bps=-14),
            mo.MarketOverview(symbol_id=2, last_price_ticks=200, change_24h_bps=0),
            mo.MarketOverview(symbol_id=3, last_price_ticks=300, change_24h_bps=15),
        ],
        next_page_token="opaque",
    )


# POLY-8786
@pytest.mark.parametrize("snake_case", [False, True])
def test_json_overview_decoder_matches_the_protobuf_decoder(snake_case: bool) -> None:
    response = _overview_response()
    data = MessageToDict(response, preserving_proto_field_name=snake_case)
    decoded = decode_market_overview_list(data)
    expected = market_overview_list_from_proto(response)
    assert [row.change_24h_bp for row in expected.markets] == ["-14", "0", "15"]
    assert [row.change_24h_bp for row in decoded.markets] == ["-14", "0", "15"]
    assert decoded.total == expected.total == 3
    assert decoded.next_page_token == expected.next_page_token == "opaque"


# POLY-8789
def _sparkline_response() -> mo.ListMarketOverviewResponse:
    return mo.ListMarketOverviewResponse(
        markets=[
            mo.MarketOverview(
                symbol_id=1,
                last_price_ticks=101,
                sparklines=[
                    mo.Sparkline(interval=mo.SPARKLINE_24H, close_ticks=[100, 101, 99]),
                    mo.Sparkline(interval=mo.SPARKLINE_1H, close_ticks=[]),
                ],
            ),
            mo.MarketOverview(symbol_id=7, last_price_ticks=5),
        ]
    )


async def test_list_exposes_the_sparklines_it_requested() -> None:
    requests: list[mo.ListMarketOverviewRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        message = mo.ListMarketOverviewRequest.FromString(req.body)
        requests.append(message)
        response = _sparkline_response() if message.include_sparklines else mo.ListMarketOverviewResponse(
            markets=[mo.MarketOverview(symbol_id=1, last_price_ticks=101)]
        )
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(api_url=http.base_url, hydrate_catalogs=False)
    try:
        with_sparklines = await client.market_overview.list(include_sparklines=True)
        without = await client.market_overview.list(include_sparklines=False)
    finally:
        await client.aclose()
        await http.aclose()
    assert [r.include_sparklines for r in requests] == [True, False]
    btc, bonk = with_sparklines.markets
    assert [(s.interval, [p.ticks for p in s.close_prices]) for s in btc.sparklines] == [
        ("SPARKLINE_24H", [100, 101, 99]),
        ("SPARKLINE_1H", []),
    ]
    assert bonk.sparklines == []
    assert without.markets[0].sparklines == []


@pytest.mark.parametrize("snake_case", [False, True])
def test_json_overview_decoder_exposes_sparklines(snake_case: bool) -> None:
    data = MessageToDict(_sparkline_response(), preserving_proto_field_name=snake_case)
    decoded = decode_market_overview_list(data)
    assert [
        (s.interval, [p.ticks for p in s.close_prices]) for s in decoded.markets[0].sparklines
    ] == [("SPARKLINE_24H", [100, 101, 99]), ("SPARKLINE_1H", [])]


class _CapturingStream:
    instance: _CapturingStream | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        _CapturingStream.instance = self

    async def start(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


async def test_managed_subscription_keeps_snapshot_sparklines_and_enriches_live_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Live publications carry no sparklines: a live row keeps the snapshot's,
    # and is decoded with its symbol and display volume (POLY-8783 parity).
    monkeypatch.setattr(market_overview, "AsyncSnapshotThenStreamSubscription", _CapturingStream)
    catalogs = _catalogs()
    service = AsyncMarketOverviewService(MagicMock(), catalogs=catalogs, realtime=MagicMock())
    emitted: list[list[MarketOverviewEntry]] = []
    await service.create_subscription(include_sparklines=True, on_event=emitted.append)
    stream = _CapturingStream.instance
    assert stream is not None
    snapshot = market_overview_list_from_proto(_sparkline_response(), catalogs)
    stream.kwargs["apply_snapshot"](snapshot, [])
    live = mo.MarketOverviewBatch(
        markets=[mo.MarketOverview(symbol_id=1, last_price_ticks=102, volume_24h_base_scaled=250)]
    )
    batch = stream.kwargs["decode"](live.SerializeToString())
    stream.kwargs["apply_live_publications"](stream.kwargs["read_publication"](batch))
    row = {r.symbol_id: r for r in emitted[-1]}[1]
    assert row.last_price is not None and row.last_price.ticks == 102
    assert row.symbol == "BTC-USDT"
    assert row.volume_24h_base == "0.0000025"
    assert [(s.interval, [p.ticks for p in s.close_prices]) for s in row.sparklines] == [
        ("SPARKLINE_24H", [100, 101, 99]),
        ("SPARKLINE_1H", []),
    ]


def test_live_overview_rows_are_enriched_from_the_catalog() -> None:
    batch = decode_market_overview_batch_bytes(
        mo.MarketOverviewBatch(
            markets=[mo.MarketOverview(symbol_id=1, volume_24h_base_scaled=250)]
        ).SerializeToString(),
        _catalogs(),
    )
    assert batch.markets[0].symbol == "BTC-USDT"
    assert batch.markets[0].volume_24h_base == "0.0000025"

