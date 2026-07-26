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


@pytest.mark.asyncio
async def test_failed_refresh_retains_publications_for_successful_retry() -> None:
    realtime = AsyncRealtimeClient("wss://example.invalid")
    attempts = {"n": 0}
    merged: list[list[bytes]] = []

    async def fetch_snapshot() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise PolyesterRealtimeError("transient snapshot failure")
        return "recovered"

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=realtime,
        channel="public:test",
        decode=lambda b: b,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda _snapshot, pending: merged.append(pending),
        apply_live_publications=lambda _p: None,
    )
    sub._handle_publication(b"before")
    assert await sub.refresh_snapshot() is False
    sub._handle_publication(b"during")
    assert await sub.refresh_snapshot() is True
    assert merged == [[b"before", b"during"]]
    assert sub.last_error is None
    await sub.aclose()


@pytest.mark.asyncio
async def test_consumer_callback_failure_is_observable_and_fail_closed() -> None:
    realtime = AsyncRealtimeClient("wss://example.invalid")
    errors: list[Exception] = []

    async def fetch_snapshot() -> str:
        return "ready"

    def apply_live(_publications: list[bytes]) -> None:
        raise RuntimeError("consumer bug")

    sub = AsyncSnapshotThenStreamSubscription(
        realtime=realtime,
        channel="public:test",
        decode=lambda b: b,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        apply_snapshot=lambda _snapshot, _pending: None,
        apply_live_publications=apply_live,
        on_error=errors.append,
    )
    assert await sub.refresh_snapshot() is True

    sub._handle_publication(b"message")

    assert sub.is_disposed()
    assert not sub.is_ready()
    assert sub.last_error is not None
    assert "apply_live_publications callback failed" in str(sub.last_error)
    assert errors and errors[-1] is sub.last_error
    sub._on_error = lambda _error: (_ for _ in ()).throw(RuntimeError("error callback bug"))
    sub._report_snapshot_error(PolyesterRealtimeError("reported safely"))
    await sub.aclose()
