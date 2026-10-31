"""Filtered market overview subscriptions drop unrelated symbols in every path."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.models.market import MarketOverviewEntry, MarketOverviewList
from polyester.services import market_overview
from polyester.services.market_overview import AsyncMarketOverviewService


class _CapturingStream:
    instance: _CapturingStream | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        _CapturingStream.instance = self

    async def start(self) -> None:
        return None

    async def aclose(self) -> None:
        return None


def _row(symbol_id: int) -> MarketOverviewEntry:
    return MarketOverviewEntry(symbol_id=symbol_id, symbol=f"S{symbol_id}-USDT")


async def _subscribe(symbols: list[str] | None) -> tuple[_CapturingStream, list[list[int]]]:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {"symbol": "S1-USDT", "symbol_id": 1, "base_quantity_scale": 8},
                {"symbol": "S2-USDT", "symbol_id": 2, "base_quantity_scale": 8},
                {"symbol": "S3-USDT", "symbol_id": 3, "base_quantity_scale": 8},
            ]
        }
    )
    service = AsyncMarketOverviewService(MagicMock(), catalogs=catalogs, realtime=MagicMock())
    emitted: list[list[int]] = []
    await service.create_subscription(
        symbols=symbols,
        on_event=lambda rows: emitted.append(sorted(row.symbol_id for row in rows)),
    )
    stream = _CapturingStream.instance
    assert stream is not None
    return stream, emitted


@pytest.mark.asyncio
async def test_filtered_subscription_drops_unrelated_live_and_buffered_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(market_overview, "AsyncSnapshotThenStreamSubscription", _CapturingStream)
    stream, emitted = await _subscribe(["S1-USDT"])
    kwargs = stream.kwargs

    batch = MarketOverviewList(markets=[_row(1), _row(2), _row(3)], total=3)
    assert [row.symbol_id for row in kwargs["read_publication"](batch)] == [1]

    snapshot = MarketOverviewList(markets=[_row(1)], total=1)
    kwargs["apply_snapshot"](snapshot, [_row(2), _row(1)])
    kwargs["apply_live_publications"]([_row(3), _row(1)])

    assert emitted == [[1], [1]]


@pytest.mark.asyncio
async def test_unfiltered_subscription_keeps_every_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(market_overview, "AsyncSnapshotThenStreamSubscription", _CapturingStream)
    stream, emitted = await _subscribe(None)
    kwargs = stream.kwargs

    batch = MarketOverviewList(markets=[_row(1), _row(2)], total=2)
    assert [row.symbol_id for row in kwargs["read_publication"](batch)] == [1, 2]
    kwargs["apply_snapshot"](MarketOverviewList(markets=[_row(1)], total=1), [_row(2)])
    kwargs["apply_live_publications"]([_row(3)])

    assert emitted == [[1, 2], [1, 2, 3]]
