"""POLY-9019: market overview rows keep the 24h range, top of book and times.

Every path that builds ``MarketOverviewEntry`` (``list``, the live
subscription, the protobuf decoder and the JSON decoder) exposes the 24h high
and low, the best bid and ask with their sizes, the last-trade time and the
listing time the server sends, exactly, and leaves an empty book side unset.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.protobuf.json_format import MessageToDict

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.market_overview import market_overview_entry_from_proto
from polyester.codecs.realtime_decode import decode_market_overview_batch_bytes
from polyester.codecs.wire_decode import decode_market_overview_entry, decode_market_overview_list
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.models.market import MarketOverviewEntry
from polyester.services.market_overview import AsyncMarketOverviewService
from polyester.types.money import Price, Quantity
from tests.unit.support import CaptureUnary

SYMBOL = "BTC-USDT"
SYMBOL_ID = 1
BASE_SCALE = 8

# The Devnet BTC-USDT row from the ticket.
WIRE = {
    "high_24h_ticks": 76167500000000,
    "low_24h_ticks": 73621960000000,
    "best_bid_ticks": 74883900000000,
    "best_bid_qty_scaled": 6166686,
    "best_ask_ticks": 74921360000000,
    "best_ask_qty_scaled": 5532396,
    "last_trade_ts_ns": 1794236100652374117,
    "listed_ts_ns": 1792404511505163000,
}


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": SYMBOL, "symbol_id": SYMBOL_ID, "base_quantity_scale": BASE_SCALE}]}
    )
    return catalogs


def _row(**overrides: Any) -> marketoverview_pb2.MarketOverview:
    fields: dict[str, Any] = {
        "symbol_id": SYMBOL_ID,
        "last_price_ticks": 74900000000000,
        "change_24h_bps": -125,
        "volume_24h_base_scaled": 12345,
        "index_price_ticks": 74890000000000,
        **WIRE,
    }
    fields.update(overrides)
    return marketoverview_pb2.MarketOverview(**fields)


def _expected(symbol: str | None, scale: int | None, symbol_id: int | None) -> dict[str, Any]:
    def qty(scaled: int) -> Quantity:
        return Quantity.from_scaled(scaled, scale=scale, symbol=symbol, symbol_id=symbol_id)

    return {
        "high_24h": Price.from_ticks(WIRE["high_24h_ticks"], symbol=symbol),
        "low_24h": Price.from_ticks(WIRE["low_24h_ticks"], symbol=symbol),
        "best_bid": Price.from_ticks(WIRE["best_bid_ticks"], symbol=symbol),
        "best_bid_qty": qty(WIRE["best_bid_qty_scaled"]),
        "best_ask": Price.from_ticks(WIRE["best_ask_ticks"], symbol=symbol),
        "best_ask_qty": qty(WIRE["best_ask_qty_scaled"]),
        "last_trade_ts_ns": str(WIRE["last_trade_ts_ns"]),
        "listed_ts_ns": str(WIRE["listed_ts_ns"]),
    }


def _new_fields(row: MarketOverviewEntry) -> dict[str, Any]:
    return {name: getattr(row, name, "<missing>") for name in _expected(None, None, None)}


def _assert_existing_fields(row: MarketOverviewEntry, symbol: str | None) -> None:
    assert row.symbol_id == SYMBOL_ID
    assert row.last_price == Price.from_ticks(74900000000000, symbol=symbol)
    assert row.index_price == Price.from_ticks(74890000000000, symbol=symbol)
    assert row.change_24h_bp == "-125"
    assert row.volume_24h_base_scaled == "12345"


def test_protobuf_decoder_keeps_range_top_of_book_and_times() -> None:
    row = market_overview_entry_from_proto(_row(), _catalogs())
    assert _new_fields(row) == _expected(SYMBOL, BASE_SCALE, SYMBOL_ID)
    assert row.best_bid.format() == "74883.9"
    _assert_existing_fields(row, SYMBOL)


def test_protobuf_decoder_without_catalogs_keeps_exact_wire_values() -> None:
    row = market_overview_entry_from_proto(_row())
    assert _new_fields(row) == _expected(None, None, SYMBOL_ID)


@pytest.mark.parametrize("side", ["bid", "ask"])
def test_an_empty_book_side_and_unset_times_decode_as_unset(side: str) -> None:
    empty = {f"best_{side}_ticks": 0, f"best_{side}_qty_scaled": 0}
    unset_times = {
        "last_trade_ts_ns": 0,
        "listed_ts_ns": 0,
        "high_24h_ticks": 0,
        "low_24h_ticks": 0,
    }
    proto_row = market_overview_entry_from_proto(_row(**empty, **unset_times), _catalogs())
    json_row = decode_market_overview_entry(MessageToDict(_row(**empty, **unset_times)))
    for row in (proto_row, json_row):
        assert getattr(row, f"best_{side}") is None
        assert getattr(row, f"best_{side}_qty") is None
        assert row.high_24h is None and row.low_24h is None
        assert row.last_trade_ts_ns == "" and row.listed_ts_ns == ""
        other = "ask" if side == "bid" else "bid"
        assert getattr(row, f"best_{other}") is not None
        assert getattr(row, f"best_{other}_qty") is not None


@pytest.mark.parametrize("names", ["json", "proto"])
def test_json_decoder_keeps_range_top_of_book_and_times(names: str) -> None:
    payload = MessageToDict(
        marketoverview_pb2.ListMarketOverviewResponse(markets=[_row()]),
        preserving_proto_field_name=names == "proto",
    )
    payload["markets"][0]["symbol"] = SYMBOL
    page = decode_market_overview_list(payload)
    row = page.markets[0]
    assert _new_fields(row) == _expected(SYMBOL, None, SYMBOL_ID)
    _assert_existing_fields(row, SYMBOL)


async def test_list_keeps_range_top_of_book_and_times() -> None:
    service = AsyncMarketOverviewService(MagicMock(), catalogs=_catalogs())
    capture = CaptureUnary(marketoverview_pb2.ListMarketOverviewResponse(markets=[_row()]))
    with patch("polyester.services.market_overview.unary_public_decoded", capture):
        page = await service.list(symbols=[SYMBOL], limit=1)
    assert _new_fields(page.markets[0]) == _expected(SYMBOL, BASE_SCALE, SYMBOL_ID)


def test_subscription_publications_keep_range_top_of_book_and_times() -> None:
    payload = marketoverview_pb2.MarketOverviewBatch(markets=[_row()]).SerializeToString()
    batch = decode_market_overview_batch_bytes(payload, _catalogs())
    assert _new_fields(batch.markets[0]) == _expected(SYMBOL, BASE_SCALE, SYMBOL_ID)
