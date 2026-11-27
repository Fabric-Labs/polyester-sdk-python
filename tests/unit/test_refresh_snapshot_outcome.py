"""The public subscription wrappers return the snapshot refresh outcome.

``MarketOverviewSubscription.refresh_snapshot()`` and
``OrderbookSubscription.refresh_snapshot()`` return ``True`` when the
snapshot was fetched and applied, and ``False`` when it was not: then
``last_error`` holds the failure, ``on_error`` received it, and live
publications stay buffered, not delivered, until a later refresh succeeds and
merges them once.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from polyester.errors import PolyesterRealtimeError
from polyester.market_overview.subscription import MarketOverviewSubscription
from polyester.orderbook.subscription import OrderbookSubscription
from polyester.realtime.client import AsyncRealtimeClient
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription


def _market_overview(stream: Any) -> MarketOverviewSubscription:
    return MarketOverviewSubscription(queue=asyncio.Queue(), close=asyncio.Event(), stream=stream)


def _orderbook(stream: Any) -> OrderbookSubscription:
    return OrderbookSubscription(
        queue=asyncio.Queue(), close=asyncio.Event(), stream=stream, set_bucket=lambda _b: None
    )


WRAPPERS: list[Callable[[Any], MarketOverviewSubscription | OrderbookSubscription]] = [
    _market_overview,
    _orderbook,
]


class _Outcomes:
    """An inner stream whose refreshes answer the given outcomes in turn."""

    def __init__(self, *outcomes: bool) -> None:
        self._outcomes = list(outcomes)
        self.last_error: BaseException | None = None

    async def refresh_snapshot(self) -> bool:
        return self._outcomes.pop(0)

    async def aclose(self) -> None:
        return None


@pytest.mark.parametrize("wrap", WRAPPERS, ids=["market_overview", "orderbook"])
async def test_refresh_snapshot_returns_the_inner_outcome(wrap: Any) -> None:
    sub = wrap(_Outcomes(False, True))
    assert await sub.refresh_snapshot() is False
    assert await sub.refresh_snapshot() is True
    await sub.aclose()


@pytest.mark.parametrize("wrap", WRAPPERS, ids=["market_overview", "orderbook"])
async def test_a_failed_refresh_keeps_delivery_paused_until_a_retry_succeeds(wrap: Any) -> None:
    attempts = {"n": 0}

    async def fetch_snapshot() -> str:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise PolyesterRealtimeError("snapshot unavailable")
        return "snapshot"

    errors: list[Exception] = []
    delivered: list[str] = []
    stream = AsyncSnapshotThenStreamSubscription(
        realtime=AsyncRealtimeClient("wss://example.invalid"),
        channel="public:test",
        decode=lambda b: b,
        fetch_snapshot=fetch_snapshot,
        read_publication=lambda p: [p],
        # Publications held back during a refresh are merged with its snapshot.
        apply_snapshot=lambda _snap, pending: delivered.extend(pending),
        apply_live_publications=delivered.extend,
        on_error=errors.append,
    )
    sub = wrap(stream)

    assert await sub.refresh_snapshot() is False
    assert isinstance(sub.last_error, PolyesterRealtimeError)
    assert [str(e) for e in errors] == ["snapshot unavailable"]
    # A publication that arrives while the snapshot is missing is held back.
    stream._handle_publication("update-1")
    assert delivered == []

    assert await sub.refresh_snapshot() is True
    assert sub.last_error is None
    # The held publication is merged once, after the snapshot.
    assert delivered == ["update-1"]
    assert len(errors) == 1
    await sub.aclose()
