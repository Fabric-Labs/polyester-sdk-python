"""Managed order books at any depth, through public paths against real local sockets.

The server here behaves like the public stream contract: it accepts a subscribe on
any depth, but publishes only on the tiers 1, 20, 50, 200 and 500, each as a SET
diff of that tier's own top-N view. Snapshots answer at any depth the snapshot enum
names, up to 1000.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest
import websockets

from polyester import AsyncPolyester
from polyester.errors import PolyesterValidationError
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.realtime.client import AsyncRealtimeClient
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
)
from tests.unit.test_server_unsubscribe import CentrifugoServer, publication

TIERS = (1, 20, 50, 200, 500)
SNAPSHOT_DEPTHS = (1, 5, 10, 20, 50, 100, 200, 500, 1000)
UNIT = 1_000_000_000  # One quote unit, in price ticks.
BEST_BID = 2000 * UNIT
BEST_ASK = 2001 * UNIT
WAIT = 5.0


def channel_for(depth: int) -> str:
    return f"public:spot:orderbook:deltas:depth:{depth}:1:proto"


def tier_for(depth: int) -> int:
    return next(tier for tier in TIERS if tier >= depth)


class TierServer(CentrifugoServer):
    """Accepts every subscribe, and counts the sockets that reached it."""

    def __init__(self) -> None:
        super().__init__()
        self.connections = 0

    async def _handle(self, ws) -> None:
        self.connections += 1
        await super()._handle(ws)


class TierMarket:
    """A book published per tier as SET diffs, and read through the snapshot API."""

    def __init__(self, server: TierServer, *, levels: int = 600) -> None:
        self.server = server
        self.bids = {BEST_BID - i * UNIT: 5 for i in range(levels)}
        self.asks = {BEST_ASK + i * UNIT: 5 for i in range(levels)}
        self.seq = 100
        self.available = True
        self.snapshot_requests: list[str] = []
        self.delivered: dict[str, int] = {}
        self.published = {tier: self._view(tier) for tier in TIERS}
        self.published_seq = dict.fromkeys(TIERS, self.seq)

    def _view(self, depth: int) -> tuple[dict[int, int], dict[int, int]]:
        bids = sorted(self.bids.items(), reverse=True)[:depth]
        asks = sorted(self.asks.items())[:depth]
        return dict(bids), dict(asks)

    async def snapshot(self, request: ParsedRequest) -> HttpScript:
        assert request.path.endswith("/GetOrderBook")
        message = orderbook_pb2.GetOrderBookRequest.FromString(request.body)
        name = orderbook_pb2.Depth.Name(message.depth)
        self.snapshot_requests.append(name)
        response = orderbook_pb2.GetOrderBookResponse(
            symbol_id=1, book_seq=self.seq, available=self.available
        )
        if self.available:
            bids, asks = self._view(int(name.removeprefix("DEPTH_")))
            for price, qty in sorted(bids.items(), reverse=True):
                response.bids.add(price_ticks=price, qty_scaled=qty)
            for price, qty in sorted(asks.items()):
                response.asks.add(price_ticks=price, qty_scaled=qty)
        return connect_proto_response(response.SerializeToString())

    async def send(
        self,
        depth: int,
        *,
        start: int,
        end: int,
        bids: dict[int, int] | None = None,
        asks: dict[int, int] | None = None,
        reset: bool = False,
    ) -> None:
        """Deliver one delta to everyone subscribed at ``depth``, as sent."""
        delta = orderbook_pb2.OrderBookDelta(
            symbol_id=1, book_seq_start=start, book_seq_end=end, reset=reset
        )
        for price, qty in (bids or {}).items():
            delta.bids.add(price_ticks=price, qty_scaled=qty)
        for price, qty in (asks or {}).items():
            delta.asks.add(price_ticks=price, qty_scaled=qty)
        channel = channel_for(depth)
        frame = publication(delta.SerializeToString())
        for ws in self.server.conns.get(channel, []):
            with contextlib.suppress(websockets.ConnectionClosed):
                await ws.send(frame)
                self.delivered[channel] = self.delivered.get(channel, 0) + 1

    async def publish(self) -> None:
        """Advance the sequence and publish each tier's diff, on the tiers only."""
        self.seq += 1
        for tier in TIERS:
            bids, asks = self._view(tier)
            old_bids, old_asks = self.published[tier]
            bid_diff = _diff(old_bids, bids)
            ask_diff = _diff(old_asks, asks)
            if not bid_diff and not ask_diff:
                continue
            await self.send(
                tier, start=self.published_seq[tier], end=self.seq, bids=bid_diff, asks=ask_diff
            )
            self.published[tier] = (bids, asks)
            self.published_seq[tier] = self.seq


