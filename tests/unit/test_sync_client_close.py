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
