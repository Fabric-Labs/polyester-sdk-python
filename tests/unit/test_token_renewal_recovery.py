"""Token renewal under refusal, disconnects and random interleavings."""

from __future__ import annotations

import asyncio
import contextlib
import os
import random
import time
from collections.abc import AsyncIterator
from typing import Any

import pytest

from polyester.codecs.realtime_decode import decode_ledger_transfer_batch_bytes
from polyester.errors import PolyesterAuthError
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.realtime.resubscribe import ServerUnsubscribedError
from tests.unit.renewal_support import Action, RenewalServer, wait_until
from tests.unit.test_token_renewal import TRANSFERS_CHANNEL


@contextlib.asynccontextmanager
async def _transfers(
    server: RenewalServer, unit: float
) -> AsyncIterator[tuple[AsyncRealtimeClient, AsyncSubscription[Any], list[BaseException]]]:
    rt = server.client(renewal_unit=unit)
    sub = await rt.subscribe_proto_batch(
        TRANSFERS_CHANNEL, decode_batch=decode_ledger_transfer_batch_bytes
    )
    errors: list[BaseException] = []
    sub.set_on_error(errors.append)

    async def drain() -> None:
        async for _ in sub:
            pass

    consumer = asyncio.create_task(drain())
    try:
        yield rt, sub, errors
    finally:
        consumer.cancel()
        with contextlib.suppress(BaseException):
            await consumer
        await rt.aclose()


def _token_api_refuses_first_renewal(server: RenewalServer) -> None:
    calls = 0

    async def hook(kind: str) -> int:
        nonlocal calls
        if kind == "sub":
            calls += 1
            # The second subscription token is the first renewal.
            if calls == 2:
                return 403
        return 200

    server.token_hook = hook


def _server_refuses_first_renewal(server: RenewalServer) -> None:
    calls = 0

    async def hook(kind: str) -> Action:
        nonlocal calls
        if kind == "sub_refresh":
            calls += 1
            if calls == 1:
                return Action.REFUSE
        return Action.ANSWER

    server.command_hook = hook


def _is_token_refusal(exc: BaseException) -> bool:
    return isinstance(exc, PolyesterAuthError) and exc.status_code == 403


def _is_server_refusal(exc: BaseException) -> bool:
    return "subscription token renewal refused: centrifugo error 109" in str(exc)


@pytest.mark.parametrize(
    ("setup", "refused"),
    [
        (_token_api_refuses_first_renewal, _is_token_refusal),
        (_server_refuses_first_renewal, _is_server_refusal),
    ],
    ids=["token API refuses", "server refuses"],
)
async def test_refused_renewal_reports_then_resubscribes(setup, refused) -> None:
    # A refused renewal is reported. The server then ends the subscription at
    # expiry, the client resubscribes with a fresh token, says so through
    # ``resubscribed``, and renews on the new connection.
    unit = 0.1
    async with RenewalServer(unit=unit, sub_ttl=2) as server:
        setup(server)
        async with _transfers(server, unit) as (_rt, sub, errors):
            await wait_until(lambda: sub.resubscribed == 1 and server.sub_renewals >= 2)
            assert server.sub_expiries == 1, "once, for the refused renewal"
            assert server.accepted == 2
            assert errors and refused(errors[0]), errors
            assert len(errors) >= 2 and isinstance(errors[1], ServerUnsubscribedError)
            assert errors[1].unsubscribe_code == 2501
            assert sub.error is None


async def test_renewal_continues_after_disconnect() -> None:
    # A dropped connection reconnects with fresh tokens and renews them on the
    # new connection; nothing from the old connection reaches it.
    unit = 0.1
    async with (
        RenewalServer(unit=unit, conn_ttl=2, sub_ttl=1) as server,
        _transfers(server, unit) as (_rt, sub, _errors),
    ):
        await wait_until(lambda: server.sub_renewals >= 1)
        assert server.drop_all() == 1
        await wait_until(lambda: server.subscribes == 2)
        renewed, refreshed = server.sub_renewals, server.refreshes
        await wait_until(
            lambda: server.sub_renewals >= renewed + 2 and server.refreshes >= refreshed + 1
        )
        assert sub.resubscribed == 1
        assert server.sub_expiries + server.conn_expiries == 0
        assert server.reused + server.stale == 0


