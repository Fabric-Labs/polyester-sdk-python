"""Events delivered by the private order stream (``client.orders.subscribe``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from polyester.errors import PolyesterRealtimeError
from polyester.models.trading import Order
from polyester.types.money import Price, Quantity


@dataclass(frozen=True, slots=True)
class PrivateOrderFill:
    """One execution of an order. ``match_id`` is the user trade's ``match_id``."""

    match_id: str
    ordinal: int
    role: str
    qty: Quantity
    price: Price | None


@dataclass(frozen=True, slots=True)
class PrivateOrderEvent:
    """A change to one order: ``accepted``, ``filled``, ``canceled``, ``rejected``,
    ``replaced`` or ``attached_risk``.

    ``reason_code`` is set for ``canceled``, ``rejected`` and ``replaced``;
    ``replacement_order_id`` for ``replaced``; ``fill`` for ``filled``.
    """

    order_id: str
    version: int
    kind: str
    reason_code: int = 0
    replacement_order_id: str = ""
    fill: PrivateOrderFill | None = None


@dataclass(frozen=True, slots=True)
class PrivateOrderCommandOutcome:
    """A command outcome that changed no order: ``amend_rejected``,
    ``cancel_rejected``, ``replace_rejected``, ``rejected`` or ``cancel_all_done``.

    ``reason`` is the order error code the Orders API returns for the same
    refusal (for example ``INSUFFICIENT_BALANCE``); empty when unset.
    """

    kind: str
    order_id: str = ""
    new_order_id: str = ""
    client_order_id: str = ""
    reason: str = ""


@dataclass(frozen=True, slots=True)
class PrivateOrdersSnapshot:
    """The account's full live view. Replace local state with ``orders``."""

    orders: list[Order]
    type: Literal["snapshot"] = "snapshot"


@dataclass(frozen=True, slots=True)
class PrivateOrdersUnit:
    """One change, applied whole.

    ``orders`` are complete changed orders: keep the copy with the higher
    ``version`` (equal versions are identical). ``removed_order_ids`` left the
    live view; a removal is not a cancellation. ``events`` are in order and
    never coalesced.
    """

    orders: list[Order]
    removed_order_ids: list[str]
    events: list[PrivateOrderEvent | PrivateOrderCommandOutcome]
    type: Literal["unit"] = "unit"


@dataclass(frozen=True, slots=True)
class PrivateOrdersStale:
    """The account's live view is temporarily behind (``True``) or caught up (``False``)."""

    stale: bool
    type: Literal["stale"] = "stale"


@dataclass(frozen=True, slots=True)
class PrivateOrdersConnected:
    """The server confirmed the subscription; again after each reconnect or resubscribe."""

    type: Literal["connected"] = "connected"


@dataclass(frozen=True, slots=True)
class PrivateOrdersDisconnected:
    """The connection or subscription carrying the stream dropped.

    The stream resumes from its last position on its own unless it ends with
    an error.
    """

    type: Literal["disconnected"] = "disconnected"


@dataclass(frozen=True, slots=True)
class PrivateOrdersError:
    """A failure the stream recovers from by itself (it keeps running).

    ``kind`` names the step that failed: ``connection_token``,
    ``subscription_token``, ``connection``, ``decode``, ``request`` or
    ``refresh``. A failure that ends the stream is raised from iteration
    instead.
    """

    kind: str
    error: PolyesterRealtimeError | Exception = field(compare=False)
    type: Literal["error"] = "error"


PrivateOrdersEvent = (
    PrivateOrdersSnapshot
    | PrivateOrdersUnit
    | PrivateOrdersStale
    | PrivateOrdersConnected
    | PrivateOrdersDisconnected
    | PrivateOrdersError
)

__all__ = [
    "PrivateOrderCommandOutcome",
    "PrivateOrderEvent",
    "PrivateOrderFill",
    "PrivateOrdersConnected",
    "PrivateOrdersDisconnected",
    "PrivateOrdersError",
    "PrivateOrdersEvent",
    "PrivateOrdersSnapshot",
    "PrivateOrdersStale",
    "PrivateOrdersUnit",
]
