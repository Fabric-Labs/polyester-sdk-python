"""A Market Overview subscription merges buffered updates into its snapshot by
freshness.

Publications that arrive while the snapshot loads are buffered and merged into
it once it is read. A buffered row whose ``last_trade_ts_ns`` is older than the
snapshot's row for that market was published before the snapshot was taken and
does not replace it. A row with the same last-trade time does replace it: it
carries index, volume and book changes made since. A newer row replaces it,
and a market missing from the snapshot is added.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from polyester.catalogs import CatalogManager
from polyester.models.market import MarketOverviewEntry, MarketOverviewList
from polyester.services.market_overview import AsyncMarketOverviewService
from polyester.types.money import Price

SNAPSHOT_TRADE = "1795721087978971514"
OLDER_TRADE = "1795721087185742363"
NEWER_TRADE = "1795721088000000000"


def _row(symbol_id: int, trade_ts: str, last: int, **fields: Any) -> MarketOverviewEntry:
    return MarketOverviewEntry(
        symbol_id=symbol_id,
        last_price=Price.from_ticks(last),
        last_trade_ts_ns=trade_ts,
        **fields,
    )


async def _merge(
    monkeypatch: pytest.MonkeyPatch,
    snapshot: list[MarketOverviewEntry],
    buffered: list[MarketOverviewEntry],
    drained: list[MarketOverviewEntry] | None = None,
    live: list[MarketOverviewEntry] | None = None,
    live_while_refreshing: list[MarketOverviewEntry] | None = None,
) -> dict[int, MarketOverviewEntry]:
    """The last view a subscription emits, merging ``buffered`` into ``snapshot``.

    Like the snapshot engine, the fake applies the snapshot with the
    publications buffered while it loaded, then ``drained``, the ones that
    arrived while it was being applied, through ``apply_drained_publications``
    before it is ready, then marks it ready and applies ``live``.
    ``live_while_refreshing`` were dispatched live, but a refresh marks the
    stream not ready before their callback runs.
    """
    captured: dict[str, Any] = {}

    class _Stream:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.ready = False

        def is_ready(self) -> bool:
            return self.ready

        async def start(self) -> None:
            captured["apply_snapshot"](MarketOverviewList(markets=snapshot), buffered)
            if drained:
                captured["apply_drained_publications"](drained)
            self.ready = True
            if live:
                captured["apply_live_publications"](live)
            if live_while_refreshing:
                self.ready = False
                captured["apply_live_publications"](live_while_refreshing)

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "polyester.services.market_overview.AsyncSnapshotThenStreamSubscription", _Stream
    )
    views: list[list[MarketOverviewEntry]] = []
    service = AsyncMarketOverviewService(
        MagicMock(), catalogs=CatalogManager(), realtime=MagicMock()
    )
    sub = await service.create_subscription(on_event=views.append)
    await sub.aclose()
    return {row.symbol_id: row for row in views[-1]}


async def test_an_older_buffered_row_does_not_regress_a_newer_snapshot_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = await _merge(
        monkeypatch,
        snapshot=[_row(1, SNAPSHOT_TRADE, 61_000)],
        buffered=[_row(1, OLDER_TRADE, 60_000)],
    )
    assert view[1].last_trade_ts_ns == SNAPSHOT_TRADE
    assert view[1].last_price == Price.from_ticks(61_000)


async def test_a_newer_buffered_row_replaces_the_snapshot_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = await _merge(
        monkeypatch,
        snapshot=[_row(1, SNAPSHOT_TRADE, 61_000)],
        buffered=[_row(1, NEWER_TRADE, 62_000)],
    )
    assert view[1].last_trade_ts_ns == NEWER_TRADE
    assert view[1].last_price == Price.from_ticks(62_000)


async def test_an_equal_trade_time_row_applies_its_index_and_volume_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = await _merge(
        monkeypatch,
        snapshot=[
            _row(
                1,
                SNAPSHOT_TRADE,
                61_000,
                index_price=Price.from_ticks(60_990),
                volume_24h_usd_scaled="100",
            )
        ],
        buffered=[
            _row(
                1,
                SNAPSHOT_TRADE,
                61_000,
                index_price=Price.from_ticks(61_005),
                volume_24h_usd_scaled="250",
            )
        ],
    )
    assert view[1].index_price == Price.from_ticks(61_005)
    assert view[1].volume_24h_usd_scaled == "250"


async def test_buffered_markets_missing_from_the_snapshot_are_added(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = await _merge(
        monkeypatch,
        snapshot=[_row(1, SNAPSHOT_TRADE, 61_000)],
        buffered=[_row(2, OLDER_TRADE, 3_000), _row(1, OLDER_TRADE, 60_000)],
    )
    assert set(view) == {1, 2}
    assert view[1].last_trade_ts_ns == SNAPSHOT_TRADE


async def test_an_older_row_arriving_while_the_snapshot_is_applied_does_not_regress_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = await _merge(
        monkeypatch,
        snapshot=[_row(1, SNAPSHOT_TRADE, 61_000)],
        buffered=[],
        drained=[_row(1, OLDER_TRADE, 60_000)],
    )
    assert view[1].last_trade_ts_ns == SNAPSHOT_TRADE
    assert view[1].last_price == Price.from_ticks(61_000)


async def test_live_updates_once_ready_apply_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    view = await _merge(
        monkeypatch,
        snapshot=[_row(1, SNAPSHOT_TRADE, 61_000)],
        buffered=[],
        live=[_row(1, OLDER_TRADE, 60_000)],
    )
    assert view[1].last_trade_ts_ns == OLDER_TRADE


async def test_a_live_dispatched_row_applies_even_if_a_refresh_starts_before_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The engine dispatched it live; readiness at callback time does not matter.
    view = await _merge(
        monkeypatch,
        snapshot=[_row(1, SNAPSHOT_TRADE, 61_000)],
        buffered=[],
        live_while_refreshing=[_row(1, OLDER_TRADE, 60_000)],
    )
    assert view[1].last_trade_ts_ns == OLDER_TRADE