def _diff(old: dict[int, int], new: dict[int, int]) -> dict[int, int]:
    changes = {price: qty for price, qty in new.items() if old.get(price) != qty}
    changes.update({price: 0 for price in old if price not in new})
    return changes


class Harness:
    def __init__(
        self, client: AsyncPolyester, market: TierMarket, server: TierServer, http: MockHttpServer
    ) -> None:
        self.client = client
        self.market = market
        self.server = server
        self.http = http


@contextlib.asynccontextmanager
async def harness(*, levels: int = 600) -> AsyncIterator[Harness]:
    async with TierServer() as server:
        market = TierMarket(server, levels=levels)
        http = await MockHttpServer.spawn(market.snapshot)
        client = AsyncPolyester(api_url=http.base_url, ws_url=server.url, hydrate_catalogs=False)
        client.catalogs.hydrate_spot_config(
            {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
        )
        try:
            yield Harness(client, market, server, http)
        finally:
            await client.aclose()
            await http.aclose()


async def next_view(sub, *, what: str = "a new view"):
    try:
        async with asyncio.timeout(WAIT):
            return await anext(sub)
    except TimeoutError:
        pytest.fail(f"no {what} within {WAIT} s: the managed book went silent")


async def subscribed_channel(server: TierServer) -> str:
    async with asyncio.timeout(WAIT):
        return await server.subscribed.get()


def bid_ticks(view) -> list[int]:
    return [level.price.ticks for level in view.bids]


def ask_ticks(view) -> list[int]:
    return [level.price.ticks for level in view.asks]


# ---------------------------------------------------------------- the mimic itself


async def test_control_an_unpublished_channel_is_accepted_and_silent() -> None:
    # Without this, a server that publishes everywhere would make every test here pass.
    async with TierServer() as server:
        market = TierMarket(server)
        rt = AsyncRealtimeClient(server.url)
        silent = await rt.subscribe_proto(channel_for(10), decode=lambda data: data)
        await server.wait_subscribed(channel_for(10))
        live = await rt.subscribe_proto(channel_for(20), decode=lambda data: data)
        await server.wait_subscribed(channel_for(20))

        market.bids[BEST_BID] = 7
        await market.publish()

        async with asyncio.timeout(WAIT):
            assert await anext(live)
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.3):
                await anext(silent)
        assert market.delivered == {channel_for(20): 1}
        assert silent.error is None, "the server accepted the unpublished subscribe"
        await rt.aclose()


# ---------------------------------------------------------------- requested depths


@pytest.mark.parametrize("depth", [5, 10, 25, 100])
async def test_depth_measured_silent_now_updates_on_deltas(depth: int) -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=depth)
        first = await next_view(sub, what="first view")

        h.market.bids[BEST_BID] = 7
        await h.market.publish()
        updated = await next_view(sub, what="view after a market move")

        assert h.market.delivered[channel_for(tier_for(depth))] == 1, "no delta was delivered"
        assert first.bids[0].qty.scaled == 5
        assert updated.bids[0].qty.scaled == 7
        assert int(updated.book_seq) > int(first.book_seq)
        assert (len(updated.bids), len(updated.asks)) == (depth, depth)
        await sub.aclose()


