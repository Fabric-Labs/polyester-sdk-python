"""Run an async call on the sync client's loop and wait for it from another thread."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import TypeVar

from polyester.errors import PolyesterError

T = TypeVar("T")

_POLL_SECONDS = 0.25


def on_client_loop(loop: asyncio.AbstractEventLoop) -> bool:
    """Whether the caller is running on ``loop``, as a client callback does."""
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


def refuse_on_client_loop(loop: asyncio.AbstractEventLoop, what: str) -> None:
    """Refuse a call that would wait on ``loop`` from code running on it.

    The loop runs client callbacks, so a callback that waited for the loop to
    finish a call would block it for good: every subscription and call on the
    client would stall.
    """
    if on_client_loop(loop):
        raise PolyesterError(
            f"{what} cannot be called from a client callback: it would wait on the "
            "client loop that runs the callback. Call it from another thread."
        )


def run_on_loop(
    loop: asyncio.AbstractEventLoop,
    call: Callable[[], Awaitable[T]],
    *,
    what: str = "a sync client method",
) -> T:
    """Run ``call()`` on ``loop`` and return its result once it has ended.

    The wait has no deadline of its own: the configured transport timeout and
    a method's own ``timeout`` bound the call, so its outcome, an unknown
    mutation outcome included, is the async call's. If the caller is
    interrupted while it waits (for example by ``KeyboardInterrupt``), the
    call is cancelled and the interruption is raised only once the call has
    stopped, so nothing is sent on the caller's behalf afterwards. A call
    on a closed client, or whose client closes while it waits, raises
    :class:`~polyester.errors.PolyesterError`, and so does a call made from a
    client callback, which runs on the loop and can't wait for it.

    ``call`` runs on the loop, so a caller interrupted before the call was
    scheduled leaves nothing behind.
    """
    if not loop.is_running():
        raise PolyesterError("the client is closed")
    refuse_on_client_loop(loop, what)
    finished = threading.Event()
    holder: dict[str, asyncio.Task[T]] = {}

    async def run() -> T:
        return await call()

    def settled(task: asyncio.Task[T]) -> None:
        # Mark the outcome retrieved: an interrupted caller never reads it.
        if not task.cancelled():
            task.exception()
        finished.set()

    def start() -> None:
        task = loop.create_task(run())
        task.add_done_callback(settled)
        holder["task"] = task

    def cancel() -> None:
        # The loop runs callbacks in order: a queued ``start`` has run by now,
        # and one that is not queued never will be.
        task = holder.get("task")
        if task is None:
            finished.set()
        else:
            task.cancel()

    try:
        loop.call_soon_threadsafe(start)
        while not finished.wait(_POLL_SECONDS):
            if not loop.is_running():
                raise PolyesterError("the client closed during the call")
    except BaseException:
        if not finished.is_set() and loop.is_running():
            loop.call_soon_threadsafe(cancel)
            while not finished.wait(_POLL_SECONDS) and loop.is_running():
                pass
        raise
    return holder["task"].result()
