from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures import Future
from concurrent.futures import wait as wait_for_future
from typing import Any, TypeVar

from polyester.errors import PolyesterRealtimeError
from polyester.realtime.client import AsyncSubscription

T = TypeVar("T")


class SyncSubscription:
    """Thread-safe handle for a sync client realtime subscription."""

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
        self._closed = False

    def set_bucket(self, bucket: str | None) -> None:
        """Forward bucket changes to orderbook subscriptions (no-op otherwise)."""
        if self._holder is None:
            return
        sub = self._holder.get("sub")
        if sub is not None and hasattr(sub, "set_bucket"):
            self._loop.call_soon_threadsafe(sub.set_bucket, bucket)

    def unsubscribe(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        future: Future[None] = asyncio.run_coroutine_threadsafe(self._close_coro(), self._loop)
        future.result(timeout=10)


def _wait_for_setup(future: Future[None], loop: asyncio.AbstractEventLoop) -> None:
    """Wait for subscription setup, which its own transport timeouts already bound.

    No fixed deadline here: it would fail slow but valid setups. The wait only ends
    early if the client loop stops, and never leaves setup running behind the caller.
    """
    try:
        while not wait_for_future([future], timeout=0.25).done:
            if not loop.is_running():
                raise PolyesterRealtimeError("client closed during subscription setup")
    except BaseException:
        future.cancel()
        raise
    future.result()


def subscribe_sync(
    loop: asyncio.AbstractEventLoop,
    subscribe: Callable[[], Awaitable[AsyncSubscription[T]]],
    *,
    on_event: Callable[[T], None],
    on_error: Callable[[Exception], None] | None = None,
) -> SyncSubscription:
    with contextlib.suppress(RuntimeError):
        if asyncio.get_running_loop() is loop:
            # Waiting on the client loop from the client loop can never finish.
            raise PolyesterRealtimeError("subscribe_sync cannot be called from a client callback")

    holder: dict[str, object | None] = {"sub": None, "task": None}

    async def _consume(sub: AsyncSubscription[T] | None = None) -> None:
        try:
            if sub is None:
                sub = await subscribe()
            holder["sub"] = sub
            async for event in sub:
                on_event(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if on_error is not None:
                on_error(exc)
            else:
                raise

    async def _close() -> None:
        task = holder.get("task")
        if isinstance(task, asyncio.Task):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
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

    _wait_for_setup(asyncio.run_coroutine_threadsafe(_start(), loop), loop)
    return SyncSubscription(loop, close_coro=_close, holder=holder)
