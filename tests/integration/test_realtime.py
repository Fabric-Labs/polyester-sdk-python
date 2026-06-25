import asyncio

import pytest

from polyester import AsyncPolyester
from tests.helpers import live_client_kwargs_from_env
from tests.integration.support import call_optional


@pytest.mark.integration
@pytest.mark.realtime
@pytest.mark.optional
async def test_orders_subscribe_receives_connection(live_credentials) -> None:
    """Validate private orders RT wiring with a function-scoped client (clean WS teardown)."""
    kwargs = live_client_kwargs_from_env(hydrate_catalogs=False)
    assert kwargs is not None
    client = AsyncPolyester(**kwargs)
    if not client.default_account_id:
        await client.aclose()
        pytest.skip("POLYESTER_ACCOUNT_ID required for private orders realtime")
    try:
        subscription = await call_optional(
            client.orders.subscribe(account_id=client.default_account_id),
            label="orders.subscribe",
        )
        try:
            try:
                await asyncio.wait_for(subscription.__anext__(), timeout=5)
            except StopAsyncIteration:
                pytest.skip("orders.subscribe closed without publications (no order activity)")
            except TimeoutError:
                pass
        finally:
            await subscription.aclose()
            await asyncio.sleep(0.1)
    finally:
        await client.aclose()
