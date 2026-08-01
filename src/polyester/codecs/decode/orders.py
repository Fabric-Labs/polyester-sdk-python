from __future__ import annotations

from polyester.codecs.proto_helpers import format_uint64_id, proto_enum_name, timestamp_to_ms
from polyester.errors import PolyesterResponseContractError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
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
    BatchReplaceAdmissionItem,
    BatchReplaceOrdersResult,
    BatchReplaceStatusItem,
    BatchReplaceStatusResult,
    CancelAllAfterResult,
    CancelAllOrdersResult,
    GetOrderResult,
    ModifyOrderResult,
    OrderErrorDetail,
    OrderFieldViolation,
    OrderMutationResult,
    OrdersList,
    PreviewOrderResult,
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
from polyester.types.money import Price, Quantity, QuantityDomain


def _qty(
    scaled: int,
    *,
    symbol_id: int,
    scale: int | None = None,
    domain: QuantityDomain = QuantityDomain.ORDER_BASE,
    symbol: str | None = None,
) -> Quantity:
    return Quantity.from_scaled(
        int(scaled),
        scale=scale,
        domain=domain,
        symbol=symbol,
        symbol_id=int(symbol_id) if symbol_id else None,
    )


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
        fee_asset=proto_enum_name(orders_pb2.FeeAsset, msg.fee_asset),
        submitted_max_quote_debit_scaled=(
            str(msg.submitted_max_quote_debit_scaled)
            if (
                "submitted_max_quote_debit_scaled"
                in msg.DESCRIPTOR.fields_by_name
                and msg.HasField("submitted_max_quote_debit_scaled")
            )
            else ""
        ),
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
        fee_asset=proto_enum_name(orders_pb2.FeeAsset, msg.fee_asset),
        referral_share_scaled=str(msg.referral_share_scaled),
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


def order_mutation_from_proto(
    msg, *, quantity_scale: int | None = None
) -> OrderMutationResult:
    client_order_id = getattr(msg, "client_order_id", "") or ""
    # CreateOrderResponse no longer carries a status field (POLY-3701): reaching
    # the client means the order was admitted, so synthesize "accepted".
    if any(field.name == "status" for field in msg.DESCRIPTOR.fields):
        status = msg.status
    else:
        status = "accepted"
    message_name = msg.DESCRIPTOR.name
    if message_name == "CreateOrderResponse":
        if not msg.order_id:
            raise PolyesterResponseContractError("CreateOrder", "missing order_id")
    elif message_name == "CancelOrderResponse" and (
        not msg.order_id or not str(status).strip()
    ):
        raise PolyesterResponseContractError(
            "CancelOrder", "missing order_id or status"
        )
    return OrderMutationResult(
        status=status,
        order_id=format_uint64_id(msg.order_id) if msg.order_id else "",
        client_order_id=client_order_id,
        resolved_base_qty_scaled=str(getattr(msg, "resolved_base_qty_scaled", 0) or ""),
        resolved_base_qty=(
            _qty(msg.resolved_base_qty_scaled, symbol_id=0, scale=quantity_scale)
            if getattr(msg, "resolved_base_qty_scaled", 0)
            else None
        ),
        submitted_max_quote_debit_scaled=(
            str(msg.submitted_max_quote_debit_scaled)
            if (
                "submitted_max_quote_debit_scaled"
                in msg.DESCRIPTOR.fields_by_name
                and msg.HasField("submitted_max_quote_debit_scaled")
            )
            else ""
        ),
    )


def _error_code_label(raw_code: int) -> str:
    if raw_code == 0:
        return "UNSPECIFIED"
    try:
        code = orders_pb2.ErrorCode.Name(raw_code)
    except (ValueError, TypeError):
        return f"UNKNOWN_ERROR_CODE({raw_code})"
    if not code or code == str(raw_code):
        return f"UNKNOWN_ERROR_CODE({raw_code})"
    return code.removeprefix("ERROR_CODE_")


def _order_error_detail_from_proto(msg: orders_pb2.ErrorDetail) -> OrderErrorDetail:
    return OrderErrorDetail(
        code=_error_code_label(int(msg.code)),
        violations=[
            OrderFieldViolation(
                field_path=item.field_path,
                rule_id=item.rule_id,
                message=item.message,
            )
            for item in msg.violations
        ],
    )


