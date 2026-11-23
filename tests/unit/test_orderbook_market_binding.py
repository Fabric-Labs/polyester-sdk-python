"""Order book levels are bound to the book's market.

A level's price carries the pair's name and its quantity the pair's name and
ID, on a snapshot (``orderbook.get``, ``orderbook_from_proto``) and on every
view of a managed book (``orderbook.create_subscription``), so
``compatible_with`` refuses reusing them for another market. Every reply here
is fixed, served over real local sockets.
"""

from __future__ import annotations

import pytest

from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.errors import PolyesterValidationError
from polyester.models import OrderbookData
from polyester.orderbook import build_orderbook_data
from polyester.types.money import Quantity
from tests.unit.test_orderbook_timestamp import (
    STREAM_DEPTH,
    SYMBOL_ID,
    _harness,
    _next,
    _snapshot,
)

SYMBOL = "BTC-USDT"


def _assert_bound(book: OrderbookData) -> None:
    levels = [*book.bids, *book.asks]
    assert levels
    for level in levels:
        assert level.price.symbol == SYMBOL
        assert level.qty == Quantity(scaled=level.qty.scaled, scale=8, symbol=SYMBOL, symbol_id=1)
        with pytest.raises(PolyesterValidationError, match="quantity symbol_id mismatch"):
            level.qty.compatible_with(symbol_id=2)
        with pytest.raises(PolyesterValidationError, match="quantity symbol mismatch"):
            level.qty.compatible_with(symbol="SOL-USDT")
        with pytest.raises(PolyesterValidationError, match="price symbol mismatch"):
            level.price.compatible_with(symbol="SOL-USDT")
        level.qty.compatible_with(symbol=SYMBOL, symbol_id=SYMBOL_ID, scale=8)


def test_snapshot_decoder_binds_levels_to_the_response_market() -> None:
    _assert_bound(
        orderbook_from_proto(_snapshot(ts=None), symbol=SYMBOL, depth=1, quantity_scale=8)
    )


def test_snapshot_decoder_prefers_the_requested_market_id() -> None:
    reply = _snapshot(ts=None)
    reply.symbol_id = 0
    _assert_bound(
        orderbook_from_proto(reply, symbol=SYMBOL, depth=1, quantity_scale=8, symbol_id=SYMBOL_ID)
    )


def test_rendered_book_binds_levels_to_its_market() -> None:
    _assert_bound(
        build_orderbook_data(
            symbol=SYMBOL,
            depth=5,
            book_seq=7,
            bids={2000: 5},
            asks={2001: 6},
            quantity_scale=8,
            symbol_id=SYMBOL_ID,
        )
    )


async def test_get_binds_levels_to_the_requested_market() -> None:
    async with _harness(_snapshot(ts=None)) as h:
        book = await h.client.orderbook.get(symbol=SYMBOL, depth=1)
    _assert_bound(book)


async def test_subscription_views_bind_levels_to_the_book_market() -> None:
    async with _harness(_snapshot(ts=None, depth=STREAM_DEPTH)) as h:
        sub = await h.client.orderbook.create_subscription(symbol=SYMBOL, depth=STREAM_DEPTH)
        first = await _next(sub)
        await sub.aclose()
    _assert_bound(first)
