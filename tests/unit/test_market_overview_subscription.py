import asyncio

from polyester.market_overview.subscription import MarketOverviewSubscription
from polyester.models.market import MarketOverviewEntry, MarketOverviewList
from polyester.types.money import Price


class _FakeStream:
    def __init__(self) -> None:
        self.started = False
        self.refreshed = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def refresh_snapshot(self) -> None:
        self.refreshed = True

    async def aclose(self) -> None:
        self.closed = True


async def test_market_overview_subscription_iterates_emitted_rows() -> None:
    queue: asyncio.Queue = asyncio.Queue()
    close = asyncio.Event()
    fake = _FakeStream()
    task = asyncio.create_task(asyncio.sleep(0))
    sub = MarketOverviewSubscription(
        queue=queue,
        close=close,
        stream=fake,
        start_task=task,
    )
    rows = [
        MarketOverviewEntry(symbol_id=1, symbol="BTC-USDT", last_price=Price.from_ticks(100)),
    ]
    await queue.put(rows)
    assert await sub.__anext__() == rows
    await sub.aclose()
    assert fake.closed


async def test_snapshot_then_stream_merges_market_overview_rows() -> None:
    emitted: list[list[MarketOverviewEntry]] = []
    by_symbol_id: dict[int, MarketOverviewEntry] = {}

    def apply_rows(rows: list[MarketOverviewEntry]) -> None:
        for row in rows:
            by_symbol_id[row.symbol_id] = row

    def emit() -> None:
        emitted.append(list(by_symbol_id.values()))

    snapshot = MarketOverviewList(
        markets=[
            MarketOverviewEntry(
                symbol_id=1,
                symbol="BTC-USDT",
                last_price=Price.from_ticks(100),
            )
        ],
        total=1,
    )
    buffered = [
        MarketOverviewEntry(symbol_id=2, symbol="ETH-USDT", last_price=Price.from_ticks(200)),
    ]

    def apply_snapshot(snap: MarketOverviewList, pending: list[MarketOverviewEntry]) -> None:
        by_symbol_id.clear()
        apply_rows(snap.markets)
        apply_rows(pending)
        emit()

    def apply_live(rows: list[MarketOverviewEntry]) -> None:
        apply_rows(rows)
        emit()

    apply_snapshot(snapshot, buffered)
    apply_live(
        [
            MarketOverviewEntry(
                symbol_id=1,
                symbol="BTC-USDT",
                last_price=Price.from_ticks(150),
            )
        ]
    )

    assert len(emitted) == 2
    assert {row.symbol_id for row in emitted[0]} == {1, 2}
    assert emitted[1][0].last_price is not None and emitted[1][0].last_price.ticks == 150