def preview_order_from_proto(
    msg: orders_pb2.PreviewOrderResponse,
    *,
    quantity_scale: int | None = None,
    symbol: str | None = None,
    symbol_id: int | None = None,
) -> PreviewOrderResult:
    if not msg.HasField("evaluated_at"):
        raise PolyesterResponseContractError(
            "PreviewOrder", "successful response is missing evaluated_at"
        )
    resolved_symbol_id = int(symbol_id) if symbol_id is not None else 0
    has_resolved = msg.HasField("resolved_base_qty_scaled")
    resolved_scaled = int(msg.resolved_base_qty_scaled) if has_resolved else 0
    return PreviewOrderResult(
        admissible=bool(msg.admissible) if msg.HasField("admissible") else None,
        rejection=(
            _order_error_detail_from_proto(msg.rejection)
            if msg.HasField("rejection")
            else None
        ),
        resolved_base_qty_scaled=str(resolved_scaled) if has_resolved else "",
        resolved_base_qty=(
            _qty(
                resolved_scaled,
                symbol_id=resolved_symbol_id,
                scale=quantity_scale,
                symbol=symbol,
            )
            if has_resolved and quantity_scale is not None
            else None
        ),
        protected_price_bound=(
            _price(msg.protected_price_bound_ticks)
            if msg.HasField("protected_price_bound_ticks")
            else None
        ),
        evaluated_at_ms=timestamp_to_ms(msg.evaluated_at),
    )


def modify_order_from_proto(msg: orders_pb2.ModifyOrderResponse) -> ModifyOrderResult:
    action_taken = proto_enum_name(orders_pb2.ModifyActionTaken, msg.action_taken)
    if not action_taken or not msg.old_order_id or not msg.final_order_id:
        raise PolyesterResponseContractError(
            "ModifyOrder", "missing action_taken, old_order_id, or final_order_id"
        )
    return ModifyOrderResult(
        action_taken=action_taken,
        old_order_id=format_uint64_id(msg.old_order_id) if msg.old_order_id else "",
        final_order_id=format_uint64_id(msg.final_order_id) if msg.final_order_id else "",
        code=msg.code,
    )


def cancel_all_from_proto(msg: orders_pb2.CancelAllOrdersResponse) -> CancelAllOrdersResult:
    status = (msg.status or "").strip()
    if not status or status.lower() not in {"submitted", "dry_run"}:
        raise PolyesterResponseContractError(
            "CancelAllOrders",
            f"invalid CancelAllOrders response: unknown status {msg.status!r}"
        )
    if status.lower() == "submitted" and (
        int(msg.submitted_cancels) + int(msg.failed_cancels) != int(msg.matched_orders)
    ):
        raise PolyesterResponseContractError(
            "CancelAllOrders",
            "response counts mismatch: "
            f"matched={msg.matched_orders} submitted={msg.submitted_cancels} "
            f"failed={msg.failed_cancels}",
        )
    if status.lower() == "dry_run" and (msg.submitted_cancels or msg.failed_cancels):
        raise PolyesterResponseContractError(
            "CancelAllOrders",
            "dry_run response unexpectedly reports submitted or failed cancels",
        )
    return CancelAllOrdersResult(
        status=msg.status,
        matched_orders=int(msg.matched_orders),
        submitted_cancels=int(msg.submitted_cancels),
        failed_cancels=int(msg.failed_cancels),
    )


def _batch_replace_admission_status(value: object) -> str:
    if value == orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED:
        return "admitted"
    if value == orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED:
        return "partially_admitted"
    if value == orders_pb2.BATCH_REPLACE_ADMISSION_STATUS_REJECTED:
        return "rejected"
    return ""


def _batch_replace_item_admission_status(value: object) -> str:
    if value == orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED:
        return "admitted"
    if value == orders_pb2.BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED:
        return "rejected"
    return ""


def _batch_replace_phase(value: object) -> str:
    if value == orders_read_pb2.BATCH_REPLACE_PHASE_ADMITTED:
        return "admitted"
    if value == orders_read_pb2.BATCH_REPLACE_PHASE_WORKING:
        return "working"
    if value == orders_read_pb2.BATCH_REPLACE_PHASE_REJECTED:
        return "rejected"
    if value == orders_read_pb2.BATCH_REPLACE_PHASE_TERMINAL:
        return "terminal"
    return ""


