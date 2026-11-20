"""Run an async call on the sync client's loop and wait for it from another thread."""

from __future__ import annotations

import asyncio
import contextlib
import threading
import weakref
from collections.abc import Awaitable, Callable
from typing import TypeVar

from polyester.errors import PolyesterError

T = TypeVar("T")

_POLL_SECONDS = 0.25

# Admission to a client loop: a loop in ``_closed_loops`` takes no new call or
# subscription setup. The lock makes closing it and admitting a call (check and
# schedule) exclusive, so every call admitted was queued before the close went on.
_admission = threading.Lock()
_closed_loops: weakref.WeakSet[asyncio.AbstractEventLoop] = weakref.WeakSet()
# Loops that stopped for good and run only to finish their shutdown: a queued
# call is abandoned there, never started.
_finishing_loops: weakref.WeakSet[asyncio.AbstractEventLoop] = weakref.WeakSet()


def close_admission(loop: asyncio.AbstractEventLoop) -> None:
    """Admit no new call or subscription setup to ``loop`` from here on.

    The sync client's close calls it before its shutdown can yield the loop or
    run it again, so a call made once the close has begun, or after a close that
    stopped waiting for a held loop, raises the closed client's error at once.
    """
    with _admission:
        _closed_loops.add(loop)


def begin_finishing(loop: asyncio.AbstractEventLoop) -> None:
    """On the loop thread, once ``loop`` has stopped for good: start no queued call.

    The loop runs again only to finish its client's shutdown; a call still
    queued, or whose task has not yet run, is abandoned instead of started.
    """
    _finishing_loops.add(loop)


def admits_calls(loop: asyncio.AbstractEventLoop) -> bool:
    """Whether ``loop`` still takes new calls: it runs and its client is not closing."""
    return loop.is_running() and loop not in _closed_loops


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
    stopped, so nothing is sent on the caller's behalf afterwards. A call made
    from a client callback, which runs on the loop and can't wait for it,
    raises :class:`~polyester.errors.PolyesterError`.

    A call on a closed client raises ``closed_error``
    (:class:`~polyester.errors.PolyesterError` by default). So does a call
    whose client closes while it waits (``closed_during``): whether the call
    started is decided once, under a lock, so one the caller is told did not
    run never starts afterwards. A call that had started when its client
    closed is waited for; one the closing loop then cancels raises
    ``closed_error`` with an unknown outcome
    (:func:`~polyester.errors.mutation_outcome_unknown` is true): a write may
    have been applied, so read it back before sending it again.

    ``call`` is called on the loop, so a caller interrupted before the call
    started, or a call the loop stops before reaching, leaves nothing behind.
    """
    if not admits_calls(loop):
        raise closed_error("the client is closed")
    refuse_on_client_loop(loop, what)
    submission = _Submission(loop)
    finished = threading.Event()
    holder: dict[str, asyncio.Task[T | _NotStarted]] = {}

    async def run() -> T | _NotStarted:
        if not submission.begin():
            return NOT_STARTED
        return await call()

    def settled(task: asyncio.Task[T | _NotStarted]) -> None:
        # Mark the outcome retrieved: an interrupted caller never reads it.
        if not task.cancelled():
            task.exception()
        finished.set()

    def start() -> None:
        if submission.abandoned():
            finished.set()
            return
        task = loop.create_task(run(), name=SUBMISSION_TASK_NAME)
        task.add_done_callback(settled)
        holder["task"] = task

    def cancel() -> None:
        # The loop runs callbacks in order: a queued ``start`` has run by now.
        task = holder.get("task")
        if task is None:
            finished.set()
        else:
            task.cancel()

    # Scheduling and waiting share one cleanup: an interruption at any point,
    # even right after ``start`` is queued, abandons a call that has not started.
    try:
        with _admission:
            # Checked again with the close excluded: ``start`` is queued before a
            # close that begins later, or not at all.
            if not admits_calls(loop):
                raise closed_error("the client is closed")
            try:
                loop.call_soon_threadsafe(start)
            except RuntimeError:
                # The loop closed since the check: ``start`` never runs.
                raise closed_error("the client is closed") from None
        while not finished.wait(_POLL_SECONDS):
            if loop.is_running():
                continue
            if submission.abandon():
                # Stopped before the call started, and now it never will.
                raise closed_error(closed_during)
            if loop.is_closed():
                # Started, and the loop closed without settling it.
                raise _unknown_outcome(closed_error, closed_during)
            # Started: the stopped loop finishes or cancels it before closing.
    except BaseException:
        if not submission.abandon() and not finished.is_set():
            # Started: stop it before the caller resumes.
            with contextlib.suppress(RuntimeError):  # closed: it stopped with the loop
                loop.call_soon_threadsafe(cancel)
            while not finished.wait(_POLL_SECONDS) and not loop.is_closed():
                pass
        raise
    task = holder.get("task")
    if task is None or not submission.started():
        raise closed_error(closed_during)
    if task.cancelled():
        # Only the closing client loop cancels a started call its caller waits for.
        raise _unknown_outcome(closed_error, closed_during)
    result = task.result()
    if isinstance(result, _NotStarted):
        raise closed_error(closed_during)
    return result


class _NotStarted:
    """What a submission's task returns when it was abandoned before it started."""


NOT_STARTED = _NotStarted()

# The name of every task ``run_on_loop`` starts, so a finishing loop can tell
# them from its own shutdown.
SUBMISSION_TASK_NAME = "polyester-sync-call"


class _Submission:
    """Whether one ``run_on_loop`` call has started, decided once under its lock.

    The loop starts it unless its caller abandoned it first or the loop is
    finishing; the caller abandons it unless it started first. Either way the
    other side sees the decision, so a call its caller was told did not run
    never starts.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._lock = threading.Lock()
        self._state = "queued"

    def begin(self) -> bool:
        """On the loop: start the call, unless it was abandoned or the loop is finishing."""
        with self._lock:
            if self._state == "queued" and self._loop not in _finishing_loops:
                self._state = "started"
                return True
            self._state = "abandoned"
            return False

    def abandon(self) -> bool:
        """By the caller: abandon the call unless it started. True if it never will."""
        with self._lock:
            if self._state == "queued":
                self._state = "abandoned"
            return self._state == "abandoned"

    def abandoned(self) -> bool:
        with self._lock:
            return self._state == "abandoned"

    def started(self) -> bool:
        with self._lock:
            return self._state == "started"


def _unknown_outcome(closed_error: type[PolyesterError], closed_during: str) -> PolyesterError:
    error = closed_error(f"{closed_during} after it started: its outcome is unknown")
    error._outcome_known = False
    return error
