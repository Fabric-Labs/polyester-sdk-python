"""The managed book follows the depth stream's rule: each update applies only to the
view it starts from, and after a gap the book waits for the next reset instead of
fetching snapshots."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models import OrderbookData
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.services.orderbook import AsyncOrderbookService


def _level(price: int, qty: int) -> orderbook_pb2.PriceLevel:
    return orderbook_pb2.PriceLevel(price_ticks=price, qty_scaled=qty)


def _delta(start: int, end: int, *, reset: bool = False, bid: int = 100, qty: int = 1):
    return OrderBookDeltaUpdate(
        book_seq_start=str(start), book_seq_end=str(end), reset=reset, bids=[[bid, qty]]
    )


SNAPSHOT = orderbook_pb2.GetOrderBookResponse(book_seq=5, available=True, bids=[_level(100, 1)])


class _Stream:
    def __init__(self) -> None:
        self.refresh_requests = 0

    async def start(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    def is_disposed(self) -> bool:
        return False

    def request_refresh(self) -> None:
        self.refresh_requests += 1

    async def aclose(self) -> None:
        return None


class _Book:
    def __init__(self) -> None:
        self.views: list[OrderbookData] = []
        self.gaps = 0
        self.stream = _Stream()
        self.hooks: dict[str, Any] = {}

    def snapshot(self, snapshot=SNAPSHOT, buffered: list[OrderBookDeltaUpdate] | None = None):
        self.hooks["apply_snapshot"](snapshot, buffered or [])

    def live(self, *deltas: OrderBookDeltaUpdate) -> None:
        self.hooks["apply_live_publications"](list(deltas))

    def seen(self) -> list[tuple[str, bool, int]]:
        return [
            (v.book_seq, v.available, v.bids[0].qty.scaled if v.bids else 0) for v in self.views
        ]


@pytest.fixture
async def book(monkeypatch):
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 101, "base_quantity_scale": 0}]}
    )
    service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=MagicMock())
    monkeypatch.setattr(
        "polyester.services.orderbook.unary_public_decoded", AsyncMock(return_value=SNAPSHOT)
    )
    state = _Book()

    def ctor(**kwargs: Any) -> _Stream:
        state.hooks.update(kwargs)
        return state.stream

    def on_gap() -> None:
        state.gaps += 1

    monkeypatch.setattr("polyester.services.orderbook.AsyncSnapshotThenStreamSubscription", ctor)
    subscription = await service.create_subscription(
        symbol="BTC-USDT",
        symbol_id=101,
        depth=10,
        on_event=state.views.append,
        on_sequence_gap=on_gap,
    )
    yield state
    await subscription.aclose()


async def test_updates_chain_from_the_end_of_the_previous_one(book) -> None:
    book.snapshot()
    book.live(_delta(5, 9, qty=2), _delta(9, 10, qty=3))

    assert book.seen() == [("5", True, 1), ("9", True, 2), ("10", True, 3)]
    assert book.gaps == 0


async def test_gap_waits_for_the_next_reset_without_fetching_snapshots(book) -> None:
    book.snapshot()
    # One past the book: the view it applies to was skipped.
    book.live(_delta(6, 7, qty=2))
    # Diffs after a gap cannot apply and add no view; the gap is reported once.
    book.live(_delta(7, 8, qty=3), _delta(8, 9, qty=4))
    book.live(_delta(0, 20, reset=True, qty=5))
    book.live(_delta(20, 21, qty=6))

    assert book.seen() == [
        ("5", True, 1),
        ("5", False, 1),
        ("20", True, 5),
        ("21", True, 6),
    ]
    assert book.gaps == 1
    assert book.stream.refresh_requests == 0


async def test_overlapping_update_is_a_gap(book) -> None:
    book.snapshot()
    book.live(_delta(3, 9, qty=2))

    assert book.seen() == [("5", True, 1), ("5", False, 1)]
    assert book.gaps == 1
    assert book.stream.refresh_requests == 0


async def test_each_gap_after_a_recovery_is_reported(book) -> None:
    book.snapshot()
    book.live(_delta(6, 7), _delta(0, 10, reset=True, qty=2), _delta(11, 12))

    assert book.gaps == 2
    assert book.seen()[-1] == ("10", False, 2)


async def test_reset_the_book_already_holds_does_not_end_the_wait(book) -> None:
    book.snapshot()
    book.live(_delta(6, 7), _delta(0, 5, reset=True, qty=9))

    assert book.seen() == [("5", True, 1), ("5", False, 1)]


async def test_buffered_reset_recovers_from_a_buffered_gap_in_one_view(book) -> None:
    book.snapshot(
        buffered=[_delta(4, 5), _delta(6, 7), _delta(7, 8), _delta(0, 9, reset=True, qty=3)]
    )

    assert book.seen() == [("9", True, 3)]
    assert book.gaps == 1
    assert book.stream.refresh_requests == 0


async def test_buffered_gap_without_a_reset_shows_the_snapshot_unavailable(book) -> None:
    book.snapshot(buffered=[_delta(5, 6, qty=2), _delta(8, 9, qty=3)])

    assert book.seen() == [("6", False, 2)]
    assert book.gaps == 1
    assert book.stream.refresh_requests == 0


async def test_a_new_snapshot_ends_the_wait(book) -> None:
    book.snapshot()
    book.live(_delta(6, 7))
    # A manual refresh or a reconnect fetches a snapshot; buffered diffs then follow it.
    refreshed = orderbook_pb2.GetOrderBookResponse(
        book_seq=30, available=True, bids=[_level(100, 4)]
    )
    book.snapshot(refreshed, [_delta(30, 31, qty=5)])

    assert book.seen() == [("5", True, 1), ("5", False, 1), ("31", True, 5)]
    assert book.gaps == 1
