from __future__ import annotations

from datetime import datetime

import msgspec

from polyester.types.money import Price


class PriceAlert(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A durable price alert (``alerts.v1.PriceAlert``; devnet only).

    It watches one market's last traded price (``price_source`` ``"last"``)
    or index price (``"index"``) and fires once when that price crosses
    ``price``: ``direction`` ``"above"`` at a price >= ``price``, ``"below"``
    at a price <= ``price``. ``reference_price`` is the watched price when the
    alert was created or last set again; an alert created past its price
    starts with ``armed`` false and fires only after the price moves back and
    crosses again. ``status`` is ``"active"``, ``"triggered"`` or
    ``"cancelled"`` (the contract's spelling, unlike a trigger's
    ``"canceled"``); ``triggered_at`` and ``triggered_price`` are set only on a
    triggered alert. ``channels`` are ``"in_app"`` and/or ``"telegram"``.
    ``revision`` starts at 1 and grows with every change: pass it as
    ``expected_revision`` to ``alerts.update``. An enum value this SDK does not
    know reads ``"unspecified"``.
    """

    alert_id: str
    symbol_id: int
    symbol: str = ""
    direction: str = "unspecified"
    price_source: str = "unspecified"
    price: Price | None = None
    reference_price: Price | None = None
    armed: bool = False
    status: str = "unspecified"
    channels: list[str] = msgspec.field(default_factory=list)
    revision: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    triggered_at: datetime | None = None
    triggered_price: Price | None = None


class PriceAlertsPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of the caller's alerts, newest first. Pass ``next_page_token``
    back as ``page_token`` with the same filters; empty on the last page."""

    alerts: list[PriceAlert] = msgspec.field(default_factory=list)
    next_page_token: str = ""


class PriceAlertUpdate(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Result of ``alerts.update``: the alert as it is now, and what the call
    did where it was applied. ``outcome`` is ``"applied"`` (it changed the
    alert), ``"unchanged"`` (the alert already held the requested values) or
    ``"replayed"`` (the idempotency key was already used for this request;
    nothing was applied now). Tell a retry from a fresh change by ``outcome``,
    never by comparing revisions."""

    alert: PriceAlert
    outcome: str = "unspecified"
