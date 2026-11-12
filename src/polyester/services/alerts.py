from __future__ import annotations

import re
from collections.abc import AsyncIterator, Sequence
from decimal import Decimal
from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.alerts import (
    CHANNEL_LABELS,
    DIRECTION_LABELS,
    PRICE_SOURCE_LABELS,
    STATUS_LABELS,
    price_alert_update_from_proto,
    price_alerts_page_from_proto,
    required_price_alert,
)
from polyester.codecs.scalars import parse_account_id
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.alerts.v1 import price_alerts_pb2 as pb
from polyester.gen.alerts.v1.price_alerts_connect import PriceAlertServiceClient
from polyester.models.alerts import PriceAlert, PriceAlertsPage, PriceAlertUpdate
from polyester.services._base import BaseService, CatalogWait
from polyester.services._generated import unary_auth_decoded
from polyester.services._symbols import resolve_optional_symbol_id, resolve_symbol_id
from polyester.services._validation import validate_limit
from polyester.types.money import Price, resolve_price_ticks

_MAX_LIST_LIMIT = 200
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{1,128}")
INT64_MAX = (1 << 63) - 1


def _by_label(labels: dict[int, str]) -> dict[str, int]:
    return {label: value for value, label in labels.items()}


_DIRECTIONS = _by_label(DIRECTION_LABELS)
_PRICE_SOURCES = _by_label(PRICE_SOURCE_LABELS)
_STATUSES = _by_label(STATUS_LABELS)
_CHANNELS = _by_label(CHANNEL_LABELS)


def _enum(value: str, labels: dict[str, int], field: str) -> Any:
    """The enum number of a label (typed ``Any``: the stubs type enums as classes)."""
    if not isinstance(value, str) or value not in labels:
        raise PolyesterValidationError(
            f"{field} must be one of {', '.join(sorted(labels))}, got {value!r}"
        )
    return labels[value]


def _channels(channels: Sequence[str]) -> list[Any]:
    if isinstance(channels, str) or not 1 <= len(channels) <= 2:
        raise PolyesterValidationError("channels must name one or two channels")
    values = [_enum(channel, _CHANNELS, "channel") for channel in channels]
    if len(set(values)) != len(values):
        raise PolyesterValidationError("channels must not repeat a channel")
    return values


def _price_ticks(price: str | Decimal | Price, symbol: str | None) -> int:
    ticks = resolve_price_ticks(price, "price", symbol=symbol)
    if not 0 < ticks <= INT64_MAX:
        raise PolyesterValidationError("price must be greater than zero")
    return ticks


def _idempotency_key(key: str | None) -> str:
    if key is None or key == "":
        return ""
    if not isinstance(key, str) or not _IDEMPOTENCY_KEY.fullmatch(key):
        raise PolyesterValidationError(
            "idempotency_key must be 1 to 128 characters of A-Z, a-z, 0-9, '.', '_', ':' or '-'"
        )
    return key


