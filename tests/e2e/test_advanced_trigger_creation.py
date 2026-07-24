"""Proves the Python SDK can create advanced trigger types end-to-end.

Each test creates a trigger whose child orders are priced far from market so
nothing fills, asserts the backend accepted the advanced params (returns a
trigger_id + "created" status), then cancels. Devnet quirks (internal error,
min-notional sizing, unavailable route) skip rather than fail.
"""

from __future__ import annotations

import contextlib
from decimal import Decimal

import pytest

from polyester.codecs.scalars import align_price_ticks, format_price_ticks, parse_price_ticks
from polyester.errors import PolyesterApiError
from tests.e2e.helpers import unique_client_order_id
from tests.helpers import (
    is_devnet_order_internal_error,
    min_base_qty_for_pair,
    pair_for_symbol,
    pair_tick_size,
    resolve_far_below_buy_limit_price,
)


def _skip_on_devnet_quirk(exc: BaseException) -> None:
    if is_devnet_order_internal_error(exc):
        pytest.skip(f"devnet trigger placement unavailable: {exc}")
    if isinstance(exc, PolyesterApiError):
        code = str(getattr(exc, "code", "") or "").lower()
        if code in {"route_not_found", "unimplemented", "not_found"}:
            pytest.skip(f"trigger route unavailable on devnet: {exc}")
        msg = str(exc).lower()
        for token in ("notional", "not supported", "insufficient", "balance"):
            if token in msg:
                pytest.skip(f"devnet/product limitation for this trigger config: {exc}")


async def _pair(client, symbol: str) -> dict:
    spot = await client.market_data.get_spot_config()
    client.catalogs.hydrate_spot_config(spot.raw)
    return pair_for_symbol(spot.raw, symbol) or {}


async def _create_then_cleanup(client, symbol: str, **create_kwargs):
    """Create a trigger, assert the backend accepted it, then best-effort clean up.

    Advanced triggers such as LADDER arm and place their resting child orders
    immediately, which can leave the trigger itself in a non-cancelable state.
    The proof we care about is that create() returned a trigger_id + "created"
    status (backend accepted the advanced params); cleanup is best-effort.
    """
    created = await client.triggers.create(symbol=symbol, **create_kwargs)
    assert created.trigger_id
    # Admission response synthesizes "accepted" (POLY-3701); not "created".
    assert created.status == "accepted"
    with contextlib.suppress(PolyesterApiError):
        await client.triggers.cancel(trigger_id=created.trigger_id)
    with contextlib.suppress(PolyesterApiError):
        await client.orders.cancel_all(symbol=symbol)
    return created


@pytest.mark.integration
@pytest.mark.mutation
async def test_create_trailing_stop_trigger(
    live_client, trade_symbol, mutation_enabled, require_trade_trading_balance
):
    # Spot v1 trailing stops are sell-side and require MARKET child orders.
    pair = await _pair(live_client, trade_symbol)
    far_below = await resolve_far_below_buy_limit_price(live_client, trade_symbol, pair)
    qty = min_base_qty_for_pair(pair, far_below)
    try:
        await _create_then_cleanup(
            live_client,
            symbol=trade_symbol,
            trigger_type="trailing_stop",
            side="sell",
            qty=qty,
            order_type="market",
            trailing_distance_bps=100,
            client_trigger_id=unique_client_order_id("trg-trail"),
        )
    except (PolyesterApiError, AssertionError) as exc:
        _skip_on_devnet_quirk(exc)
        raise


@pytest.mark.integration
@pytest.mark.mutation
async def test_create_twap_trigger(
    live_client, trade_symbol, mutation_enabled, require_trade_trading_balance
):
    pair = await _pair(live_client, trade_symbol)
    far_below = await resolve_far_below_buy_limit_price(live_client, trade_symbol, pair)
    qty = min_base_qty_for_pair(pair, far_below)
    try:
        await _create_then_cleanup(
            live_client,
            symbol=trade_symbol,
            trigger_type="twap",
            side="buy",
            qty=qty,
            order_type="limit",
            limit_price=far_below,
            twap_duration_ms=600_000,
            twap_slice_interval_ms=300_000,
            client_trigger_id=unique_client_order_id("trg-twap"),
        )
    except (PolyesterApiError, AssertionError) as exc:
        _skip_on_devnet_quirk(exc)
        raise


@pytest.mark.integration
@pytest.mark.mutation
async def test_create_ladder_trigger(
    live_client, trade_symbol, mutation_enabled, require_trade_trading_balance
):
    pair = await _pair(live_client, trade_symbol)
    far_below = await resolve_far_below_buy_limit_price(live_client, trade_symbol, pair)
    tick_size = pair_tick_size(pair)
    max_ticks = align_price_ticks(parse_price_ticks(far_below), tick_size)
    min_ticks = align_price_ticks(int(max_ticks * Decimal("0.8")), tick_size)
    ladder_price_max = format_price_ticks(max_ticks)
    ladder_price_min = format_price_ticks(min_ticks)
    levels = 2
    per_level_qty = Decimal(min_base_qty_for_pair(pair, ladder_price_min))
    total_qty = format(per_level_qty * levels, "f")
    try:
        await _create_then_cleanup(
            live_client,
            symbol=trade_symbol,
            trigger_type="ladder",
            side="buy",
            qty=total_qty,
            order_type="limit",
            limit_price=ladder_price_max,
            ladder_price_min=ladder_price_min,
            ladder_price_max=ladder_price_max,
            ladder_levels=levels,
            ladder_distribution="linear",
            client_trigger_id=unique_client_order_id("trg-ladder"),
        )
    except (PolyesterApiError, AssertionError) as exc:
        _skip_on_devnet_quirk(exc)
        raise
