from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from polyester.models.market import MarketOverviewEntry
from polyester.realtime.client import next_update


class MarketOverviewSubscription:
    """Merged market-overview stream: REST snapshot then realtime row updates."""

    def __init__(
        self,
        *,
        queue: asyncio.Queue[list[MarketOverviewEntry] | None],
        close: asyncio.Event,
        stream,
        start_task: asyncio.Task[None] | None = None,
    ) -> None:
        self._queue = queue
        self._close = close
        self._stream = stream
        self._start_task = start_task

    @property
    def last_error(self) -> BaseException | None:
        stream = self._stream
        return getattr(stream, "last_error", None)

    async def refresh_snapshot(self) -> bool:
        """Fetch a new snapshot and merge the publications held back meanwhile.

        Returns ``True`` once the refresh completed and live delivery has
        resumed; ``last_error`` is then cleared. Returns ``False`` when the
        refresh did not complete and resume delivery: the snapshot fetch
        failed (``last_error`` holds the error, and ``on_error``, if given,
        received it), or the subscription is closed or closed during the
        refresh. A failed fetch is returned as ``False``, not raised, and the
        SDK does not retry it; cancelling the awaiting task still raises
        ``asyncio.CancelledError``.

        Until a refresh succeeds, live publications are held back, not
        delivered. They are merged once after a later successful refresh only
        while the subscription stays open and its bounded recovery buffer
        holds them: when the buffer overflows, the subscription closes with a
        ``PolyesterRealtimeOverflowError`` in ``last_error`` (also passed to
        ``on_error``) and the held publications are dropped. To retry, call
        ``refresh_snapshot()`` again; once the subscription is closed,
        subscribe again.
        """
        return await self._stream.refresh_snapshot()

    async def aclose(self) -> None:
        self._close.set()
        await self._stream.aclose()
        if self._start_task is not None and not self._start_task.done():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._start_task
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)

    async def __aenter__(self) -> MarketOverviewSubscription:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def unsubscribe(self) -> None:
        asyncio.get_running_loop().create_task(self.aclose())

    def __aiter__(self) -> AsyncIterator[list[MarketOverviewEntry]]:
        return self

    async def __anext__(self) -> list[MarketOverviewEntry]:
        # Every reader ends once the subscription closes; see next_update.
        item: list[MarketOverviewEntry] = await next_update(self._queue, self._close)
        return item
