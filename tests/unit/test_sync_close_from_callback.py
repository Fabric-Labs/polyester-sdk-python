"""POLY-9018: sync client methods called from a client callback.

A ``SyncSubscription`` closed from a callback stops delivery at once and
returns without waiting on the client loop it is running on. Every other sync
method that would have to wait on that loop refuses at once instead of
blocking it.
"""

from __future__ import annotations

import asyncio
import os
import random
import threading
import time
from typing import Any

import pytest

from polyester import Polyester
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV
from polyester.errors import PolyesterError
from polyester.services.changelog import AsyncChangelogService
from polyester.services.orders import AsyncOrdersService

# A close from a callback must not wait on the loop: well under the
# 10 s wait that used to time out.
PROMPT_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)


class Stream:
    """A subscription that has ``events`` ready at once when released, then
    stays open."""

    def __init__(self, events: list[Any], *, yield_between: bool = False) -> None:
        self.events = list(events)
        self.yield_between = yield_between
        self.aclose_calls = 0
        self.closed = threading.Event()
        self.gate = asyncio.Event()

    def release(self, client: Polyester) -> None:
        client._loop.call_soon_threadsafe(self.gate.set)

    async def __aiter__(self):
        await self.gate.wait()
        for event in self.events:
            yield event
            if self.yield_between:
                await asyncio.sleep(0)
        await asyncio.Event().wait()

    async def aclose(self) -> None:
        self.aclose_calls += 1
        self.closed.set()


def _serve(monkeypatch: pytest.MonkeyPatch, *streams: Stream) -> None:
    pending = iter(streams)

    async def subscribe(self, **kwargs):
        return next(pending)

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)


@pytest.mark.parametrize("method", ["close", "unsubscribe"])
def test_closing_a_subscription_from_its_own_callback_returns_at_once(monkeypatch, method):
    stream = Stream(["first", "second", "third"])
    _serve(monkeypatch, stream)
    delivered: list[str] = []
    outcome: list[object] = []
    handled = threading.Event()
    holder: dict[str, Any] = {}

    def on_event(event: str) -> None:
        delivered.append(event)
        started = time.monotonic()
        try:
            getattr(holder["sub"], method)()
            outcome.append(time.monotonic() - started)
        except BaseException as error:
            outcome.append(error)
        finally:
            handled.set()

    client = Polyester(hydrate_catalogs=False)
    try:
        holder["sub"] = client.orders.subscribe_sync(on_event=on_event, on_error=outcome.append)
        stream.release(client)
        assert handled.wait(15), "on_event never ran"
        assert len(outcome) == 1
        assert not isinstance(outcome[0], BaseException), f"{method}() raised {outcome[0]!r}"
        assert outcome[0] < PROMPT_SECONDS, f"{method}() blocked for {outcome[0]:.3f} s"
        assert stream.closed.wait(5), "the stream was never closed"
        time.sleep(0.05)
        assert delivered == ["first"], "events were delivered after close() returned"
        assert stream.aclose_calls == 1
        # Closing again, from outside the loop, is a no-op.
        holder["sub"].close()
        assert stream.aclose_calls == 1
    finally:
        client.close()
    assert not client._loop_thread.is_alive()


def test_closing_another_subscription_from_a_callback_returns_at_once(monkeypatch):
    trigger = Stream(["go"])
    target = Stream([], yield_between=True)
    _serve(monkeypatch, target, trigger)
    outcome: list[object] = []
    handled = threading.Event()
    holder: dict[str, Any] = {}

    def on_event(_: str) -> None:
        started = time.monotonic()
        try:
            holder["target"].close()
            outcome.append(time.monotonic() - started)
        except BaseException as error:
            outcome.append(error)
        finally:
            handled.set()

    client = Polyester(hydrate_catalogs=False)
    try:
        holder["target"] = client.orders.subscribe_sync(on_event=lambda _: None)
        client.orders.subscribe_sync(on_event=on_event, on_error=outcome.append)
        target.release(client)
        trigger.release(client)
        assert handled.wait(15), "on_event never ran"
        assert not isinstance(outcome[0], BaseException), f"close() raised {outcome[0]!r}"
        assert outcome[0] < PROMPT_SECONDS
        assert target.closed.wait(5), "the other stream was never closed"
    finally:
        client.close()
    assert target.aclose_calls == 1


