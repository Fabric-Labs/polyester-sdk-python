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
    AttachedRisk,
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
    RiskLeg,
    TrailingStop,
    UserTradesList,
)
from polyester.models import (
    Order as PublicOrder,
)
from polyester.models import (
    UserTrade as PublicUserTrade,
)
from polyester.types.money import Price, Quantity


def _qty(scaled: int, *, symbol_id: int, scale: int | None = None) -> Quantity:
    return Quantity.from_scaled(int(scaled), scale=scale, symbol_id=int(symbol_id))


def _price(ticks: int, *, symbol_id: int | None = None) -> Price:
    return Price.from_ticks(int(ticks), symbol=None)


def _trigger_price_source_label(value: int) -> str:
    name = proto_enum_name(orders_pb2.TriggerPriceSource, value)
    if name.endswith("_price"):
        return name.removesuffix("_price")
    return name


def _risk_execution_order_type(child) -> tuple[str, int | None]:
    """Return (order_type, limit_price_ticks) from a RiskExecution child."""
    if child is None:
        return "", None
    if child.HasField("limit_gtc"):
        return "limit", int(child.limit_gtc.price_ticks) or None
    if child.HasField("market_ioc"):
        return "market", None
    return "", None


def _risk_leg_from_policy(policy) -> RiskLeg | None:
    if policy is None or not policy.trigger_price_ticks:
        return None
    order_type, limit_ticks = _risk_execution_order_type(
        policy.child if policy.HasField("child") else None
    )
    return RiskLeg(
        trigger_price=_price(policy.trigger_price_ticks),
        order_type=order_type,
        limit_price=_price(limit_ticks) if limit_ticks else None,
    )


def _trailing_stop_from_policy(policy) -> TrailingStop | None:
    if policy is None:
        return None
    return TrailingStop(
        distance_ticks=int(policy.trailing_distance_ticks),
        distance_bps=int(policy.trailing_distance_bps),
        max_slippage_ticks=int(policy.max_slippage_ticks),
        max_slippage_bps=int(policy.max_slippage_bps),
        activation_price=(
            _price(policy.activation_price_ticks) if policy.activation_price_ticks else None
        ),
    )


def _attached_risk_from_proto(msg) -> AttachedRisk | None:
    if msg is None:
        return None
    take_profit = None
    if msg.HasField("take_profit") and msg.take_profit.HasField("policy"):
        take_profit = _risk_leg_from_policy(msg.take_profit.policy)
    trailing_stop = None
    if msg.HasField("trailing_stop") and msg.trailing_stop.HasField("policy"):
        trailing_stop = _trailing_stop_from_policy(msg.trailing_stop.policy)
    stop_loss = None
    # Match TS: when trailing is present, stop-loss is suppressed.
    if trailing_stop is None and msg.HasField("stop_loss") and msg.stop_loss.HasField("policy"):
        stop_loss = _risk_leg_from_policy(msg.stop_loss.policy)
    if take_profit is None and stop_loss is None and trailing_stop is None:
        return None
    return AttachedRisk(
        take_profit=take_profit,
        stop_loss=stop_loss,
        trailing_stop=trailing_stop,
        oco=bool(msg.oco),
    )


def order_from_proto(msg: Order, *, quantity_scale: int | None = None) -> PublicOrder:
    status = proto_enum_name(OrderStatus, msg.status) if msg.status else ""
    symbol_id = int(msg.symbol_id)
    attached = (
        _attached_risk_from_proto(msg.attached_risk) if msg.HasField("attached_risk") else None
    )
    return PublicOrder(
        order_id=format_uint64_id(msg.order_id),
        symbol_id=symbol_id,
        client_order_id=msg.client_order_id,
        side=proto_enum_name(orders_pb2.Side, msg.side),
        status=status,
        order_type=proto_enum_name(orders_pb2.OrderType, msg.order_type),
        tif=proto_enum_name(orders_pb2.TimeInForce, msg.time_in_force),
        orig_qty=_qty(msg.orig_qty_scaled, symbol_id=symbol_id, scale=quantity_scale),
        cum_qty=_qty(msg.cum_qty_scaled, symbol_id=symbol_id, scale=quantity_scale),
        leaves_qty=_qty(msg.leaves_qty_scaled, symbol_id=symbol_id, scale=quantity_scale),
        price=_price(msg.price_ticks) if msg.price_ticks else None,
        avg_px=_price(msg.avg_price_ticks) if msg.avg_price_ticks else None,
        created_ts_ns=str(msg.created_ts_ns),
        version=int(msg.version),
        post_only=bool(msg.post_only),
        attached_risk=attached,
    )


def orders_list_from_proto(msg: GetOpenOrdersResponse | GetOrderHistoryResponse) -> OrdersList:
    return OrdersList(
        orders=[order_from_proto(item) for item in msg.orders],
        next_page_token=msg.next_page_token,
    )


def user_trade_from_proto(msg: UserTrade, *, quantity_scale: int | None = None) -> PublicUserTrade:
    symbol_id = int(msg.symbol_id)
    return PublicUserTrade(
        symbol_id=symbol_id,
        match_id=str(msg.match_id),
        order_id=format_uint64_id(msg.order_id),
        side=proto_enum_name(orders_pb2.Side, msg.side),
        is_maker=bool(msg.is_maker),
        price=_price(msg.price_ticks) if msg.price_ticks else None,
        qty=_qty(msg.qty_scaled, symbol_id=symbol_id, scale=quantity_scale),
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
    # CreateOrderResponse no longer carries a status field (POLY-3701): reaching
    # the client means the order was admitted, so synthesize "accepted".
    if any(field.name == "status" for field in msg.DESCRIPTOR.fields):
        status = msg.status
    else:
        status = "accepted"
    return OrderMutationResult(
        status=status,
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


def _batch_create_result_item(item) -> BatchCreateResultItem:
    # POLY-3701: each item carries an accepted/rejected oneof instead of flat
    # status/order_id/code fields.
    if item.HasField("accepted"):
        return BatchCreateResultItem(
            status="accepted",
            order_id=(format_uint64_id(item.accepted.order_id) if item.accepted.order_id else ""),
            client_order_id=item.client_order_id,
        )
    if item.HasField("rejected"):
        return BatchCreateResultItem(
            status="rejected",
            client_order_id=item.client_order_id,
            code=proto_enum_name(orders_pb2.ErrorCode, item.rejected.error.code),
        )
    return BatchCreateResultItem(client_order_id=item.client_order_id)


def batch_create_from_proto(msg: orders_pb2.BatchCreateOrdersResponse) -> BatchCreateOrdersResult:
    results = [_batch_create_result_item(item) for item in msg.results]
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
