from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.orderbook.subscription import OrderbookSubscription
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription
from polyester.services.orderbook import AsyncOrderbookService


@pytest.mark.asyncio
async def test_snapshot_then_stream_refresh_applies_snapshot() -> None:
    calls: list[str] = []

    async def fetch_snapshot():
        calls.append("fetch")
        return {"seq": 1}

    stream = AsyncSnapshotThenStreamSubscription(
        realtime=MagicMock(),
        channel="public:test:proto",
        decode=lambda _payload: OrderBookDeltaUpdate(),
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda delta: [delta],
        apply_snapshot=lambda snap, pending: calls.append(f"apply:{snap['seq']}:{len(pending)}"),
        apply_live_publications=lambda pubs: calls.append(f"live:{len(pubs)}"),
    )

    await stream.refresh_snapshot()
    assert calls == ["fetch", "apply:1:0"]
    assert stream.is_ready() is True


@pytest.mark.asyncio
async def test_snapshot_then_stream_fires_on_snapshot_refresh_hook() -> None:
    events: list[str] = []

    async def fetch_snapshot():
        return {"seq": 2}

    stream = AsyncSnapshotThenStreamSubscription(
        realtime=MagicMock(),
        channel="public:test:proto",
        decode=lambda _payload: OrderBookDeltaUpdate(),
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda delta: [delta],
        apply_snapshot=lambda _snap, _pending: None,
        apply_live_publications=lambda _pubs: None,
        on_snapshot_refresh=lambda: events.append("snapshot_refresh"),
    )
    await stream.refresh_snapshot()
    assert events == ["snapshot_refresh"]


@pytest.mark.asyncio
async def test_snapshot_then_stream_wires_on_reconnect_callback() -> None:
    """Constructor must accept and store on_reconnect (fired after WS reconnect)."""
    events: list[str] = []
    stream = AsyncSnapshotThenStreamSubscription(
        realtime=MagicMock(),
        channel="public:test:proto",
        decode=lambda _payload: OrderBookDeltaUpdate(),
        fetch_snapshot=AsyncMock(return_value={"seq": 1}),
        read_publication=lambda delta: [delta],
        apply_snapshot=lambda _snap, _pending: None,
        apply_live_publications=lambda _pubs: None,
        on_reconnect=lambda: events.append("reconnect"),
    )
    assert stream._on_reconnect is not None
    stream._on_reconnect()
    assert events == ["reconnect"]


@pytest.mark.asyncio
async def test_snapshot_then_stream_buffers_until_ready() -> None:
    applied: list[int] = []

    async def fetch_snapshot():
        stream._handle_publication(OrderBookDeltaUpdate(book_seq_end="1"))
        stream._handle_publication(OrderBookDeltaUpdate(book_seq_end="2"))
        return {"seq": 1}

    stream = AsyncSnapshotThenStreamSubscription(
        realtime=MagicMock(),
        channel="public:test:proto",
        decode=lambda _payload: OrderBookDeltaUpdate(),
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda delta: [delta],
        apply_snapshot=lambda _snap, pending: applied.append(len(pending)),
        apply_live_publications=lambda pubs: applied.append(100 + len(pubs)),
    )

    await stream.refresh_snapshot()
    assert applied == [2]


@pytest.mark.asyncio
async def test_orderbook_subscription_context_manager_closes_stream() -> None:
    stream = AsyncMock()
    start_task = asyncio.create_task(asyncio.sleep(0))
    subscription = OrderbookSubscription(
        queue=asyncio.Queue(),
        close=asyncio.Event(),
        stream=stream,
        set_bucket=lambda _bucket: None,
        start_task=start_task,
    )

    async with subscription as entered:
        assert entered is subscription

    stream.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_subscription_requires_symbol_id_when_unknown() -> None:
    service = AsyncOrderbookService(MagicMock(), realtime=MagicMock())
    with pytest.raises(Exception, match="symbol_id is required"):
        await service.create_subscription(symbol="UNKNOWN-USDT")


@pytest.mark.asyncio
async def test_create_subscription_uses_capped_depth_channel(monkeypatch) -> None:
    transport = MagicMock()
    realtime = MagicMock()
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 101,
                    "base_quantity_scale": 8,
                }
            ]
        }
    )
    service = AsyncOrderbookService(transport, catalogs=catalogs, realtime=realtime)

    snapshot = orderbook_pb2.GetOrderBookResponse(book_seq=1)
    captured_channel: dict[str, str] = {}

    monkeypatch.setattr(
        "polyester.services.orderbook.unary_public_decoded",
        AsyncMock(return_value=snapshot),
    )

    class _Harness:
        async def start(self) -> None:
            return None

        def is_ready(self) -> bool:
            return True

        def is_disposed(self) -> bool:
            return False

        async def aclose(self) -> None:
            return None

        async def refresh_snapshot(self) -> None:
            return None

    def ctor(**kwargs):
        captured_channel["channel"] = kwargs["channel"]
        kwargs["apply_snapshot"](snapshot, [])
        return _Harness()

    monkeypatch.setattr(
        "polyester.services.orderbook.AsyncSnapshotThenStreamSubscription",
        ctor,
    )

    subscription = await service.create_subscription(
        symbol="BTC-USDT",
        symbol_id=101,
        depth=1000,
    )
    await subscription.aclose()

    assert captured_channel["channel"] == "public:spot:orderbook:deltas:depth:500:101:proto"
