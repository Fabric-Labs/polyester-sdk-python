"""Typed exclusive order identity (order id XOR client order id)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class OrderId:
    """Exchange-assigned order id."""

    value: str | int
    # How polyester.pure, which holds the order key rules, recognises it.
    _polyester_kind: ClassVar[str] = "order_id"


@dataclass(frozen=True, slots=True)
class ClientOrderId:
    """Caller-supplied client order id."""

    value: str
    _polyester_kind: ClassVar[str] = "client_order_id"


OrderKey = OrderId | ClientOrderId

__all__ = ["ClientOrderId", "OrderId", "OrderKey"]
