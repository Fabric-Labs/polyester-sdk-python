"""The server's order book timestamp, on every public order book path.

``GetOrderBookResponse.ts`` and ``OrderBookDelta.ts`` are the server's best-effort
times. The SDK reports them as aware UTC datetimes, exact to the microsecond, and
``None`` when the server sent none: never the local receipt time. A managed book's
view carries the time of the latest snapshot or delta applied to it.

Every reply here is fixed, served over real local sockets.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import msgspec
import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.orderbook import depth_tier_value
from polyester.codecs.realtime_decode import decode_orderbook_delta_bytes
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models import OrderbookData
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.services.orderbook import AsyncOrderbookService
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)
from tests.unit.test_server_unsubscribe import CentrifugoServer, publication

WAIT = 5.0
SYMBOL_ID = 1
STREAM_DEPTH = 20
CHANNEL = f"public:spot:orderbook:deltas:depth:{STREAM_DEPTH}:{SYMBOL_ID}:proto"


def _ts(text: str) -> Timestamp:
    value = Timestamp()
    value.FromJsonString(text)
    return value


# The time Devnet sent on a BTC-USDT snapshot, and three later ones.
SNAPSHOT_TS = _ts("2026-11-19T18:40:33.060385485Z")
DELTA_TS = _ts("2026-11-19T18:40:33.161000999Z")
STALE_TS = _ts("2026-11-19T18:40:34.000000000Z")
RESET_TS = _ts("2026-11-19T18:40:35.250000001Z")
REFRESH_TS = _ts("2026-11-19T18:40:36.000000500Z")

# The same instants, to the microsecond: the nanoseconds below it are truncated.
SNAPSHOT_AT = datetime(2026, 11, 19, 18, 40, 33, 60385, tzinfo=UTC)
DELTA_AT = datetime(2026, 11, 19, 18, 40, 33, 161000, tzinfo=UTC)
RESET_AT = datetime(2026, 11, 19, 18, 40, 35, 250000, tzinfo=UTC)
REFRESH_AT = datetime(2026, 11, 19, 18, 40, 36, 0, tzinfo=UTC)


def _snapshot(
    *, ts: Timestamp | None, seq: int = 7, depth: int = 1
) -> orderbook_pb2.GetOrderBookResponse:
    response = orderbook_pb2.GetOrderBookResponse(
        symbol_id=SYMBOL_ID,
        book_seq=seq,
        book_epoch=2,
        available=True,
        depth=depth_tier_value(depth),
    )
    response.bids.add(price_ticks=2000, qty_scaled=5)
    response.asks.add(price_ticks=2001, qty_scaled=6)
    if ts is not None:
        response.ts.CopyFrom(ts)
    return response


def _delta(
    *,
    start: int,
    end: int,
    ts: Timestamp | None,
    reset: bool = False,
    bid_qty: int = 7,
) -> orderbook_pb2.OrderBookDelta:
    delta = orderbook_pb2.OrderBookDelta(
        symbol_id=SYMBOL_ID, book_seq_start=start, book_seq_end=end, reset=reset
    )
    delta.bids.add(price_ticks=2000, qty_scaled=bid_qty)
    if ts is not None:
        delta.ts.CopyFrom(ts)
    return delta


class _Market:
    """Answers each snapshot request with the next fixed reply."""

    def __init__(self, snapshots: list[orderbook_pb2.GetOrderBookResponse]) -> None:
        self.snapshots = snapshots
        self.requests = 0

    async def snapshot(self, request: ParsedRequest) -> HttpScript:
        assert request.path.endswith("/GetOrderBook")
        reply = self.snapshots[min(self.requests, len(self.snapshots) - 1)]
        self.requests += 1
        return connect_proto_response(reply.SerializeToString())


class _Harness:
    def __init__(self, client: AsyncPolyester, server: CentrifugoServer, market: _Market) -> None:
        self.client = client
        self.server = server
        self.market = market

    async def send(self, delta: orderbook_pb2.OrderBookDelta) -> None:
        await self.server.push(CHANNEL, publication(delta.SerializeToString()))


@contextlib.asynccontextmanager
async def _harness(*snapshots: orderbook_pb2.GetOrderBookResponse) -> AsyncIterator[_Harness]:
    async with CentrifugoServer() as server:
        market = _Market(list(snapshots) or [_snapshot(ts=None)])
        http = await MockHttpServer.spawn(market.snapshot)
        client = AsyncPolyester(api_url=http.base_url, ws_url=server.url, hydrate_catalogs=False)
        client.catalogs.hydrate_spot_config(
            {"pairs": [{"symbol": "BTC-USDT", "symbol_id": SYMBOL_ID, "base_quantity_scale": 8}]}
        )
        try:
            yield _Harness(client, server, market)
        finally:
            await client.aclose()
            await http.aclose()


async def _next(sub) -> Any:
    async with asyncio.timeout(WAIT):
        return await anext(sub)


def _without_ts(book: OrderbookData) -> OrderbookData:
    return msgspec.structs.replace(book, ts=None)


# ---------------------------------------------------------------- orderbook.get


@pytest.mark.parametrize(("sent", "expected"), [(SNAPSHOT_TS, SNAPSHOT_AT), (None, None)])
async def test_get_reports_the_snapshot_time_or_none(
    sent: Timestamp | None, expected: datetime | None
) -> None:
    async with _harness(_snapshot(ts=sent)) as h:
        book = await h.client.orderbook.get(symbol="BTC-USDT", depth=1)
    assert book.ts == expected
    if expected is not None:
        assert book.ts.tzinfo is UTC
    # The rest of the snapshot is unchanged.
    assert (book.symbol, book.depth, book.book_seq, book.book_epoch) == ("BTC-USDT", 1, "7", "2")
    assert book.available is True
    assert [(level.price.ticks, level.qty.scaled) for level in book.bids] == [(2000, 5)]
    assert [(level.price.ticks, level.qty.scaled) for level in book.asks] == [(2001, 6)]


async def test_get_results_differ_only_in_the_time() -> None:
    async with _harness(_snapshot(ts=SNAPSHOT_TS), _snapshot(ts=None)) as h:
        with_time = await h.client.orderbook.get(symbol="BTC-USDT", depth=1)
        without_time = await h.client.orderbook.get(symbol="BTC-USDT", depth=1)
    assert with_time != without_time
    assert _without_ts(with_time) == without_time


def test_snapshot_time_omitted_from_json_when_absent() -> None:
    absent = orderbook_from_proto(_snapshot(ts=None), symbol="BTC-USDT", depth=1, quantity_scale=8)
    present = orderbook_from_proto(
        _snapshot(ts=SNAPSHOT_TS), symbol="BTC-USDT", depth=1, quantity_scale=8
    )
    assert b'"ts"' not in msgspec.json.encode(absent)
    assert msgspec.json.decode(msgspec.json.encode(present))["ts"] == "2026-11-19T18:40:33.060385Z"


def test_a_sent_epoch_time_is_kept() -> None:
    # Presence decides, not the value: a sent Unix epoch is a time, not "none".
    book = orderbook_from_proto(
        _snapshot(ts=Timestamp(seconds=0, nanos=0)), symbol="BTC-USDT", depth=1, quantity_scale=8
    )
    assert book.ts == datetime(1970, 1, 1, tzinfo=UTC)
    delta = decode_orderbook_delta_bytes(
        _delta(start=7, end=8, ts=Timestamp(seconds=0, nanos=0)).SerializeToString()
    )
    assert delta.ts == datetime(1970, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------- subscribe_deltas


@pytest.mark.parametrize(("sent", "expected"), [(DELTA_TS, DELTA_AT), (None, None)])
async def test_raw_delta_reports_the_update_time_or_none(
    sent: Timestamp | None, expected: datetime | None
) -> None:
    async with _harness() as h:
        sub = await h.client.orderbook.subscribe_deltas(symbol_id=SYMBOL_ID, depth=STREAM_DEPTH)
        await h.server.wait_subscribed(CHANNEL)
        await h.send(_delta(start=7, end=8, ts=sent))
        delta = await _next(sub)
        await sub.aclose()
    assert delta.ts == expected
    if expected is not None:
        assert delta.ts.tzinfo is UTC
    assert (delta.symbol_id, delta.book_seq_start, delta.book_seq_end) == (SYMBOL_ID, "7", "8")
    assert delta.bids == [("2000", "7")]


# ---------------------------------------------------------------- managed book


@pytest.mark.parametrize(("sent", "expected"), [(SNAPSHOT_TS, SNAPSHOT_AT), (None, None)])
async def test_managed_book_first_view_has_the_snapshot_time(
    sent: Timestamp | None, expected: datetime | None
) -> None:
    async with _harness(_snapshot(ts=sent, depth=STREAM_DEPTH)) as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=STREAM_DEPTH)
        first = await _next(sub)
        await sub.aclose()
    assert first.ts == expected
    assert (first.book_seq, first.available) == ("7", True)


@pytest.mark.parametrize("snapshot_ts", [SNAPSHOT_TS, None], ids=["snapshot_ts", "no_snapshot_ts"])
async def test_managed_book_time_follows_applied_snapshots_and_deltas(
    snapshot_ts: Timestamp | None,
) -> None:
    async with _harness(
        _snapshot(ts=snapshot_ts, depth=STREAM_DEPTH),
        _snapshot(ts=REFRESH_TS, seq=20, depth=STREAM_DEPTH),
        _snapshot(ts=None, seq=30, depth=STREAM_DEPTH),
    ) as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=STREAM_DEPTH)
        first = await _next(sub)
        assert first.ts == (SNAPSHOT_AT if snapshot_ts is not None else None)

        # An applied delta's time replaces the snapshot's.
        await h.send(_delta(start=7, end=8, ts=DELTA_TS, bid_qty=8))
        applied = await _next(sub)
        assert (applied.book_seq, applied.ts) == ("8", DELTA_AT)

        # A stale delta, already in the book, is not applied: the time stays.
        await h.send(_delta(start=6, end=8, ts=STALE_TS, bid_qty=9))
        stale = await _next(sub)
        assert (stale.book_seq, stale.bids[0].qty.scaled, stale.ts) == ("8", 8, DELTA_AT)

        # Neither is a delta that skips a view: the book waits for a reset.
        await h.send(_delta(start=9, end=10, ts=STALE_TS, bid_qty=10))
        gap = await _next(sub)
        assert (gap.book_seq, gap.available, gap.ts) == ("8", False, DELTA_AT)

        # A reset is applied, with its own time.
        await h.send(_delta(start=0, end=11, ts=RESET_TS, reset=True, bid_qty=11))
        reset = await _next(sub)
        assert (reset.book_seq, reset.available, reset.ts) == ("11", True, RESET_AT)

        # An applied delta without a time leaves the view without one.
        await h.send(_delta(start=11, end=12, ts=None, bid_qty=12))
        untimed = await _next(sub)
        assert (untimed.book_seq, untimed.ts) == ("12", None)

        # A new snapshot replaces the book, and its time with it, absent included.
        await sub.refresh_snapshot()
        refreshed = await _next(sub)
        assert (refreshed.book_seq, refreshed.ts) == ("20", REFRESH_AT)
        await sub.refresh_snapshot()
        refreshed_untimed = await _next(sub)
        assert (refreshed_untimed.book_seq, refreshed_untimed.ts) == ("30", None)
        await sub.aclose()


class _Stream:
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


async def _buffered_view(
    monkeypatch, snapshot: orderbook_pb2.GetOrderBookResponse, buffered: list[OrderBookDeltaUpdate]
) -> list[OrderbookData]:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": SYMBOL_ID, "base_quantity_scale": 8}]}
    )
    service = AsyncOrderbookService(MagicMock(), catalogs=catalogs, realtime=MagicMock())
    monkeypatch.setattr(
        "polyester.services.orderbook.unary_public_decoded", AsyncMock(return_value=snapshot)
    )
    hooks: dict[str, Any] = {}

    def stream(**kwargs: Any) -> _Stream:
        hooks.update(kwargs)
        return _Stream()

    monkeypatch.setattr("polyester.services.orderbook.AsyncSnapshotThenStreamSubscription", stream)
    views: list[OrderbookData] = []
    subscription = await service.create_subscription(
        symbol="BTC-USDT", symbol_id=SYMBOL_ID, depth=STREAM_DEPTH, on_event=views.append
    )
    hooks["apply_snapshot"](snapshot, buffered)
    await subscription.aclose()
    return views


def _update(delta: orderbook_pb2.OrderBookDelta) -> OrderBookDeltaUpdate:
    return decode_orderbook_delta_bytes(delta.SerializeToString())


async def test_buffered_deltas_view_has_the_last_applied_time(monkeypatch) -> None:
    # The snapshot and the deltas buffered behind it are one view: the last applied
    # delta's time is its time, and a stale one after it does not change it.
    views = await _buffered_view(
        monkeypatch,
        _snapshot(ts=SNAPSHOT_TS, depth=STREAM_DEPTH),
        [
            _update(_delta(start=7, end=8, ts=DELTA_TS)),
            _update(_delta(start=6, end=8, ts=STALE_TS)),
        ],
    )
    assert [(view.book_seq, view.ts) for view in views] == [("8", DELTA_AT)]


async def test_buffered_stale_deltas_keep_the_snapshot_time(monkeypatch) -> None:
    views = await _buffered_view(
        monkeypatch,
        _snapshot(ts=SNAPSHOT_TS, depth=STREAM_DEPTH),
        [_update(_delta(start=5, end=7, ts=STALE_TS))],
    )
    assert [(view.book_seq, view.ts) for view in views] == [("7", SNAPSHOT_AT)]
