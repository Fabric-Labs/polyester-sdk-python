"""Live private-channel realtime coverage (auth + trading/ledger streams)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from polyester import AsyncPolyester
from tests.helpers import live_client_kwargs_from_env
from tests.integration.support import call_optional

SubscribeFn = Callable[[AsyncPolyester], Awaitable[object]]


async def _with_fresh_client(
    subscribe: SubscribeFn,
    *,
    label: str,
    account_required: bool = True,
) -> None:
    kwargs = live_client_kwargs_from_env(hydrate_catalogs=False)
    assert kwargs is not None
    client = AsyncPolyester(**kwargs)
    if account_required and not client.default_account_id:
        await client.aclose()
        pytest.skip(f"POLYESTER_ACCOUNT_ID required for {label}")
    try:
        subscription = await call_optional(subscribe(client), label=label)
        try:
            try:
                await asyncio.wait_for(subscription.__anext__(), timeout=5)  # type: ignore[attr-defined]
            except StopAsyncIteration:
                pytest.skip(f"{label} closed without publications")
            except TimeoutError:
                # Subscribe + auth token path succeeded; no activity on the channel yet.
                pass
        finally:
            await subscription.aclose()  # type: ignore[attr-defined]
            await asyncio.sleep(0.1)
    finally:
        await client.aclose()


@pytest.mark.integration
@pytest.mark.realtime
@pytest.mark.optional
@pytest.mark.parametrize(
    ("label", "subscribe"),
    [
        ("api_keys.subscribe", lambda c: c.api_keys.subscribe()),
        (
            "policies.subscribe_api_policies",
            lambda c: c.policies.subscribe_api_policies(),
        ),
        (
            "policies.subscribe_subaccount_policies",
            lambda c: c.policies.subscribe_subaccount_policies(),
        ),
        ("sub_accounts.subscribe", lambda c: c.sub_accounts.subscribe()),
        (
            "address_book.subscribe_view_invalidations",
            lambda c: c.address_book.subscribe_view_invalidations(),
        ),
        ("balances.subscribe", lambda c: c.balances.subscribe()),
        ("transfers.subscribe", lambda c: c.transfers.subscribe()),
        ("trades.subscribe", lambda c: c.trades.subscribe()),
        ("triggers.subscribe", lambda c: c.triggers.subscribe()),
        ("triggers.subscribe_events", lambda c: c.triggers.subscribe_events()),
        ("orders.subscribe", lambda c: c.orders.subscribe()),
    ],
    ids=[
        "api_keys",
        "api_policies",
        "subaccount_policies",
        "subaccounts",
        "address_books",
        "balances",
        "transfers",
        "trades",
        "triggers",
        "trigger_events",
        "orders",
    ],
)
async def test_private_subscribe_connects(
    live_credentials,
    label: str,
    subscribe: SubscribeFn,
) -> None:
    await _with_fresh_client(subscribe, label=label)
