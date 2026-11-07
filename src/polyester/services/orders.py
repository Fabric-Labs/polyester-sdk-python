from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import msgspec

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import (
    batch_cancel_from_proto,
    batch_create_from_proto,
    batch_replace_from_proto,
    batch_replace_status_from_proto,
    cancel_all_after_from_proto,
    cancel_all_from_proto,
    get_order_from_proto,
    modify_order_from_proto,
    order_mutation_from_proto,
    orders_list_from_proto,
    preview_order_from_proto,
)
from polyester.codecs.orders import (
    batch_cancel_orders_to_proto,
    batch_create_orders_to_proto,
    batch_replace_orders_to_proto,
    cancel_all_after_to_proto,
    cancel_all_orders_to_proto,
    create_order_to_proto,
    modify_order_to_proto,
    normalize_create_order_request,
    parse_optional_subaccount_id,
    preview_order_to_proto,
    resolve_quantity_scale,
    resolve_quote_quantity_scale,
    set_order_key,
)
from polyester.codecs.scalars import id_to_int
from polyester.errors import (
    PolyesterApiError,
    PolyesterBatchReplaceTimeoutError,
    PolyesterRateLimitError,
    PolyesterResponseContractError,
    PolyesterServerError,
    PolyesterTransportError,
    PolyesterValidationError,
    is_not_found,
)
from polyester.gen.orders.v1.orders_connect import OrdersServiceClient
from polyester.gen.orders.v1.orders_pb2 import CancelOrderRequest
from polyester.gen.orders.v1.orders_read_connect import OrdersReadServiceClient
from polyester.gen.orders.v1.orders_read_pb2 import (
    GetBatchReplaceStatusRequest,
    GetOpenOrdersRequest,
    GetOrderHistoryRequest,
    GetOrderRequest,
)
from polyester.models import (
    AttachedRisk,
    BatchCancelOrdersResult,
    BatchCreateOrdersResult,
    BatchReplaceItem,
    BatchReplaceOrdersResult,
    BatchReplaceStatusResult,
    CancelAllAfterResult,
    CancelAllOrdersResult,
    CreateOrderRequest,
    GetOrderResult,
    ModifyOrderResult,
    OrderId,
    OrderKey,
    OrderMutationResult,
    OrdersList,
    PreviewOrderResult,
    StopAllTradingResult,
    StopAllTradingTriggerFailure,
)
from polyester.models.private_orders import PrivateOrdersEvent
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import require_realtime
from polyester.services._scope import AccountScope, ScopedSubAccountMixin, resolve_account_id
from polyester.services._symbols import (
    resolve_cancel_all_symbol_ids,
    resolve_optional_symbol_id,
    resolve_order_identity,
    resolve_symbol_id,
)
from polyester.services._validation import validate_limit
from polyester.types import Quantity

if TYPE_CHECKING:
    from polyester.services.triggers import AsyncTriggersService

# Trigger statuses a trigger can still fire from; stop_all_trading cancels them.
LIVE_TRIGGER_STATUSES = ("created", "armed", "running", "paused")
_STOP_ALL_TRIGGERS_PAGE = 1000

# GetBatchReplaceStatus keeps a batch's status this long from acceptance.
BATCH_REPLACE_STATUS_WINDOW_SECONDS = 60.0
_BATCH_REPLACE_POLL_INITIAL = 0.05
_BATCH_REPLACE_POLL_MAX = 0.5


