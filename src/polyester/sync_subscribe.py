from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures import Future
from typing import Any, TypeVar

from polyester._sync_bridge import on_client_loop, run_on_loop
from polyester.errors import PolyesterRealtimeError
from polyester.orderbook.local_book import parse_bucket_ticks
from polyester.realtime.client import AsyncSubscription

T = TypeVar("T")


class SyncSubscription:
    """Thread-safe handle for a sync client realtime subscription.

    ``close()`` (or ``unsubscribe()``) works from any thread and from a client
    callback, the subscription's own ``on_event`` included. Delivery stops at
    once either way: no ``on_event`` starts after ``close()`` returns.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        *,
        close_coro: Callable[[], Coroutine[Any, Any, None]],
        holder: dict[str, object | None] | None = None,
    ) -> None:
        self._loop = loop
        self._close_coro = close_coro
        self._holder = holder
        self._lock = threading.Lock()
        self._closing: Future[None] | None = None
        # Set once an off-loop caller has seen the close finish (and so its
        # failure, if any, reported); until then every off-loop caller waits.
        self._finished = False

    def set_bucket(self, bucket: str | None) -> None:
        """Forward bucket changes to orderbook subscriptions (no-op otherwise).

        An invalid bucket raises :class:`PolyesterValidationError` here, in the caller,
        and keeps the current bucket.
        """
        if self._holder is None:
            return
        sub = self._holder.get("sub")
        if sub is not None and hasattr(sub, "set_bucket"):
            parse_bucket_ticks(bucket)
            # Once the client has closed there is no stream left to change.
            with contextlib.suppress(RuntimeError):
                self._loop.call_soon_threadsafe(sub.set_bucket, bucket)

    def since_last_publication(self) -> float | None:
        """An order book's ``since_last_publication``; ``None`` for other streams."""
        sub = None if self._holder is None else self._holder.get("sub")
        age = getattr(sub, "since_last_publication", None)
        return age() if callable(age) else None

    @property
    def resubscribed(self) -> int:
        """Successful reconnects after the first connect, as the async
        subscription's ``resubscribed`` counts them; 0 before it is set up.
        A non-zero or increasing value means publications may have been
        missed while disconnected."""
        sub = None if self._holder is None else self._holder.get("sub")
        count = getattr(sub, "resubscribed", 0)
        return count if isinstance(count, int) else 0

    def take_resubscribed(self) -> bool:
        """True once per reconnect since the previous take, as the async
        subscription's ``take_resubscribed()`` reports it; False before the
        subscription is set up and for a stream with no such signal. Callable
        from any thread, a client callback included. ``on_event`` is not
        called for a reconnect, so check this on a timer of its own: an idle
        stream may deliver nothing after the reconnect."""
        sub = None if self._holder is None else self._holder.get("sub")
        take = getattr(sub, "take_resubscribed", None)
        return bool(take()) if callable(take) else False

    def unsubscribe(self) -> None:
        self.close()

    def close(self) -> None:
        """Stop delivery and close the subscription.

        From another thread, this waits up to 10 s for the close to finish and
        raises a failure of the subscription or of its close. Every caller
        that waits while the close is in flight waits for it, the client's
        own close included, and gets its failure. From a client callback,
        which runs on the client loop, it schedules the close on the loop and
        returns at once; the close finishes after the callback returns, and
        the next ``close()`` from another thread, or :meth:`Polyester.close`,
        waits for it and raises its failure. Once a caller has seen the close
        finish, further calls do nothing.
        """
        with self._lock:
            closing = self._closing
            if closing is None:
                if self._holder is not None:
                    # Read by the delivery loop on the client loop before each event.
                    self._holder["closed"] = True
                if self._loop.is_closed():
                    # The client closed, and its loop with it: nothing is left to stop.
                    self._finished = True
                    return
                closing = self._closing = asyncio.run_coroutine_threadsafe(
                    self._close_coro(), self._loop
                )
            if on_client_loop(self._loop) or self._finished:
                return
        try:
            closing.result(timeout=10)
        finally:
            if closing.done():
                with self._lock:
                    self._finished = True


def subscribe_sync(
    loop: asyncio.AbstractEventLoop,
    subscribe: Callable[[], Awaitable[AsyncSubscription[T]]],
    *,
    on_event: Callable[[T], object],
    on_error: Callable[[Exception], object] | None = None,
) -> SyncSubscription:
    if on_client_loop(loop):
        # Waiting on the client loop from the client loop can never finish.
        raise PolyesterRealtimeError("subscribe_sync cannot be called from a client callback")

    holder: dict[str, object | None] = {"sub": None, "task": None, "closed": False}

    async def _consume(sub: AsyncSubscription[T] | None = None) -> None:
        try:
            if sub is None:
                sub = await subscribe()
            holder["sub"] = sub
            async for event in sub:
                # A close from a callback returns before the stream stops, and
                # events can be ready without a suspension point: stop here.
                if holder["closed"]:
                    break
                on_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if on_error is not None:
                on_error(exc)
            else:
                raise

    async def _close() -> None:
        try:
            task = holder.get("task")
            if isinstance(task, asyncio.Task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        finally:
            # An iteration failure raised above must not leave the stream open.
            sub = holder.get("sub")
            if sub is not None:
                aclose = getattr(sub, "aclose", None)
                if callable(aclose):
                    await aclose()

    async def _start() -> None:
        sub = None
        if on_error is None:
            # With no callback to report to, a setup failure must reach the caller.
            sub = await subscribe()
            holder["sub"] = sub
        holder["task"] = asyncio.create_task(_consume(sub))

    # Setup is bounded by its own transport timeouts, not a fixed deadline that
    # would fail slow but valid setups. It starts on the loop, so a setup the
    # closing loop never reaches leaves nothing behind, and the wait ends early,
    # with the setup stopped, when the client closes or the caller is interrupted.
    run_on_loop(
        loop,
        _start,
        what="subscribe_sync",
        closed_error=PolyesterRealtimeError,
        closed_during="client closed during subscription setup",
    )
    return SyncSubscription(loop, close_coro=_close, holder=holder)
