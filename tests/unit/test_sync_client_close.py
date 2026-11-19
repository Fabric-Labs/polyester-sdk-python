"""The sync client's ``close()`` releases its event loop and is idempotent.

``Polyester`` runs a private event loop on its own thread. ``close()`` stops
that loop and closes it, so the loop's selector and self-pipe descriptors are
released, and a second ``close()`` (for example an explicit one inside a
``with`` block) returns at once without scheduling work on the stopped loop.
"""

from __future__ import annotations

import asyncio
import gc
import os
import sys
import threading
import time
import warnings

import pytest

from polyester import AsyncPolyester, Polyester
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV
from polyester.errors import PolyesterError, PolyesterRealtimeError
from polyester.services.orders import AsyncOrdersService

# A repeated close does nothing, so it must return far inside the 10 s wait a
# close on a stopped loop used to take.
PROMPT_SECONDS = 1.0


@pytest.fixture(autouse=True)
def _no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)


def _open_fds() -> int:
    return len(os.listdir("/proc/self/fd"))


def test_close_closes_the_client_loop() -> None:
    client = Polyester(hydrate_catalogs=False)
    client.close()
    assert not client._loop_thread.is_alive()
    assert client._loop.is_closed()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="counts /proc/self/fd")
def test_repeated_create_and_close_returns_the_descriptor_count() -> None:
    # One cycle first, so lazily imported modules and caches are in place.
    Polyester(hydrate_catalogs=False).close()
    gc.collect()
    before = _open_fds()
    # Keep every client alive: garbage collection must not be what frees the loops.
    clients = []
    for _ in range(20):
        client = Polyester(hydrate_catalogs=False)
        client.close()
        clients.append(client)
    after = _open_fds()
    assert after <= before, f"{after - before} descriptors left open after 20 cycles"
    assert all(client._loop.is_closed() for client in clients)


def _close_again_promptly(client: Polyester) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        started = time.monotonic()
        client.close()
        elapsed = time.monotonic() - started
        # An abandoned coroutine warns when it is collected.
        gc.collect()
    assert elapsed < PROMPT_SECONDS, f"second close() took {elapsed:.3f} s"
    assert [str(w.message) for w in caught] == []


def test_second_close_returns_at_once_without_a_warning() -> None:
    client = Polyester(hydrate_catalogs=False)
    client.close()
    _close_again_promptly(client)
    assert client._loop.is_closed()


def test_explicit_close_inside_with_block_is_not_repeated() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        started = time.monotonic()
        with Polyester(hydrate_catalogs=False) as client:
            client.close()
        elapsed = time.monotonic() - started
        gc.collect()
    assert elapsed < PROMPT_SECONDS, f"close() then __exit__ took {elapsed:.3f} s"
    assert [str(w.message) for w in caught] == []
    assert client._loop.is_closed()


def test_concurrent_closes_all_return_and_close_the_loop_once() -> None:
    client = Polyester(hydrate_catalogs=False)
    aclose_calls = 0
    original = client._client.aclose

    async def counting_aclose() -> None:
        nonlocal aclose_calls
        aclose_calls += 1
        await original()

    client._client.aclose = counting_aclose  # type: ignore[method-assign]
    start = threading.Barrier(4)
    errors: list[BaseException] = []

    def close() -> None:
        try:
            start.wait(5)
            client.close()
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=close, daemon=True) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)
    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert aclose_calls == 1
    assert client._loop.is_closed()


def test_calls_after_close_fail_as_closed() -> None:
    client = Polyester(hydrate_catalogs=False)
    client.close()
    with pytest.raises(PolyesterError, match="closed"):
        client.get_time()
    with pytest.raises(PolyesterRealtimeError, match="closed"):
        client.orders.subscribe_sync(on_event=lambda _: None)


def test_subscription_closed_with_the_client_closes_again_quietly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = threading.Event()

    class Stream:
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield None

        async def aclose(self) -> None:
            closed.set()

    async def subscribe(self, **kwargs):
        return Stream()

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    handle = client.orders.subscribe_sync(on_event=lambda _: None)
    client.close()
    assert closed.is_set()
    started = time.monotonic()
    handle.close()
    assert time.monotonic() - started < PROMPT_SECONDS


