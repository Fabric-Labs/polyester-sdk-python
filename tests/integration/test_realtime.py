import asyncio

import pytest

from polyester import AsyncPolyester
from tests.helpers import live_client_kwargs_from_env, pick_smoke_symbol
from tests.integration.support import call_optional

# Centrifugo default ping interval is 25s; hold the subscription a bit longer.
REALTIME_HEARTBEAT_HOLD_SECONDS = 35


@pytest.mark.integration
@pytest.mark.realtime
async def test_public_trades_subscription_survives_centrifugo_ping() -> None:
    """Regression: missing pong replies used to close the websocket with code 3012."""
    async with AsyncPolyester() as client:
        await client.wait_for_catalogs()
        spot = await client.market_data.get_spot_config()
        symbol = pick_smoke_symbol(spot.raw)

        subscription = await client.market_data.subscribe_trades(symbol=symbol)
        try:
            deadline = asyncio.get_running_loop().time() + REALTIME_HEARTBEAT_HOLD_SECONDS
            while asyncio.get_running_loop().time() < deadline:
                try:
                    await asyncio.wait_for(subscription.__anext__(), timeout=2.0)
                except TimeoutError:
                    continue
                except StopAsyncIteration:
                    pytest.fail(
                        "public trades subscription closed before Centrifugo heartbeat window "
                        f"elapsed ({REALTIME_HEARTBEAT_HOLD_SECONDS}s)"
                    )
        finally:
            await subscription.aclose()
            await asyncio.sleep(0.1)


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
