"""Read a resource until it is final, within a deadline."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from polyester.errors import PolyesterTimeoutError

T = TypeVar("T")


async def poll_until_final(
    read: Callable[[], Awaitable[T]],
    is_final: Callable[[T], bool],
    *,
    timeout: float | None,
    initial: float,
    maximum: float,
    expired: Callable[[T | None], str],
) -> T:
    """``read`` until ``is_final`` holds, waiting ``initial`` seconds between
    reads and doubling up to ``maximum``.

    With a ``timeout``, the deadline bounds every read and every wait: a read
    still in flight at the deadline is cancelled, and a read that completes
    after it does not count, so the result is never returned late. Expiry
    raises :class:`~polyester.errors.PolyesterTimeoutError` with
    ``expired(last)``, ``last`` being the last result read in time or
    ``None``. Errors of a read are raised as they come.
    """
    deadline = None if timeout is None else time.monotonic() + max(timeout, 0.0)
    last: T | None = None
    delay = initial

    def remaining() -> float | None:
        return None if deadline is None else deadline - time.monotonic()

    def expiry(cause: BaseException | None = None) -> PolyesterTimeoutError:
        error = PolyesterTimeoutError(expired(last))
        error.__cause__ = cause
        return error

    while True:
        left = remaining()
        if left is not None and left <= 0:
            raise expiry()
        window = asyncio.timeout(left)
        try:
            async with window:
                result = await read()
        except TimeoutError as exc:
            if window.expired():
                raise expiry(exc) from exc
            raise
        left = remaining()
        if left is not None and left <= 0:
            raise expiry()
        last = result
        if is_final(result):
            return result
        await asyncio.sleep(delay if left is None else min(delay, left))
        delay = min(delay * 2, maximum)
