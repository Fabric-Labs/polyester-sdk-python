from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Callable

from polyester.models import OrderbookData


class OrderbookSubscription:
    """Stateful order book stream with snapshot prefetch and sequence-checked deltas."""

    def __init__(
        self,
        *,
        queue: asyncio.Queue[OrderbookData | None],
        close: asyncio.Event,
        stream,
        set_bucket: Callable[[str | None], None],
        start_task: asyncio.Task[None] | None = None,
        on_aclose: Callable[[], None] | None = None,
        publication_age: Callable[[], float] | None = None,
    ) -> None:
        self._queue = queue
        self._close = close
        self._stream = stream
        self._set_bucket = set_bucket
        self._start_task = start_task
        self._on_aclose = on_aclose
        started = time.monotonic()
        self._publication_age = publication_age or (lambda: time.monotonic() - started)

    def set_bucket(self, bucket: str | None) -> None:
        self._set_bucket(bucket)

    def since_last_publication(self) -> float:
        """Seconds since the stream last delivered a publication, or since the start.

        Views from a snapshot or a bucket change don't count. It tells a stalled
        publisher from a quiet market: the server republishes each book's whole view,
        as a reset, about every 30 s even when nothing changed (seen on every market and
        depth of devnet and testnet, though the public contract does not promise a
        cadence). A quiet market stays well under that, and an age far above it, such
        as 90 s, means the publisher or the path to it stalled while the socket stayed
        open. The SDK sets no threshold and takes no action: poll it, and on a stall
        call ``refresh_snapshot``, or close and subscribe again.
        """
        return self._publication_age()

    @property
    def last_error(self) -> BaseException | None:
        stream = self._stream
        return getattr(stream, "last_error", None)

    async def refresh_snapshot(self) -> None:
        await self._stream.refresh_snapshot()

    async def aclose(self) -> None:
        self._close.set()
        if self._on_aclose is not None:
            self._on_aclose()
        await self._stream.aclose()
        if self._start_task is not None and not self._start_task.done():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._start_task
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)

    async def __aenter__(self) -> OrderbookSubscription:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def unsubscribe(self) -> None:
        """Fire-and-forget close for TS-style ergonomics in running loops."""
        asyncio.get_running_loop().create_task(self.aclose())

    def __aiter__(self) -> AsyncIterator[OrderbookData]:
        return self

    async def __anext__(self) -> OrderbookData:
        if self._close.is_set() and self._queue.empty():
            raise StopAsyncIteration
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item