def test_client_close_waits_for_a_close_scheduled_from_a_callback(monkeypatch):
    """The client's own close finishes a close a callback scheduled, and
    reports that close's failure, before the loop stops."""
    failure = RuntimeError("aclose-proof")
    released = asyncio.Event()

    class SlowClose(Stream):
        async def aclose(self) -> None:
            await released.wait()
            self.aclose_calls += 1
            raise failure

    stream = SlowClose(["first"])
    _serve(monkeypatch, stream)
    holder: dict[str, Any] = {}
    handled = threading.Event()

    def on_event(_: str) -> None:
        holder["sub"].close()
        handled.set()

    client = Polyester(hydrate_catalogs=False)
    holder["sub"] = client.orders.subscribe_sync(on_event=on_event)
    stream.release(client)
    assert handled.wait(15), "on_event never ran"
    client._loop.call_soon_threadsafe(released.set)
    with pytest.raises(RuntimeError, match="aclose-proof"):
        client.close()
    assert stream.aclose_calls == 1
    assert not client._loop_thread.is_alive()


def _refused(call) -> list[object]:
    """Run ``call`` from a client callback and return what it did."""
    outcome: list[object] = []
    handled = threading.Event()

    def on_event(_: str) -> None:
        started = time.monotonic()
        try:
            outcome.append(call())
        except BaseException as error:
            outcome.append(error)
        outcome.append(time.monotonic() - started)
        handled.set()

    return [outcome, handled, on_event]


@pytest.mark.parametrize("kind", ["call", "iterate"])
def test_a_waiting_sync_call_from_a_callback_is_refused_at_once(monkeypatch, kind):
    stream = Stream(["first"])
    _serve(monkeypatch, stream)

    async def get(self, *args, **kwargs):
        return "unreachable"

    async def iter_posts(self, *args, **kwargs):
        yield "unreachable"

    monkeypatch.setattr(AsyncOrdersService, "get", get)
    monkeypatch.setattr(AsyncChangelogService, "iter_posts", iter_posts)
    client = Polyester(hydrate_catalogs=False)

    def call() -> object:
        if kind == "call":
            return client.orders.get(order_id="1")
        return list(client.changelog.iter_posts())

    outcome, handled, on_event = _refused(call)
    try:
        client.orders.subscribe_sync(on_event=on_event, on_error=outcome.append)
        stream.release(client)
        assert handled.wait(5), f"a sync {kind} from a callback blocked the client loop"
        error, elapsed = outcome
        assert isinstance(error, PolyesterError), f"expected a refusal, got {error!r}"
        assert "client callback" in str(error)
        assert elapsed < PROMPT_SECONDS
        # The loop is still serving calls from other threads.
        assert client.orders.get(order_id="1") == "unreachable"
    finally:
        client.close()


def test_closing_the_client_from_a_callback_is_refused_at_once(monkeypatch):
    stream = Stream(["first"])
    _serve(monkeypatch, stream)
    client = Polyester(hydrate_catalogs=False)
    outcome, handled, on_event = _refused(client.close)
    try:
        client.orders.subscribe_sync(on_event=on_event, on_error=outcome.append)
        stream.release(client)
        assert handled.wait(30), "on_event never finished"
        error, elapsed = outcome
        assert isinstance(error, PolyesterError), f"expected a refusal, got {error!r}"
        assert "client callback" in str(error)
        assert elapsed < PROMPT_SECONDS
        assert client._loop_thread.is_alive(), "the refused close stopped the loop"
    finally:
        client.close()
    assert stream.aclose_calls == 1
    assert not client._loop_thread.is_alive()


