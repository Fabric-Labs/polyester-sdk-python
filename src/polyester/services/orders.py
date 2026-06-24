from __future__ import annotations

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
    quantity_scale_for_symbol,
)
from polyester.codecs.realtime_decode import decode_order_bytes
from polyester.codecs.scalars import id_to_int
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
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime

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
            normalized = CreateOrderRequest(
                symbol=normalized.symbol,
                symbol_id=normalized.symbol_id,
                side=normalized.side,
                order_type=normalized.order_type,
                tif=normalized.tif,
                qty=normalized.qty,
                price=normalized.price,
                sub_account_id=self._resolve_sub_account_id(None),
                client_order_id=normalized.client_order_id,
                expires_at=normalized.expires_at,
            )
        quantity_scale = (
            self._catalogs.base_quantity_scale_for_symbol(normalized.symbol)
            if normalized.symbol
            else 8
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
        new_price: str | None = None,
        new_qty: str | None = None,
        new_attached_risk: dict | None = None,
        behavior: str | None = None,
        new_client_order_id: str | None = None,
    ) -> ModifyOrderResult:
        scale = quantity_scale_for_symbol(self._catalogs, symbol)
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
        max_orders: int | None = None,
        request_id: str | None = None,
    ) -> CancelAllOrdersResult:
        proto_request = cancel_all_orders_to_proto(
            sub_account_id=self._resolve_sub_account_id(sub_account_id, account=account),
            symbol=symbol,
            side=side,
            dry_run=dry_run,
            max_orders=max_orders,
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
        scale = quantity_scale_for_symbol(self._catalogs, symbol) if symbol else 8
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
        scale = quantity_scale_for_symbol(self._catalogs, symbol) if symbol else 8
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
