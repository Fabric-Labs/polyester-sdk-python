from polyester.orderbook.local_book import (
    apply_delta,
    build_orderbook_data,
    levels_to_map,
    parse_bucket_ticks,
    side_to_levels,
)
from polyester.models.realtime import OrderBookDeltaUpdate


def test_levels_to_map_skips_zero_qty() -> None:
    book = levels_to_map([("100", "5"), ("101", "0"), ("102", "3")])
    assert book == {100: 5, 102: 3}


def test_apply_delta_updates_and_deletes_levels() -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=1,
        delta=OrderBookDeltaUpdate(
            book_seq_start="2",
            book_seq_end="2",
            bids=[("100500", "25"), ("100", "0")],
            asks=[("101", "0"), ("102", "4")],
        ),
    )
    assert refresh is False
    assert seq == 2
    assert bids == {100500: 25}
    assert asks == {102: 4}


def test_apply_delta_reset_clears_book() -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=5,
        delta=OrderBookDeltaUpdate(reset=True, book_seq_start="0", book_seq_end="1", bids=[("50", "1")]),
    )
    assert refresh is False
    assert seq == 1
    assert bids == {50: 1}
    assert asks == {}


def test_apply_delta_detects_sequence_gap() -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=1,
        delta=OrderBookDeltaUpdate(book_seq_start="5", book_seq_end="5"),
    )
    assert refresh is True
    assert seq == 1
    assert bids == {100: 5}


def test_apply_delta_ignores_stale_updates() -> None:
    bids = {100: 5}
    asks: dict[int, int] = {}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=10,
        delta=OrderBookDeltaUpdate(book_seq_start="8", book_seq_end="9", bids=[("50", "1")]),
    )
    assert refresh is False
    assert seq == 10
    assert bids == {100: 5}


def test_build_orderbook_data_sorts_sides() -> None:
    data = build_orderbook_data(
        symbol="ETH-USDT",
        depth=2,
        book_seq=3,
        bids={100: 1, 200: 2, 300: 3},
        asks={150: 1, 120: 2, 110: 3},
    )
    assert data.book_seq == "3"
    assert [level.price_ticks for level in data.bids] == ["300", "200"]
    assert [level.price_ticks for level in data.asks] == ["110", "120"]


def test_bucket_aggregation() -> None:
    bids = {100_000_000: 10, 100_500_000: 25}
    levels = side_to_levels(bids, side="bids", limit=10, bucket_ticks=1_000_000)
    prices = {level.price_ticks for level in levels}
    assert "100000000" in prices


def test_parse_bucket_ticks() -> None:
    assert parse_bucket_ticks("0.01") == 10_000
    assert parse_bucket_ticks(None) is None
    assert parse_bucket_ticks("not-a-price") is None