def _seeds() -> list[int]:
    count = int(os.environ.get("POLYESTER_INTERLEAVING_SEEDS", "48"))
    only = os.environ.get("POLYESTER_INTERLEAVING_SEED")
    return [int(only)] if only is not None else list(range(count))


@pytest.mark.parametrize("seed", _seeds())
def test_randomized_close_interleavings_keep_the_close_contract(monkeypatch, seed):
    """Seeded schedules of closes from callbacks and from other threads.

    Randomized per seed: the number of subscriptions, how many events each has
    ready, whether the stream yields to the loop between events, which event
    triggers a close, which subscription that callback closes, close() or
    unsubscribe(), an extra close from another thread after a random delay,
    and whether the test closes each handle or leaves it to the client.
    Replay one schedule with POLYESTER_INTERLEAVING_SEED=<seed>.
    """
    rng = random.Random(seed)
    count = rng.randint(1, 4)
    streams = [
        Stream(
            [f"s{index}e{n}" for n in range(rng.randint(1, 6))], yield_between=rng.random() < 0.5
        )
        for index in range(count)
    ]
    _serve(monkeypatch, *streams)
    lock = threading.Lock()
    clock = iter(range(1_000_000))
    started: dict[int, list[int]] = {index: [] for index in range(count)}
    closed_at: dict[int, int] = {}
    in_callback_closes: list[object] = []
    handles: list[Any] = []
    plans = []
    for index in range(count):
        trigger = rng.randrange(len(streams[index].events)) if rng.random() < 0.7 else None
        plans.append((trigger, rng.randrange(count), rng.choice(["close", "unsubscribe"])))

    def close_and_record(target: int, method: str) -> None:
        getattr(handles[target], method)()
        with lock:
            closed_at.setdefault(target, next(clock))

    def make_on_event(index: int):
        trigger, target, method = plans[index]
        seen = [0]

        def on_event(_: str) -> None:
            with lock:
                started[index].append(next(clock))
            position = seen[0]
            seen[0] += 1
            # A target subscribed after this event can't be closed from it yet.
            if position != trigger or target >= len(handles):
                return
            began = time.monotonic()
            try:
                close_and_record(target, method)
                in_callback_closes.append(time.monotonic() - began)
            except BaseException as error:
                in_callback_closes.append(error)

        return on_event

    client = Polyester(hydrate_catalogs=False)
    try:
        for index in range(count):
            handles.append(
                client.orders.subscribe_sync(
                    on_event=make_on_event(index), on_error=in_callback_closes.append
                )
            )
        for index in rng.sample(range(count), count):
            streams[index].release(client)
        outside = rng.randrange(count)
        delay = rng.choice([0.0, 0.0005, 0.002, 0.01])
        closer = threading.Thread(
            target=lambda: (time.sleep(delay), close_and_record(outside, "close"))
        )
        closer.start()
        closer.join(15)
        assert not closer.is_alive(), f"seed {seed}: close from another thread hung"
        if rng.random() < 0.5:
            for index in range(count):
                close_and_record(index, "close")
    finally:
        client.close()
    assert not client._loop_thread.is_alive(), f"seed {seed}: the client did not shut down"

    for outcome in in_callback_closes:
        assert not isinstance(outcome, BaseException), f"seed {seed}: {outcome!r}"
        assert outcome < PROMPT_SECONDS, f"seed {seed}: a callback close took {outcome:.3f} s"
    for index, stream in enumerate(streams):
        assert stream.aclose_calls == 1, (
            f"seed {seed}: stream {index} closed {stream.aclose_calls}x"
        )
        if index in closed_at:
            late = [tick for tick in started[index] if tick > closed_at[index]]
            assert not late, f"seed {seed}: stream {index} delivered after close() returned"
