"""POLY-8563: a stalled publisher must be distinguishable from a quiet market.

The server republishes every book about every 30 s, so the time since the stream's
last publication tells them apart; the managed book reports it.
"""

from __future__ import annotations

import asyncio
import time

from tests.unit.test_orderbook_published_depths import BEST_BID, harness, next_view


async def test_managed_book_reports_time_since_last_publication() -> None:
    async with harness() as h:
        created = time.monotonic()
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=20)
        await next_view(sub, what="first view")

        # No publication yet: the age runs from the subscription's start.
        await asyncio.sleep(0.25)
        age = sub.since_last_publication()
        assert 0.25 <= age <= time.monotonic() - created

        # A publication restarts it.
        h.market.bids[BEST_BID] = 7
        await h.market.publish()
        await next_view(sub, what="view after a publication")
        assert sub.since_last_publication() < 0.2

        # Silence makes it grow again; a bucket change is not a publication.
        await asyncio.sleep(0.3)
        sub.set_bucket("1")
        await next_view(sub, what="view after a bucket change")
        assert sub.since_last_publication() >= 0.3
        await sub.aclose()
