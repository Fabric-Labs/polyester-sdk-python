import asyncio

import pytest

from polyester.errors import PolyesterApiError
from tests.e2e.helpers import unique_client_order_id, usdt_funded_buy_stop_params


async def _wait_for_trigger(client, trigger_id: str, *, timeout: float = 10):
    attempts = max(1, int(timeout / 0.5))
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            trigger = await client.triggers.get(trigger_id=trigger_id)
            if trigger is not None:
                return trigger
        except PolyesterApiError as exc:
            if str(exc.code or "").lower() != "not_found":
                raise
            last_error = exc
        await asyncio.sleep(0.5)
    raise AssertionError(f"Trigger {trigger_id} was not readable within {timeout}s") from last_error


async def _wait_for_trigger_events(client, trigger_id: str, *, timeout: float = 10):
    attempts = max(1, int(timeout / 0.5))
    events = None
    for _ in range(attempts):
        events = await client.triggers.list_events(trigger_id=trigger_id, limit=10)
        if any(event.trigger_id == trigger_id for event in events.events):
            return events
        await asyncio.sleep(0.5)
    raise AssertionError(f"Trigger events for {trigger_id} were not visible within {timeout}s")


@pytest.mark.integration
@pytest.mark.mutation
async def test_trigger_pause_resume_cancel(
    live_client, smoke_symbol, mutation_enabled, require_trading_balance
):
    """USDT-funded buy stop on ETH-USDT (limit child order reserves quote balance)."""
    trigger_price, limit_price, qty = await usdt_funded_buy_stop_params(
        live_client, smoke_symbol
    )
    client_trigger_id = unique_client_order_id("trg")

    created = await live_client.triggers.create(
        symbol=smoke_symbol,
        trigger_type="stop_loss",
        side="buy",
        qty=qty,
        trigger_price=trigger_price,
        limit_price=limit_price,
        order_type="limit",
        client_trigger_id=client_trigger_id,
    )
    assert created.trigger_id
    assert created.status == "created"

    cancelled_ok = False
    try:
        trigger = await _wait_for_trigger(live_client, created.trigger_id)
        assert trigger.trigger_id == created.trigger_id
        assert trigger.client_trigger_id == client_trigger_id
        assert trigger.status == "armed"

        paused = await live_client.triggers.pause(trigger_id=created.trigger_id)
        assert paused.trigger_id == created.trigger_id
        assert paused.status == "paused"

        resumed = await live_client.triggers.resume(trigger_id=created.trigger_id)
        assert resumed.trigger_id == created.trigger_id
        assert resumed.status == "armed"

        cancelled = await live_client.triggers.cancel(trigger_id=created.trigger_id)
        assert cancelled.trigger_id == created.trigger_id
        assert cancelled.status == "cancelled"
        cancelled_ok = True
    finally:
        if not cancelled_ok:
            await live_client.triggers.cancel(trigger_id=created.trigger_id)

    events = await _wait_for_trigger_events(live_client, created.trigger_id)
    assert any(event.trigger_id == created.trigger_id for event in events.events)
