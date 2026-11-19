"""Run an async call on the sync client's loop and wait for it from another thread."""

from __future__ import annotations

import asyncio
import contextlib
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
    closed_error: type[PolyesterError] = PolyesterError,
    closed_during: str = "the client closed during the call",
) -> T:
    """Run ``call()`` on ``loop`` and return its result once it has ended.

    The wait has no deadline of its own: the configured transport timeout and
    a method's own ``timeout`` bound the call, so its outcome, an unknown
    mutation outcome included, is the async call's. If the caller is
    interrupted while it waits (for example by ``KeyboardInterrupt``), the
    call is cancelled and the interruption is raised only once the call has
    stopped, so nothing is sent on the caller's behalf afterwards. A call
    on a closed client, or whose client closes while it waits (its call
    cancelled as the client loop finishes included), raises ``closed_error``
    (:class:`~polyester.errors.PolyesterError` by default, with
    ``closed_during`` once the call had been scheduled). A call made from a
    client callback, which runs on the loop and can't wait for it, raises
    :class:`~polyester.errors.PolyesterError`.

    ``call`` is called on the loop, so a caller interrupted before the call was
    scheduled, or a call the loop stops before reaching, leaves nothing behind.
    """
    if not loop.is_running():
        raise closed_error("the client is closed")
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
        try:
            loop.call_soon_threadsafe(start)
        except RuntimeError:
            # The loop closed since the check above: ``start`` never runs.
            raise closed_error("the client is closed") from None
        while not finished.wait(_POLL_SECONDS):
            if not loop.is_running():
                raise closed_error(closed_during)
    except BaseException:
        if not finished.is_set() and loop.is_running():
            # A loop closed since the check stopped the call with it.
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(cancel)
            while not finished.wait(_POLL_SECONDS) and loop.is_running():
                pass
        raise
    task = holder["task"]
    if task.cancelled():
        # Only the closing client loop cancels a call its caller still waits for.
        raise closed_error(closed_during)
    return task.result()