class AsyncAlertsService(BaseService):
    """Price alerts (``alerts.v1.PriceAlertService``).

    Available on devnet; not yet routed on testnet. Alerts belong to the main
    (root) account: a session or an API key of the main account manages them,
    and an API key scoped to a sub-account is refused with
    :class:`~polyester.errors.PolyesterAuthError` (``SUBACCOUNT_KEY_REFUSED``,
    HTTP 403). The exchange evaluates them, so they survive restarts; an alert
    fires once, when the watched price crosses its price, and is delivered to
    the in-app inbox and/or the account's linked Telegram account.

    Prices are quote units: a decimal string, a ``Decimal`` or a
    :class:`~polyester.types.money.Price`. Refusals carry the
    ``alerts.v1.ErrorCode`` name as ``code``. ``PRICE_UNAVAILABLE`` raises a
    retryable :class:`~polyester.errors.PolyesterServerError`: nothing
    changed. ``SERVICE_UNAVAILABLE`` raises a ``PolyesterServerError`` whose
    outcome is unknown for a create, update or cancel
    (:func:`~polyester.errors.mutation_outcome_unknown`): send a create or
    update again with the same ``idempotency_key``, cancel again (it is
    idempotent), or read the alerts back. ``REVISION_CONFLICT``
    means the alert changed since you read it (read it again);
    ``IDEMPOTENCY_CONFLICT`` means the key was used for another request (the
    original stands). Pass an ``idempotency_key`` to make a create or update
    safe to send again after a lost answer.
    """

    def __init__(
        self,
        transport,
        catalogs: CatalogManager | None = None,
        *,
        wait_for_catalogs: CatalogWait | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._wait_for_catalogs = wait_for_catalogs

    async def create(
        self,
        *,
        direction: str,
        price: str | Decimal | Price,
        channels: Sequence[str],
        symbol: str | None = None,
        symbol_id: int | None = None,
        price_source: str | None = None,
        idempotency_key: str | None = None,
    ) -> PriceAlert:
        """Create an alert on one market (``symbol`` or ``symbol_id``).

        ``direction`` is ``"above"`` (fires at a price >= ``price``) or
        ``"below"`` (at a price <= ``price``). ``price_source`` is ``"last"``
        (last traded price) or ``"index"``; ``None`` watches the index price
        where the market has one and the last price otherwise, and the
        returned alert states which. ``channels`` names one or two of
        ``"in_app"`` and ``"telegram"``. The current price is recorded as the
        alert's ``reference_price``; an alert whose condition already holds
        there starts unarmed and fires only after the price moves back and
        crosses again. The same ``idempotency_key`` and request return the
        alert created first. A :class:`~polyester.types.Price` bound to a
        market must be bound to this one, as the catalogs name it: a bound
        price is refused with
        :class:`~polyester.errors.PolyesterValidationError` before sending
        when the catalogs do not know the market's ``symbol_id`` (they are
        empty, still loading and then failed, or don't list it), whatever
        ``symbol`` says, since nothing proves which market that ID is. An
        unbound price works with any ``symbol_id``. A response without the
        created alert raises
        :class:`~polyester.errors.PolyesterResponseContractError`; the alert
        may exist, so read the alerts back or send the create again with the
        same ``idempotency_key``.
        """
        direction_value = _enum(direction, _DIRECTIONS, "direction")
        source_value = (
            pb.PRICE_SOURCE_UNSPECIFIED
            if price_source is None
            else _enum(price_source, _PRICE_SOURCES, "price_source")
        )
        channel_values = _channels(channels)
        key = _idempotency_key(idempotency_key)
        bound_symbol = price.symbol if isinstance(price, Price) else None
        if symbol or bound_symbol is not None:
            # A bound price is checked against the market's catalog name.
            await self._ensure_catalogs(required=bool(symbol))
        resolved_id = resolve_symbol_id(
            self._catalogs, symbol=symbol, symbol_id=symbol_id, label="alerts.create"
        )
        # The market a bound price is checked against is the catalogs' name for
        # the ID sent. A caller's ``symbol`` beside an ID the catalogs don't
        # know proves nothing about that ID, so it is never used for the check.
        market = self._catalogs.symbol_for_symbol_id(resolved_id) if self._catalogs else None
        if bound_symbol is not None and market is None:
            raise PolyesterValidationError(
                f"price is bound to {bound_symbol}, but the catalogs do not name "
                f"symbol_id {resolved_id}, so it cannot be checked; hydrate catalogs "
                "or pass an unbound price"
            )
        request = pb.CreateAlertRequest(
            symbol_id=resolved_id,
            direction=direction_value,
            price_source=source_value,
            price_ticks=_price_ticks(price, market),
            channels=channel_values,
            idempotency_key=key,
        )
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded(
            self._transport,
            PriceAlertServiceClient,
            lambda client, req: client.create_alert(req),
            request,
            lambda msg: required_price_alert(msg, "CreateAlert", self._catalogs),
        )

    async def list(
        self,
        *,
        statuses: Sequence[str] | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> PriceAlertsPage:
        """One page of the caller's alerts, newest first.

        ``statuses`` keeps alerts in those states (``"active"``,
        ``"triggered"``, ``"cancelled"``); ``symbol`` or ``symbol_id`` keeps
        one market. ``limit`` defaults to 50 on the server, at most 200. Pass
        ``next_page_token`` back as ``page_token`` with the same filters.
        """
        status_values: list[Any] = []
        if statuses is not None:
            if isinstance(statuses, str):
                raise PolyesterValidationError("statuses must be a sequence of labels")
            status_values = [_enum(status, _STATUSES, "status") for status in statuses]
            if len(set(status_values)) != len(status_values):
                raise PolyesterValidationError("statuses must not repeat a status")
        validated_limit = validate_limit(limit, allow_none=True)
        if validated_limit is not None and not 0 <= validated_limit <= _MAX_LIST_LIMIT:
            raise PolyesterValidationError(f"limit must be from 0 to {_MAX_LIST_LIMIT}")
        if symbol:
            await self._ensure_catalogs()
        resolved_id = resolve_optional_symbol_id(
            self._catalogs, symbol=symbol, symbol_id=symbol_id, label="alerts.list"
        )
        request = pb.ListAlertsRequest(
            statuses=status_values,
            symbol_id=resolved_id or 0,
            limit=validated_limit or 0,
            page_token=page_token or "",
        )
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded(
            self._transport,
            PriceAlertServiceClient,
            lambda client, req: client.list_alerts(req),
            request,
            lambda msg: price_alerts_page_from_proto(msg, self._catalogs),
        )

    async def iter_alerts(
        self,
        *,
        statuses: Sequence[str] | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> AsyncIterator[PriceAlert]:
        """Every alert matching the filters of :meth:`list`, newest first,
        fetching pages as needed."""
        requested: set[str] = set()
        token = page_token
        while True:
            if token:
                requested.add(token)
            page = await self.list(
                statuses=statuses,
                symbol=symbol,
                symbol_id=symbol_id,
                limit=limit,
                page_token=token,
            )
            for alert in page.alerts:
                yield alert
            if not page.next_page_token:
                return
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ListAlerts", "next_page_token repeats an earlier page token"
                )
            token = page.next_page_token

    async def update(
        self,
        *,
        alert_id: str | int,
        expected_revision: int,
        direction: str | None = None,
        price: str | Decimal | Price | None = None,
        channels: Sequence[str] | None = None,
        idempotency_key: str | None = None,
    ) -> PriceAlertUpdate:
        """Change an alert's ``direction``, ``price`` and/or ``channels``.

        Only the fields you pass change. ``price`` must be unbound (a decimal
        string, a ``Decimal`` or ``Price.from_ticks(ticks)``): a
        :class:`~polyester.types.Price` bound to a market, such as an alert's
        own ``price``, is refused with
        :class:`~polyester.errors.PolyesterValidationError` before sending,
        since the update names the alert, not its market, and nothing proves
        the binding. With none, the call changes no field:
        it sets a triggered alert again as it is, and changes nothing on an
        active one. Updating a triggered alert sets it again.
        ``expected_revision`` is the alert's ``revision`` from your last read;
        a stale one is refused ``REVISION_CONFLICT``. The same
        ``idempotency_key`` and changes (``expected_revision`` aside) apply at
        most once: a repeat returns the alert as it is now with ``outcome``
        ``"replayed"``. A cancelled alert can no longer change. A response
        without the alert raises
        :class:`~polyester.errors.PolyesterResponseContractError` whatever its
        ``outcome``: the update may have applied, so read the alert back.
        """
        parsed_id = parse_account_id(alert_id, "alert_id")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            raise PolyesterValidationError("expected_revision must be an integer")
        if expected_revision <= 0:
            raise PolyesterValidationError("expected_revision must be greater than zero")
        request = pb.UpdateAlertRequest(
            alert_id=parsed_id,
            expected_revision=expected_revision,
            idempotency_key=_idempotency_key(idempotency_key),
        )
        # Both are required on the wire, also when they are empty.
        request.update.SetInParent()
        request.update_mask.SetInParent()
        if direction is not None:
            request.update.direction = _enum(direction, _DIRECTIONS, "direction")
            request.update_mask.paths.append("direction")
        if price is not None:
            if isinstance(price, Price) and price.symbol is not None:
                # The update names the alert, not its market, so nothing
                # proves a bound price is for that market.
                raise PolyesterValidationError(
                    f"alerts.update cannot check a price bound to {price.symbol} against "
                    "the alert's market; pass an unbound price: a decimal string, a "
                    "Decimal or Price.from_ticks(ticks)"
                )
            request.update.price_ticks = _price_ticks(price, None)
            request.update_mask.paths.append("price_ticks")
        if channels is not None:
            request.update.channels.extend(_channels(channels))
            request.update_mask.paths.append("channels")
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded(
            self._transport,
            PriceAlertServiceClient,
            lambda client, req: client.update_alert(req),
            request,
            lambda msg: price_alert_update_from_proto(msg, self._catalogs),
        )

    async def cancel(self, *, alert_id: str | int) -> PriceAlert:
        """Cancel an active alert. Cancelling a cancelled alert returns it
        unchanged; a triggered alert is refused ``ALERT_TRIGGERED`` (update it
        to set it again). A response without the alert raises
        :class:`~polyester.errors.PolyesterResponseContractError`: cancel
        again (it is idempotent) or read the alert back."""
        request = pb.CancelAlertRequest(alert_id=parse_account_id(alert_id, "alert_id"))
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded(
            self._transport,
            PriceAlertServiceClient,
            lambda client, req: client.cancel_alert(req),
            request,
            lambda msg: required_price_alert(msg, "CancelAlert", self._catalogs),
        )