def batch_replace_from_proto(
    msg: orders_pb2.BatchReplaceOrdersResponse,
) -> BatchReplaceOrdersResult:
    if not msg.batch_request_id:
        raise PolyesterResponseContractError("BatchReplaceOrders", "missing batch_request_id")
    status = _batch_replace_admission_status(msg.status)
    if not status:
        raise PolyesterResponseContractError(
            "BatchReplaceOrders", f"unknown admission status: {msg.status}"
        )
    decoded_accepted = 0
    decoded_rejected = 0
    for item in msg.results:
        item_status = _batch_replace_item_admission_status(item.status)
        if item_status == "admitted":
            decoded_accepted += 1
        elif item_status == "rejected":
            decoded_rejected += 1
        else:
            raise PolyesterResponseContractError(
                "BatchReplaceOrders",
                f"batch replace response has unknown item status: {item.status}",
            )

    results = [
        BatchReplaceAdmissionItem(
            item_index=int(item.item_index),
            status=_batch_replace_item_admission_status(item.status),
            client_order_id=item.client_order_id,
            old_order_id=format_uint64_id(item.old_order_id) if item.old_order_id else "",
            replacement_order_id=(
                format_uint64_id(item.replacement_order_id) if item.replacement_order_id else ""
            ),
            code=item.code,
        )
        for item in msg.results
    ]
    accepted_count = int(msg.accepted_count)
    rejected_count = int(msg.rejected_count)
    if (
        accepted_count != decoded_accepted
        or rejected_count != decoded_rejected
        or accepted_count + rejected_count != len(results)
    ):
        raise PolyesterResponseContractError(
            "BatchReplaceOrders",
            "batch replace response counts do not match decoded outcomes: "
            f"accepted={accepted_count}/{decoded_accepted} "
            f"rejected={rejected_count}/{decoded_rejected} results={len(results)}"
        )
    return BatchReplaceOrdersResult(
        batch_request_id=format_uint64_id(msg.batch_request_id),
        status=status,
        results=results,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        accepted_ts_ns=int(msg.accepted_ts_ns),
    )


def batch_replace_status_from_proto(msg) -> BatchReplaceStatusResult:
    if not msg.batch_request_id:
        raise PolyesterResponseContractError("GetBatchReplaceStatus", "missing batch_request_id")
    admission_status = _batch_replace_admission_status(msg.admission_status)
    if not admission_status:
        raise PolyesterResponseContractError(
            "GetBatchReplaceStatus",
            f"unknown admission status: {msg.admission_status}",
        )
    items: list[BatchReplaceStatusItem] = []
    decoded_accepted = 0
    decoded_rejected = 0
    for item in msg.items:
        phase = _batch_replace_phase(item.phase)
        if not phase:
            raise PolyesterResponseContractError(
                "GetBatchReplaceStatus", f"unknown batch replace phase: {item.phase}"
            )
        items.append(
            BatchReplaceStatusItem(
                item_index=int(item.item_index),
                phase=phase,
                old_order_id=format_uint64_id(item.old_order_id) if item.old_order_id else "",
                replacement_order_id=(
                    format_uint64_id(item.replacement_order_id)
                    if item.replacement_order_id
                    else ""
                ),
                order_status=proto_enum_name(OrderStatus, item.order_status),
                code=item.code,
                updated_ts_ns=int(item.updated_ts_ns),
            )
        )
        if phase in {"admitted", "working", "terminal"}:
            decoded_accepted += 1
        else:
            decoded_rejected += 1
    accepted_count = int(msg.accepted_count)
    rejected_count = int(msg.rejected_count)
    if (
        accepted_count != decoded_accepted
        or rejected_count != decoded_rejected
        or accepted_count + rejected_count != len(items)
    ):
        raise PolyesterResponseContractError(
            "GetBatchReplaceStatus",
            "batch replace status counts do not match decoded phases: "
            f"accepted={accepted_count}/{decoded_accepted} "
            f"rejected={rejected_count}/{decoded_rejected} items={len(items)}",
        )
    return BatchReplaceStatusResult(
        batch_request_id=format_uint64_id(msg.batch_request_id),
        admission_status=admission_status,
        items=items,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        accepted_ts_ns=int(msg.accepted_ts_ns),
        updated_ts_ns=int(msg.updated_ts_ns),
    )


