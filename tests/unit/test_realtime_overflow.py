"""Realtime queue overflow must fail the subscription, never silent-drop."""

from __future__ import annotations

import asyncio

import pytest

from polyester.errors import PolyesterRealtimeOverflowError
from polyester.realtime.client import AsyncSubscription, enqueue_or_overflow


@pytest.mark.asyncio
async def test_enqueue_or_overflow_succeeds_with_capacity() -> None:
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)
    close = asyncio.Event()
    enqueue_or_overflow(queue, 1, close=close)
    assert queue.get_nowait() == 1
    assert not close.is_set()


@pytest.mark.asyncio
async def test_enqueue_or_overflow_fails_when_full() -> None:
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=1)
    close = asyncio.Event()
    enqueue_or_overflow(queue, 1, close=close)
    with pytest.raises(PolyesterRealtimeOverflowError, match="queue full"):
        enqueue_or_overflow(queue, 2, close=close)
    assert close.is_set()


@pytest.mark.asyncio
async def test_async_subscription_raises_stored_overflow_error() -> None:
    queue: asyncio.Queue[int | None] = asyncio.Queue(maxsize=1)
    close = asyncio.Event()
    sub = AsyncSubscription[int](queue=queue, close=close)
    sub._set_error(PolyesterRealtimeOverflowError("queue full; consumer too slow"))
    close.set()
    with pytest.raises(PolyesterRealtimeOverflowError, match="queue full"):
        await anext(sub)
