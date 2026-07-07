from __future__ import annotations

from typing import Any

import msgspec

from polyester.models.trading import Order, OrderMutationResult, OrdersList

# Backward-compatible aliases for early alpha imports.
OpenOrdersResult = OrdersList
CreateOrderResult = OrderMutationResult


class OrderbookLevel(msgspec.Struct, kw_only=True, omit_defaults=True):
    price: str = ""
    qty: str = ""
    price_ticks: str = ""
    qty_scaled: str = ""
    price_display: str | None = None
    qty_display: str | None = None


class OrderbookData(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol: str
    depth: int
    book_seq: str
    bids: list[OrderbookLevel]
    asks: list[OrderbookLevel]


class ApiData(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Escape hatch for responses not yet modeled as typed structs."""

    raw: dict[str, Any]


class SpotConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Spot pair catalog payload. Prefer resolving symbols via ``client.catalogs``."""

    raw: dict[str, Any]


class CreateOrderRequest(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol: str | None = None
    symbol_id: int | None = None
    side: str
    order_type: str
    tif: str | None = None
    qty: str
    price: str | None = None
    sub_account_id: str | None = None
    client_order_id: str | None = None
    post_only: bool = False
    expires_at: str | None = None
    attached_risk: dict[str, Any] | None = None
    market_client_ref_price: str | None = None


__all__ = [
    "CreateOrderRequest",
    "CreateOrderResult",
    "OpenOrdersResult",
    "Order",
    "OrderbookData",
    "OrderbookLevel",
    "SpotConfig",
]