async def test_every_requested_depth_rides_its_tier_and_trims() -> None:
    async with harness() as h:
        seen_tiers = set()
        qty = 5
        for depth in range(1, 501):
            tier = tier_for(depth)
            seen_tiers.add(tier)
            sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=depth)
            assert await subscribed_channel(h.server) == channel_for(tier), depth
            first = await next_view(sub, what=f"first view at depth {depth}")
            assert h.market.snapshot_requests[-1] == f"DEPTH_{tier}", depth
            assert first.depth == depth
            assert bid_ticks(first) == [BEST_BID - i * UNIT for i in range(depth)]
            assert ask_ticks(first) == [BEST_ASK + i * UNIT for i in range(depth)]

            before = h.market.delivered.get(channel_for(tier), 0)
            qty += 1
            h.market.bids[BEST_BID] = qty
            await h.market.publish()
            updated = await next_view(sub, what=f"view after a delta at depth {depth}")
            assert h.market.delivered[channel_for(tier)] == before + 1, depth
            assert updated.depth == depth
            assert updated.bids[0].qty.scaled == qty, depth
            assert (len(updated.bids), len(updated.asks)) == (depth, depth), depth
            await sub.aclose()
            # Sockets of closed subscriptions must not count as later delivery.
            h.server.conns.clear()
        assert seen_tiers == set(TIERS)
        assert h.server.connections == 500


@pytest.mark.parametrize("tier", TIERS)
async def test_each_tier_uses_itself_for_channel_snapshot_and_view(tier: int) -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=tier)
        assert await subscribed_channel(h.server) == channel_for(tier)
        view = await next_view(sub, what="first view")
        assert h.market.snapshot_requests == [f"DEPTH_{tier}"]
        assert (view.depth, len(view.bids), len(view.asks)) == (tier, tier, tier)
        h.market.asks[BEST_ASK] = 9
        await h.market.publish()
        assert (await next_view(sub)).asks[0].qty.scaled == 9
        await sub.aclose()


async def test_default_depth_stays_fifty() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT")
        assert await subscribed_channel(h.server) == channel_for(50)
        assert (await next_view(sub, what="first view")).depth == 50
        await sub.aclose()


@pytest.mark.parametrize("depth", [501, 1000, 5000, 0, -1, True, 10.5, "10"])
async def test_unservable_depth_is_refused_before_connecting(depth) -> None:
    async with harness() as h:
        with pytest.raises(PolyesterValidationError, match="depth"):
            await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=depth)
        await asyncio.sleep(0.05)
        assert h.server.connections == 0
        assert h.market.snapshot_requests == []

        # Control: the same client does reach this server at the top tier.
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=500)
        await next_view(sub, what="first view")
        assert h.server.connections == 1
        assert h.market.snapshot_requests == ["DEPTH_500"]
        await sub.aclose()


async def test_refusal_above_the_top_tier_names_the_limit_and_the_snapshot() -> None:
    async with harness() as h:
        with pytest.raises(PolyesterValidationError) as refused:
            await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=1000)
        assert "500" in str(refused.value)
        assert "orderbook.get" in str(refused.value)


# ---------------------------------------------------------------- the trimmed view


async def test_trimmed_view_promotes_the_next_level_after_a_removal() -> None:
    # Fails if the snapshot is taken at the requested depth: level 11 would be unknown.
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=10)
        first = await next_view(sub, what="first view")
        assert bid_ticks(first)[-1] == BEST_BID - 9 * UNIT

        del h.market.bids[BEST_BID]
        await h.market.publish()
        updated = await next_view(sub, what="view after a removal")

        assert bid_ticks(updated) == [BEST_BID - i * UNIT for i in range(1, 11)]
        await sub.aclose()


async def test_levels_outside_the_view_stay_tracked() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=10)
        await next_view(sub, what="first view")
        deep = BEST_BID - 14 * UNIT

        h.market.bids[deep] = 33
        await h.market.publish()
        quiet = await next_view(sub, what="view after a deep change")
        assert deep not in bid_ticks(quiet), "trimmed to the requested depth"
        assert quiet.book_seq == str(h.market.seq)

        for i in range(5):
            del h.market.bids[BEST_BID - i * UNIT]
        await h.market.publish()
        promoted = await next_view(sub, what="view after removals")
        level = promoted.bids[bid_ticks(promoted).index(deep)]
        assert level.qty.scaled == 33
        await sub.aclose()


