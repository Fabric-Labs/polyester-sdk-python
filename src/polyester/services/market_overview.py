from __future__ import annotations

import asyncio
import builtins
import contextlib
from collections.abc import Awaitable, Callable

from polyester.catalogs import CatalogManager
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
from polyester.services._symbols import resolve_symbol_ids
from polyester.services._validation import validate_limit


class AsyncMarketOverviewService(BaseService):
    def __init__(
        self,
        transport,
        *,
        catalogs: CatalogManager | None = None,
        realtime: AsyncRealtimeClient | None = None,
        wait_for_catalogs: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs or CatalogManager()
        self._realtime = realtime
        self._wait_for_catalogs = wait_for_catalogs

    async def _ensure_catalogs(self) -> None:
        if self._wait_for_catalogs is not None:
            await self._wait_for_catalogs()

    async def list(
        self,
        *,
        symbols: builtins.list[str] | None = None,
        limit: int = 50,
        page_token: str = "",
        include_sparklines: bool = False,
    ) -> MarketOverviewList:
        validated_limit = validate_limit(limit)
        if symbols:
            await self._ensure_catalogs()
        request = ListMarketOverviewRequest(
            limit=validated_limit,
            page_token=page_token,
            include_sparklines=include_sparklines,
        )
        resolved_ids = resolve_symbol_ids(
            self._catalogs, symbols, label="market_overview.list symbols"
        )
        if resolved_ids:
            request.symbol_id.extend(resolved_ids)
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.list_market_overview(req),
            request,
            lambda msg: market_overview_list_from_proto(msg, self._catalogs),
        )

    async def subscribe(self) -> AsyncSubscription[MarketOverviewList]:
        """Raw Centrifugo batches (no snapshot merge). Prefer ``create_subscription``."""
        return await subscribe_public_proto(
            self._realtime,
            channel="public:spot:market_overview:updates:proto",
            decode=lambda payload: decode_market_overview_batch_bytes(payload, self._catalogs),
        )

    async def create_subscription(
        self,
        *,
        symbols: builtins.list[str] | None = None,
        limit: int = 50,
        include_sparklines: bool = False,
        on_event: Callable[[builtins.list[MarketOverviewEntry]], None] | None = None,
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
            if close.is_set():
                return
            try:
                from polyester.realtime.client import enqueue_or_overflow

                enqueue_or_overflow(
                    queue,
                    snapshot,
                    close=close,
                    message="market overview subscription queue full; consumer too slow",
                )
            except Exception:
                close.set()
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(None)

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
            decode=lambda payload: decode_market_overview_batch_bytes(payload, self._catalogs),
            fetch_snapshot=fetch_snapshot,
            read_publication=lambda batch: batch.markets,
            apply_snapshot=apply_snapshot,
            apply_live_publications=apply_live,
            max_buffered_publications=2000,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error,
        )

        subscription = MarketOverviewSubscription(
            queue=queue,
            close=close,
            stream=stream,
        )
        try:
            await stream.start()
        except BaseException:
            await subscription.aclose()
            raise
        return subscription