async def test_connection_renewal_counts_from_connect_reply() -> None:
    # The connection token's lifetime runs from the connect reply, not from the
    # end of setup: a slow subscription token must not push the first
    # connection renewal past the server's expiry.
    unit = 0.2
    sub_calls = 0

    async def hook(kind: str) -> int:
        nonlocal sub_calls
        if kind == "sub":
            sub_calls += 1
            # Only the setup's subscription token is slow, by more than the grace.
            if sub_calls == 1:
                await asyncio.sleep(0.15)
        return 200

    async with RenewalServer(unit=unit, conn_ttl=2, grace=0.06) as server:
        server.token_hook = hook
        async with _transfers(server, unit) as (_rt, sub, _errors):
            await asyncio.sleep(8 * unit)
            counts = (
                f"expiries={server.conn_expiries} connections={server.accepted} "
                f"renewals={server.refreshes}"
            )
            assert server.conn_expiries == 0, counts
            assert server.accepted == 1, counts
            assert server.refreshes >= 3, counts
            assert sub.resubscribed == 0


async def test_token_renewal_interleaves_with_reconnects() -> None:
    # Renewals race reconnects: token fetches and renewal answers take random
    # time and the server drops the connection at random moments, so a drop
    # lands before, during or after a renewal. Whatever the order, a healthy
    # client never lets a token expire, never sends a token twice or on a
    # connection it was not fetched for, reconnects only for the drops, and
    # stops renewing once closed. RENEWAL_SEED replays a run.
    seed = int(os.environ.get("RENEWAL_SEED", time.time_ns()))
    print(f"RENEWAL_SEED={seed}")
    rng = random.Random(seed)
    for iteration in range(8):
        iteration_seed = rng.getrandbits(64)
        try:
            await _run_interleaving(iteration_seed)
        except BaseException as exc:
            raise AssertionError(
                f"iteration {iteration} (RENEWAL_SEED={seed}, iteration seed {iteration_seed})"
            ) from exc


async def _run_interleaving(seed: int) -> None:
    unit = 0.04
    rng = random.Random(seed)
    shared = random.Random(seed ^ 0x5A5A)
    server = RenewalServer(
        unit=unit,
        # Grace covers the slowest token fetch plus the slowest answer.
        grace=3 * unit,
        conn_ttl=rng.randrange(3),
        sub_ttl=1 + rng.randrange(2),
    )

    async def token_hook(_kind: str) -> int:
        await asyncio.sleep(shared.uniform(0, unit))
        return 200

    async def command_hook(_kind: str) -> Action:
        await asyncio.sleep(shared.uniform(0, unit / 2))
        return Action.ANSWER

    server.token_hook = token_hook
    server.command_hook = command_hook
    config = f"conn_ttl={server.conn_ttl} sub_ttl={server.sub_ttl}"
    async with server:
        rt = server.client(renewal_unit=unit)
        sub = await rt.subscribe_proto_batch(
            TRANSFERS_CHANNEL, decode_batch=decode_ledger_transfer_batch_bytes
        )
        try:
            drops = 1 + rng.randrange(2)
            for drop in range(drops):
                await asyncio.sleep(rng.uniform(0, 4 * unit))
                assert server.drop_all() == 1, f"drop {drop}"
                await wait_until(lambda drop=drop: server.subscribes == drop + 2)
            # Each renewal waits a TTL plus the injected delays; two more of
            # each show renewal running on the last connection.
            renewed, refreshed = server.sub_renewals, server.refreshes
            await wait_until(
                lambda: (
                    server.sub_renewals >= renewed + 2
                    and (not server.conn_ttl or server.refreshes >= refreshed + 2)
                )
            )
            assert server.sub_expiries + server.conn_expiries == 0, config
            assert server.reused + server.stale == 0, "used or stale tokens"
            assert server.accepted == drops + 1, f"{server.accepted} connections, {drops} drops"
            assert sub.resubscribed == drops
            assert sub.error is None
        finally:
            await sub.aclose()
        settled = server.sub_tokens + server.conn_tokens
        await asyncio.sleep(4 * unit)
        assert server.sub_tokens + server.conn_tokens == settled, "token fetched after close"
        await rt.aclose()
