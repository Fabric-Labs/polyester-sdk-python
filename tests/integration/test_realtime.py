import asyncio

import pytest

from polyester import AsyncPolyester
from polyester.models import PrivateOrdersConnected, PrivateOrdersSnapshot
from tests.helpers import live_client_kwargs_from_env, pick_trade_symbol
from tests.integration.support import call_optional

# Centrifugo default ping interval is 25s; hold the subscription a bit longer.
REALTIME_HEARTBEAT_HOLD_SECONDS = 35


@pytest.mark.integration
@pytest.mark.realtime
async def test_public_trades_subscription_survives_centrifugo_ping(live_credentials) -> None:
    """Regression: missing pong replies used to close the websocket with code 3012."""
    kwargs = live_client_kwargs_from_env(hydrate_catalogs=True)
    assert kwargs is not None
    client = AsyncPolyester(**kwargs)
    try:
        await client.wait_for_catalogs()
        spot = await client.market_data.get_spot_config()
        # Heartbeat / mutation paths honor POLYESTER_TEST_TRADE_SYMBOL (F-23).
        symbol = pick_trade_symbol(spot.raw)
        print(f"trade_symbol={symbol}", flush=True)

        subscription = await client.market_data.subscribe_trades(symbol=symbol)
        try:
            deadline = asyncio.get_running_loop().time() + REALTIME_HEARTBEAT_HOLD_SECONDS
            publications = 0
            while asyncio.get_running_loop().time() < deadline:
                if subscription._close.is_set():
                    pytest.fail(
                        "public trades subscription closed before Centrifugo heartbeat window "
                        f"elapsed ({REALTIME_HEARTBEAT_HOLD_SECONDS}s)"
                    )
                task = subscription._task
                if task is not None and task.done():
                    if exc := task.exception():
                        raise exc
                    pytest.fail(
                        "public trades subscription closed before Centrifugo heartbeat window "
                        f"elapsed ({REALTIME_HEARTBEAT_HOLD_SECONDS}s)"
                    )
                try:
                    await asyncio.wait_for(subscription.__anext__(), timeout=2.0)
                    publications += 1
                except TimeoutError:
                    pass
            assert publications > 0, (
                "protobuf subscription stayed open but delivered no publications"
            )
        finally:
            await subscription.aclose()
            await asyncio.sleep(0.1)
    finally:
        await client.aclose()


@pytest.mark.integration
@pytest.mark.realtime
@pytest.mark.optional
async def test_orders_subscribe_receives_connection(live_credentials) -> None:
    """Validate the private order socket with a function-scoped client (clean WS teardown)."""
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
            first = await asyncio.wait_for(subscription.__anext__(), timeout=5)
            assert isinstance(first, PrivateOrdersConnected)
            # A subscribe without a cursor always starts with the full live view.
            snapshot = await asyncio.wait_for(subscription.__anext__(), timeout=10)
            assert isinstance(snapshot, PrivateOrdersSnapshot)
        finally:
            await subscription.aclose()
            await asyncio.sleep(0.1)
    finally:
        await client.aclose()