async def test_gap_in_a_delta_outside_the_view_refreshes_at_the_tier() -> None:
    async with harness() as h:
        gaps: list[str] = []
        sub = await h.client.orderbook.create_subscription(
            symbol="BTC-USDT", depth=10, on_sequence_gap=lambda: gaps.append("gap")
        )
        await next_view(sub, what="first view")
        deep = BEST_BID - 14 * UNIT

        # Sequences from the snapshot's 100, skipping ahead; only level 15 changes.
        h.market.bids[deep] = 44
        h.market.seq = 200
        await h.market.send(20, start=150, end=200, bids={deep: 44})
        refreshed = await next_view(sub, what="view after the gap refresh")

        assert gaps == ["gap"]
        assert h.market.snapshot_requests == ["DEPTH_20", "DEPTH_20"]
        assert refreshed.book_seq == "200"
        assert len(refreshed.bids) == 10
        await sub.aclose()


async def test_sequence_zero_snapshot_still_detects_a_gap_at_a_trimmed_depth() -> None:
    async with harness() as h:
        gaps: list[str] = []
        h.market.seq = 0
        sub = await h.client.orderbook.create_subscription(
            symbol="BTC-USDT", depth=10, on_sequence_gap=lambda: gaps.append("gap")
        )
        first = await next_view(sub, what="first view")
        assert first.book_seq == "0"
        assert len(first.bids) == 10

        h.market.seq = 6
        await h.market.send(20, start=5, end=6, bids={BEST_BID: 8})
        refreshed = await next_view(sub, what="view after the gap refresh")

        assert gaps == ["gap"]
        assert refreshed.book_seq == "6"
        assert refreshed.bids[0].qty.scaled == 5, "the gapped delta must not be applied"
        await sub.aclose()


async def test_sequence_zero_snapshot_applies_the_next_contiguous_delta() -> None:
    async with harness() as h:
        gaps: list[str] = []
        h.market.seq = 0
        sub = await h.client.orderbook.create_subscription(
            symbol="BTC-USDT", depth=10, on_sequence_gap=lambda: gaps.append("gap")
        )
        await next_view(sub, what="first view")

        await h.market.send(20, start=1, end=1, bids={BEST_BID: 8})
        updated = await next_view(sub, what="view after a delta")

        assert gaps == []
        assert (updated.book_seq, updated.bids[0].qty.scaled) == ("1", 8)
        assert h.market.snapshot_requests == ["DEPTH_20"]
        await sub.aclose()


async def test_unavailable_book_stays_unknown_then_recovers_trimmed() -> None:
    async with harness() as h:
        h.market.available = False
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=10)
        unknown = await next_view(sub, what="first view")
        assert (unknown.available, unknown.depth, unknown.bids) == (False, 10, [])

        # A reset delta carries no availability: the view stays unavailable.
        await h.market.send(20, start=0, end=101, reset=True, bids={BEST_BID: 5})
        still = await next_view(sub, what="view after a reset")
        assert still.available is False

        h.market.available = True
        recovered = await next_view(sub, what="view after the book came back")
        assert recovered.available is True
        assert (len(recovered.bids), len(recovered.asks)) == (10, 10)
        assert set(h.market.snapshot_requests) == {"DEPTH_20"}
        assert len(h.market.snapshot_requests) == 2
        await sub.aclose()


async def test_reset_delta_replaces_the_book_and_stays_trimmed() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=2)
        await next_view(sub, what="first view")
        prices = {BEST_BID - i * UNIT: 3 for i in range(20)}
        await h.market.send(20, start=0, end=500, reset=True, bids=prices, asks={})
        view = await next_view(sub, what="view after a reset")
        assert bid_ticks(view) == [BEST_BID, BEST_BID - UNIT]
        assert view.asks == []
        assert view.book_seq == "500"
        await sub.aclose()


async def test_coarse_bucket_aggregates_the_tier_then_trims_to_the_depth() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=2, bucket="5")
        view = await next_view(sub, what="first view")
        # Bids floor to 2000 (one level) and 1995 (five levels); asks ceil to 2005 and 2010.
        assert bid_ticks(view) == [2000 * UNIT, 1995 * UNIT]
        assert [level.qty.scaled for level in view.bids] == [5, 25]
        assert ask_ticks(view) == [2005 * UNIT, 2010 * UNIT]
        assert [level.qty.scaled for level in view.asks] == [25, 25]

        h.market.bids[BEST_BID - UNIT] = 15
        await h.market.publish()
        updated = await next_view(sub, what="view after a delta")
        assert [level.qty.scaled for level in updated.bids] == [5, 35]
        await sub.aclose()


