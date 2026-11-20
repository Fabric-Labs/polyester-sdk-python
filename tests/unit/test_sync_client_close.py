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


def test_subscribe_while_the_loop_stops_is_refused_and_queues_nothing(
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
        # Only the subscriber's own scheduling counts: the client's other threads
        # may still hand the loop a result while it stops.
        if threading.current_thread().name == "subscriber":
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
        subscriber = threading.Thread(target=subscribe_sync, name="subscriber", daemon=True)
        subscriber.start()
        # Refused at once, with the loop still held in its final iteration.
        subscriber.join(5)
        assert not subscriber.is_alive(), "subscribe_sync waited on a closing client"
        assert not queued.is_set(), "subscribe_sync queued work on a closing client"
        proceed.set()
        closer.join(10)
        assert not closer.is_alive()
        gc.collect()
    assert len(outcome) == 1
    assert issubclass(outcome[0][0], PolyesterRealtimeError), outcome
    assert "closed" in outcome[0][1]
    assert loop.is_closed()
    assert [str(w.message) for w in caught] == []
    assert _asyncio_errors(caplog) == []


def _outcome_within(call, seconds: float) -> str:
    """Run ``call`` on another thread: its error type and message, "ok", or "waiting"."""
    outcome: list[str] = []

    def run() -> None:
        try:
            call()
            outcome.append("ok")
        except BaseException as error:
            outcome.append(f"{type(error).__name__}: {error}")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    return outcome[0] if outcome else "waiting"


def test_calls_after_a_timed_out_close_are_refused(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("polyester.client._SHUTDOWN_WAIT_SECONDS", 0.2)
    monkeypatch.setattr("polyester.client._LOOP_JOIN_SECONDS", 0.2)
    reached: list[str] = []

    async def subscribe(self, **kwargs):
        reached.append("subscribe")
        raise AssertionError("setup must not start on a closed client")

    monkeypatch.setattr(AsyncOrdersService, "subscribe", subscribe)
    client = Polyester(hydrate_catalogs=False)

    async def get_time():
        reached.append("get_time")

    client._client.get_time = get_time  # type: ignore[method-assign]
    aclose = client._client.aclose
    shutting_down = threading.Event()
    finish_shutdown = threading.Event()

    async def held_aclose() -> None:
        # The loop runs again from here: the loop thread is finishing the shutdown.
        shutting_down.set()
        while not finish_shutdown.is_set():
            await asyncio.sleep(0.01)
        await aclose()

    client._client.aclose = held_aclose  # type: ignore[method-assign]
    blocking = threading.Event()
    release = threading.Event()

    def block() -> None:
        blocking.set()
        release.wait(60)

    client._loop.call_soon_threadsafe(block)
    assert blocking.wait(5), "the blocking callback never ran"
    client.close()
    assert client._loop_thread.is_alive(), "the close did not time out"
    try:
        # The loop is still held by the callback.
        assert _outcome_within(client.get_time, 2) == "PolyesterError: the client is closed"
        release.set()
        assert shutting_down.wait(5), "the loop thread never resumed the shutdown"
        assert client._loop.is_running()
        # The loop runs again, finishing the shutdown: still nothing is admitted.
        assert _outcome_within(client.get_time, 2) == "PolyesterError: the client is closed"
        assert (
            _outcome_within(lambda: client.orders.subscribe_sync(on_event=lambda _: None), 2)
            == "PolyesterRealtimeError: the client is closed"
        )
        assert reached == []
    finally:
        release.set()
        finish_shutdown.set()
        client._loop_thread.join(5)
    assert not client._loop_thread.is_alive()
    assert client._loop.is_closed()
    assert _asyncio_errors(caplog) == []


def test_a_call_queued_in_the_loops_final_iteration_leaves_no_coroutine() -> None:
    # Below the client's admission: a call already admitted when the loop stops
    # is created on the loop, so the start the loop never runs leaves nothing.
    from polyester._sync_bridge import run_on_loop

    loop = asyncio.new_event_loop()
    stopping = threading.Event()
    queued = threading.Event()
    proceed = threading.Event()
    stop = loop.stop
    call_soon_threadsafe = loop.call_soon_threadsafe

    def stop_then_hold() -> None:
        stop()
        stopping.set()
        proceed.wait(5)

    def recording_call_soon_threadsafe(callback, *args, **kwargs):
        handle = call_soon_threadsafe(callback, *args, **kwargs)
        if stopping.is_set():
            queued.set()
        return handle

    def run() -> None:
        try:
            loop.run_forever()
        finally:
            loop.close()

    thread = threading.Thread(target=run, daemon=True)
    started = threading.Event()
    loop.call_soon(started.set)
    thread.start()
    assert started.wait(5)
    reached: list[str] = []

    async def call() -> None:
        reached.append("call")

    outcome: list[str] = []

    def caller() -> None:
        try:
            run_on_loop(loop, call)
        except BaseException as error:
            outcome.append(f"{type(error).__name__}: {error}")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        loop.call_soon_threadsafe(stop_then_hold)
        assert stopping.wait(5)
        loop.call_soon_threadsafe = recording_call_soon_threadsafe  # type: ignore[method-assign]
        waiter = threading.Thread(target=caller, daemon=True)
        waiter.start()
        assert queued.wait(5), "the call was never queued"
        proceed.set()
        thread.join(5)
        waiter.join(5)
        gc.collect()
    assert not waiter.is_alive()
    assert outcome == ["PolyesterError: the client closed during the call"]
    assert reached == []
    assert loop.is_closed()
    assert [str(w.message) for w in caught] == []


def _pause_before_finishing(client: Polyester) -> tuple[threading.Event, threading.Event]:
    """Hold the loop thread between ``run_forever`` returning and its finishing.

    Returns ``(paused, resume)``: ``paused`` is set once the loop has stopped
    and not yet finished; setting ``resume`` lets it finish and close.
    """
    paused = threading.Event()
    resume = threading.Event()
    finish = client._finish_loop

    def paused_finish() -> None:
        paused.set()
        resume.wait(30)
        finish()

    client._finish_loop = paused_finish  # type: ignore[method-assign]
    return paused, resume


def _record_scheduling_from(loop: asyncio.AbstractEventLoop, name: str) -> threading.Event:
    """Set once the thread called ``name`` schedules work on ``loop``."""
    scheduled = threading.Event()
    call_soon_threadsafe = loop.call_soon_threadsafe

    def recording(callback, *args, **kwargs):
        handle = call_soon_threadsafe(callback, *args, **kwargs)
        if threading.current_thread().name == name:
            scheduled.set()
        return handle

    loop.call_soon_threadsafe = recording  # type: ignore[method-assign]
    return scheduled


def _hold_loop(client: Polyester) -> threading.Event:
    blocking = threading.Event()
    release = threading.Event()

    def block() -> None:
        blocking.set()
        release.wait(60)

    client._loop.call_soon_threadsafe(block)
    assert blocking.wait(5), "the blocking callback never ran"
    return release


@pytest.mark.parametrize("kind", ["read", "write"])
def test_a_call_queued_before_a_timed_out_close_never_starts_after_it_failed(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from polyester.errors import mutation_outcome_unknown
    from polyester.models import OrderId

    monkeypatch.setattr("polyester.client._SHUTDOWN_WAIT_SECONDS", 0.2)
    monkeypatch.setattr("polyester.client._LOOP_JOIN_SECONDS", 0.2)
    client = Polyester(hydrate_catalogs=False)
    sent: list[str] = []

    async def get_time():
        sent.append("get_time")

    async def cancel(*args, **kwargs):
        sent.append("cancel")

    client._client.get_time = get_time  # type: ignore[method-assign]
    client._client.orders.cancel = cancel  # type: ignore[method-assign]
    paused, resume = _pause_before_finishing(client)
    release = _hold_loop(client)
    queued = _record_scheduling_from(client._loop, "caller")
    outcome: list[BaseException] = []

    def caller() -> None:
        try:
            if kind == "read":
                client.get_time()
            else:
                client.orders.cancel(key=OrderId(11))
        except BaseException as error:
            outcome.append(error)

    waiter = threading.Thread(target=caller, name="caller", daemon=True)
    waiter.start()
    try:
        assert queued.wait(5), "the call was never queued"
        client.close()  # times out: the callback still holds the loop
        release.set()
        assert paused.wait(5), "the loop never stopped"
        # Stopped, not yet finished: the caller is told now that the call failed.
        waiter.join(5)
        assert not waiter.is_alive(), "the caller kept waiting on a stopped loop"
    finally:
        release.set()
        resume.set()
    client._loop_thread.join(10)
    assert not client._loop_thread.is_alive()
    assert len(outcome) == 1
    error = outcome[0]
    assert isinstance(error, PolyesterError)
    assert "closed" in str(error)
    # Told it failed, the call never started: its failure is definite.
    assert sent == []
    assert not mutation_outcome_unknown(error)


def test_a_write_in_flight_when_the_loop_stops_has_an_unknown_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polyester.errors import mutation_outcome_unknown
    from polyester.models import OrderId

    client = Polyester(hydrate_catalogs=False)
    started = threading.Event()

    async def cancel(*args, **kwargs):
        # Sent, and waiting for its answer when the client closes.
        started.set()
        await asyncio.Event().wait()

    client._client.orders.cancel = cancel  # type: ignore[method-assign]
    paused, resume = _pause_before_finishing(client)
    outcome: list[BaseException] = []

    def caller() -> None:
        try:
            client.orders.cancel(key=OrderId(11))
        except BaseException as error:
            outcome.append(error)

    waiter = threading.Thread(target=caller, name="caller", daemon=True)
    waiter.start()
    try:
        assert started.wait(5), "the write never started"
        closer = threading.Thread(target=client.close, daemon=True)
        closer.start()
        assert paused.wait(10), "the loop never stopped"
        # The write started: its caller must not be told yet that it failed.
        time.sleep(3 * 0.25)  # three of the caller's polls of the stopped loop
        assert waiter.is_alive(), f"the caller returned while its write was in flight: {outcome}"
    finally:
        resume.set()
    waiter.join(10)
    closer.join(10)
    assert not waiter.is_alive()
    assert len(outcome) == 1
    error = outcome[0]
    assert isinstance(error, PolyesterError)
    assert mutation_outcome_unknown(error), repr(error)
    assert client._loop.is_closed()


class _Interrupted(BaseException):
    """Stands in for a KeyboardInterrupt delivered to the caller."""


def test_a_caller_interrupted_right_after_queueing_its_call_never_sends_it() -> None:
    from polyester.models import OrderId

    client = Polyester(hydrate_catalogs=False)
    sent: list[str] = []

    async def cancel(*args, **kwargs):
        sent.append("cancel")

    client._client.orders.cancel = cancel  # type: ignore[method-assign]
    # The loop is held, so the queued start cannot run before the interruption.
    release = _hold_loop(client)
    loop = client._loop
    call_soon_threadsafe = loop.call_soon_threadsafe

    def queue_then_interrupt(callback, *args, **kwargs):
        handle = call_soon_threadsafe(callback, *args, **kwargs)
        if threading.current_thread().name == "caller":
            # Delivered after the call is queued, before the submission returns.
            raise _Interrupted
        return handle

    loop.call_soon_threadsafe = queue_then_interrupt  # type: ignore[method-assign]
    outcome: list[str] = []

    def caller() -> None:
        try:
            client.orders.cancel(key=OrderId(11))
        except BaseException as error:
            outcome.append(type(error).__name__)

    waiter = threading.Thread(target=caller, name="caller", daemon=True)
    waiter.start()
    waiter.join(5)
    try:
        assert not waiter.is_alive()
        assert outcome == ["_Interrupted"]
    finally:
        loop.call_soon_threadsafe = call_soon_threadsafe  # type: ignore[method-assign]
        release.set()
    # Let the loop run everything queued before this (a start, then its task's
    # first step, each a turn of the loop) before closing: the write never ran.
    for _ in range(3):
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0), loop).result(5)
    client.close()
    assert sent == []
