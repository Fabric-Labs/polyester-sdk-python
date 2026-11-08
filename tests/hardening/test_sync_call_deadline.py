"""A sync client call ends only when its async call has ended.

The sync client adds no deadline of its own: the configured transport timeout
and each method's own ``timeout`` bound a call, and a mutation cut short by
them raises an error whose outcome is unknown. A caller interrupted while it
waits (for example by Ctrl-C) gets its interruption only once the call has
stopped, so nothing is sent on its behalf afterwards.

The interleaving test draws the interruption time and the server's reply time
from one seed. Set ``POLYESTER_INTERLEAVING_SEED`` to replay a failing run and
``POLYESTER_INTERLEAVINGS`` to run more schedules.
"""

from __future__ import annotations

import asyncio
import os
import random
import signal
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from polyester import Polyester
from polyester.errors import PolyesterError, PolyesterTimeoutError, mutation_outcome_unknown
from polyester.models.order_key import OrderId
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

CANCEL_PATH = "/orders.v1.OrdersService/CancelOrder"
UNAVAILABLE = HttpScript.json(503, {"code": "unavailable", "message": "catching up"})


def _interleavings() -> int:
    return int(os.environ.get("POLYESTER_INTERLEAVINGS", "40"))


def _seed() -> int:
    raw = os.environ.get("POLYESTER_INTERLEAVING_SEED")
    return int(raw) if raw else random.SystemRandom().randrange(2**32)


class _ThreadedApi:
    """A local API on its own thread and loop that records when calls arrive."""

    def __init__(self) -> None:
        self.arrivals: list[float] = []
        self.reply_after: float | None = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._server = asyncio.run_coroutine_threadsafe(
            MockHttpServer.spawn(self._handle), self._loop
        ).result(timeout=5)
        self.base_url = self._server.base_url

    async def _handle(self, req: ParsedRequest) -> HttpScript:
        if req.path != CANCEL_PATH:
            return HttpScript.not_found()
        self.arrivals.append(time.monotonic())
        if self.reply_after is None:
            return HttpScript.never_respond()
        await asyncio.sleep(self.reply_after)
        return UNAVAILABLE

    def close(self) -> None:
        asyncio.run_coroutine_threadsafe(self._server.aclose(), self._loop).result(timeout=5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        self._loop.close()


@contextmanager
def _sync_client(*, timeout: float = 30.0) -> Iterator[tuple[Polyester, _ThreadedApi]]:
    api = _ThreadedApi()
    creds = make_test_credentials()
    client = Polyester(
        api_url=api.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        timeout=timeout,
    )
    try:
        yield client, api
    finally:
        client.close()
        api.close()


def _pending_calls(client: Polyester) -> int:
    """Tasks still running on the client loop, other than this probe."""

    async def count() -> int:
        current = asyncio.current_task()
        return sum(1 for task in asyncio.all_tasks() if task is not current)

    return asyncio.run_coroutine_threadsafe(count(), client._loop).result(timeout=5)


class _CallerInterrupted(BaseException):
    """Stands in for a KeyboardInterrupt delivered while the caller waits."""


@contextmanager
def _interrupt_caller_after(delay: float) -> Iterator[None]:
    """Deliver a signal to this (main) thread after ``delay`` seconds while armed."""
    armed = threading.Event()
    armed.set()

    def handler(_signum: int, _frame: Any) -> None:
        if armed.is_set():
            armed.clear()
            raise _CallerInterrupted

    previous = signal.signal(signal.SIGUSR1, handler)
    main = threading.main_thread().ident
    assert main is not None
    timer = threading.Timer(delay, signal.pthread_kill, args=(main, signal.SIGUSR1))
    timer.start()
    try:
        yield
    finally:
        armed.clear()
        timer.cancel()
        timer.join()
        signal.signal(signal.SIGUSR1, previous)


pytestmark = pytest.mark.skipif(
    threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGUSR1"),
    reason="needs POSIX signals delivered to the main thread",
)


def test_sync_mutation_past_the_configured_timeout_has_an_unknown_outcome() -> None:
    with _sync_client(timeout=0.5) as (client, api):
        started = time.monotonic()
        with pytest.raises(PolyesterTimeoutError) as caught:
            client.orders.cancel(key=OrderId(11))
        elapsed = time.monotonic() - started
        assert len(api.arrivals) == 1
        assert mutation_outcome_unknown(caught.value)
        assert 0.5 <= elapsed < 5.0
        assert _pending_calls(client) == 0


def test_sync_call_on_a_closed_client_fails_at_once() -> None:
    api = _ThreadedApi()
    try:
        creds = make_test_credentials()
        client = Polyester(
            api_url=api.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            hydrate_catalogs=False,
        )
        client.close()
        started = time.monotonic()
        with pytest.raises(PolyesterError, match="closed"):
            client.orders.cancel(key=OrderId(11))
        assert time.monotonic() - started < 2.0
        assert api.arrivals == []
    finally:
        api.close()


def _interrupted_schedule(seed: int) -> None:
    rng = random.Random(seed)
    interrupt_after = rng.uniform(0.0, 0.06)
    reply_after = None if rng.random() < 0.5 else rng.uniform(0.0, 0.08)
    with _sync_client() as (client, api):
        api.reply_after = reply_after
        try:
            with _interrupt_caller_after(interrupt_after):
                client.orders.cancel(key=OrderId(11))
        except (_CallerInterrupted, PolyesterError):
            pass
        pending = _pending_calls(client)
        time.sleep(0.15)
        detail = (
            f"seed={seed} interrupt_after={interrupt_after:.4f} reply_after={reply_after}: "
            "replay with POLYESTER_INTERLEAVING_SEED"
        )
        assert pending == 0, f"call still running after the caller returned ({detail})"
        assert len(api.arrivals) <= 1, f"request sent again after the caller returned ({detail})"


def test_interrupted_sync_mutation_stops_before_the_caller_resumes() -> None:
    base = _seed()
    for offset in range(_interleavings()):
        _interrupted_schedule((base + offset) % 2**32)
