from __future__ import annotations

import functools
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.triggers import (
    batch_cancel_triggers_from_proto,
    cancel_oco_from_proto,
    create_oco_from_proto,
    get_trigger_from_proto,
    trigger_events_list_from_proto,
    trigger_mutation_from_proto,
    trigger_status_from_label,
    triggers_list_from_proto,
)
from polyester.codecs.oco import create_oco_to_proto, validate_client_list_id
from polyester.codecs.orders import (
    catalog_order_scales,
    parse_optional_subaccount_id,
    resolve_quantity_scale,
)
from polyester.codecs.realtime_decode import decode_trigger_bytes, decode_trigger_event_batch_bytes
from polyester.codecs.scalars import id_to_int
from polyester.codecs.triggers import (
    batch_cancel_triggers_to_proto,
    create_trigger_to_proto,
    modify_trigger_to_proto,
    trigger_type_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1.triggers_connect import TriggersServiceClient
from polyester.gen.triggers.v1.triggers_pb2 import (
    CancelOcoRequest,
    CancelTriggerRequest,
    GetTriggerRequest,
    ListTriggerEventsRequest,
    ListTriggersRequest,
    PauseTriggerRequest,
    ResumeTriggerRequest,
    TriggerEventType,
)
from polyester.models import (
    BatchCancelTriggersResult,
    CancelOcoResult,
    CreateOcoResult,
    RiskLeg,
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
from polyester.services._symbols import (
    display_symbol_for_id,
    resolve_optional_symbol_id,
    resolve_symbol_id,
)
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
        catalogs load. Reads wait for a spot config load in progress, never for
        the funding config.
        """
        return catalog_order_scales(self._catalogs, symbol_id)

    def _symbol(self, symbol_id: int) -> str:
        """The pair's name the loaded catalogs know; ``""`` before they load
        or for a pair they do not list."""
        return display_symbol_for_id(self._catalogs, symbol_id)

    def _decode_trigger(self, payload: bytes) -> Trigger:
        """Decode a trigger stream update with the pair's catalog scales and name."""
        return decode_trigger_bytes(payload, scales=self._order_scales, symbols=self._symbol)

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
        trigger_type: str | None = None,
        parent_order_id: str | int | None = None,
        order_list_id: str | int | None = None,
        client_list_id: str | None = None,
    ) -> TriggersList:
        """List triggers.

        ``status`` accepts one or more of: created, armed, running, completed,
        canceled, failed, paused. Unknown values, ``cancelled`` included, raise
        ``PolyesterValidationError`` before sending.

        ``trigger_type`` keeps one strategy: ``stop_loss``, ``take_profit``,
        ``trailing_stop``, ``twap`` or ``ladder``, the labels
        :meth:`create` takes. ``parent_order_id`` keeps the attached-risk
        triggers of one order (its order ID, base58 or decimal). Either one
        that is not valid raises ``PolyesterValidationError`` before sending;
        left out, the list is not filtered by it.

        ``order_list_id`` keeps the take-profit and the stop-loss of one OCO
        (the ID :meth:`create_oco` returned), and ``client_list_id`` those of
        the OCO created with that client list ID: use it to find an OCO whose
        create raised an error for which ``mutation_outcome_unknown`` is true.
        ``client_list_id`` is 1 to 36 bytes in UTF-8, any characters, and is
        sent unchanged. An ``order_list_id`` of 0, or an empty or longer
        ``client_list_id``, raises ``PolyesterValidationError`` before sending.
        Each trigger reads back its ``order_list_id`` and ``client_list_id``.

        With the catalogs loaded, each trigger's ``symbol`` names its pair.

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
        if trigger_type is not None:
            request.trigger_type = trigger_type_to_proto(trigger_type)
        if parent_order_id is not None:
            parent = id_to_int(parent_order_id, "parent_order_id")
            if parent == 0:
                raise PolyesterValidationError("parent_order_id must be a non-zero order ID")
            request.parent_order_id = parent
        if order_list_id is not None:
            order_list = id_to_int(order_list_id, "order_list_id")
            if order_list == 0:
                raise PolyesterValidationError("order_list_id must be a non-zero OCO ID")
            request.order_list_id = order_list
        if client_list_id is not None:
            request.client_list_id = validate_client_list_id(client_list_id)
        # Decoded with the pair's catalog scales: a load in progress is
        # awaited, and a failed one leaves the quantities unscaled.
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.list_triggers(req),
            request,
            functools.partial(
                triggers_list_from_proto, scales=self._order_scales, symbols=self._symbol
            ),
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

        With the catalogs loaded, the trigger's ``symbol`` names its pair.
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
            functools.partial(
                get_trigger_from_proto, scales=self._order_scales, symbols=self._symbol
            ),
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
        order_type: str | None = None,
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

        ``order_type`` is ``market`` or ``limit``; left out, it is ``market``
        for a stop-loss, take-profit, trailing stop or TWAP. A ladder places
        limit GTC orders only: it takes ``limit`` or no ``order_type``, and any
        other value raises ``PolyesterValidationError`` before sending.

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

    async def create_oco(
        self,
        *,
        account: AccountScope | None = None,
        symbol: str,
        side: str,
        qty: str,
        take_profit: RiskLeg | dict[str, Any],
        stop_loss: RiskLeg | dict[str, Any],
        client_list_id: str | None = None,
        self_trade_prevention_mode: str | None = None,
        sub_account_id: str | int | None = None,
    ) -> CreateOcoResult:
        """Create an OCO (one-cancels-the-other): a take-profit and a stop-loss
        over a quantity the account already holds.

        Both legs trade ``side`` for ``qty``. The quantity is reserved once,
        when the OCO is created, and both legs share it, so it can be sold or
        bought only once. A ``sell`` OCO protects a held base position: its
        take-profit is above the last price and its stop-loss below it. A
        ``buy`` OCO spends held quote: its take-profit is below the last price
        and its stop-loss above it.

        ``take_profit`` and ``stop_loss`` each take a ``RiskLeg`` or a dict, as
        an order's attached take-profit and stop-loss do: ``trigger_price``,
        ``order_type`` (``market``, the default, places a market order (IOC);
        ``limit`` places a resting limit order (GTC) at ``limit_price``) and
        ``trigger_price_source`` (``last``, the default, or ``index``).

        The first leg to reach its trigger price places its order for the
        OCO's remaining quantity. If that order fills only partly, the other
        leg keeps protecting the rest. Cancelling either leg with
        :meth:`cancel`, or the OCO with :meth:`cancel_oco`, cancels both.
        Cancelling all orders and the cancel-all-after timer leave an OCO with
        no working order alone; a leg's working order they cancel cancels the
        OCO. An OCO whose trigger price the last price has already reached is
        accepted, then both legs are rejected with
        ``TRIGGER_WOULD_TRIGGER_IMMEDIATELY``: read the legs for their status.

        ``self_trade_prevention_mode`` is ``expire_taker``, ``expire_maker``
        (the server's default when unset) or ``expire_both``.

        ``client_list_id`` identifies this create: 1 to 36 bytes in UTF-8, any
        characters, sent exactly as given. Left out, the SDK generates one,
        which the result echoes. Both legs read the OCO back on
        ``Trigger.order_list_id`` and ``Trigger.client_list_id``. Sending the
        same create again with the same ``client_list_id`` returns the same
        OCO while it is active and for 60 seconds after both legs end; a
        different create with the same ID is refused
        ``CONFLICT_DUPLICATE_CLIENT_TRIGGER_ID``. A create not confirmed in
        time raises an error for which ``mutation_outcome_unknown`` is true
        (``TRIGGER_CREATE_OUTCOME_UNKNOWN``): the OCO may exist, so look for
        its legs with ``list(client_list_id=...)`` before retrying. An ID you
        choose and keep is what lets you do that, so set one when you may need
        to. An empty one, or one over 36 bytes, raises
        ``PolyesterValidationError`` before sending.
        """
        await self._ensure_catalogs()
        symbol_id: int | None = None
        if self._wait_for_catalogs is not None:
            # The catalogs are loaded: an unknown symbol is refused as unknown,
            # not for its scale. Without hydration the scale is checked first.
            symbol_id = resolve_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=None, label="triggers.create_oco"
            )
        scale = resolve_quantity_scale(self._catalogs, symbol, qty)
        if symbol_id is None:
            symbol_id = resolve_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=None, label="triggers.create_oco"
            )
        request = create_oco_to_proto(
            symbol=symbol,
            symbol_id=symbol_id,
            side=side,
            qty=qty,
            take_profit=take_profit,
            stop_loss=stop_loss,
            quantity_scale=scale,
            client_list_id=client_list_id,
            self_trade_prevention_mode=self_trade_prevention_mode,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
        )
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.create_oco(req),
            request,
            create_oco_from_proto,
        )

    async def cancel_oco(
        self,
        *,
        account: AccountScope | None = None,
        order_list_id: str | int,
        sub_account_id: str | int | None = None,
    ) -> CancelOcoResult:
        """Cancel an OCO by the ``order_list_id`` :meth:`create_oco` returned.

        Both legs end canceled and the OCO's reserved quantity is released. An
        ID that is not an OCO of the account, such as a trigger ID or a leg's
        ID, is refused ``TRIGGER_NOT_FOUND`` and nothing is canceled. An OCO
        that has already ended is refused ``TRIGGER_STATUS_INVALID``.
        """
        request = CancelOcoRequest(order_list_id=id_to_int(order_list_id, "order_list_id"))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.cancel_oco(req),
            request,
            cancel_oco_from_proto,
        )

    async def batch_cancel(
        self,
        *,
        account: AccountScope | None = None,
        trigger_ids: Sequence[str | int],
        sub_account_id: str | int | None = None,
        request_id: str | None = None,
    ) -> BatchCancelTriggersResult:
        """Cancel up to 50 triggers in one request.

        Each trigger is canceled as :meth:`cancel` cancels it (a TWAP's or
        ladder's open child orders with it) and answered on its own in
        ``results``, in the order of ``trigger_ids``: ``accepted``, and the
        trigger's events report when it is canceled, or ``rejected`` with a
        ``code``. One item's rejection does not stop the others.
        ``TRIGGER_NOT_FOUND`` names an ID that is none of the account's
        triggers, and ``TRIGGER_STATUS_INVALID`` a trigger that has already
        ended: treat it as done. Retry an item rejected
        ``RATE_LIMIT_EXCEEDED``, ``PAIR_BACKLOGGED`` or
        ``TRIGGER_CONTROL_IN_PROGRESS`` in a new request with a new
        ``request_id``. Each trigger counts one against the account's cancel
        rate limit, as a :meth:`cancel` does.

        ``trigger_ids`` takes 1 to 50 distinct trigger IDs; cancel more with
        further requests. An empty, longer or repeating list, or an ID of 0,
        raises ``PolyesterValidationError`` before sending.

        ``request_id`` identifies the request for 2 minutes: sending the same
        ``trigger_ids`` again with it returns the original results and cancels
        nothing again, so retry a request that timed out unchanged. The same
        ``request_id`` with other ``trigger_ids`` rejects every item with
        ``CONFLICT_IDEMPOTENCY_KEY_REUSE``. Left out or empty, the SDK
        generates one; set one you keep when you may need to retry.
        """
        request = batch_cancel_triggers_to_proto(
            trigger_ids=trigger_ids,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
        )
        return await unary_auth_decoded(
            self._transport,
            TriggersServiceClient,
            lambda client, req: client.batch_cancel_triggers(req),
            request,
            batch_cancel_triggers_from_proto,
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
        it. ``max_slippage_bps`` is 1 to 10000, as at creation: a buy
        stop-loss or take-profit with a market child accepts 10000, and the
        server refuses it for a sell or a trailing stop
        (``MAX_SLIPPAGE_INVALID``). ``0`` clears a cap (ticks or bps) and a
        market child falls back to the pair's default slippage.
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
            decode=self._decode_trigger,
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
