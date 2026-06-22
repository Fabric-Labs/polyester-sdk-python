from __future__ import annotations

import asyncio
import os
import uuid

from tests.helpers import (
    FAR_ABOVE_BUY_STOP_PRICE_HINTS,
    FAR_BELOW_BUY_PRICE_HINTS,
    min_base_qty_for_pair,
)


async def usdt_funded_buy_limit_params(client, symbol: str) -> tuple[str, str]:
    """Return (price, qty) for a post-only buy on a USDT-quoted pair.

    Uses a symbol-specific price far below typical devnet spot so min-notional
    sizing stays small while reserving quote (USDT) balance.
    """
    spot = await client.market_data.get_spot_config()
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == symbol), {})

    price = (
        os.getenv("POLYESTER_TEST_PRICE")
        or os.getenv("POLYESTER_SMOKE_PRICE")
        or FAR_BELOW_BUY_PRICE_HINTS.get(symbol)
        or "100"
    )
    qty = os.getenv("POLYESTER_TEST_QTY") or os.getenv("POLYESTER_SMOKE_QTY")
    if qty is None:
        qty = min_base_qty_for_pair(pair, price)
    return price, qty


async def usdt_funded_buy_stop_params(client, symbol: str) -> tuple[str, str, str]:
    """Return (trigger_price, limit_price, qty) for a buy stop unlikely to fire.

    Buy stop/limit child orders reserve USDT (quote) on USDT-quoted pairs such as
    ETH-USDT — suitable when the trading account is funded with USDT only.
    """
    spot = await client.market_data.get_spot_config()
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == symbol), {})

    trigger_price = (
        os.getenv("POLYESTER_TEST_TRIGGER_PRICE")
        or FAR_ABOVE_BUY_STOP_PRICE_HINTS.get(symbol)
        or "50000"
    )
    limit_price = os.getenv("POLYESTER_TEST_TRIGGER_LIMIT_PRICE") or trigger_price
    qty = os.getenv("POLYESTER_TEST_QTY") or os.getenv("POLYESTER_SMOKE_QTY")
    if qty is None:
        qty = min_base_qty_for_pair(pair, limit_price)
    return trigger_price, limit_price, qty


def unique_client_order_id(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


async def wait_for_open_order(
    client, client_order_id: str, *, limit: int = 50, timeout: float = 10
):
    attempts = max(1, int(timeout / 0.5))
    for _ in range(attempts):
        open_orders = await client.orders.list_open(limit=limit)
        for order in open_orders.orders:
            if order.client_order_id == client_order_id:
                return order
        await asyncio.sleep(0.5)
    raise AssertionError(f"Open order {client_order_id} was not visible within {timeout}s")


async def wait_for_no_open_order(
    client, client_order_id: str, *, limit: int = 50, timeout: float = 10
) -> None:
    attempts = max(1, int(timeout / 0.5))
    for _ in range(attempts):
        open_orders = await client.orders.list_open(limit=limit)
        if not any(order.client_order_id == client_order_id for order in open_orders.orders):
            return
        await asyncio.sleep(0.5)
    raise AssertionError(f"Open order {client_order_id} was still visible after {timeout}s")


# Backwards-compatible alias for existing imports.
far_below_market_limit_params = usdt_funded_buy_limit_params
