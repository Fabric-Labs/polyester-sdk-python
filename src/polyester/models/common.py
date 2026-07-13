from __future__ import annotations

from decimal import Decimal
from typing import Any

import msgspec

from polyester.models.trading import Order, OrderMutationResult, OrdersList
from polyester.types.money import Price, Quantity

# Backward-compatible aliases for early alpha imports.
OpenOrdersResult = OrdersList
CreateOrderResult = OrderMutationResult

# Public write inputs: human decimal or resolved typed scalars.
QtyInput = str | Decimal | Quantity
PriceInput = str | Decimal | Price


class OrderbookLevel(msgspec.Struct, kw_only=True, omit_defaults=True):
    price: Price | None = None
    qty: Quantity | None = None


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
    # Any: msgspec accepts str | Decimal | Quantity at runtime.
    qty: Any
    price: Any | None = None
    sub_account_id: str | None = None
    client_order_id: str | None = None
    post_only: bool = False
    expires_at: str | None = None
    attached_risk: dict[str, Any] | None = None
    market_client_ref_price: Any | None = None


__all__ = [
    "CreateOrderRequest",
    "CreateOrderResult",
    "OpenOrdersResult",
    "Order",
    "OrderbookData",
    "OrderbookLevel",
    "SpotConfig",
]