def test_failed_start_up_closes_the_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    loops: list[asyncio.AbstractEventLoop] = []
    new_event_loop = asyncio.new_event_loop

    def recording_new_event_loop() -> asyncio.AbstractEventLoop:
        loop = new_event_loop()
        loops.append(loop)
        return loop

    def fail(self, **kwargs) -> None:
        raise PolyesterError("catalogs unavailable")

    monkeypatch.setattr("polyester.client.asyncio.new_event_loop", recording_new_event_loop)
    monkeypatch.setattr(AsyncPolyester, "__init__", fail)
    with pytest.raises(PolyesterError, match="catalogs unavailable"):
        Polyester(hydrate_catalogs=False)
    assert len(loops) == 1
    assert loops[0].is_closed()


def _asyncio_errors(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "asyncio" and r.levelno >= 40]


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="counts /proc/self/fd")
def test_loop_closes_when_its_thread_outlives_the_close_wait(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Short waits, so the close gives up on a loop a callback is blocking.
    monkeypatch.setattr("polyester.client._SHUTDOWN_WAIT_SECONDS", 0.2, raising=False)
    monkeypatch.setattr("polyester.client._LOOP_JOIN_SECONDS", 0.2, raising=False)
    Polyester(hydrate_catalogs=False).close()
    gc.collect()
    before = _open_fds()
    client = Polyester(hydrate_catalogs=False)
    shut_down = threading.Event()
    aclose = client._client.aclose

    async def recording_aclose() -> None:
        await aclose()
        shut_down.set()

    client._client.aclose = recording_aclose  # type: ignore[method-assign]
    blocking = threading.Event()
    release = threading.Event()

    def block() -> None:
        blocking.set()
        release.wait(60)

    client._loop.call_soon_threadsafe(block)
    assert blocking.wait(5), "the blocking callback never ran"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client.close()
        # The close gave up waiting: the callback still holds the loop.
        assert client._loop_thread.is_alive()
        started = time.monotonic()
        client.close()
        assert time.monotonic() - started < PROMPT_SECONDS
        release.set()
        client._loop_thread.join(5)
        assert not client._loop_thread.is_alive()
        gc.collect()
    # The loop thread finished the shutdown the close started, then closed the loop.
    assert shut_down.is_set(), "the client was never shut down"
    assert client._loop.is_closed()
    assert _open_fds() <= before
    assert [str(w.message) for w in caught] == []
    assert _asyncio_errors(caplog) == []


def test_subscribe_queued_while_the_loop_stops_leaves_nothing_behind(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def subscribe(self, **kwargs):
        raise AssertionError("setup must not start on a closing client")

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)
    loop = client._loop
    stopping = threading.Event()
    queued = threading.Event()
    proceed = threading.Event()
    stop = loop.stop
    call_soon_threadsafe = loop.call_soon_threadsafe

    def stop_then_hold() -> None:
        # The loop is in its final iteration from here: still running, stopping.
        stop()
        stopping.set()
        proceed.wait(5)

    def recording_call_soon_threadsafe(callback, *args, **kwargs):
        handle = call_soon_threadsafe(callback, *args, **kwargs)
        if stopping.is_set():
            queued.set()
        return handle

    loop.stop = stop_then_hold  # type: ignore[method-assign]
    loop.call_soon_threadsafe = recording_call_soon_threadsafe  # type: ignore[method-assign]
    # Keep no exception object: its traceback would keep an abandoned coroutine alive.
    outcome: list[tuple[type[BaseException], str]] = []

    def subscribe_sync() -> None:
        try:
            client.orders.subscribe_sync(on_event=lambda _: None)
        except BaseException as error:
            outcome.append((type(error), str(error)))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        closer = threading.Thread(target=client.close, daemon=True)
        closer.start()
        assert stopping.wait(5), "the loop never stopped"
        subscriber = threading.Thread(target=subscribe_sync, daemon=True)
        subscriber.start()
        assert queued.wait(5), "subscribe_sync never queued its setup"
        proceed.set()
        closer.join(10)
        subscriber.join(10)
        assert not closer.is_alive()
        assert not subscriber.is_alive()
        gc.collect()
    assert len(outcome) == 1
    assert issubclass(outcome[0][0], PolyesterRealtimeError), outcome
    assert "closed" in outcome[0][1]
    assert loop.is_closed()
    assert [str(w.message) for w in caught] == []
    assert _asyncio_errors(caplog) == []
