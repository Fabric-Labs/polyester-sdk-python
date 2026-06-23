from __future__ import annotations

from polyester.codecs.proto_helpers import format_uint64_id, proto_enum_name
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.orders.v1.orders_read_pb2 import (
    GetOpenOrdersResponse,
    GetOrderHistoryResponse,
    GetOrderResponse,
    Order,
    OrderStatus,
    UserTrade,
)
from polyester.models import (
    BatchCancelOrdersResult,
    BatchCancelResultItem,
    BatchCreateOrdersResult,
    BatchCreateResultItem,
    BatchModifyOrdersResult,
    BatchModifyResultItem,
    CancelAllAfterResult,
    CancelAllOrdersResult,
    GetOrderResult,
    ModifyOrderResult,
    OrderMutationResult,
    OrdersList,
    UserTradesList,
)
from polyester.models import (
    Order as PublicOrder,
)
from polyester.models import (
    UserTrade as PublicUserTrade,
)


def order_from_proto(msg: Order) -> PublicOrder:
    status = proto_enum_name(OrderStatus, msg.status) if msg.status else ""
    return PublicOrder(
        order_id=format_uint64_id(msg.order_id),
        symbol_id=int(msg.symbol_id),
        client_order_id=msg.client_order_id,
        side=proto_enum_name(orders_pb2.Side, msg.side),
        status=status,
        order_type=proto_enum_name(orders_pb2.OrderType, msg.order_type),
        tif=proto_enum_name(orders_pb2.TimeInForce, msg.time_in_force),
        orig_qty=str(msg.orig_qty_scaled),
        cum_qty=str(msg.cum_qty_scaled),
        leaves_qty=str(msg.leaves_qty_scaled),
        price_ticks=str(msg.price_ticks),
        avg_px_ticks=str(msg.avg_price_ticks),
        created_ts_ns=str(msg.created_ts_ns),
    )


def orders_list_from_proto(msg: GetOpenOrdersResponse | GetOrderHistoryResponse) -> OrdersList:
    return OrdersList(
        orders=[order_from_proto(item) for item in msg.orders],
        next_page_token=msg.next_page_token,
    )


def user_trade_from_proto(msg: UserTrade) -> PublicUserTrade:
    return PublicUserTrade(
        symbol_id=int(msg.symbol_id),
        match_id=str(msg.match_id),
        order_id=format_uint64_id(msg.order_id),
        side=proto_enum_name(orders_pb2.Side, msg.side),
        is_maker=bool(msg.is_maker),
        price_ticks=str(msg.price_ticks),
        qty_scaled=str(msg.qty_scaled),
        fee_scaled=str(msg.fee_scaled),
        ts_ns=str(msg.ts_ns),
    )


def user_trades_list_from_proto(msg) -> UserTradesList:
    return UserTradesList(
        trades=[user_trade_from_proto(item) for item in msg.trades],
        next_page_token=msg.next_page_token,
    )


def get_order_from_proto(msg: GetOrderResponse) -> GetOrderResult:
    order = order_from_proto(msg.order) if msg.HasField("order") else None
    trades = [user_trade_from_proto(item) for item in msg.trades]
    return GetOrderResult(order=order, trades=trades)


def order_mutation_from_proto(msg) -> OrderMutationResult:
    client_order_id = getattr(msg, "client_order_id", "") or ""
    return OrderMutationResult(
        status=msg.status,
        order_id=format_uint64_id(msg.order_id) if msg.order_id else "",
        client_order_id=client_order_id,
    )


def modify_order_from_proto(msg: orders_pb2.ModifyOrderResponse) -> ModifyOrderResult:
    return ModifyOrderResult(
        action_taken=proto_enum_name(orders_pb2.ModifyActionTaken, msg.action_taken),
        old_order_id=format_uint64_id(msg.old_order_id) if msg.old_order_id else "",
        final_order_id=format_uint64_id(msg.final_order_id) if msg.final_order_id else "",
        code=msg.code,
    )


def cancel_all_from_proto(msg: orders_pb2.CancelAllOrdersResponse) -> CancelAllOrdersResult:
    return CancelAllOrdersResult(
        status=msg.status,
        matched_orders=int(msg.matched_orders),
        submitted_cancels=int(msg.submitted_cancels),
    )


def batch_modify_from_proto(msg: orders_pb2.BatchModifyOrdersResponse) -> BatchModifyOrdersResult:
    results = [
        BatchModifyResultItem(
            status=item.status,
            client_order_id=item.client_order_id,
            final_order_id=format_uint64_id(item.final_order_id) if item.final_order_id else "",
            code=item.code,
        )
        for item in msg.results
    ]
    return BatchModifyOrdersResult(
        results=results,
        amended_count=int(msg.amended_count),
        replaced_count=int(msg.replaced_count),
        rejected_count=int(msg.rejected_count),
    )


def batch_create_from_proto(msg: orders_pb2.BatchCreateOrdersResponse) -> BatchCreateOrdersResult:
    results = [
        BatchCreateResultItem(
            status=item.status,
            order_id=format_uint64_id(item.order_id) if item.order_id else "",
            client_order_id=item.client_order_id,
            code=item.code,
        )
        for item in msg.results
    ]
    return BatchCreateOrdersResult(
        results=results,
        accepted_count=int(msg.accepted_count),
        rejected_count=int(msg.rejected_count),
    )


def batch_cancel_from_proto(msg: orders_pb2.BatchCancelOrdersResponse) -> BatchCancelOrdersResult:
    results = [
        BatchCancelResultItem(
            status=item.status,
            order_id=format_uint64_id(item.order_id) if item.order_id else "",
            client_order_id=item.client_order_id,
            code=item.code,
        )
        for item in msg.results
    ]
    return BatchCancelOrdersResult(
        results=results,
        accepted_count=int(msg.accepted_count),
        rejected_count=int(msg.rejected_count),
    )


def cancel_all_after_from_proto(msg: orders_pb2.CancelAllAfterResponse) -> CancelAllAfterResult:
    return CancelAllAfterResult(
        status=msg.status,
        effective_timeout_sec=int(msg.effective_timeout_sec),
        expires_at_ts_ns=str(msg.expires_at_ts_ns),
    )