def _batch_create_result_item(item) -> BatchCreateResultItem:
    # Each item carries exactly one accepted/rejected outcome.
    if item.HasField("accepted"):
        return BatchCreateResultItem(
            status="accepted",
            order_id=(format_uint64_id(item.accepted.order_id) if item.accepted.order_id else ""),
            client_order_id=item.client_order_id,
        )
    if item.HasField("rejected"):
        raw_code = int(item.rejected.error.code)
        if raw_code == 0:
            code = "error_code_unspecified"
        try:
            if raw_code:
                code = proto_enum_name(orders_pb2.ErrorCode, raw_code)
        except (ValueError, TypeError):
            code = f"unknown_error_code({raw_code})"
        if raw_code and code == str(raw_code):
            code = f"unknown_error_code({raw_code})"
        return BatchCreateResultItem(
            status="rejected",
            client_order_id=item.client_order_id,
            code=code,
        )
    raise PolyesterResponseContractError(
        "BatchCreateOrders",
        "batch create response item has neither accepted nor rejected outcome"
    )


def batch_create_from_proto(msg: orders_pb2.BatchCreateOrdersResponse) -> BatchCreateOrdersResult:
    results = [_batch_create_result_item(item) for item in msg.results]
    accepted_count = int(msg.accepted_count)
    rejected_count = int(msg.rejected_count)
    decoded_accepted = sum(item.status == "accepted" for item in results)
    decoded_rejected = sum(item.status == "rejected" for item in results)
    if (
        accepted_count != decoded_accepted
        or rejected_count != decoded_rejected
        or accepted_count + rejected_count != len(results)
    ):
        raise PolyesterResponseContractError(
            "BatchCreateOrders",
            "batch create response counts do not match decoded outcomes: "
            f"accepted={accepted_count}/{decoded_accepted} "
            f"rejected={rejected_count}/{decoded_rejected} results={len(results)}"
        )
    return BatchCreateOrdersResult(
        results=results,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )


def batch_cancel_from_proto(msg: orders_pb2.BatchCancelOrdersResponse) -> BatchCancelOrdersResult:
    decoded_accepted = 0
    decoded_rejected = 0
    for item in msg.results:
        status = item.status.lower()
        if status == "accepted":
            decoded_accepted += 1
        elif status == "rejected":
            decoded_rejected += 1
        else:
            raise PolyesterResponseContractError(
                "BatchCancelOrders",
                f"batch cancel response has unknown status: {item.status}"
            )

    results = [
        BatchCancelResultItem(
            status=item.status,
            order_id=format_uint64_id(item.order_id) if item.order_id else "",
            client_order_id=item.client_order_id,
            code=item.code,
        )
        for item in msg.results
    ]
    accepted_count = int(msg.accepted_count)
    rejected_count = int(msg.rejected_count)
    if (
        accepted_count != decoded_accepted
        or rejected_count != decoded_rejected
        or accepted_count + rejected_count != len(results)
    ):
        raise PolyesterResponseContractError(
            "BatchCancelOrders",
            "batch cancel response counts do not match decoded outcomes: "
            f"accepted={accepted_count}/{decoded_accepted} "
            f"rejected={rejected_count}/{decoded_rejected} results={len(results)}"
        )
    return BatchCancelOrdersResult(
        results=results,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )


def cancel_all_after_from_proto(msg: orders_pb2.CancelAllAfterResponse) -> CancelAllAfterResult:
    status = (msg.status or "").strip()
    if not status or status.lower() not in {"armed", "disabled"}:
        raise PolyesterResponseContractError(
            "CancelAllAfter",
            f"invalid CancelAllAfter response: unknown status {msg.status!r}"
        )
    return CancelAllAfterResult(
        status=msg.status,
        effective_timeout_sec=int(msg.effective_timeout_sec),
        expires_at_ts_ns=str(msg.expires_at_ts_ns),
    )