async def test_coarse_bucket_above_the_price_shows_the_zero_bid_at_a_trimmed_depth() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(
            symbol="BTC-USDT", depth=10, bucket="100000"
        )
        view = await next_view(sub, what="first view")
        assert bid_ticks(view) == [0]
        assert view.bids[0].qty.scaled == 5 * 20, "every tier level floors into the zero bucket"
        assert ask_ticks(view) == [100000 * UNIT]
        await sub.aclose()


async def test_zero_price_outside_the_trimmed_view_resyncs_at_the_tier() -> None:
    # Refused before it reaches the book: rebuilt from a fresh tier snapshot, still open.
    async with harness() as h:
        errors: list[Exception] = []
        gaps: list[str] = []
        sub = await h.client.orderbook.create_subscription(
            symbol="BTC-USDT",
            depth=10,
            on_error=errors.append,
            on_sequence_gap=lambda: gaps.append("gap"),
        )
        first = await next_view(sub, what="first view")
        await h.market.send(20, start=100, end=101, bids={0: 5})
        refreshed = await next_view(sub, what="view after the refused delta")
        assert refreshed.book_seq == first.book_seq
        assert bid_ticks(refreshed) == bid_ticks(first)
        assert h.market.snapshot_requests == ["DEPTH_20", "DEPTH_20"]
        assert gaps == ["gap"]
        assert errors == []
        assert sub.last_error is None
        await sub.aclose()


async def test_reconnect_stays_on_the_tier_and_refetches_at_it() -> None:
    async with harness() as h:
        reconnects: list[str] = []
        sub = await h.client.orderbook.create_subscription(
            symbol="BTC-USDT", depth=10, on_reconnect=lambda: reconnects.append("r")
        )
        assert await subscribed_channel(h.server) == channel_for(20)
        await next_view(sub, what="first view")

        await h.server.conns[channel_for(20)][-1].close()
        async with asyncio.timeout(10):
            assert await h.server.subscribed.get() == channel_for(20)
        refreshed = await next_view(sub, what="view after the reconnect")
        assert reconnects == ["r"]
        assert h.market.snapshot_requests == ["DEPTH_20", "DEPTH_20"]
        assert len(refreshed.bids) == 10
        await sub.aclose()


# ---------------------------------------------------------------- raw reads


@pytest.mark.parametrize("tier", TIERS)
async def test_raw_deltas_at_a_published_tier_are_delivered(tier: int) -> None:
    async with harness() as h:
        sub = await h.client.orderbook.subscribe_deltas(symbol_id=1, depth=tier)
        assert await subscribed_channel(h.server) == channel_for(tier)
        h.market.bids[BEST_BID] = 7
        await h.market.publish()
        async with asyncio.timeout(WAIT):
            delta = await anext(sub)
        assert h.market.delivered[channel_for(tier)] == 1
        assert (delta.book_seq_start, delta.book_seq_end) == ("100", "101")
        assert (str(BEST_BID), "7") in delta.bids
        await sub.aclose()


@pytest.mark.parametrize("depth", [5, 10, 25, 100, 501, 1000, 0, -1, True, 20.0, "20"])
async def test_raw_deltas_at_an_unpublished_depth_are_refused(depth) -> None:
    async with harness() as h:
        with pytest.raises(PolyesterValidationError, match="1, 20, 50, 200, 500"):
            await h.client.orderbook.subscribe_deltas(symbol_id=1, depth=depth)
        await asyncio.sleep(0.05)
        assert h.server.connections == 0


@pytest.mark.parametrize("depth", SNAPSHOT_DEPTHS)
async def test_raw_snapshot_serves_every_enum_depth(depth: int) -> None:
    async with harness(levels=1100) as h:
        book = await h.client.orderbook.get(symbol="BTC-USDT", depth=depth)
        assert h.market.snapshot_requests == [f"DEPTH_{depth}"]
        assert (book.depth, len(book.bids), len(book.asks)) == (depth, depth, depth)
        assert h.server.connections == 0
