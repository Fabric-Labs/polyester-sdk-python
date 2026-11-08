"""A consumer that joins a private order stream gets ``Connected`` first.

Joining while the stream is disconnected, it waits for the reconnect and
then gets ``Connected`` before the cached snapshot, ready and stale state, as
a consumer joining a connected stream does.

Each schedule draws, from one seed, the cached view (orders, ready, stale),
the close code, when the consumer joins (while disconnected or once
reconnected), the pauses around the join, and what the resumed subscription
sends next. Set ``POLYESTER_INTERLEAVING_SEED`` to replay a failing run and
``POLYESTER_INTERLEAVINGS`` to run more schedules.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Callable
from typing import Any

from polyester.codecs.scalars import format_id
from polyester.gen.privatews.v1 import private_ws_pb2 as pb
from polyester.models import (
    PrivateOrdersConnected,
    PrivateOrdersReady,
    PrivateOrdersSnapshot,
    PrivateOrdersStale,
)
from polyester.realtime import private_orders
from polyester.realtime.private_orders import PrivateOrderStream, private_ws_url
from tests.unit.test_private_orders_stream import (
    ACCOUNT_B58,
    CHANNEL,
    EVENT_TIMEOUT,
    FakePrivateWsServer,
    Tokens,
    fast_backoff,  # noqa: F401  (autouse fixture)
    next_event,
    open_stream,
    order,
)


def _interleavings() -> int:
    return int(os.environ.get("POLYESTER_INTERLEAVINGS", "32"))


def _seed() -> int:
    raw = os.environ.get("POLYESTER_INTERLEAVING_SEED")
    return int(raw) if raw else random.SystemRandom().randrange(2**32)


async def _until(condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(EVENT_TIMEOUT):
        while not condition():
            await asyncio.sleep(0.001)


def _drain(subscription: Any) -> list[Any]:
    events = []
    while not subscription._queue.empty():
        events.append(subscription._queue.get_nowait())
    return events


async def _schedule(seed: int) -> None:
    rng = random.Random(seed)
    cached = [order(i) for i in range(1, rng.randint(0, 3) + 1)]
    ready = rng.random() < 0.5
    stale = rng.random() < 0.5
    close_code = rng.choice([4408, 1001, 4401])
    join_while_disconnected = rng.random() < 0.75
    pause_before_join = rng.uniform(0.0, 0.02)
    pause_after_join = rng.uniform(0.0, 0.02)
    after = rng.choice(["nothing", "ready", "snapshot", "available"])
    detail = (
        f"seed={seed} orders={len(cached)} ready={ready} stale={stale} close={close_code} "
        f"join_while_disconnected={join_while_disconnected} after={after}: "
        "replay with POLYESTER_INTERLEAVING_SEED"
    )

    server = FakePrivateWsServer()
    await server.start()
    tokens = Tokens()
    stream = PrivateOrderStream(
        url=private_ws_url(server.api_url),
        fetch_connect_token=tokens.connect,
        fetch_subscribe_token=tokens.subscribe,
    )
    try:
        sub, first = await open_stream(server, stream)
        await first.snapshot("s1", "c1", cached)
        assert isinstance(await next_event(sub), PrivateOrdersSnapshot)
        seq = 4
        if ready:
            await first.send("s1", seq, ready=pb.Ready())
            seq += 1
            assert isinstance(await next_event(sub), PrivateOrdersReady)
        if stale:
            await first.send("s1", seq, unavailable=pb.Unavailable(reason=pb.FAILOVER))
            assert isinstance(await next_event(sub), PrivateOrdersStale)
        await first.close(close_code)
        await _until(lambda: stream._subs[CHANNEL].state == "disconnected")
        second = await server.next_connection()
        await second.expect("auth")

        late_task: asyncio.Task[Any] | None = None
        if join_while_disconnected:
            await asyncio.sleep(pause_before_join)
            late_task = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
            await asyncio.sleep(pause_after_join)
        await second.confirm("s2")
        if late_task is None:
            await _until(lambda: stream._subs[CHANNEL].state == "connected")
            await asyncio.sleep(pause_before_join)
            late_task = asyncio.create_task(stream.subscribe(ACCOUNT_B58))
        late = await asyncio.wait_for(late_task, EVENT_TIMEOUT)
        if after == "ready":
            await second.send("s2", 1, ready=pb.Ready())
        elif after == "snapshot":
            await second.snapshot("s2", "c2", [order(9)])
        elif after == "available":
            await second.send("s2", 1, available=pb.Available())
        await asyncio.sleep(0.05)
        events = _drain(late)
        kinds = [type(event).__name__ for event in events]

        assert events and isinstance(events[0], PrivateOrdersConnected), (
            f"first event {kinds}; expected Connected first ({detail})"
        )
        assert len([e for e in events if isinstance(e, PrivateOrdersConnected)]) == 1, (
            f"{kinds} ({detail})"
        )
        assert isinstance(events[1], PrivateOrdersSnapshot), f"{kinds} ({detail})"
        assert [o.order_id for o in events[1].orders] == [
            format_id(i) for i in range(1, len(cached) + 1)
        ], f"{kinds} ({detail})"
        if after == "snapshot":
            assert [o.order_id for o in events[-1].orders] == [format_id(9)], f"{detail}"
    finally:
        await stream.aclose()
        await server.aclose()


async def test_consumer_joining_during_a_disconnection_gets_connected_first(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(private_orders, "RECONNECT_BASE_DELAY", 0.001)
    monkeypatch.setattr(private_orders, "RECONNECT_MAX_DELAY", 0.005)
    base = _seed()
    for offset in range(_interleavings()):
        await _schedule((base + offset) % 2**32)
