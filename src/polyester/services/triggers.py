from __future__ import annotations

import functools
from collections.abc import Sequence
from decimal import Decimal

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.triggers import (
    get_trigger_from_proto,
    trigger_events_list_from_proto,
    trigger_mutation_from_proto,
    trigger_status_from_label,
    triggers_list_from_proto,
)
from polyester.codecs.orders import (
    catalog_order_scales,
    parse_optional_subaccount_id,
    resolve_quantity_scale,
)
from polyester.codecs.realtime_decode import decode_trigger_bytes, decode_trigger_event_batch_bytes
from polyester.codecs.scalars import id_to_int
from polyester.codecs.triggers import (
    create_trigger_to_proto,
    modify_trigger_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1.triggers_connect import TriggersServiceClient
from polyester.gen.triggers.v1.triggers_pb2 import (
    CancelTriggerRequest,
    GetTriggerRequest,
    ListTriggerEventsRequest,
    ListTriggersRequest,
    PauseTriggerRequest,
    ResumeTriggerRequest,
    TriggerEventType,
)
from polyester.models import (
    Trigger,
    TriggerEvent,
    TriggerEventsList,
    TriggerMutationResult,
    TriggersList,
)
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService, CatalogWait
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import (
    subscribe_account_proto,
    subscribe_account_proto_batch,
)
from polyester.services._retry import (
    TRIGGER_READ_RETRY,
    unary_auth_decoded_retry_unavailable,
)
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._symbols import resolve_optional_symbol_id, resolve_symbol_id
from polyester.services._validation import validate_limit
from polyester.types.money import Price


class AsyncTriggersService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager,
        default_sub_account_id: str | None,
        *,
        default_account_id: str | int | None = None,
        realtime: AsyncRealtimeClient | None = None,
        wait_for_catalogs: CatalogWait | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime
        self._wait_for_catalogs = wait_for_catalogs

    def _order_scales(self, symbol_id: int) -> tuple[int | None, int | None]:
        """The pair's (base, quote) quantity scales the loaded catalogs know.

        Trigger reads and the trigger stream decode ``qty`` and the TWAP and
        ladder ``executed_qty`` with the base scale; ``None`` before the
        catalogs load. Reads don't wait for them.
        """
        return catalog_order_scales(self._catalogs, symbol_id)

    async def _optional_control_symbol_id(
        self, *, symbol: str | None, symbol_id: int | None, label: str
    ) -> int:
        """Symbol ID for modify/resume; ``0`` targets the trigger's own market."""
        if symbol is not None:
            await self._ensure_catalogs()
        return (
            resolve_optional_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=symbol_id, label=label
            )
            or 0
        )

    async def list(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        symbol: str | None = None,
        status: str | Sequence[str] | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> TriggersList:
        """List triggers.

        ``status`` accepts one or more of: created, armed, running, completed,
        canceled, failed, paused. Unknown values, ``cancelled`` included, raise
        ``PolyesterValidationError`` before sending.

        Like :meth:`get`, this read resends the same request while the server
        answers ``unavailable`` (HTTP 503), for about 2 seconds.
        """
        validated_limit = validate_limit(limit)
        request = ListTriggersRequest(limit=validated_limit)
        if page_token:
            request.page_token = page_token
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if symbol:
            await self._ensure_catalogs()
            request.symbol_id = (
                resolve_optional_symbol_id(
                    self._catalogs, symbol=symbol, label="triggers.list symbol"
                )
                or 0
            )
        if status is not None:
            labels = [status] if isinstance(status, str) else list(status)
            request.status.extend(trigger_status_from_label(label) for label in labels)
        # Decoded with the pair's catalog scales: a load in progress is
        # awaited, and a failed one leaves the quantities unscaled.
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.list_triggers(req),
            request,
            functools.partial(triggers_list_from_proto, scales=self._order_scales),
            policy=TRIGGER_READ_RETRY,
        )

    async def get(
        self,
        *,
        account: AccountScope | None = None,
        trigger_id: str | int,
        sub_account_id: str | int | None = None,
    ) -> Trigger | None:
        """Read one trigger.

        After an answered :meth:`modify`, :meth:`pause` or :meth:`resume`, the
        read shows the change or answers ``unavailable`` (HTTP 503) until it
        can. This method resends the same request on ``unavailable``: after
        25 ms, doubling up to 500 ms, for about 2 seconds, then raises
        ``PolyesterServerError``.
        """
        request = GetTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        # Decoded with the pair's catalog scales: a load in progress is
        # awaited, and a failed one leaves the quantities unscaled.
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.get_trigger(req),
            request,
            functools.partial(get_trigger_from_proto, scales=self._order_scales),
            policy=TRIGGER_READ_RETRY,
        )

    async def create(
        self,
        *,
        account: AccountScope | None = None,
        symbol: str,
        trigger_type: str,
        side: str,
        qty: str,
        trigger_price: str | None = None,
        order_type: str = "market",
        limit_price: str | Decimal | Price | None = None,
        trigger_price_source: str | None = None,
        tif: str | None = None,
        sub_account_id: str | int | None = None,
        client_trigger_id: str | None = None,
        post_only: bool = False,
        fee_asset: str | None = None,
        self_trade_prevention_mode: str | None = None,
        trailing_distance_ticks: int | None = None,
        trailing_distance_bps: int | None = None,
        activation_price: str | None = None,
        max_slippage_ticks: int | None = None,
        max_slippage_bps: int | None = None,
        twap_duration_ms: int | None = None,
        twap_slice_interval_ms: int | None = None,
        ladder_price_min: str | None = None,
        ladder_price_max: str | None = None,
        ladder_levels: int | None = None,
        ladder_distribution: str | None = None,
    ) -> TriggerMutationResult:
        """Create a standalone trigger.

        Options for another strategy or child execution raise
        ``PolyesterValidationError`` before sending. Trailing distances and
        ``activation_price`` apply only to ``trailing_stop``; TWAP and ladder
        settings apply only to their respective strategies.

        ``trailing_distance_ticks`` is a price delta in 1e-9 quote-unit ticks, the
        scale of every price tick: on BTC-USDT, 50 USDT is ``50_000_000_000`` and
        0.5 USDT is ``500_000_000`` (``int(Decimal("0.5").scaleb(9))``). It is not a
        count of the pair's tick size. ``trailing_distance_bps`` is 1 to 10000.

        ``limit_price`` is the child's limit price for a limit stop-loss or
        take-profit. For ``trigger_type="trailing_stop"`` with ``side="buy"`` it
        is the required maximum price, the most the child pays per unit (a
        9-decimal string or ``Decimal``, or ``Price.from_ticks`` for ticks);
        a sell trailing stop takes none. The maximum price is fixed at create.

        ``tif`` is the child's time in force. A limit stop-loss or take-profit
        child takes ``gtc`` (the default when unset), ``ioc`` or ``fok``; ladder
        and TWAP limit slices take ``gtc``. A market child and a trailing stop
        always execute IOC: they take ``ioc`` or no ``tif``, and ``gtc`` or
        ``fok`` raises ``PolyesterValidationError`` before sending.

        ``trigger_price_source`` (``last``, ``index`` or ``mark``) sets the
        price a stop-loss, take-profit or trailing stop watches; unset means
        the last trade price.

        ``client_trigger_id`` identifies this create. Left out or empty, the SDK
        generates one, which reads back on the trigger. An ID you choose and
        keep is what lets you find the trigger after an unknown outcome, so set
        one when you may need to. A blank one raises
        ``PolyesterValidationError`` before sending.
        """
        await self._ensure_catalogs()
        symbol_id: int | None = None
        if self._wait_for_catalogs is not None:
            # The catalogs are loaded: an unknown symbol is refused as unknown,
            # not for its scale. Without hydration the scale is checked first.
            symbol_id = resolve_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=None, label="triggers.create"
            )
        scale = resolve_quantity_scale(self._catalogs, symbol, qty)
        if symbol_id is None:
            symbol_id = resolve_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=None, label="triggers.create"
            )
        request = create_trigger_to_proto(
            symbol=symbol,
            symbol_id=symbol_id,
            trigger_type=trigger_type,
            trigger_price=trigger_price,
            side=side,
            qty=qty,
            order_type=order_type,
            limit_price=limit_price,
            trigger_price_source=trigger_price_source,
            tif=tif,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            client_trigger_id=client_trigger_id,
            post_only=post_only,
            fee_asset=fee_asset,
            self_trade_prevention_mode=self_trade_prevention_mode,
            trailing_distance_ticks=trailing_distance_ticks,
            trailing_distance_bps=trailing_distance_bps,
            activation_price=activation_price,
            max_slippage_ticks=max_slippage_ticks,
            max_slippage_bps=max_slippage_bps,
            twap_duration_ms=twap_duration_ms,
            twap_slice_interval_ms=twap_slice_interval_ms,
            ladder_price_min=ladder_price_min,
            ladder_price_max=ladder_price_max,
            ladder_levels=ladder_levels,
            ladder_distribution=ladder_distribution,
            quantity_scale=scale,
        )
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.create_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def cancel(
        self,
        *,
        account: AccountScope | None = None,
        trigger_id: str | int,
        sub_account_id: str | int | None = None,
    ) -> TriggerMutationResult:
        request = CancelTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.cancel_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def modify(
        self,
        *,
        account: AccountScope | None = None,
        trigger_id: str | int,
        symbol: str | None = None,
        symbol_id: int | None = None,
        sub_account_id: str | int | None = None,
        trigger_price: str | Decimal | Price | None = None,
        trailing_distance_ticks: int | None = None,
        trailing_distance_bps: int | None = None,
        activation_price: str | Decimal | Price | None = None,
        max_slippage_ticks: int | None = None,
        max_slippage_bps: int | None = None,
    ) -> TriggerMutationResult:
        """Patch a live trigger; omitted fields stay unchanged.

        Without ``symbol``/``symbol_id`` the trigger's own market is used; when
        given, it must be that market, and an API key limited to specific
        markets must give it. A ``Price`` bound to another market is refused
        when ``symbol`` or ``symbol_id`` is given. A child's limit price is
        fixed at creation: cancel the trigger and create a new one to change
        it. ``max_slippage_bps`` is 1 to 9999; ``0`` clears a cap (ticks or
        bps) and a market child falls back to the pair's default slippage.
        ``trailing_distance_ticks`` is a price delta in 1e-9 quote-unit ticks, as on
        ``create`` (``500_000_000`` is 0.5 quote units).
        """
        resolved_symbol_id = await self._optional_control_symbol_id(
            symbol=symbol, symbol_id=symbol_id, label="triggers.modify"
        )
        market: str | None = None
        bound = [
            price
            for price in (trigger_price, activation_price)
            if isinstance(price, Price) and price.symbol is not None
        ]
        if resolved_symbol_id and bound:
            # A bound price is checked against the named market; one that
            # can't be named can't be checked, so the price is refused.
            await self._ensure_catalogs()
            if self._catalogs is not None:
                market = self._catalogs.symbol_for_symbol_id(resolved_symbol_id)
            if market is None:
                raise PolyesterValidationError(
                    f"triggers.modify cannot check a price bound to {bound[0].symbol} "
                    f"against symbol_id {resolved_symbol_id}: the market is not in the "
                    "catalogs; hydrate catalogs or pass an unbound price"
                )
        request = modify_trigger_to_proto(
            trigger_id=trigger_id,
            symbol_id=resolved_symbol_id,
            symbol=market,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            trigger_price=trigger_price,
            trailing_distance_ticks=trailing_distance_ticks,
            trailing_distance_bps=trailing_distance_bps,
            activation_price=activation_price,
            max_slippage_ticks=max_slippage_ticks,
            max_slippage_bps=max_slippage_bps,
        )
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.modify_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def pause(
        self,
        *,
        account: AccountScope | None = None,
        trigger_id: str | int,
        sub_account_id: str | int | None = None,
    ) -> TriggerMutationResult:
        request = PauseTriggerRequest(trigger_id=id_to_int(trigger_id, "trigger_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.pause_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def resume(
        self,
        *,
        account: AccountScope | None = None,
        trigger_id: str | int,
        symbol: str | None = None,
        symbol_id: int | None = None,
        sub_account_id: str | int | None = None,
    ) -> TriggerMutationResult:
        """Resume a paused trigger; ``symbol`` is optional as for :meth:`modify`."""
        request = ResumeTriggerRequest(
            trigger_id=id_to_int(trigger_id, "trigger_id"),
            symbol_id=await self._optional_control_symbol_id(
                symbol=symbol, symbol_id=symbol_id, label="triggers.resume"
            ),
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.resume_trigger(req),
            request,
            trigger_mutation_from_proto,
        )

    async def list_events(
        self,
        *,
        account: AccountScope | None = None,
        trigger_id: str | int,
        sub_account_id: str | int | None = None,
        limit: int = 50,
        event_type: str | None = None,
        page_token: str | None = None,
    ) -> TriggerEventsList:
        from typing import cast

        from polyester.codecs.decode.triggers import trigger_event_type_from_label

        validated_limit = validate_limit(limit)
        request = ListTriggerEventsRequest(
            trigger_id=id_to_int(trigger_id, "trigger_id"),
            limit=validated_limit,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if event_type:
            request.event_type = cast(TriggerEventType, trigger_event_type_from_label(event_type))
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.list_trigger_events(req),
            request,
            trigger_events_list_from_proto,
            policy=TRIGGER_READ_RETRY,
        )

    async def subscribe(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[Trigger]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:spot:triggers:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=functools.partial(decode_trigger_bytes, scales=self._order_scales),
        )

    async def subscribe_events(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[TriggerEvent]:
        return await subscribe_account_proto_batch(
            self._realtime,
            channel_template="private:spot:triggers:events:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode_batch=decode_trigger_event_batch_bytes,
        )
