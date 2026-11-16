import pytest

from polyester.errors import PolyesterValidationError
from polyester.models import OrderbookData
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.orderbook.local_book import (
    apply_delta,
    apply_side_delta,
    bucket_side,
    build_orderbook_data,
    compare_snapshots,
    levels_to_map,
    parse_bucket_ticks,
    side_to_levels,
)


def test_levels_to_map_rejects_missing_price_or_quantity() -> None:
    with pytest.raises(PolyesterValidationError, match="missing quantity"):
        levels_to_map([("100", "5"), ("101", "0")])
    with pytest.raises(PolyesterValidationError, match="missing price"):
        levels_to_map([("0", "5")])


def test_apply_delta_updates_and_deletes_levels() -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, refresh = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=1,
        delta=OrderBookDeltaUpdate(
            book_seq_start="1",
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
            book_seq_start="6",
            book_seq_end="6",
            bids=[("50", "1")],
        ),
    )
    assert refresh is False
    assert seq == 6
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


@pytest.mark.parametrize(
    ("seq_start", "seq_end"),
    [
        # The next sequence number: the book skipped the view it applies to.
        ("11", "12"),
        # Starts before the book: overlaps views the book already holds.
        ("9", "12"),
    ],
    ids=["skips a view", "overlaps the book"],
)
def test_apply_delta_applies_only_to_the_exact_view_it_starts_from(
    seq_start: str, seq_end: str
) -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, out_of_sync = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=10,
        delta=OrderBookDeltaUpdate(
            book_seq_start=seq_start, book_seq_end=seq_end, bids=[("100", "0"), ("99", "7")]
        ),
    )
    assert out_of_sync is True
    assert seq == 10
    assert bids == {100: 5}
    assert asks == {101: 2}


def test_apply_delta_chains_updates_that_start_where_the_last_ended() -> None:
    bids = {100: 5}
    asks: dict[int, int] = {}
    seq = 10
    for start, end, qty in (("10", "17", "6"), ("17", "18", "7"), ("18", "25", "8")):
        seq, out_of_sync = apply_delta(
            bids=bids,
            asks=asks,
            current_book_seq=seq,
            delta=OrderBookDeltaUpdate(book_seq_start=start, book_seq_end=end, bids=[("100", qty)]),
        )
        assert out_of_sync is False
    assert seq == 25
    assert bids == {100: 8}


def test_apply_delta_reset_replaces_a_book_whatever_its_sequence() -> None:
    bids = {100: 5}
    asks = {101: 2}
    seq, out_of_sync = apply_delta(
        bids=bids,
        asks=asks,
        current_book_seq=10,
        delta=OrderBookDeltaUpdate(
            reset=True, book_seq_start="0", book_seq_end="40", asks=[("103", "1")]
        ),
    )
    assert out_of_sync is False
    assert seq == 40
    assert bids == {}
    assert asks == {103: 1}


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
    assert parse_bucket_ticks("0.01") == 10_000_000
    assert parse_bucket_ticks(None) is None
    with pytest.raises(PolyesterValidationError, match="invalid orderbook bucket"):
        parse_bucket_ticks("not-a-price")


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


def _snapshot(epoch: str, seq: str) -> OrderbookData:
    return OrderbookData(
        symbol="BTC-USDT", depth=50, book_seq=seq, bids=[], asks=[], book_epoch=epoch
    )


@pytest.mark.parametrize(
    ("a", "b", "want"),
    [
        (("3", "10"), ("3", "10"), 0),
        (("3", "11"), ("3", "10"), 1),
        (("3", "9"), ("3", "10"), -1),
        # A higher epoch is newer whatever its sequence: a new epoch may restart it.
        (("4", "1"), ("3", "984321"), 1),
        (("3", "984321"), ("4", "1"), -1),
        # An unavailable snapshot (epoch 0) is older than any snapshot of a later epoch.
        (("0", "0"), ("1", "0"), -1),
        (("18446744073709551615", "0"), ("18446744073709551614", "18446744073709551615"), 1),
    ],
)
def test_compare_snapshots_orders_by_epoch_then_sequence(a, b, want) -> None:
    assert compare_snapshots(_snapshot(*a), _snapshot(*b)) == want
    assert compare_snapshots(_snapshot(*b), _snapshot(*a)) == -want


@pytest.mark.parametrize(
    ("epoch", "seq"),
    [
        ("", "10"),  # a managed subscription's view: no epoch
        ("3", ""),
        ("-1", "10"),
        ("3", "+10"),
        ("3", " 10"),
        ("3", "1e3"),
        ("٣", "10"),
        ("18446744073709551616", "10"),
    ],
)
def test_compare_snapshots_refuses_a_view_without_a_snapshot_position(epoch, seq) -> None:
    with pytest.raises(PolyesterValidationError, match="orderbook.get"):
        compare_snapshots(_snapshot(epoch, seq), _snapshot("1", "1"))
    with pytest.raises(PolyesterValidationError, match="orderbook.get"):
        compare_snapshots(_snapshot("1", "1"), _snapshot(epoch, seq))
