"""Live verification for POLY-3624 recovery hooks (devnet Centrifugo + Connect)."""

from __future__ import annotations

import asyncio

import pytest

from polyester import AsyncPolyester
from tests.helpers import live_client_kwargs_from_env, pick_smoke_symbol


@pytest.mark.integration
@pytest.mark.realtime
async def test_orderbook_subscription_receives_updates_and_exposes_recovery_hooks(
    live_credentials,
) -> None:
    """Orderbook snapshot-then-stream should deliver books and accept recovery callbacks."""
    kwargs = live_client_kwargs_from_env(hydrate_catalogs=True)
    assert kwargs is not None
    client = AsyncPolyester(**kwargs)
    events: list[str] = []
    try:
        await client.wait_for_catalogs()
        spot = await client.market_data.get_spot_config()
        symbol = pick_smoke_symbol(spot.raw)

        sub = await client.orderbook.create_subscription(
            symbol=symbol,
            depth=50,
            on_snapshot_refresh=lambda: events.append("snapshot_refresh"),
            on_sequence_gap=lambda: events.append("sequence_gap"),
            on_reconnect=lambda: events.append("reconnect"),
        )
        try:
            book = await asyncio.wait_for(anext(sub), timeout=20)
            assert book.symbol
            # Initial snapshot refresh should have fired during STS start.
            assert "snapshot_refresh" in events
            await asyncio.sleep(3)
            assert not sub._close.is_set()
        finally:
            await sub.aclose()
    finally:
        await client.aclose()
