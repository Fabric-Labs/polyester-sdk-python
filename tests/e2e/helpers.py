from __future__ import annotations

import asyncio
import os
import uuid

from polyester.errors import PolyesterApiError
from tests.helpers import (
    DevnetOrderNotIndexedError,
    min_base_qty_for_pair,
    resolve_far_above_buy_stop_price,
    resolve_far_below_buy_limit_price,
)


async def usdt_funded_buy_limit_params(client, symbol: str) -> tuple[str, str]:
    """Return (price, qty) for a post-only buy on a USDT-quoted pair.

    Uses a symbol-specific price far below typical devnet spot so min-notional
    sizing stays small while reserving quote (USDT) balance.
    """
    spot = await client.market_data.get_spot_config()
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == symbol), {})

    price = await resolve_far_below_buy_limit_price(client, symbol, pair)
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

    trigger_price = await resolve_far_above_buy_stop_price(client, symbol, pair)
    limit_price = os.getenv("POLYESTER_TEST_TRIGGER_LIMIT_PRICE") or trigger_price
    qty = os.getenv("POLYESTER_TEST_QTY") or os.getenv("POLYESTER_SMOKE_QTY")
    if qty is None:
        qty = min_base_qty_for_pair(pair, limit_price)
    return trigger_price, limit_price, qty


def unique_client_order_id(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


_OPEN_ORDER_STATUSES = frozenset({"pending", "working", "pending_cancel"})
_TERMINAL_ORDER_STATUSES = frozenset({"canceled", "rejected", "filled"})


async def wait_for_open_order(
    client, client_order_id: str, *, limit: int = 50, timeout: float = 15
):
    """Wait until an order is open; poll get first (devnet list_open can lag)."""
    attempts = max(1, int(timeout / 0.5))
    last_status: str | None = None
    for _ in range(attempts):
        try:
            detail = await client.orders.get(client_order_id=client_order_id)
        except PolyesterApiError as exc:
            if str(exc.code or "").lower() != "not_found":
                raise
        else:
            if detail.order is not None and detail.order.client_order_id == client_order_id:
                order = detail.order
                if not order.status or order.status in _OPEN_ORDER_STATUSES:
                    return order
                last_status = order.status
                if order.status in _TERMINAL_ORDER_STATUSES:
                    raise AssertionError(
                        f"Order {client_order_id} reached terminal status "
                        f"{order.status!r} instead of staying open"
                    )
        open_orders = await client.orders.list_open(limit=limit)
        for order in open_orders.orders:
            if order.client_order_id == client_order_id:
                return order
        await asyncio.sleep(0.5)
    message = f"Open order {client_order_id} was not visible within {timeout}s"
    if last_status is not None:
        message += f" (last get status: {last_status!r})"
        raise AssertionError(message)
    raise DevnetOrderNotIndexedError(message)


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


async def wait_for_terminal_order(client, client_order_id: str, *, timeout: float = 20):
    attempts = max(1, int(timeout / 0.5))
    last_detail = None
    for _ in range(attempts):
        try:
            detail = await client.orders.get(client_order_id=client_order_id)
        except PolyesterApiError as exc:
            if str(exc.code or "").lower() != "not_found":
                raise
        else:
            last_detail = detail
            if detail.order is not None and detail.order.status in _TERMINAL_ORDER_STATUSES:
                return detail
        await asyncio.sleep(0.5)
    status = None
    if last_detail is not None and last_detail.order is not None:
        status = last_detail.order.status
    raise AssertionError(
        f"Order {client_order_id} did not reach terminal status within {timeout}s"
        + (f" (last status: {status!r})" if status else "")
    )


async def btc_usdt_market_qty(client, symbol: str = "BTC-USDT") -> str:
    spot = await client.market_data.get_spot_config()
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == symbol), {})
    if not pair:
        raise ValueError(f"{symbol} is not in spot config")
    price = await resolve_far_below_buy_limit_price(client, symbol, pair)
    qty = os.getenv("POLYESTER_TEST_TRADE_QTY") or os.getenv("POLYESTER_TEST_QTY")
    if qty is None:
        qty = min_base_qty_for_pair(pair, price)
    return qty
