"""Live private-channel realtime coverage (auth + trading/ledger streams).

Permission fixtures (F-24): each subscribe group needs the matching API-key
scope. Missing permission returns structured Auth/403 and soft-skips (fails
closed under ``POLYESTER_TEST_STRICT_LIVE=1``):

- ``address_book.subscribe_view_invalidations`` → address-book read
- ``transfers.subscribe`` → transfer:read
- ``orders`` / ``trades`` / ``triggers`` → trading read
- ``balances.subscribe`` → ledger read
- ``api_keys`` / ``policies`` / ``sub_accounts`` → auth admin read
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterApiError, PolyesterAuthError, PolyesterServerError
from tests.helpers import live_client_kwargs_from_env
from tests.integration.support import (
    devnet_proto_mismatch,
    jwt_session_only,
    route_unavailable,
)

SubscribeFn = Callable[[AsyncPolyester], Awaitable[object]]

# Explicit permission requirements for private realtime fixtures (F-24).
PERMISSION_REQUIREMENTS: dict[str, str] = {
    "address_book.subscribe_view_invalidations": "address-book read",
    "transfers.subscribe": "transfer:read",
    "balances.subscribe": "ledger read",
    "orders.subscribe": "trading read",
    "trades.subscribe": "trading read",
    "triggers.subscribe": "trading read",
    "triggers.subscribe_events": "trading read",
    "api_keys.subscribe": "auth admin read",
    "policies.subscribe_api_policies": "auth admin read",
    "policies.subscribe_subaccount_policies": "auth admin read",
    "sub_accounts.subscribe": "auth admin read",
}


def _is_permission_denied(exc: BaseException) -> bool:
    msg = str(exc).lower()
    permissionish = (
        "permission denied" in msg
        or "permission_denied" in msg
        or "http 403" in msg
    )
    if isinstance(exc, PolyesterAuthError):
        return permissionish or str(exc.code or "").lower() == "permission_denied"
    if isinstance(exc, PolyesterApiError):
        code = str(getattr(exc, "code", "") or "").lower()
        return permissionish or "permission_denied" in code
    return False


async def _subscribe_optional(subscribe: SubscribeFn, client: AsyncPolyester, *, label: str):
    required_perm = PERMISSION_REQUIREMENTS.get(label, "required scope")
    try:
        return await subscribe(client)
    except Exception as exc:  # noqa: BLE001
        if _is_permission_denied(exc):
            pytest.skip(
                f"{label} missing required API-key permission "
                f"({required_perm}; declare fixture scopes): {exc}"
            )
        if route_unavailable(exc):
            pytest.skip(f"{label} not mounted on devnet")
        if jwt_session_only(exc):
            pytest.skip(f"{label} requires JWT/session auth (API key not accepted on devnet)")
        if isinstance(exc, PolyesterServerError) and devnet_proto_mismatch(exc):
            pytest.skip(f"{label} unavailable on devnet: {exc}")
        raise


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
        subscription = await _subscribe_optional(subscribe, client, label=label)
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
