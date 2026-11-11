"""Independent credentials for one API key must never share a signature.

The server rejects a repeated (API key, signature) pair within its freshness
window. Signatures are deterministic, so two identical requests signed for the
same key at the same millisecond collide unless every credentials object for
that key draws timestamps from one allocator.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
import os
import random
import threading
import types
import uuid
import weakref

import pytest

import polyester.auth as auth_module
from polyester.auth import (
    MAX_SIGNING_FUTURE_SKEW_MS,
    ApiKeyCredentials,
    load_api_key_credentials,
    sign_request,
    sign_request_async,
)

# An obviously fake Ed25519 seed (0xa0, 0xa1, ...).
SYNTHETIC_SEED = bytes(range(0xA0, 0xC0))
FROZEN_MS = 1_800_000_000_000
URL = "https://api.example.test/orders.v1.OrdersService/CreateOrder"


class FakeClock:
    """Thread-safe wall clock in milliseconds, driven by the test."""

    def __init__(self, now_ms: int) -> None:
        self._now_ms = now_ms
        self._lock = threading.Lock()

    def time_ns(self) -> int:
        with self._lock:
            return self._now_ms * 1_000_000

    def advance(self, ms: int) -> None:
        with self._lock:
            self._now_ms += ms

    @property
    def now_ms(self) -> int:
        with self._lock:
            return self._now_ms


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    fake = FakeClock(FROZEN_MS)
    monkeypatch.setattr(auth_module, "time", types.SimpleNamespace(time_ns=fake.time_ns))
    return fake


def fresh_key_id() -> str:
    return f"key_shared_{uuid.uuid4().hex}"


def independent_credentials(key_id: str, count: int) -> list[ApiKeyCredentials]:
    loaded: list[ApiKeyCredentials] = []
    for index in range(count):
        if index % 2:
            creds = load_api_key_credentials(
                api_key_id=key_id, api_private_key=SYNTHETIC_SEED.hex(), from_env=False
            )
            assert creds is not None
        else:
            creds = ApiKeyCredentials(key_id=key_id, private_key=SYNTHETIC_SEED)
        loaded.append(creds)
    return loaded


def test_independent_credentials_never_reuse_a_signature_in_one_millisecond(
    clock: FakeClock,
) -> None:
    first, second = independent_credentials(fresh_key_id(), 2)
    a = sign_request(first, method="POST", url=URL, body=b"{}")
    b = sign_request(second, method="POST", url=URL, body=b"{}")
    assert a["X-API-TIMESTAMP"] != b["X-API-TIMESTAMP"]
    assert a["X-API-SIGNATURE"] != b["X-API-SIGNATURE"]


async def test_independent_credentials_never_reuse_a_signature_async(clock: FakeClock) -> None:
    first, second = independent_credentials(fresh_key_id(), 2)
    signed = await asyncio.gather(
        *(
            sign_request_async(creds, method="POST", url=URL, body=b"{}")
            for creds in (first, second, first, second)
        )
    )
    assert len({headers["X-API-SIGNATURE"] for headers in signed}) == 4
    sync_signed = sign_request(second, method="POST", url=URL, body=b"{}")
    assert sync_signed["X-API-SIGNATURE"] not in {h["X-API-SIGNATURE"] for h in signed}


def test_backpressured_clients_on_separate_event_loops_share_one_key(clock: FakeClock) -> None:
    """Each sync client runs its own event loop; a shared key must not tie them to one loop."""
    key_id = fresh_key_id()
    creds = independent_credentials(key_id, 2)
    # Fill the lead so every async caller has to wait for the clock.
    for _ in range(MAX_SIGNING_FUTURE_SKEW_MS + 1):
        sign_request(creds[0], method="GET", url=URL, body=b"")

    results: list[dict[str, str]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    started = threading.Barrier(3)

    def worker(index: int) -> None:
        async def run() -> None:
            signed = await asyncio.gather(
                *(
                    sign_request_async(creds[index], method="POST", url=URL, body=b"{}")
                    for _ in range(3)
                )
            )
            with lock:
                results.extend(signed)

        started.wait()
        try:
            asyncio.run(run())
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    started.wait()
    for _ in range(200):
        clock.advance(1)
        threading.Event().wait(0.002)
        if len(results) == 6:
            break
    for thread in threads:
        thread.join(timeout=15)
    assert not errors, errors
    assert len(results) == 6
    assert len({headers["X-API-SIGNATURE"] for headers in results}) == 6


def test_closed_event_loop_is_not_retained_after_backpressure(clock: FakeClock) -> None:
    """The process-wide allocator must not keep a finished event loop alive."""
    creds = ApiKeyCredentials(key_id=fresh_key_id(), private_key=SYNTHETIC_SEED)
    for _ in range(MAX_SIGNING_FUTURE_SKEW_MS + 1):
        sign_request(creds, method="GET", url=URL, body=b"")

    async def contend(signer: ApiKeyCredentials) -> list[dict[str, str]]:
        # Two waiters contend for the loop's lock while capacity is exhausted.
        tasks = [
            asyncio.ensure_future(sign_request_async(signer, method="POST", url=URL, body=b"{}"))
            for _ in range(3)
        ]
        await asyncio.sleep(0.01)
        # A cancelled waiter must release the gate too.
        tasks[2].cancel()
        clock.advance(5)
        signed = await asyncio.gather(*tasks[:2])
        with contextlib.suppress(asyncio.CancelledError):
            await tasks[2]
        return signed

    loop = asyncio.new_event_loop()
    try:
        signed = loop.run_until_complete(contend(creds))
    finally:
        loop.close()
    assert len({headers["X-API-SIGNATURE"] for headers in signed}) == 2
    loop_ref = weakref.ref(loop)
    del loop, creds
    gc.collect()
    assert loop_ref() is None, "a closed event loop is still referenced by the signing allocator"


def _seed_range() -> range:
    if replay := os.getenv("POLYESTER_SIGNING_SEED"):
        return range(int(replay), int(replay) + 1)
    return range(int(os.getenv("POLYESTER_SIGNING_SEEDS", "64")))


@pytest.mark.parametrize("seed", _seed_range())
def test_seeded_interleavings_of_independent_credentials(clock: FakeClock, seed: int) -> None:
    """Seeded schedules mixing sync threads and async loops across credentials objects.

    Randomized per seed: the number of credentials objects, sync or async
    workers, each step's credentials, concurrent fan-out, yields, and clock
    advances. Replay one schedule with POLYESTER_SIGNING_SEED=<seed>; widen the
    sweep with POLYESTER_SIGNING_SEEDS=<count>.
    """
    rng = random.Random(seed)
    creds = independent_credentials(fresh_key_id(), 2 + rng.randrange(4))
    workers = []
    for _ in range(2 + rng.randrange(5)):
        steps = [
            (
                rng.randrange(len(creds)),  # credentials object
                1 + rng.randrange(4),  # concurrent signatures in this step
                rng.randrange(3),  # 0: none, 1: yield, 2: advance the clock 1 ms
            )
            for _ in range(5 + rng.randrange(30))
        ]
        workers.append((rng.random() < 0.5, steps))

    start_ms = clock.now_ms
    results: list[dict[str, str]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()
    barrier = threading.Barrier(len(workers))

    def run_sync(steps: list[tuple[int, int, int]]) -> None:
        for index, fan_out, action in steps:
            if action == 1:
                threading.Event().wait(0)
            elif action == 2:
                clock.advance(1)
            signed = [
                sign_request(creds[index], method="POST", url=URL, body=b"{}")
                for _ in range(fan_out)
            ]
            with lock:
                results.extend(signed)

    async def run_async(steps: list[tuple[int, int, int]]) -> None:
        for index, fan_out, action in steps:
            if action == 1:
                await asyncio.sleep(0)
            elif action == 2:
                clock.advance(1)
            signed = await asyncio.gather(
                *(
                    sign_request_async(creds[index], method="POST", url=URL, body=b"{}")
                    for _ in range(fan_out)
                )
            )
            with lock:
                results.extend(signed)

    def worker(is_async: bool, steps: list[tuple[int, int, int]]) -> None:
        barrier.wait()
        try:
            if is_async:
                asyncio.run(run_async(steps))
            else:
                run_sync(steps)
        except Exception as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=item) for item in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, f"seed {seed}: {errors!r}"
    expected = sum(fan_out for _, steps in workers for _, fan_out, _ in steps)
    assert len(results) == expected
    timestamps = [int(headers["X-API-TIMESTAMP"]) for headers in results]
    signatures = {headers["X-API-SIGNATURE"] for headers in results}
    assert len(signatures) == expected, (
        f"seed {seed}: {len(creds)} credentials, {len(workers)} workers: "
        f"{expected} signatures, {len(signatures)} distinct"
    )
    assert len(set(timestamps)) == expected
    assert min(timestamps) >= start_ms
    assert max(timestamps) <= clock.now_ms + MAX_SIGNING_FUTURE_SKEW_MS
