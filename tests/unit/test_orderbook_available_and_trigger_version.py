"""Order book snapshot ``available`` and trigger ``version``."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.decode.triggers import get_trigger_from_proto, trigger_from_proto
from polyester.codecs.realtime_decode import decode_trigger_bytes
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import OrderbookData
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.services.orderbook import AsyncOrderbookService


def _level(price: int, qty: int) -> orderbook_pb2.PriceLevel:
    return orderbook_pb2.PriceLevel(price_ticks=price, qty_scaled=qty)


def test_snapshot_read_reports_available() -> None:
    book = orderbook_from_proto(
        orderbook_pb2.GetOrderBookResponse(
            book_seq=5, available=True, bids=[_level(100, 1)], asks=[_level(101, 2)]
        ),
        symbol="BTC-USDT",
        depth=10,
        quantity_scale=8,
    )
    assert book.available is True
    assert len(book.bids) == 1


def test_unavailable_snapshot_read_is_unknown_not_empty() -> None:
    book = orderbook_from_proto(
        orderbook_pb2.GetOrderBookResponse(book_seq=5, available=False),
        symbol="BTC-USDT",
        depth=10,
        quantity_scale=8,
    )
    assert book.available is False
    assert book.bids == [] and book.asks == []


def test_snapshot_read_reports_the_wire_available_even_with_levels() -> None:
    # ``available`` is the server's value; levels do not imply it.
    book = orderbook_from_proto(
        orderbook_pb2.GetOrderBookResponse(book_seq=5, asks=[_level(101, 2)]),
        symbol="BTC-USDT",
        depth=10,
        quantity_scale=8,
    )
    assert book.available is False


class _Harness:
    async def start(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    def is_disposed(self) -> bool:
        return False

    def request_refresh(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


async def _subscription_emits(
    monkeypatch, snapshot: orderbook_pb2.GetOrderBookResponse, deltas: list[OrderBookDeltaUpdate]
) -> list[OrderbookData]:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 101, "base_quantity_scale": 8}]}
    )
    service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=MagicMock())
    monkeypatch.setattr(
        "polyester.services.orderbook.unary_public_decoded", AsyncMock(return_value=snapshot)
    )
    hooks: dict[str, Any] = {}

    def ctor(**kwargs: Any) -> _Harness:
        hooks.update(kwargs)
        return _Harness()

    monkeypatch.setattr("polyester.services.orderbook.AsyncSnapshotThenStreamSubscription", ctor)
    emitted: list[OrderbookData] = []
    subscription = await service.create_subscription(
        symbol="BTC-USDT", symbol_id=101, depth=10, on_event=emitted.append
    )
    hooks["apply_snapshot"](snapshot, [])
    hooks["apply_live_publications"](deltas)
    await subscription.aclose()
    return emitted


@pytest.mark.asyncio
async def test_subscription_book_follows_snapshot_availability(monkeypatch) -> None:
    emitted = await _subscription_emits(
        monkeypatch,
        orderbook_pb2.GetOrderBookResponse(book_seq=5, available=True, bids=[_level(100, 1)]),
        [OrderBookDeltaUpdate(book_seq_start=6, book_seq_end=6, bids=[[99, 3]])],
    )
    assert [book.available for book in emitted] == [True, True]


@pytest.mark.asyncio
async def test_subscription_book_reports_the_snapshot_wire_available(monkeypatch) -> None:
    emitted = await _subscription_emits(
        monkeypatch, orderbook_pb2.GetOrderBookResponse(book_seq=5, bids=[_level(100, 1)]), []
    )
    assert [book.available for book in emitted] == [False]


@pytest.mark.asyncio
async def test_subscription_book_from_unavailable_snapshot_stays_unknown_until_reset(
    monkeypatch,
) -> None:
    emitted = await _subscription_emits(
        monkeypatch,
        orderbook_pb2.GetOrderBookResponse(book_seq=5, available=False),
        [
            OrderBookDeltaUpdate(book_seq_start=6, book_seq_end=6, bids=[[99, 3]]),
            # A reset replaces the whole book: from here it is known.
            OrderBookDeltaUpdate(book_seq_start=7, book_seq_end=7, reset=True, asks=[[101, 1]]),
            OrderBookDeltaUpdate(book_seq_start=8, book_seq_end=8, asks=[[102, 1]]),
        ],
    )
    assert [book.available for book in emitted] == [False, False, True, True]


def test_trigger_version_from_reads_and_realtime_updates() -> None:
    msg = triggers_pb2.Trigger(trigger_id=9, symbol_id=101, version=3)
    assert trigger_from_proto(msg).version == 3
    read = get_trigger_from_proto(triggers_pb2.GetTriggerResponse(trigger=msg))
    assert read is not None and read.version == 3
    assert decode_trigger_bytes(msg.SerializeToString()).version == 3


def test_trigger_version_is_zero_when_unset() -> None:
    assert trigger_from_proto(triggers_pb2.Trigger(trigger_id=9, symbol_id=101)).version == 0