class AsyncOrdersService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager,
        default_sub_account_id: str | None,
        *,
        default_account_id: str | int | None = None,
        realtime: AsyncRealtimeClient | None = None,
        wait_for_catalogs: Callable[[], Awaitable[None]] | None = None,
        triggers: AsyncTriggersService | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime
        self._wait_for_catalogs = wait_for_catalogs
        self._triggers = triggers

    async def _ensure_catalogs(self) -> None:
        if self._wait_for_catalogs is not None:
            await self._wait_for_catalogs()

    async def list_open(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        page_token: str | None = None,
        limit: int | None = None,
        include_attached_risk: bool = False,
        include_attached_risk_state: bool = False,
        trigger_id: str | int | None = None,
    ) -> OrdersList:
        """List open orders.

        When ``trigger_id`` is set, only child orders created by that trigger
        are returned (for example TWAP/ladder slice children).
        """
        validated_limit = validate_limit(limit, allow_none=True)
        request = GetOpenOrdersRequest(
            include_attached_risk=include_attached_risk,
            include_attached_risk_state=include_attached_risk_state,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if page_token:
            request.page_token = page_token
        if validated_limit is not None:
            request.limit = validated_limit
        if trigger_id is not None and trigger_id != "":
            request.trigger_id = id_to_int(trigger_id, "trigger_id")
        return await unary_auth_decoded(
            self._transport,
            OrdersReadServiceClient,
            lambda client, req: client.get_open_orders(req),
            request,
            orders_list_from_proto,
        )

    async def list_history(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        page_token: str | None = None,
        limit: int = 100,
        include_attached_risk: bool = False,
        include_attached_risk_state: bool = False,
        trigger_id: str | int | None = None,
    ) -> OrdersList:
        """List order history.

        When ``trigger_id`` is set, only child orders created by that trigger
        are returned (for example TWAP/ladder slice children).
        """
        validated_limit = validate_limit(limit)
        request = GetOrderHistoryRequest(
            limit=validated_limit,
            include_attached_risk=include_attached_risk,
            include_attached_risk_state=include_attached_risk_state,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if symbol_id is not None:
            request.symbol_id.append(symbol_id)
        elif symbol:
            resolved = resolve_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=None, label="list_history"
            )
            request.symbol_id.append(resolved)
        if page_token:
            request.page_token = page_token
        if trigger_id is not None and trigger_id != "":
            request.trigger_id = id_to_int(trigger_id, "trigger_id")
        return await unary_auth_decoded(
            self._transport,
            OrdersReadServiceClient,
            lambda client, req: client.get_order_history(req),
            request,
            orders_list_from_proto,
        )

    async def get(
        self,
        *,
        key: OrderKey,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        include_attached_risk: bool = False,
        include_attached_risk_state: bool = False,
        include_execution_history: bool | None = None,
        limit: int | None = None,
        page_token: str | None = None,
    ) -> GetOrderResult:
        """Fetch one order and an optional page of lineage execution history.

        Execution history is enabled by default on the server. Pass
        ``include_execution_history=False`` for state-only polling and omit
        ``limit`` / ``page_token``. Continue pagination with the same physical
        ``order_id`` and ``next_page_token``. An empty page is not a
        settlement watermark; ``cum_qty`` / ``avg_px`` are lineage-cumulative.
        """
        if include_execution_history is False and (
            limit is not None or (page_token is not None and page_token != "")
        ):
            raise PolyesterValidationError(
                "orders.get limit and page_token require include_execution_history"
            )
        request = GetOrderRequest(
            include_attached_risk=include_attached_risk,
            include_attached_risk_state=include_attached_risk_state,
        )
        if include_execution_history is not None:
            request.include_execution_history = include_execution_history
        validated_limit = validate_limit(limit, allow_none=True)
        if validated_limit is not None:
            request.limit = validated_limit
        if page_token:
            request.page_token = page_token
        set_order_key(request, key, op="get")
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            OrdersReadServiceClient,
            lambda client, req: client.get_order(req),
            request,
            get_order_from_proto,
        )

    async def create(
        self,
        request: CreateOrderRequest | None = None,
        *,
        account: str | dict[str, str] | None = None,
        **kwargs: Any,
    ) -> OrderMutationResult:
        """Create an order.

        ``client_order_id`` is optional. Set a stable non-empty value so you
        can reconcile after an ambiguous failure. Look up that id before
        creating again; a second create with the same id is a conflict if the
        first attempt admitted.
        """
        normalized = normalize_create_order_request(request, **kwargs)
        normalized = msgspec.structs.replace(
            normalized,
            sub_account_id=self._resolve_sub_account_id(normalized.sub_account_id, account=account),
        )
        await self._ensure_catalogs()
        canonical_symbol, symbol_id = resolve_order_identity(
            self._catalogs,
            symbol=normalized.symbol,
            symbol_id=normalized.symbol_id,
            label="orders.create",
        )
        quantity_scale = resolve_quantity_scale(
            self._catalogs, normalized.symbol, normalized.qty, symbol_id=symbol_id
        )
        quote_quantity_scale = resolve_quote_quantity_scale(
            self._catalogs, normalized.symbol, normalized.max_quote_debit, symbol_id=symbol_id
        )
        normalized = msgspec.structs.replace(
            normalized, symbol_id=symbol_id, symbol=canonical_symbol
        )
        proto_request = create_order_to_proto(
            normalized,
            quantity_scale=quantity_scale,
            quote_quantity_scale=quote_quantity_scale,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.create_order(req),
            proto_request,
            lambda response: order_mutation_from_proto(response, quantity_scale=quantity_scale),
        )

    async def preview_order(
        self,
        request: CreateOrderRequest | None = None,
        *,
        account: str | dict[str, str] | None = None,
        **kwargs: Any,
    ) -> PreviewOrderResult:
        """Check current order admissibility without creating an order.

        Returns resolved base size and protected price bound when available.
        Does not return fee or quote-debit estimates. Accepts the same public
        create shape; the wire request wraps an ``OrderIntent``.
        """
        normalized = normalize_create_order_request(request, **kwargs)
        normalized = msgspec.structs.replace(
            normalized,
            sub_account_id=self._resolve_sub_account_id(normalized.sub_account_id, account=account),
        )
        await self._ensure_catalogs()
        canonical_symbol, symbol_id = resolve_order_identity(
            self._catalogs,
            symbol=normalized.symbol,
            symbol_id=normalized.symbol_id,
            label="orders.preview",
            require_catalog=False,
        )
        # The response uses the canonical pair's scale, even for a scaled input.
        quantity_scale = self._catalogs.base_quantity_scale_for_symbol_id(symbol_id)
        if quantity_scale is None:
            if isinstance(normalized.qty, Quantity) and normalized.qty.scale is not None:
                quantity_scale = normalized.qty.scale
            else:
                raise PolyesterValidationError(
                    "preview quantity scale is unavailable; hydrate catalogs or pass "
                    "a Quantity with an explicit scale"
                )
        scale_symbol = self._catalogs.symbol_for_symbol_id(symbol_id)
        quote_quantity_scale = resolve_quote_quantity_scale(
            self._catalogs, scale_symbol, normalized.max_quote_debit
        )
        normalized = msgspec.structs.replace(
            normalized, symbol_id=symbol_id, symbol=canonical_symbol
        )
        proto_request = preview_order_to_proto(
            normalized,
            quantity_scale=quantity_scale,
            quote_quantity_scale=quote_quantity_scale,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.preview_order(req),
            proto_request,
            lambda response: preview_order_from_proto(
                response,
                quantity_scale=quantity_scale,
                symbol=normalized.symbol,
                symbol_id=symbol_id,
            ),
        )

    async def cancel(
        self,
        *,
        key: OrderKey,
        account: AccountScope | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        sub_account_id: str | None = None,
    ) -> OrderMutationResult:
        """Cancel one order.

        A cancel of an order that has already ended, by an earlier cancel
        (this one repeated) or otherwise, raises :class:`PolyesterApiError`
        ``ERROR_CODE_ORDER_ALREADY_TERMINAL``; :func:`is_order_already_terminal`
        tells it apart from other refusals. Treat it as "already done" and read
        the order for how it ended. A client order ID names its order for at
        least a minute after the order ends; after that a retry by client
        order ID may read ``ERROR_CODE_ORDER_UNKNOWN``, so retry by order ID
        once you have it. Every cancel, a repeat included, counts against the
        cancel rate limit.
        """
        if symbol is not None and symbol_id is not None:
            raise PolyesterValidationError("cancel accepts only one of symbol or symbol_id")
        if symbol is not None:
            symbol_id = resolve_symbol_id(
                self._catalogs,
                symbol=symbol,
                symbol_id=None,
                label="cancel",
            )
        request = CancelOrderRequest()
        set_order_key(request, key, op="cancel")
        if symbol_id is not None:
            request.symbol_id = symbol_id
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.cancel_order(req),
            request,
            order_mutation_from_proto,
        )

    async def modify(
        self,
        *,
        key: OrderKey,
        symbol: str,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        request_id: str | None = None,
        new_price: object | None = None,
        new_qty: object | None = None,
        new_attached_risk: dict | AttachedRisk | None = None,
        behavior: str | None = None,
        new_client_order_id: str | None = None,
    ) -> ModifyOrderResult:
        await self._ensure_catalogs()
        scale = resolve_quantity_scale(self._catalogs, symbol, new_qty)
        proto_request = modify_order_to_proto(
            symbol=symbol,
            symbol_id=resolve_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=None, label="orders.modify"
            ),
            key=key,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
            new_price=new_price,
            new_qty=new_qty,
            new_attached_risk=new_attached_risk,
            behavior=behavior,
            new_client_order_id=new_client_order_id,
            quantity_scale=scale,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.modify_order(req),
            proto_request,
            modify_order_from_proto,
        )

    async def cancel_all(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        symbol: str | None = None,
        symbols: list[str] | None = None,
        symbol_ids: list[int] | None = None,
        side: str | None = None,
        dry_run: bool = False,
        request_id: str | None = None,
    ) -> CancelAllOrdersResult:
        if symbol or symbols:
            await self._ensure_catalogs()
        proto_request = cancel_all_orders_to_proto(
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            symbol_ids=resolve_cancel_all_symbol_ids(
                self._catalogs,
                symbol=symbol,
                symbols=symbols,
                symbol_ids=symbol_ids,
                label="orders.cancel_all",
            ),
            side=side,
            dry_run=dry_run,
            request_id=request_id,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.cancel_all_orders(req),
            proto_request,
            cancel_all_from_proto,
        )

    async def stop_all_trading(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        symbol: str | None = None,
        request_id: str | None = None,
    ) -> StopAllTradingResult:
        """Cancel every live trigger, then every open order.

        Cancel-all and the dead-man switch cancel open orders only, never
        triggers: an armed stop still fires later. This lists the live
        triggers (``created``, ``armed``, ``running``, ``paused``; attached legs
        included) page by page, cancels each, and only then calls
        :meth:`cancel_all`, so an order a trigger places before its cancel is
        still canceled. ``symbol`` limits both steps to one market.

        An error while listing the triggers is raised before anything is
        canceled. A trigger whose cancel fails, for any reason, is recorded in
        ``trigger_failures`` with its error; the other triggers are still
        canceled and the cancel-all still runs. An error from the cancel-all
        itself is raised.
        """
        if self._triggers is None:
            raise PolyesterValidationError("stop_all_trading needs the client's triggers service")
        scope = self._resolve_sub_account_id(sub_account_id, account=account)
        explicit_scope = scope if scope is not None else ""
        trigger_ids: list[str] = []
        seen_tokens: set[str] = set()
        page_token: str | None = None
        while True:
            page = await self._triggers.list(
                sub_account_id=explicit_scope,
                symbol=symbol,
                status=LIVE_TRIGGER_STATUSES,
                limit=_STOP_ALL_TRIGGERS_PAGE,
                page_token=page_token,
            )
            trigger_ids.extend(t.trigger_id for t in page.triggers if t.trigger_id)
            if not page.next_page_token:
                break
            if page.next_page_token in seen_tokens:
                raise PolyesterResponseContractError(
                    "ListTriggers", "next_page_token repeats an earlier page"
                )
            seen_tokens.add(page.next_page_token)
            page_token = page.next_page_token
        canceled: list[str] = []
        failures: list[StopAllTradingTriggerFailure] = []
        for trigger_id in dict.fromkeys(trigger_ids):
            try:
                await self._triggers.cancel(trigger_id=trigger_id, sub_account_id=explicit_scope)
            except Exception as exc:
                failures.append(StopAllTradingTriggerFailure(trigger_id=trigger_id, error=exc))
                continue
            canceled.append(trigger_id)
        cancel_all = await self.cancel_all(
            sub_account_id=explicit_scope,
            symbol=symbol,
            request_id=request_id,
        )
        return StopAllTradingResult(
            canceled_trigger_ids=canceled,
            trigger_failures=failures,
            cancel_all=cancel_all,
        )

    async def batch_replace(
        self,
        *,
        account: AccountScope | None = None,
        items: list[BatchReplaceItem | dict],
        sub_account_id: str | None = None,
        symbol: str,
        request_id: str | None = None,
    ) -> BatchReplaceOrdersResult:
        await self._ensure_catalogs()
        symbol_id = resolve_symbol_id(
            self._catalogs, symbol=symbol, symbol_id=None, label="batch_replace"
        )
        scale = resolve_quantity_scale(
            self._catalogs,
            symbol,
            *(
                item.new_qty if isinstance(item, BatchReplaceItem) else item.get("new_qty")
                for item in items
            ),
        )
        proto_request = batch_replace_orders_to_proto(
            items=items,
            symbol_id=symbol_id,
            symbol=symbol,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
            quantity_scale=scale,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.batch_replace_orders(req),
            proto_request,
            batch_replace_from_proto,
        )

    async def get_batch_replace_status(
        self,
        *,
        batch_request_id: str,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
    ) -> BatchReplaceStatusResult:
        request = GetBatchReplaceStatusRequest(
            batch_request_id=id_to_int(batch_request_id, "batch_request_id")
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            OrdersReadServiceClient,
            lambda client, req: client.get_batch_replace_status(req),
            request,
            batch_replace_status_from_proto,
        )

    async def wait_batch_replace(
        self,
        *,
        batch_request_id: str,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        timeout: float | None = None,
    ) -> BatchReplaceStatusResult:
        """Poll :meth:`get_batch_replace_status` until no item is ``admitted``.

        Returns the first status whose items are all ``working``, ``rejected``
        or ``terminal``. A ``rejected`` item changed nothing: its order keeps
        ``old_order_id`` and its previous price and quantity, and
        ``error_code`` names the refusal as a single modify would raise it
        (for example ``ERROR_CODE_POST_ONLY_CROSS``).

        Polls start 50 ms apart and back off to 500 ms. The status appears a
        few seconds after admission, so ``not_found`` keeps polling, as do
        ``unavailable``, other server errors and network errors. The server
        keeps a batch's status for 60 seconds from acceptance, so the wait
        ends there, or after ``timeout`` seconds when that comes first, even
        during a read, with
        :class:`~polyester.errors.PolyesterBatchReplaceTimeoutError` carrying
        the last status read: a ``not_found`` proves nothing, so reconcile the
        orders themselves. Other errors, rate limits included, are raised as
        they come; cancelling the call cancels it.
        """
        request = GetBatchReplaceStatusRequest(
            batch_request_id=id_to_int(batch_request_id, "batch_request_id")
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        started = time.monotonic()
        deadline = started + BATCH_REPLACE_STATUS_WINDOW_SECONDS
        if timeout is not None:
            deadline = min(deadline, started + max(timeout, 0.0))
        window_known = False
        delay = _BATCH_REPLACE_POLL_INITIAL
        last: BatchReplaceStatusResult | None = None

        def expired(cause: BaseException | None = None) -> PolyesterBatchReplaceTimeoutError:
            error = PolyesterBatchReplaceTimeoutError(
                f"batch replace {batch_request_id} has no settled status by the end "
                "of its status window; reconcile the orders with order reads",
                batch_request_id=batch_request_id,
                last_status=last,
            )
            error.__cause__ = cause
            return error

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise expired()
            # The deadline also bounds a read in flight.
            read_deadline = asyncio.timeout(remaining)
            try:
                async with read_deadline:
                    current = await unary_auth_decoded(
                        self._transport,
                        OrdersReadServiceClient,
                        lambda client, req: client.get_batch_replace_status(req),
                        request,
                        batch_replace_status_from_proto,
                    )
            except Exception as exc:
                if read_deadline.expired():
                    raise expired(exc) from exc
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    # connectrpc reports a cancelled request as an error;
                    # the caller cancelled, so cancel.
                    raise asyncio.CancelledError() from exc
                if not _is_transient_status_read_error(exc):
                    raise
            else:
                last = current
                if is_batch_replace_settled(last):
                    return last
                if not window_known and last.accepted_ts_ns:
                    # The window runs from acceptance; never extend it past
                    # 60 s from the first read when clocks disagree.
                    window_known = True
                    left = (
                        last.accepted_ts_ns / 1e9
                        + BATCH_REPLACE_STATUS_WINDOW_SECONDS
                        - time.time()
                    )
                    deadline = min(deadline, time.monotonic() + max(left, 0.0))
            await asyncio.sleep(max(min(delay, deadline - time.monotonic()), 0.0))
            delay = min(delay * 2, _BATCH_REPLACE_POLL_MAX)

    async def batch_create(
        self,
        *,
        account: AccountScope | None = None,
        items: list[CreateOrderRequest | dict[str, Any]],
        sub_account_id: str | None = None,
        symbol: str | None = None,
        request_id: str | None = None,
        allow_partial: bool = False,
    ) -> BatchCreateOrdersResult:
        await self._ensure_catalogs()
        resolved_items: list[CreateOrderRequest] = []
        item_scales: list[tuple[int, int]] = []
        for item in items:
            normalized = (
                item
                if isinstance(item, CreateOrderRequest)
                else normalize_create_order_request(item)
            )
            canonical_symbol, symbol_id = resolve_order_identity(
                self._catalogs,
                symbol=(
                    normalized.symbol
                    if normalized.symbol_id is not None
                    else normalized.symbol or symbol
                ),
                symbol_id=normalized.symbol_id,
                label="batch_create",
            )
            item_scales.append(
                (
                    resolve_quantity_scale(
                        self._catalogs, normalized.symbol, normalized.qty, symbol_id=symbol_id
                    ),
                    resolve_quote_quantity_scale(
                        self._catalogs,
                        normalized.symbol,
                        normalized.max_quote_debit,
                        symbol_id=symbol_id,
                    ),
                )
            )
            resolved_items.append(
                msgspec.structs.replace(normalized, symbol_id=symbol_id, symbol=canonical_symbol)
            )
        proto_request = batch_create_orders_to_proto(
            items=resolved_items,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
            allow_partial=allow_partial,
            item_scales=item_scales,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.batch_create_orders(req),
            proto_request,
            batch_create_from_proto,
        )

    async def batch_cancel(
        self,
        *,
        account: AccountScope | None = None,
        items: list[dict],
        sub_account_id: str | None = None,
        request_id: str | None = None,
    ) -> BatchCancelOrdersResult:
        proto_request = batch_cancel_orders_to_proto(
            items=items,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.batch_cancel_orders(req),
            proto_request,
            batch_cancel_from_proto,
        )

    async def cancel_all_after(
        self,
        *,
        account: AccountScope | None = None,
        timeout_sec: int,
        sub_account_id: str | None = None,
        symbol: str | None = None,
        side: str | None = None,
        request_id: str | None = None,
    ) -> CancelAllAfterResult:
        if symbol:
            await self._ensure_catalogs()
        proto_request = cancel_all_after_to_proto(
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            timeout_sec=timeout_sec,
            symbol_id=resolve_optional_symbol_id(
                self._catalogs, symbol=symbol, label="orders.cancel_all_after symbol"
            ),
            side=side,
            request_id=request_id,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.cancel_all_after(req),
            proto_request,
            cancel_all_after_from_proto,
        )

    async def subscribe(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[PrivateOrdersEvent]:
        """Stream an account's live orders over the private WebSocket.

        Returns once the server confirmed the subscription. Iterate the
        events: ``PrivateOrdersSnapshot`` (the full live view; replace local
        state), ``PrivateOrdersUnit`` (changed orders, removed order IDs and
        order events), ``PrivateOrdersReady`` (the stream reflects every order
        read made before the subscribe; wait for it before relying on the
        stream), ``PrivateOrdersStale``, ``PrivateOrdersConnected``,
        ``PrivateOrdersDisconnected`` and ``PrivateOrdersError``. Orders are
        the same ``Order`` model the reads return; keep the copy with the
        higher ``version``. Gaps, expired tokens and reconnects resume from
        the last applied position automatically. A failure that ends the
        stream (for example a refused token) is raised from iteration.
        """
        client = require_realtime(self._realtime)
        resolved = resolve_account_id(account_id, self._default_account_id)
        return await client.subscribe_private_orders(resolved)

    async def wait_for_order_trades_complete(
        self,
        *,
        key: OrderKey,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        timeout: float = 10.0,
        poll_interval: float = 0.1,
    ) -> GetOrderResult:
        """Poll ``get`` until projected trade qtys sum to order ``cum_qty`` or timeout.

        GetOrder can report lineage-cumulative ``cum_qty`` before every fill is
        visible on the trades list (eventual consistency). This helper pages
        execution history and does not treat an empty page as a watermark.
        The result holds the last poll's order, trades and transfers, with that
        read's ``executions_complete``.

        ``timeout`` (seconds) bounds the whole wait, page reads included: a read
        still in flight when it passes is abandoned and
        ``PolyesterTransportError`` is raised; a timeout of 0 or less times out
        before any read. A ``next_page_token`` that repeats a page token of the
        same poll raises ``PolyesterResponseContractError``.
        """
        return await wait_for_order_trades_complete(
            self,
            key=key,
            account=account,
            sub_account_id=sub_account_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )


async def wait_for_order_trades_complete(
    orders: AsyncOrdersService,
    *,
    key: OrderKey,
    account: AccountScope | None = None,
    sub_account_id: str | None = None,
    timeout: float = 10.0,
    poll_interval: float = 0.1,
) -> GetOrderResult:
    """Poll until ``sum(trade.qty) == order.cum_qty`` or ``timeout`` elapses.

    One deadline bounds every page read and every sleep between polls.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(timeout, 0.0)

    def timed_out() -> PolyesterTransportError:
        return PolyesterTransportError(
            f"timed out waiting for order trades to match cum_qty (key={key!r})"
        )

    while True:
        if loop.time() >= deadline:
            raise timed_out()
        budget = asyncio.timeout_at(deadline)
        try:
            async with budget:
                last = await _get_order_execution_pages(
                    orders,
                    key=key,
                    account=account,
                    sub_account_id=sub_account_id,
                )
        except Exception as exc:
            # The transport can report the read the deadline cut short as its
            # own error rather than as a cancellation.
            if budget.expired():
                raise timed_out() from exc
            raise
        if _order_trades_projection_complete(last):
            return last
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise timed_out()
        await asyncio.sleep(min(max(poll_interval, 0.0), remaining))


async def _get_order_execution_pages(
    orders: AsyncOrdersService,
    *,
    key: OrderKey,
    account: AccountScope | None = None,
    sub_account_id: str | None = None,
) -> GetOrderResult:
    """Read one order with every page of its execution history: the order, the
    trades and transfers of all pages, and the final page's
    ``executions_complete``."""
    page_token: str | None = None
    requested: set[str] = set()
    trades: list = []
    transfers: list = []
    order = None
    while True:
        page = await orders.get(
            key=key,
            account=account,
            sub_account_id=sub_account_id,
            include_execution_history=True,
            page_token=page_token,
        )
        if page.order is not None:
            if page.order.order_id:
                key = OrderId(page.order.order_id)
            order = page.order
        trades.extend(page.trades)
        transfers.extend(page.transfers)
        if not page.next_page_token:
            return GetOrderResult(
                order=order,
                trades=trades,
                transfers=transfers,
                next_page_token="",
                executions_complete=page.executions_complete,
            )
        if page.next_page_token in requested:
            raise PolyesterResponseContractError(
                "GetOrder", "next_page_token repeats an earlier page token"
            )
        requested.add(page.next_page_token)
        page_token = page.next_page_token


def _order_trades_projection_complete(result: GetOrderResult) -> bool:
    order = result.order
    if order is None or order.cum_qty is None:
        return False
    cum = order.cum_qty.scaled
    if cum == 0:
        return True
    trade_sum = 0
    for trade in result.trades:
        if trade.qty is None:
            return False
        trade_sum += trade.qty.scaled
    return trade_sum == cum


def _is_transient_status_read_error(exc: BaseException) -> bool:
    """A status read error worth polling through: the status is not written
    yet (``not_found``), or the server or network failed for now. Rate limits
    are raised to the caller."""
    # This operation only reads status, so an ambiguous gateway timeout is safe
    # to poll through even though its general mutation retry flag is false.
    if isinstance(exc, PolyesterRateLimitError):
        return False
    if is_not_found(exc) or isinstance(exc, (PolyesterServerError, PolyesterTransportError)):
        return True
    return isinstance(exc, PolyesterApiError) and exc.code in (
        "AUTH_TEMPORARILY_UNAVAILABLE",
        "ERROR_CODE_ACCOUNT_REPAIRING",
    )


def is_batch_replace_settled(status: BatchReplaceStatusResult) -> bool:
    """Whether every replacement has left admission and reached a stable phase.

    ``terminal`` means the successor's lifecycle is terminal, not necessarily
    that the original replacement request failed. Poll status to reconcile
    predecessor/successor IDs and phases; do not infer finality from admission.
    """
    return bool(status.items) and all(
        item.phase in {"working", "rejected", "terminal"} for item in status.items
    )
