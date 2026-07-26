"""POLY-3746: SnapshotThenStream surfaces refresh errors and clears on success."""

from __future__ import annotations

import pytest

from polyester.errors import PolyesterRealtimeError
from polyester.realtime.client import AsyncRealtimeClient
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription


@pytest.mark.asyncio
async def test_refresh_snapshot_stores_last_error_and_clears_on_success() -> None:
    realtime = AsyncRealtimeClient("wss://example.invalid")
    attempts = {"n": 0}

    async def fetch_snapshot() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise PolyesterRealtimeError("snapshot boom")
        return "ok"

    applied: list[str] = []

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=realtime,
        channel="public:test",
        decode=lambda b: b,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda snap, _pending: applied.append(snap),
        apply_live_publications=lambda _p: None,
    )

    assert await sub.refresh_snapshot() is False
    assert sub.is_ready() is False
    assert sub.last_error is not None
    assert "snapshot boom" in str(sub.last_error)

    assert await sub.refresh_snapshot() is True
    assert sub.is_ready() is True
    assert sub.last_error is None
    assert applied == ["ok"]
    await sub.aclose()


@pytest.mark.asyncio
async def test_reconnect_refresh_fail_closed_after_retry() -> None:
    realtime = AsyncRealtimeClient("wss://example.invalid")
    errors: list[Exception] = []

    async def fetch_snapshot() -> str:
        raise PolyesterRealtimeError("always fail")

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=realtime,
        channel="public:test",
        decode=lambda b: b,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda _s, _p: None,
        apply_live_publications=lambda _p: None,
        on_error=errors.append,
    )

    await sub._refresh_after_reconnect()
    assert sub.is_disposed()
    assert sub.last_error is not None
    assert len(errors) >= 1
    await sub.aclose()
