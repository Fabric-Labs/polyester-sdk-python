from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable

from polyester.codecs.decode.market_overview import market_overview_list_from_proto
from polyester.codecs.realtime_decode import decode_market_overview_batch_bytes
from polyester.gen.marketoverview.v1.marketoverview_connect import MarketOverviewServiceClient
from polyester.gen.marketoverview.v1.marketoverview_pb2 import ListMarketOverviewRequest
from polyester.market_overview.subscription import MarketOverviewSubscription
from polyester.models.market import MarketOverviewEntry, MarketOverviewList
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded
from polyester.services._realtime_subscribe import require_realtime, subscribe_public_proto


class AsyncMarketOverviewService(BaseService):
    def __init__(self, transport, *, realtime: AsyncRealtimeClient | None = None) -> None:
        super().__init__(transport)
        self._realtime = realtime

    async def list(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 50,
        page_token: str = "",
        include_sparklines: bool = False,
    ) -> MarketOverviewList:
        request = ListMarketOverviewRequest(
            limit=limit,
            page_token=page_token,
            include_sparklines=include_sparklines,
        )
        if symbols:
            request.symbols.extend(symbols)
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.list_market_overview(req),
            request,
            market_overview_list_from_proto,
        )

    async def subscribe(self) -> AsyncSubscription[MarketOverviewList]:
        """Raw Centrifugo batches (no snapshot merge). Prefer ``create_subscription``."""
        return await subscribe_public_proto(
            self._realtime,
            channel="public:spot:market_overview:updates:proto",
            decode=decode_market_overview_batch_bytes,
        )

    async def create_subscription(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 50,
        include_sparklines: bool = False,
        on_event: Callable[[list[MarketOverviewEntry]], None] | None = None,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> MarketOverviewSubscription:
        """Snapshot-then-stream merged overview rows (TS parity)."""
        realtime = require_realtime(self._realtime)
        channel = "public:spot:market_overview:updates:proto"
        by_symbol_id: dict[int, MarketOverviewEntry] = {}
        queue: asyncio.Queue[list[MarketOverviewEntry] | None] = asyncio.Queue(maxsize=50)
        close = asyncio.Event()

        def emit() -> None:
            if close.is_set():
                return
            snapshot = list(by_symbol_id.values())
            if on_event is not None:
                on_event(snapshot)
            if not close.is_set():
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(snapshot)

        def apply_rows(rows: list[MarketOverviewEntry]) -> None:
            for row in rows:
                by_symbol_id[row.symbol_id] = row

        async def fetch_snapshot() -> MarketOverviewList:
            return await self.list(
                symbols=symbols,
                limit=limit,
                include_sparklines=include_sparklines,
            )

        def apply_snapshot(
            snapshot: MarketOverviewList,
            buffered: list[MarketOverviewEntry],
        ) -> None:
            by_symbol_id.clear()
            apply_rows(snapshot.markets)
            apply_rows(buffered)
            emit()

        def apply_live(rows: list[MarketOverviewEntry]) -> None:
            apply_rows(rows)
            emit()

        stream = AsyncSnapshotThenStreamSubscription(
            realtime=realtime,
            channel=channel,
            decode=decode_market_overview_batch_bytes,
            fetch_snapshot=fetch_snapshot,
            read_publication=lambda batch: batch.markets,
            apply_snapshot=apply_snapshot,
            apply_live_publications=apply_live,
            max_buffered_publications=2000,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error,
        )

        async def start() -> None:
            await stream.start()

        start_task = asyncio.create_task(start())
        return MarketOverviewSubscription(
            queue=queue,
            close=close,
            stream=stream,
            start_task=start_task,
        )
