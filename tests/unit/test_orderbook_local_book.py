import pytest

from polyester.codecs.orderbook import depth_to_connect_enum
from polyester.errors import PolyesterValidationError
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.orderbook.local_book import (
    apply_delta,
    apply_side_delta,
    bucket_side,
    build_orderbook_data,
    levels_to_map,
    parse_bucket_ticks,
    side_to_levels,
)


def test_levels_to_map_rejects_missing_price_or_quantity() -> None:
    with pytest.raises(PolyesterValidationError, match="missing quantity"):
        levels_to_map([("100", "5"), ("101", "0")])
    with pytest.raises(PolyesterValidationError, match="missing price"):
        levels_to_map([("0", "5")])


def test_depth_mapping_preserves_protocol_boundaries() -> None:
    assert depth_to_connect_enum(1) == "DEPTH_1"
    assert depth_to_connect_enum(5) == "DEPTH_5"
    assert depth_to_connect_enum(500) == "DEPTH_500"
    assert depth_to_connect_enum(1000) == "DEPTH_1000"


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


def test_apply_delta_rejects_malformed_levels_without_advancing_or_mutating() -> None:
    bids = {100: 5}
    asks = {200: 3}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=1,
        delta=OrderBookDeltaUpdate(
            book_seq_start="2",
            book_seq_end="2",
            bids=[("100", "-1"), ("101", "4")],
        ),
    )
    assert refresh is True
    assert seq == 1
    assert bids == {100: 5}
    assert asks == {200: 3}


@pytest.mark.parametrize(
    ("seq_start", "seq_end"),
    [("9", "2"), ("bad", "2"), ("-1", "2")],
)
def test_apply_delta_rejects_invalid_sequences_without_mutating(
    seq_start: str, seq_end: str
) -> None:
    bids = {100: 5}
    asks = {200: 3}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=3,
        delta=OrderBookDeltaUpdate(
            reset=True,
            book_seq_start=seq_start,
            book_seq_end=seq_end,
            bids=[("101", "4")],
        ),
    )
    assert refresh is True
    assert seq == 3
    assert bids == {100: 5}
    assert asks == {200: 3}


def test_apply_delta_reset_clears_book() -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=5,
        delta=OrderBookDeltaUpdate(
            reset=True,
            book_seq_start="0",
            book_seq_end="1",
            bids=[("50", "1")],
        ),
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
        quantity_scale=8,
    )
    assert data.book_seq == "3"
    assert [level.price.ticks for level in data.bids] == [300, 200]
    assert [level.price.ticks for level in data.asks] == [110, 120]


def test_bucket_aggregation_formats_decimal_levels() -> None:
    bids = {100_000_000: 100_000_000}
    levels = side_to_levels(
        bids,
        side="bids",
        limit=10,
        bucket_ticks=1_000_000,
        quantity_scale=8,
    )
    assert levels[0].price is not None and levels[0].price.ticks == 100_000_000
    assert levels[0].qty is not None and levels[0].qty.scaled == 100_000_000
    assert levels[0].qty.format() == "1"


def test_parse_bucket_ticks() -> None:
    assert parse_bucket_ticks("0.01") == 10_000
    assert parse_bucket_ticks(None) is None
    assert parse_bucket_ticks("not-a-price") is None


def test_bucket_side_rounds_asks_up() -> None:
    book = {101: 2, 105: 3}
    assert bucket_side(book, 10, asks=False) == {100: 5}
    assert bucket_side(book, 10, asks=True) == {110: 5}


def test_bucket_side_rejects_negative_price() -> None:
    with pytest.raises(PolyesterValidationError, match="non-negative"):
        bucket_side({-1: 1}, 10)


def test_apply_side_delta_ignores_negative_levels() -> None:
    book = {100: 5}
    apply_side_delta(book, [("-1", "3"), ("100", "-2"), ("101", "4")])
    assert book == {100: 5, 101: 4}


def test_build_orderbook_data_rejects_negative_levels() -> None:
    with pytest.raises(PolyesterValidationError):
        build_orderbook_data(
            symbol="ETH-USDT",
            depth=2,
            book_seq=3,
            bids={-5: 1},
            asks={110: 1},
            quantity_scale=8,
        )
