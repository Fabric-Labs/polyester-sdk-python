from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import (
    batch_cancel_from_proto,
    batch_create_from_proto,
    batch_modify_from_proto,
    cancel_all_after_from_proto,
    cancel_all_from_proto,
    get_order_from_proto,
    modify_order_from_proto,
    order_mutation_from_proto,
    orders_list_from_proto,
)
from polyester.codecs.orders import (
    batch_cancel_orders_to_proto,
    batch_create_orders_to_proto,
    batch_modify_orders_to_proto,
    cancel_all_after_to_proto,
    cancel_all_orders_to_proto,
    create_order_to_proto,
    modify_order_to_proto,
    normalize_create_order_request,
    parse_optional_subaccount_id,
    resolve_quantity_scale,
)
from polyester.codecs.realtime_decode import decode_order_bytes
from polyester.codecs.scalars import id_to_int
from polyester.errors import PolyesterTransportError, PolyesterValidationError
from polyester.gen.orders.v1.orders_connect import OrdersServiceClient
from polyester.gen.orders.v1.orders_pb2 import CancelOrderRequest
from polyester.gen.orders.v1.orders_read_connect import OrdersReadServiceClient
from polyester.gen.orders.v1.orders_read_pb2 import (
    GetOpenOrdersRequest,
    GetOrderHistoryRequest,
    GetOrderRequest,
)
from polyester.models import (
    BatchCancelOrdersResult,
    BatchCreateOrdersResult,
    BatchModifyOrdersResult,
    CancelAllAfterResult,
    CancelAllOrdersResult,
    CreateOrderRequest,
    GetOrderResult,
    ModifyOrderResult,
    Order,
    OrderMutationResult,
    OrdersList,
)
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._symbols import resolve_symbol_id


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
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime
        self._wait_for_catalogs = wait_for_catalogs

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
    ) -> OrdersList:
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
        if limit is not None:
            request.limit = limit
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
    ) -> OrdersList:
        request = GetOrderHistoryRequest(
            limit=limit,
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
        account: AccountScope | None = None,
        order_id: str | int | None = None,
        client_order_id: str | None = None,
        sub_account_id: str | None = None,
        include_attached_risk: bool = False,
        include_attached_risk_state: bool = False,
    ) -> GetOrderResult:
        if order_id is None and client_order_id is None:
            raise ValueError("get requires order_id or client_order_id")
        request = GetOrderRequest(
            include_attached_risk=include_attached_risk,
            include_attached_risk_state=include_attached_risk_state,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if order_id is not None:
            request.order_id = id_to_int(order_id, "order_id")
        if client_order_id:
            request.client_order_id = client_order_id
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
        if account is not None:
            kwargs = {
                **kwargs,
                "sub_account_id": self._resolve_sub_account_id(account=account),
            }
        normalized = normalize_create_order_request(request, **kwargs)
        if normalized.sub_account_id is None:
            resolved_sub = self._resolve_sub_account_id(None)
            if resolved_sub is not None:
                normalized = CreateOrderRequest(
                    symbol=normalized.symbol,
                    symbol_id=normalized.symbol_id,
                    side=normalized.side,
                    order_type=normalized.order_type,
                    tif=normalized.tif,
                    qty=normalized.qty,
                    price=normalized.price,
                    sub_account_id=resolved_sub,
                    client_order_id=normalized.client_order_id,
                    post_only=normalized.post_only,
                    expires_at=normalized.expires_at,
                    attached_risk=normalized.attached_risk,
                    market_client_ref_price=normalized.market_client_ref_price,
                )
        await self._ensure_catalogs()
        quantity_scale = resolve_quantity_scale(
            self._catalogs, normalized.symbol, normalized.qty
        )
        proto_request = create_order_to_proto(normalized, quantity_scale=quantity_scale)
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.create_order(req),
            proto_request,
            order_mutation_from_proto,
        )

    async def cancel(
        self,
        *,
        account: AccountScope | None = None,
        order_id: str | int | None = None,
        client_order_id: str | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        sub_account_id: str | None = None,
    ) -> OrderMutationResult:
        if order_id is None and client_order_id is None:
            raise ValueError("cancel requires order_id or client_order_id")
        if symbol_id is None and symbol:
            symbol_id = self._catalogs.symbol_id_for_symbol(symbol)
        request = CancelOrderRequest()
        if order_id is not None:
            request.order_id = id_to_int(order_id, "order_id")
        if client_order_id:
            request.client_order_id = client_order_id
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
        account: AccountScope | None = None,
        symbol: str,
        order_id: str | int | None = None,
        client_order_id: str | None = None,
        sub_account_id: str | None = None,
        request_id: str | None = None,
        new_price: object | None = None,
        new_qty: object | None = None,
        new_attached_risk: dict | None = None,
        behavior: str | None = None,
        new_client_order_id: str | None = None,
    ) -> ModifyOrderResult:
        await self._ensure_catalogs()
        scale = resolve_quantity_scale(self._catalogs, symbol, new_qty)
        proto_request = modify_order_to_proto(
            symbol=symbol,
            order_id=order_id,
            client_order_id=client_order_id,
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
        side: str | None = None,
        dry_run: bool = False,
        request_id: str | None = None,
    ) -> CancelAllOrdersResult:
        proto_request = cancel_all_orders_to_proto(
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            symbol=symbol,
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

    async def batch_modify(
        self,
        *,
        account: AccountScope | None = None,
        items: list[dict],
        sub_account_id: str | None = None,
        symbol: str | None = None,
        request_id: str | None = None,
        behavior_default: str | None = None,
        allow_partial: bool = False,
    ) -> BatchModifyOrdersResult:
        await self._ensure_catalogs()
        scale = resolve_quantity_scale(
            self._catalogs,
            symbol,
            *(item.get("new_qty") for item in items),
        )
        proto_request = batch_modify_orders_to_proto(
            items=items,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
            behavior_default=behavior_default,
            allow_partial=allow_partial,
            quantity_scale=scale,
        )
        return await unary_auth_decoded(
            self._transport,
            OrdersServiceClient,
            lambda client, req: client.batch_modify_orders(req),
            proto_request,
            batch_modify_from_proto,
        )

    async def batch_create(
        self,
        *,
        account: AccountScope | None = None,
        items: list[CreateOrderRequest | dict],
        sub_account_id: str | None = None,
        symbol: str | None = None,
        request_id: str | None = None,
        allow_partial: bool = False,
    ) -> BatchCreateOrdersResult:
        qty_values: list[object | None] = []
        scale_symbol = symbol
        for item in items:
            if isinstance(item, CreateOrderRequest):
                qty_values.append(item.qty)
                if scale_symbol is None and item.symbol:
                    scale_symbol = item.symbol
            else:
                qty_values.append(item.get("qty"))
                if scale_symbol is None and item.get("symbol"):
                    scale_symbol = str(item["symbol"])
        await self._ensure_catalogs()
        scale = resolve_quantity_scale(self._catalogs, scale_symbol, *qty_values)
        proto_request = batch_create_orders_to_proto(
            items=items,
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            request_id=request_id,
            allow_partial=allow_partial,
            quantity_scale=scale,
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
        proto_request = cancel_all_after_to_proto(
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            timeout_sec=timeout_sec,
            symbol=symbol,
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
    ) -> AsyncSubscription[Order]:
        """Subscribe to private order updates for an account."""
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:spot:orders:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_order_bytes,
        )

    async def wait_for_order_trades_complete(
        self,
        *,
        order_id: str | int | None = None,
        client_order_id: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        timeout: float = 10.0,
        poll_interval: float = 0.1,
    ) -> GetOrderResult:
        """Poll ``get`` until projected trade qtys sum to order ``cum_qty`` or timeout.

        GetOrder can report ``cum_qty`` before every fill is visible on the trades
        list (eventual consistency). Prefer this helper after fills instead of
        treating a single get as final trade projection.
        """
        return await wait_for_order_trades_complete(
            self,
            order_id=order_id,
            client_order_id=client_order_id,
            account=account,
            sub_account_id=sub_account_id,
            timeout=timeout,
            poll_interval=poll_interval,
        )


async def wait_for_order_trades_complete(
    orders: AsyncOrdersService,
    *,
    order_id: str | int | None = None,
    client_order_id: str | None = None,
    account: AccountScope | None = None,
    sub_account_id: str | None = None,
    timeout: float = 10.0,
    poll_interval: float = 0.1,
) -> GetOrderResult:
    """Poll until ``sum(trade.qty) == order.cum_qty`` or ``timeout`` elapses."""
    if order_id is None and client_order_id is None:
        raise PolyesterValidationError(
            "wait_for_order_trades_complete requires order_id or client_order_id"
        )
    deadline = time.monotonic() + max(timeout, 0.0)
    last: GetOrderResult | None = None
    while True:
        last = await orders.get(
            account=account,
            order_id=order_id,
            client_order_id=client_order_id,
            sub_account_id=sub_account_id,
        )
        if _order_trades_projection_complete(last):
            return last
        if time.monotonic() >= deadline:
            raise PolyesterTransportError(
                "timed out waiting for order trades to match cum_qty "
                f"(order_id={order_id!r}, client_order_id={client_order_id!r})"
            )
        await asyncio.sleep(max(poll_interval, 0.0))


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
