"""POLY-8563 review: the publication age is never negative, read from any thread.

The sync handle reads the age from the caller's thread while the client loop records
publications. Reading the clock before the last publication's time let a publication
recorded in between make the age negative.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time

from tests.unit.test_orderbook_published_depths import BEST_BID, harness, next_view


async def test_age_read_from_another_thread_is_never_negative() -> None:
    async with harness() as h:
        sub = await h.client.orderbook.create_subscription(symbol="BTC-USDT", depth=1)
        await next_view(sub, what="first view")

        stop = threading.Event()
        bad: list[float] = []
        reads = 0

        def read() -> None:
            nonlocal reads
            while not stop.is_set():
                age = sub.since_last_publication()
                reads += 1
                if age < 0:
                    bad.append(age)

        interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)
        reader = threading.Thread(target=read)
        reader.start()
        try:
            deadline = time.monotonic() + 1.0
            qty = 5
            while time.monotonic() < deadline:
                qty += 1
                h.market.bids[BEST_BID] = qty
                await h.market.publish()
                await asyncio.sleep(0)
        finally:
            stop.set()
            reader.join()
            sys.setswitchinterval(interval)
        await sub.aclose()
        assert reads > 0
        assert not bad, f"{len(bad)} of {reads} reads were negative, first {bad[0]}"
