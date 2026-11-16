"""Order-book depth, delta and market-binding regressions (POLY-8581/8583/8586/8588)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.orderbook.local_book import apply_delta, build_orderbook_data
from polyester.realtime.client import AsyncSubscription
from polyester.services.orderbook import AsyncOrderbookService


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {"symbol": "LTC-USDT", "symbol_id": 3, "base_quantity_scale": 8},
                {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8},
            ]
        }
    )
    return catalogs


def _book(**overrides):
    args = {
        "symbol": "BTC-USDT",
        "depth": 10,
        "book_seq": 4,
        "bids": {100: 5, 99: 2},
        "asks": {101: 3, 102: 1},
        "quantity_scale": 8,
    }
    args.update(overrides)
    return build_orderbook_data(**args)


# POLY-8581: a negative depth is invalid caller input, not a slice from the end.
@pytest.mark.parametrize("depth", [-1, -2])
@pytest.mark.parametrize("populated", [False, True])
def test_build_orderbook_data_refuses_negative_depth(depth: int, populated: bool) -> None:
    sides = {} if populated else {"bids": {}, "asks": {}}
    with pytest.raises(PolyesterValidationError, match="depth"):
        _book(depth=depth, **sides)


@pytest.mark.parametrize("depth", [0, 1, 2])
def test_build_orderbook_data_trims_to_nonnegative_depth(depth: int) -> None:
    data = _book(depth=depth)
    assert data.depth == depth
    assert len(data.bids) == len(data.asks) == depth


def _delta(bids=(), asks=(), *, start="10", end="11", reset=False) -> OrderBookDeltaUpdate:
    return OrderBookDeltaUpdate(
        book_seq_start=start,
        book_seq_end=end,
        bids=[list(row) for row in bids],
        asks=[list(row) for row in asks],
        reset=reset,
    )


# POLY-8583: a positive quantity at price zero can't be rendered, so the whole
# delta fails closed like any malformed delta.
@pytest.mark.parametrize(
    "delta",
    [
        _delta(bids=[("0", "4")]),
        _delta(asks=[("0", "4")]),
        _delta(bids=[("103", "7"), ("0", "4")]),
        _delta(bids=[("103", "7")], asks=[("0", "4")]),
        _delta(bids=[("103", "7")], asks=[("0", "4")], end="12", reset=True),
    ],
    ids=["bid", "ask", "mixed-bid", "mixed-ask", "reset"],
)
def test_apply_delta_refuses_zero_price_level(delta: OrderBookDeltaUpdate) -> None:
    bids = {100: 5}
    asks = {200: 3}
    assert apply_delta(bids=bids, asks=asks, current_book_seq=10, delta=delta) == (10, True)
    assert bids == {100: 5}
    assert asks == {200: 3}
    _book(bids=bids, asks=asks)


def test_apply_delta_keeps_valid_deletions_and_inserts() -> None:
    bids = {100: 5, 99: 1}
    asks = {200: 3}
    delta = _delta(bids=[("99", "0"), ("0", "0")], asks=[("201", "2")])
    assert apply_delta(bids=bids, asks=asks, current_book_seq=10, delta=delta) == (11, False)
    assert bids == {100: 5}
    assert asks == {200: 3, 201: 2}
    _book(bids=bids, asks=asks, bucket_ticks=10)


def _snapshot_service(monkeypatch, *, levels: int = 1):
    requests = []

    async def fake_unary(_transport, _client, _call, request, decoder):
        requests.append(request)
        return decoder(
            orderbook_pb2.GetOrderBookResponse(
                symbol_id=request.symbol_id,
                book_seq=7,
                book_epoch=3,
                max_depth=5000,
                available=True,
                bids=[
                    orderbook_pb2.PriceLevel(price_ticks=52_320_000_000 - i, qty_scaled=5)
                    for i in range(levels)
                ],
                asks=[
                    orderbook_pb2.PriceLevel(price_ticks=52_330_000_000 + i, qty_scaled=6)
                    for i in range(levels)
                ],
            )
        )

    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fake_unary)
    return AsyncOrderbookService(MagicMock(), catalogs=_catalogs()), requests


# The depth is a level count sent as given: no rounding to the old fixed depths and no
# local maximum, since the server reports its own (max_depth). 0 is sent as 0, the
# server's default of 50, which the result reports. Only what the uint32 field cannot
# carry, or a value that is not an integer, is refused before any request.
@pytest.mark.parametrize(
    ("depth", "wire", "reported"),
    [
        (0, 0, 50),
        (1, 1, 1),
        (2, 2, 2),
        (11, 11, 11),
        (50, 50, 50),
        (1001, 1001, 1001),
        (2500, 2500, 2500),
        (5000, 5000, 5000),
        (6000, 6000, 6000),
        (2**32 - 1, 2**32 - 1, 2**32 - 1),
    ],
)
async def test_snapshot_sends_depth_as_given(
    monkeypatch, depth: int, wire: int, reported: int
) -> None:
    service, requests = _snapshot_service(monkeypatch)
    book = await service.get(symbol="BTC-USDT", depth=depth)
    assert [r.depth for r in requests] == [wire]
    assert book.depth == reported


@pytest.mark.parametrize("depth", [-1, -2, 2**32, True, 2.5, "20", None])
async def test_snapshot_refuses_unsupported_depth_before_request(monkeypatch, depth) -> None:
    service, requests = _snapshot_service(monkeypatch)
    with pytest.raises(PolyesterValidationError, match="depth"):
        await service.get(symbol="BTC-USDT", depth=depth)
    assert requests == []


async def test_snapshot_carries_epoch_and_max_depth(monkeypatch) -> None:
    service, _ = _snapshot_service(monkeypatch)
    book = await service.get(symbol="BTC-USDT", depth=20)
    assert (book.book_seq, book.book_epoch, book.max_depth) == ("7", "3", 5000)


def test_snapshot_without_max_depth_decodes_zero() -> None:
    book = orderbook_from_proto(
        orderbook_pb2.GetOrderBookResponse(symbol_id=1, available=False),
        symbol="BTC-USDT",
        depth=50,
        quantity_scale=8,
    )
    assert (book.book_epoch, book.max_depth, book.available) == ("0", 0, False)


def _assert_bound(levels, symbol: str) -> None:
    assert levels
    for level in levels:
        assert level.price.symbol == symbol
        assert level.qty.symbol == symbol
        level.price.compatible_with(symbol=symbol)
        level.qty.compatible_with(symbol=symbol, scale=8)
        with pytest.raises(PolyesterValidationError, match="symbol mismatch"):
            level.price.compatible_with(symbol="BTC-USDT")
        with pytest.raises(PolyesterValidationError, match="symbol mismatch"):
            level.qty.compatible_with(symbol="BTC-USDT", scale=8)


# POLY-8588: book levels keep the market they were read for.
async def test_snapshot_levels_are_bound_to_their_market(monkeypatch) -> None:
    service, _ = _snapshot_service(monkeypatch, levels=2)
    book = await service.get(symbol="LTC-USDT", depth=5)
    _assert_bound(book.bids, "LTC-USDT")
    _assert_bound(book.asks, "LTC-USDT")


def test_decoded_and_rendered_levels_are_bound_to_their_market() -> None:
    msg = orderbook_pb2.GetOrderBookResponse(
        book_seq=1,
        bids=[orderbook_pb2.PriceLevel(price_ticks=52_320_000_000, qty_scaled=5)],
        asks=[orderbook_pb2.PriceLevel(price_ticks=52_330_000_000, qty_scaled=6)],
    )
    decoded = orderbook_from_proto(msg, symbol="LTC-USDT", depth=5, quantity_scale=8)
    _assert_bound(decoded.bids + decoded.asks, "LTC-USDT")
    for bucket in (None, 10):
        rendered = _book(symbol="LTC-USDT", bucket_ticks=bucket)
        _assert_bound(rendered.bids + rendered.asks, "LTC-USDT")


async def test_managed_snapshot_and_delta_views_are_bound_to_their_market(monkeypatch) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(
        return_value=AsyncSubscription(queue=queue, close=asyncio.Event())
    )
    fetch = AsyncMock(
        return_value=orderbook_pb2.GetOrderBookResponse(
            book_seq=1,
            available=True,
            bids=[orderbook_pb2.PriceLevel(price_ticks=52_320_000_000, qty_scaled=3)],
            asks=[orderbook_pb2.PriceLevel(price_ticks=52_330_000_000, qty_scaled=4)],
        )
    )
    monkeypatch.setattr("polyester.services.orderbook.unary_public_decoded", fetch)
    service = AsyncOrderbookService(MagicMock(), catalogs=_catalogs(), realtime=realtime)
    sub = await service.create_subscription(symbol="LTC-USDT", depth=10)
    try:
        first = await asyncio.wait_for(anext(sub), 3)
        _assert_bound(first.bids + first.asks, "LTC-USDT")
        await queue.put(
            OrderBookDeltaUpdate(
                symbol_id=3,
                book_seq_start="1",
                book_seq_end="2",
                bids=[["52310000000", "9"]],
                asks=[],
            )
        )
        view = await asyncio.wait_for(anext(sub), 3)
        assert view.book_seq == "2"
        _assert_bound(view.bids + view.asks, "LTC-USDT")
    finally:
        await sub.aclose()
