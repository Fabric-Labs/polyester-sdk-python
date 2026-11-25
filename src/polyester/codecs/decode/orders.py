from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import NamedTuple

from google.protobuf.message import Message

from polyester.codecs.decode.balances import u128_from_proto
from polyester.codecs.decode.common import require_id
from polyester.codecs.decode.invariants import (
    paired_ts_ns,
    qty_scaled_from_response,
    ts_ns_from_response,
    ts_ns_string_from_response,
)
from polyester.codecs.decode.ratelimit import rate_limit_detail_from_proto
from polyester.codecs.proto_helpers import (
    format_optional_uint64_id,
    format_uint64_id,
    has_field,
    proto_enum_name,
    timestamp_to_ms,
    timestamp_to_rfc3339,
)
from polyester.codecs.scalars import format_qty_scaled
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
from polyester.gen.orders.v1.orders_read_pb2 import (
    OrderLineage as ProtoOrderLineage,
)
from polyester.gen.orders.v1.orders_read_pb2 import (
    OrderOrigin as ProtoOrderOrigin,
)
from polyester.gen.orders.v1.orders_read_pb2 import (
    OrderTransfer as ProtoOrderTransfer,
)
from polyester.models import (
    AttachedRisk,
    AttachedRiskLegState,
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
    CancelledOrder,
    DeadManSwitchScope,
    GetOrderResult,
    ModifyOrderResult,
    OrderErrorDetail,
    OrderFeeTotal,
    OrderFieldViolation,
    OrderLineage,
    OrderMutationResult,
    OrderOrigin,
    OrdersList,
    OrderTransfer,
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

_E18 = 18


class OrderMarket(NamedTuple):
    """The market a create, preview or batch item was sent to.

    The answers to those calls do not name their pair, so their decoders take
    it from the request: a resolved quantity carries the pair's name and ID,
    and ``compatible_with`` refuses it for another market.
    """

    symbol: str | None
    """The pair's catalog name; ``None`` when the catalogs do not list it."""
    symbol_id: int
    quantity_scale: int | None
    """The pair's base quantity scale; ``None`` when it is unknown."""


PairSymbols = Callable[[int], str]
"""A pair's catalog name by ``symbol_id``; ``""`` where unknown."""


def pair_symbol(symbols: PairSymbols | None, symbol_id: int) -> str | None:
    """The pair name ``symbols`` knows for ``symbol_id``; ``None`` when it
    knows none, and for symbol ID 0, which names no pair."""
    if symbols is None or not symbol_id:
        return None
    return symbols(int(symbol_id)) or None


def _qty(
    scaled: int,
    *,
    field: str,
    symbol: str | None,
    symbol_id: int,
    scale: int | None = None,
    domain: QuantityDomain = QuantityDomain.ORDER_BASE,
) -> Quantity:
    # The market is required: a quantity without it passes compatible_with
    # for any other market.
    return Quantity.from_scaled(
        qty_scaled_from_response(scaled, field=field),
        scale=scale,
        domain=domain,
        symbol=symbol or None,
        symbol_id=int(symbol_id) if symbol_id else None,
    )


def _price(ticks: int, *, symbol: str | None) -> Price:
    return Price.from_ticks(int(ticks), symbol=symbol or None)


def _resolved_base_qty(scaled: int, market: OrderMarket, *, field: str) -> Quantity:
    """A create, preview or batch item's resolved base quantity, bound to the
    market the order was sent to."""
    return _qty(
        scaled,
        field=field,
        symbol=market.symbol,
        symbol_id=market.symbol_id,
        scale=market.quantity_scale,
    )


def _optional_scaled(msg: Message, field_name: str) -> str:
    """An optional int64 echo such as ``submitted_max_quote_debit_scaled`` as
    its decimal string; empty when absent."""
    if field_name in msg.DESCRIPTOR.fields_by_name and msg.HasField(field_name):
        return str(getattr(msg, field_name))
    return ""


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


def _attached_risk_state_from_proto(msg) -> AttachedRiskLegState | None:
    # NOT_CONFIGURED is the server's state for a leg the parent order does not have.
    if msg is None or msg.status == orders_read_pb2.AttachedRiskLegState.NOT_CONFIGURED:
        return None
    return AttachedRiskLegState(
        status=(
            proto_enum_name(orders_read_pb2.AttachedRiskLegState.Status, msg.status)
            if msg.status
            else ""
        ),
        armed_ts_ns=ts_ns_string_from_response(
            msg.armed_ts_ns,
            context="AttachedRiskLegState",
            field_name="armed_ts_ns",
            empty_when_zero=True,
        ),
        terminal_ts_ns=ts_ns_string_from_response(
            msg.terminal_ts_ns,
            context="AttachedRiskLegState",
            field_name="terminal_ts_ns",
            empty_when_zero=True,
        ),
        trigger_id=(format_uint64_id(msg.trigger_id) if msg.HasField("trigger_id") else ""),
        child_order_id=(
            format_uint64_id(msg.child_order_id) if msg.HasField("child_order_id") else ""
        ),
    )


def _risk_leg_from_policy(
    policy,
    *,
    symbol: str | None,
    state: AttachedRiskLegState | None = None,
) -> RiskLeg | None:
    if policy is None or not policy.trigger_price_ticks:
        return RiskLeg(state=state) if state is not None else None
    order_type, limit_ticks = _risk_execution_order_type(
        policy.child if policy.HasField("child") else None
    )
    return RiskLeg(
        trigger_price=_price(policy.trigger_price_ticks, symbol=symbol),
        trigger_price_source=_trigger_price_source_label(policy.trigger_price_source),
        order_type=order_type,
        limit_price=_price(limit_ticks, symbol=symbol) if limit_ticks else None,
        state=state,
    )


def _trailing_stop_from_policy(
    policy,
    *,
    symbol: str | None,
    state: AttachedRiskLegState | None = None,
) -> TrailingStop | None:
    if policy is None:
        return TrailingStop(state=state) if state is not None else None
    distance_ticks = int(policy.trailing_distance_ticks)
    distance_bps = int(policy.trailing_distance_bps)
    # Missing or non-positive distance is not a usable trailing stop; omit
    # rather than fabricating a zero-distance stop.
    if distance_ticks <= 0 and distance_bps <= 0:
        return TrailingStop(state=state) if state is not None else None
    max_slippage_ticks = int(policy.max_slippage_ticks)
    max_slippage_bps = int(policy.max_slippage_bps)
    return TrailingStop(
        distance_ticks=distance_ticks,
        distance_bps=distance_bps,
        max_slippage_ticks=max_slippage_ticks if max_slippage_ticks > 0 else 0,
        max_slippage_bps=max_slippage_bps if max_slippage_bps > 0 else 0,
        activation_price=(
            _price(policy.activation_price_ticks, symbol=symbol)
            if policy.activation_price_ticks
            else None
        ),
        limit_price=(
            _price(policy.limit_price_ticks, symbol=symbol)
            if policy.limit_price_ticks > 0
            else None
        ),
        trigger_price_source=_trigger_price_source_label(policy.trigger_price_source),
        state=state,
    )


def _attached_risk_from_proto(msg, *, symbol: str | None) -> AttachedRisk | None:
    if msg is None:
        return None
    take_profit = None
    if msg.HasField("take_profit"):
        take_profit = _risk_leg_from_policy(
            msg.take_profit.policy if msg.take_profit.HasField("policy") else None,
            symbol=symbol,
            state=(
                _attached_risk_state_from_proto(msg.take_profit.state)
                if msg.take_profit.HasField("state")
                else None
            ),
        )
    trailing_stop = None
    if msg.HasField("trailing_stop"):
        trailing_stop = _trailing_stop_from_policy(
            msg.trailing_stop.policy if msg.trailing_stop.HasField("policy") else None,
            symbol=symbol,
            state=(
                _attached_risk_state_from_proto(msg.trailing_stop.state)
                if msg.trailing_stop.HasField("state")
                else None
            ),
        )
    stop_loss = None
    if msg.HasField("stop_loss"):
        stop_loss = _risk_leg_from_policy(
            msg.stop_loss.policy if msg.stop_loss.HasField("policy") else None,
            symbol=symbol,
            state=(
                _attached_risk_state_from_proto(msg.stop_loss.state)
                if msg.stop_loss.HasField("state")
                else None
            ),
        )
    if take_profit is None and stop_loss is None and trailing_stop is None:
        return None
    return AttachedRisk(
        take_profit=take_profit,
        stop_loss=stop_loss,
        trailing_stop=trailing_stop,
        oco=bool(msg.oco),
    )


def order_lineage_from_proto(msg: ProtoOrderLineage | None) -> OrderLineage | None:
    if msg is None or (not msg.id and not msg.generation):
        return None
    return OrderLineage(id=format_uint64_id(msg.id), generation=int(msg.generation))


def _order_origin_from_proto(msg: ProtoOrderOrigin) -> OrderOrigin | None:
    origin = OrderOrigin(
        scope=proto_enum_name(orders_read_pb2.OrderOriginScope, int(msg.scope)),
        trigger_type=proto_enum_name(orders_read_pb2.OrderTriggerType, int(msg.trigger_type)),
        trigger_id=format_uint64_id(msg.trigger_id) if msg.HasField("trigger_id") else "",
        parent_order_id=(
            format_uint64_id(msg.parent_order_id) if msg.HasField("parent_order_id") else ""
        ),
        child_seq=int(msg.child_seq),
    )
    return None if origin == OrderOrigin() else origin


def order_transfer_from_proto(msg: ProtoOrderTransfer) -> OrderTransfer:
    return OrderTransfer(
        match_id=str(msg.match_id) if msg.match_id else "",
        symbol_id=int(msg.symbol_id),
        asset_id=int(msg.asset_id),
        amount_e18=u128_from_proto(msg.amount_e18) if msg.HasField("amount_e18") else "0",
        is_debit=bool(msg.is_debit),
        transfer_code=int(msg.transfer_code),
        account_code=int(msg.account_code),
        ts_ns=ts_ns_string_from_response(
            msg.ts_ns,
            context="OrderTransfer",
            empty_when_zero=True,
        ),
        tx_id=msg.tx_id,
    )


OrderScales = Callable[[int], tuple[int | None, int | None]]
"""A pair's ``(base, quote)`` quantity scales by ``symbol_id``; ``None`` where unknown."""


def pair_scales(scales: OrderScales | None, symbol_id: int) -> tuple[int | None, int | None]:
    """The ``(base, quote)`` quantity scales ``scales`` knows for ``symbol_id``.

    ``(None, None)`` for symbol ID 0, which names no pair: a refused batch
    replacement read through ``GetOrder`` carries no symbol.
    """
    if scales is None or not symbol_id:
        return None, None
    return scales(int(symbol_id))


def scaled_order_from_proto(
    msg: Order, scales: OrderScales | None, symbols: PairSymbols | None = None
) -> PublicOrder:
    """Decode an order with its pair's scales from ``scales`` and its pair's
    name from ``symbols`` (both catalog lookups)."""
    base, quote = pair_scales(scales, msg.symbol_id)
    return order_from_proto(
        msg,
        quantity_scale=base,
        quote_quantity_scale=quote,
        symbol=pair_symbol(symbols, msg.symbol_id),
    )


def order_from_proto(
    msg: Order,
    *,
    quantity_scale: int | None = None,
    quote_quantity_scale: int | None = None,
    symbol: str | None = None,
) -> PublicOrder:
    """Decode an order. Its quantities carry its ``symbol_id``, and its
    quantities and prices carry ``symbol``, the pair's name, when given."""
    status = proto_enum_name(OrderStatus, msg.status) if msg.status else ""
    symbol_id = int(msg.symbol_id)
    attached = (
        _attached_risk_from_proto(msg.attached_risk, symbol=symbol)
        if msg.HasField("attached_risk")
        else None
    )

    def qty(scaled: int, field: str) -> Quantity:
        return _qty(scaled, field=field, symbol=symbol, symbol_id=symbol_id, scale=quantity_scale)

    return PublicOrder(
        order_id=format_uint64_id(msg.order_id),
        symbol_id=symbol_id or None,
        client_order_id=msg.client_order_id,
        side=proto_enum_name(orders_pb2.Side, msg.side) or None,
        status=status,
        order_type=proto_enum_name(orders_pb2.OrderType, msg.order_type) or None,
        tif=proto_enum_name(orders_pb2.TimeInForce, msg.time_in_force) or None,
        orig_qty=qty(msg.orig_qty_scaled, "Order.orig_qty_scaled"),
        cum_qty=qty(msg.cum_qty_scaled, "Order.cum_qty_scaled"),
        inherited_cum_qty=qty(msg.inherited_cum_qty_scaled, "Order.inherited_cum_qty_scaled"),
        leaves_qty=qty(msg.leaves_qty_scaled, "Order.leaves_qty_scaled"),
        display_qty=qty(msg.display_qty_scaled, "Order.display_qty_scaled"),
        hidden_qty=qty(msg.hidden_qty_scaled, "Order.hidden_qty_scaled"),
        price=_price(msg.price_ticks, symbol=symbol) if msg.price_ticks else None,
        avg_px=_price(msg.avg_price_ticks, symbol=symbol) if msg.avg_price_ticks else None,
        created_ts_ns=ts_ns_string_from_response(
            msg.created_ts_ns,
            context="Order",
            field_name="created_ts_ns",
            empty_when_zero=True,
        ),
        terminal_ts_ns=ts_ns_string_from_response(
            msg.terminal_ts_ns,
            context="Order",
            field_name="terminal_ts_ns",
            empty_when_zero=True,
        ),
        version=int(msg.version),
        post_only=bool(msg.post_only),
        fee_asset=proto_enum_name(orders_pb2.FeeAsset, msg.fee_asset) or None,
        self_trade_prevention_mode=(
            proto_enum_name(orders_pb2.SelfTradePreventionMode, int(msg.self_trade_prevention_mode))
            or None
        ),
        submitted_max_quote_debit_scaled=_optional_scaled(msg, "submitted_max_quote_debit_scaled"),
        submitted_quote_proceeds_scaled=_optional_scaled(msg, "submitted_quote_proceeds_scaled"),
        attached_risk=attached,
        lineage=(
            order_lineage_from_proto(msg.lineage)
            if "lineage" in msg.DESCRIPTOR.fields_by_name and msg.HasField("lineage")
            else None
        ),
        origin=_order_origin_from_proto(msg.origin) if msg.HasField("origin") else None,
        market_client_ref_price=(
            _price(msg.market_client_ref_price_ticks, symbol=symbol)
            if msg.market_client_ref_price_ticks > 0
            else None
        ),
        market_max_slippage=(
            _price(msg.market_max_slippage_ticks, symbol=symbol)
            if msg.market_max_slippage_ticks > 0
            else None
        ),
        market_max_slippage_bps=int(msg.market_max_slippage_bps),
        expire_at=(
            timestamp_to_rfc3339(msg.expire_at)
            if "expire_at" in msg.DESCRIPTOR.fields_by_name and msg.HasField("expire_at")
            else None
        ),
        batch_request_id=format_optional_uint64_id(msg.batch_request_id),
        reject_reason=reject_reason_label(int(msg.reject_reason)) if msg.reject_reason else None,
        cancel_reason=cancel_reason_label(int(msg.cancel_reason)) if msg.cancel_reason else None,
        avg_price=(
            Decimal(format_qty_scaled(int(u128_from_proto(msg.avg_price_e18)), _E18))
            if has_field(msg, "avg_price_e18")
            else None
        ),
        cum_notional_scaled=(
            u128_from_proto(msg.cum_notional) if has_field(msg, "cum_notional") else "0"
        ),
        fee_total=(
            OrderFeeTotal(
                amount_e18=(
                    u128_from_proto(msg.fee_total.amount_e18)
                    if msg.fee_total.HasField("amount_e18")
                    else "0"
                ),
                is_rebate=bool(msg.fee_total.is_rebate),
                qty=qty(msg.fee_total.qty_scaled, "OrderFeeTotal.qty_scaled"),
            )
            if has_field(msg, "fee_total")
            else None
        ),
        quote_quantity_scale=quote_quantity_scale,
    )


def _require_lineage_id(operation: str, msg: Order | UserTrade) -> None:
    # A lineage is optional; when present it must name its lineage.
    if msg.HasField("lineage"):
        require_id(operation, "lineage.id", msg.lineage.id)


def _require_order_ids(operation: str, msg: Order) -> None:
    require_id(operation, "order_id", msg.order_id)
    _require_lineage_id(operation, msg)


def orders_list_from_proto(
    msg: GetOpenOrdersResponse | GetOrderHistoryResponse,
    *,
    scales: OrderScales | None = None,
    symbols: PairSymbols | None = None,
) -> OrdersList:
    operation = msg.DESCRIPTOR.name.removesuffix("Response")
    for item in msg.orders:
        _require_order_ids(operation, item)
    return OrdersList(
        orders=[scaled_order_from_proto(item, scales, symbols) for item in msg.orders],
        next_page_token=msg.next_page_token,
    )


def user_trade_from_proto(
    msg: UserTrade, *, quantity_scale: int | None = None, symbol: str | None = None
) -> PublicUserTrade:
    """Decode a trade. Its quantity carries its ``symbol_id``, and its
    quantity and price carry ``symbol``, the pair's name, when given."""
    symbol_id = int(msg.symbol_id)
    return PublicUserTrade(
        symbol_id=symbol_id,
        match_id=str(msg.match_id),
        order_id=format_uint64_id(msg.order_id),
        side=proto_enum_name(orders_pb2.Side, msg.side),
        is_maker=bool(msg.is_maker),
        price=_price(msg.price_ticks, symbol=symbol) if msg.price_ticks else None,
        qty=_qty(
            msg.qty_scaled,
            field="UserTrade.qty_scaled",
            symbol=symbol,
            symbol_id=symbol_id,
            scale=quantity_scale,
        ),
        fee_amount_e18=(
            u128_from_proto(msg.fee_amount_e18) if msg.HasField("fee_amount_e18") else "0"
        ),
        fee_asset=proto_enum_name(orders_pb2.FeeAsset, msg.fee_asset),
        referral_share_amount_e18=(
            u128_from_proto(msg.referral_share_amount_e18)
            if msg.HasField("referral_share_amount_e18")
            else "0"
        ),
        ts_ns=ts_ns_string_from_response(
            msg.ts_ns,
            context="UserTrade",
            empty_when_zero=True,
        ),
        fee_is_rebate=bool(msg.fee_is_rebate),
        lineage=(
            order_lineage_from_proto(msg.lineage)
            if "lineage" in msg.DESCRIPTOR.fields_by_name and msg.HasField("lineage")
            else None
        ),
    )


def scaled_user_trade_from_proto(
    msg: UserTrade, scales: OrderScales | None, symbols: PairSymbols | None = None
) -> PublicUserTrade:
    """Decode a trade with its pair's base quantity scale from ``scales`` and
    its pair's name from ``symbols``."""
    return user_trade_from_proto(
        msg,
        quantity_scale=pair_scales(scales, msg.symbol_id)[0],
        symbol=pair_symbol(symbols, msg.symbol_id),
    )


def user_trades_list_from_proto(
    msg, *, scales: OrderScales | None = None, symbols: PairSymbols | None = None
) -> UserTradesList:
    for item in msg.trades:
        _require_lineage_id("GetUserTrades", item)
    return UserTradesList(
        trades=[scaled_user_trade_from_proto(item, scales, symbols) for item in msg.trades],
        transfers=[order_transfer_from_proto(item) for item in getattr(msg, "transfers", [])],
        next_page_token=msg.next_page_token,
    )


def get_order_from_proto(
    msg: GetOrderResponse,
    *,
    scales: OrderScales | None = None,
    symbols: PairSymbols | None = None,
) -> GetOrderResult:
    if not msg.HasField("order"):
        raise PolyesterResponseContractError("GetOrder", "missing order")
    _require_order_ids("GetOrder", msg.order)
    for item in msg.trades:
        _require_lineage_id("GetOrder", item)
    order = scaled_order_from_proto(msg.order, scales, symbols) if msg.HasField("order") else None
    trades = [scaled_user_trade_from_proto(item, scales, symbols) for item in msg.trades]
    transfers = [order_transfer_from_proto(item) for item in getattr(msg, "transfers", [])]
    next_page_token = getattr(msg, "next_page_token", "") or ""
    return GetOrderResult(
        order=order,
        trades=trades,
        transfers=transfers,
        next_page_token=next_page_token,
        executions_complete=bool(msg.executions_complete),
    )


def _cancel_order_status(value: int) -> str:
    name = proto_enum_name(orders_pb2.CancelOrderResponse.Status, value)
    return name if name == "accepted" else ""


def _cancel_all_status(value: int) -> str:
    name = proto_enum_name(orders_pb2.CancelAllOrdersResponse.Status, value)
    return name if name in {"submitted", "dry_run"} else ""


def _cancel_all_listing_status(value: int) -> str:
    return proto_enum_name(orders_pb2.CancelAllOrdersResponse.ListingStatus, value)


def _cancel_all_after_status(value: int) -> str:
    name = proto_enum_name(orders_pb2.CancelAllAfterResponse.Status, value)
    return name if name in {"armed", "disabled"} else ""


def _batch_cancel_item_status(value: int) -> str:
    name = proto_enum_name(orders_pb2.BatchCancelResultItem.Status, value)
    return name if name in {"accepted", "rejected"} else ""


def _leg_trigger_id(msg: Message, field_name: str) -> str:
    """Public ID of an attached-risk leg trigger a response reports.

    A leg the order does not configure is absent on the wire and stays empty.
    """
    if field_name not in msg.DESCRIPTOR.fields_by_name or not msg.HasField(field_name):
        return ""
    value = int(getattr(msg, field_name))
    return format_uint64_id(value) if value else ""


def order_mutation_from_proto(msg, *, market: OrderMarket | None) -> OrderMutationResult:
    """Decode a create or cancel answer.

    ``market`` is the market a create was sent to: a create answer does not
    name its pair, and its ``resolved_base_qty`` is bound to that market. A
    cancel answer has no quantity and takes ``None``.
    """
    client_order_id = getattr(msg, "client_order_id", "") or ""
    message_name = msg.DESCRIPTOR.name
    # CreateOrderResponse no longer carries a status field (POLY-3701): reaching
    # the client means the order was admitted, so synthesize "accepted".
    if message_name == "CancelOrderResponse":
        status = _cancel_order_status(msg.status)
    else:
        status = "accepted"
    if message_name == "CreateOrderResponse":
        if not msg.order_id:
            raise PolyesterResponseContractError("CreateOrder", "missing order_id")
    elif message_name == "CancelOrderResponse" and (not msg.order_id or not status):
        raise PolyesterResponseContractError("CancelOrder", "missing order_id or status")
    resolved = qty_scaled_from_response(
        getattr(msg, "resolved_base_qty_scaled", 0) or 0,
        field=f"{message_name}.resolved_base_qty_scaled",
    )
    if resolved and market is None:
        raise ValueError(f"decoding a {message_name} resolved quantity needs the order's market")
    return OrderMutationResult(
        status=status,
        order_id=format_uint64_id(msg.order_id) if msg.order_id else "",
        client_order_id=client_order_id,
        resolved_base_qty_scaled=str(resolved) if resolved else "",
        resolved_base_qty=(
            _resolved_base_qty(resolved, market, field=f"{message_name}.resolved_base_qty_scaled")
            if resolved and market is not None
            else None
        ),
        submitted_max_quote_debit_scaled=_optional_scaled(msg, "submitted_max_quote_debit_scaled"),
        submitted_quote_proceeds_scaled=_optional_scaled(msg, "submitted_quote_proceeds_scaled"),
        take_profit_trigger_id=_leg_trigger_id(msg, "take_profit_trigger_id"),
        stop_loss_trigger_id=_leg_trigger_id(msg, "stop_loss_trigger_id"),
        trailing_stop_trigger_id=_leg_trigger_id(msg, "trailing_stop_trigger_id"),
        accepted_ts_ns=(
            paired_ts_ns(msg, "accepted_at_ts_ns", "accepted_at")
            if message_name == "CreateOrderResponse"
            else None
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


def reject_reason_label(raw_code: int) -> str:
    """An order's or order event's ``reject_reason``, and an order command
    outcome's ``reason``: the Orders API error code in lower case without its
    ``ERROR_CODE_`` prefix (``post_only_cross``). A code this SDK does not know
    reads ``UNKNOWN_ERROR_CODE(n)``."""
    label = _error_code_label(raw_code)
    if label.startswith("UNKNOWN_ERROR_CODE("):
        return label
    return label.lower()


def cancel_reason_label(raw: int) -> str:
    """Why a canceled order ended, in lower case without the
    ``CANCEL_REASON_`` prefix (``user_request``). A reason this SDK does not
    know reads ``UNKNOWN_CANCEL_REASON(n)``."""
    try:
        name = orders_read_pb2.CancelReason.Name(raw)
    except ValueError:
        return f"UNKNOWN_CANCEL_REASON({raw})"
    return name.removeprefix("CANCEL_REASON_").lower()


def _field_violations_from_proto(msg: orders_pb2.ErrorDetail) -> list[OrderFieldViolation]:
    """The field violations of an order error detail, in the order sent."""
    return [
        OrderFieldViolation(field_path=item.field_path, rule_id=item.rule_id, message=item.message)
        for item in msg.violations
    ]


def _order_error_detail_from_proto(
    msg: orders_pb2.ErrorDetail, *, symbol: str | None
) -> OrderErrorDetail:
    return OrderErrorDetail(
        code=_error_code_label(int(msg.code)),
        violations=_field_violations_from_proto(msg),
        rate_limit=(
            rate_limit_detail_from_proto(msg.rate_limit) if msg.HasField("rate_limit") else None
        ),
        price_band_limit=(
            _price(msg.price_band_limit_ticks, symbol=symbol)
            if msg.HasField("price_band_limit_ticks")
            else None
        ),
    )


def preview_order_from_proto(
    msg: orders_pb2.PreviewOrderResponse,
    *,
    market: OrderMarket,
) -> PreviewOrderResult:
    """Decode a preview of an order for ``market``, the market it names.

    Its resolved quantity and prices are bound to that market; the resolved
    quantity is ``None`` when the market's base scale is unknown.
    """
    if not msg.HasField("evaluated_at"):
        raise PolyesterResponseContractError(
            "PreviewOrder", "successful response is missing evaluated_at"
        )
    has_resolved = msg.HasField("resolved_base_qty_scaled")
    resolved_scaled = (
        qty_scaled_from_response(
            msg.resolved_base_qty_scaled, field="PreviewOrderResponse.resolved_base_qty_scaled"
        )
        if has_resolved
        else 0
    )
    return PreviewOrderResult(
        admissible=bool(msg.admissible) if msg.HasField("admissible") else None,
        rejection=(
            _order_error_detail_from_proto(msg.rejection, symbol=market.symbol)
            if msg.HasField("rejection")
            else None
        ),
        resolved_base_qty_scaled=str(resolved_scaled) if has_resolved else "",
        resolved_base_qty=(
            _resolved_base_qty(
                resolved_scaled, market, field="PreviewOrderResponse.resolved_base_qty_scaled"
            )
            if has_resolved and market.quantity_scale is not None
            else None
        ),
        protected_price_bound=(
            _price(msg.protected_price_bound_ticks, symbol=market.symbol)
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
        take_profit_trigger_id=_leg_trigger_id(msg, "take_profit_trigger_id"),
        stop_loss_trigger_id=_leg_trigger_id(msg, "stop_loss_trigger_id"),
        trailing_stop_trigger_id=_leg_trigger_id(msg, "trailing_stop_trigger_id"),
        ts_ns=paired_ts_ns(msg, "ts_ns", "ts"),
    )


def cancel_all_from_proto(msg: orders_pb2.CancelAllOrdersResponse) -> CancelAllOrdersResult:
    status = _cancel_all_status(msg.status)
    if not status:
        raise PolyesterResponseContractError(
            "CancelAllOrders", f"invalid CancelAllOrders response: unknown status {msg.status!r}"
        )
    if status == "submitted" and (
        int(msg.submitted_cancels) + int(msg.failed_cancels) != int(msg.matched_orders)
    ):
        raise PolyesterResponseContractError(
            "CancelAllOrders",
            "response counts mismatch: "
            f"matched={msg.matched_orders} submitted={msg.submitted_cancels} "
            f"failed={msg.failed_cancels}",
        )
    if status == "dry_run" and (msg.submitted_cancels or msg.failed_cancels):
        raise PolyesterResponseContractError(
            "CancelAllOrders",
            "dry_run response unexpectedly reports submitted or failed cancels",
        )
    for item in msg.cancelled_orders:
        require_id("CancelAllOrders", "order_id", item.order_id)
    return CancelAllOrdersResult(
        status=status,
        matched_orders=int(msg.matched_orders),
        submitted_cancels=int(msg.submitted_cancels),
        failed_cancels=int(msg.failed_cancels),
        cancelled_orders=[
            CancelledOrder(
                order_id=format_uint64_id(item.order_id),
                client_order_id=item.client_order_id,
            )
            for item in msg.cancelled_orders
        ],
        total_cancelled=int(msg.total_cancelled),
        truncated=bool(msg.truncated),
        listing_status=_cancel_all_listing_status(msg.listing_status),
        matched_triggers=int(msg.matched_triggers),
        ts_ns=paired_ts_ns(msg, "ts_ns", "ts"),
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
            rate_limit=(
                rate_limit_detail_from_proto(item.error.rate_limit)
                if item.HasField("error") and item.error.HasField("rate_limit")
                else None
            ),
            action_taken=proto_enum_name(orders_pb2.ModifyActionTaken, item.action_taken),
            violations=_field_violations_from_proto(item.error),
            existing_order_id=(
                format_uint64_id(item.error.existing_order_id)
                if item.error.existing_order_id
                else ""
            ),
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
            f"rejected={rejected_count}/{decoded_rejected} results={len(results)}",
        )
    return BatchReplaceOrdersResult(
        batch_request_id=format_uint64_id(msg.batch_request_id),
        status=status,
        results=results,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        # The exact nanoseconds, or the paired Timestamp when only that is sent.
        accepted_ts_ns=ts_ns_from_response(
            paired_ts_ns(msg, "accepted_ts_ns", "accepted_ts") or 0,
            context="BatchReplaceOrders",
            field_name="accepted_ts_ns",
        ),
    )


def batch_replace_item_error_code(code: str) -> str:
    """Name a batch replace status item's refusal as ``PolyesterApiError.code``
    names it: ``POST_ONLY_CROSS`` becomes ``ERROR_CODE_POST_ONLY_CROSS``, the
    code a single modify raises. A code this SDK does not know stays as sent;
    empty stays empty."""
    if not code:
        return ""
    prefixed = code if code.startswith("ERROR_CODE_") else f"ERROR_CODE_{code}"
    return prefixed if prefixed in orders_pb2.ErrorCode.DESCRIPTOR.values_by_name else code


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
                # A refused item has no replacement order: never expose an ID.
                replacement_order_id=(
                    format_uint64_id(item.replacement_order_id)
                    if item.replacement_order_id and phase != "rejected"
                    else ""
                ),
                order_status=proto_enum_name(OrderStatus, item.order_status),
                code=item.code,
                error_code=batch_replace_item_error_code(item.code),
                updated_ts_ns=ts_ns_from_response(
                    item.updated_ts_ns,
                    context="GetBatchReplaceStatus",
                    field_name="updated_ts_ns",
                ),
                action_taken=proto_enum_name(orders_pb2.ModifyActionTaken, item.action_taken),
            )
        )
        if phase == "rejected":
            decoded_rejected += 1
    accepted_count = int(msg.accepted_count)
    rejected_count = int(msg.rejected_count)
    # The counts describe admission. An item refused after admission reads
    # ``rejected`` but still counts as accepted, so only the items refused at
    # admission bound the rejected phases from below.
    if accepted_count + rejected_count != len(items) or decoded_rejected < rejected_count:
        raise PolyesterResponseContractError(
            "GetBatchReplaceStatus",
            "batch replace status counts do not match decoded phases: "
            f"accepted={accepted_count} rejected={rejected_count} "
            f"rejected_phases={decoded_rejected} items={len(items)}",
        )
    return BatchReplaceStatusResult(
        batch_request_id=format_uint64_id(msg.batch_request_id),
        admission_status=admission_status,
        items=items,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        accepted_ts_ns=ts_ns_from_response(
            msg.accepted_ts_ns,
            context="GetBatchReplaceStatus",
            field_name="accepted_ts_ns",
        ),
        updated_ts_ns=ts_ns_from_response(
            msg.updated_ts_ns,
            context="GetBatchReplaceStatus",
            field_name="updated_ts_ns",
        ),
    )


def _batch_create_result_item(item, market: OrderMarket) -> BatchCreateResultItem:
    # Each item carries exactly one accepted/rejected outcome.
    if item.HasField("accepted"):
        require_id("BatchCreateOrders", "order_id", item.accepted.order_id)
        resolved = qty_scaled_from_response(
            item.accepted.resolved_base_qty_scaled,
            field="BatchCreateResultItem.accepted.resolved_base_qty_scaled",
        )
        return BatchCreateResultItem(
            status="accepted",
            order_id=format_uint64_id(item.accepted.order_id),
            client_order_id=item.client_order_id,
            take_profit_trigger_id=_leg_trigger_id(item.accepted, "take_profit_trigger_id"),
            stop_loss_trigger_id=_leg_trigger_id(item.accepted, "stop_loss_trigger_id"),
            trailing_stop_trigger_id=_leg_trigger_id(item.accepted, "trailing_stop_trigger_id"),
            submitted_max_quote_debit_scaled=_optional_scaled(
                item.accepted, "submitted_max_quote_debit_scaled"
            ),
            submitted_quote_proceeds_scaled=_optional_scaled(
                item.accepted, "submitted_quote_proceeds_scaled"
            ),
            resolved_base_qty_scaled=str(resolved) if resolved else "",
            resolved_base_qty=(
                _resolved_base_qty(
                    resolved,
                    market,
                    field="BatchCreateResultItem.accepted.resolved_base_qty_scaled",
                )
                if resolved
                else None
            ),
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
        rate_limit = (
            rate_limit_detail_from_proto(item.rejected.error.rate_limit)
            if item.rejected.HasField("error") and item.rejected.error.HasField("rate_limit")
            else None
        )
        existing_order_id = item.rejected.error.existing_order_id
        return BatchCreateResultItem(
            status="rejected",
            client_order_id=item.client_order_id,
            code=code,
            rate_limit=rate_limit,
            existing_order_id=format_uint64_id(existing_order_id) if existing_order_id else "",
            violations=_field_violations_from_proto(item.rejected.error),
        )
    raise PolyesterResponseContractError(
        "BatchCreateOrders", "batch create response item has neither accepted nor rejected outcome"
    )


def batch_create_from_proto(
    msg: orders_pb2.BatchCreateOrdersResponse,
    *,
    markets: Sequence[OrderMarket],
) -> BatchCreateOrdersResult:
    """Decode a batch create answer. ``markets`` are the requested items'
    markets in request order, the order of the results: an accepted item's
    ``resolved_base_qty`` is bound to its own item's market and scale, so a
    batch over several pairs binds each to its own.

    The answer has one result per requested item. One with another number
    of results raises ``PolyesterResponseContractError``: a result could not
    be matched to its item, so its quantity could be bound to another pair.
    """
    if len(msg.results) != len(markets):
        raise PolyesterResponseContractError(
            "BatchCreateOrders",
            "batch create response has a result count that does not match the request: "
            f"results={len(msg.results)} items={len(markets)}",
        )
    results = [
        _batch_create_result_item(item, market)
        for item, market in zip(msg.results, markets, strict=True)
    ]
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
            f"rejected={rejected_count}/{decoded_rejected} results={len(results)}",
        )
    return BatchCreateOrdersResult(
        results=results,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        ts_ns=paired_ts_ns(msg, "ts_ns", "ts"),
    )


def batch_cancel_from_proto(msg: orders_pb2.BatchCancelOrdersResponse) -> BatchCancelOrdersResult:
    decoded_accepted = 0
    decoded_rejected = 0
    for item in msg.results:
        status = _batch_cancel_item_status(item.status)
        if status == "accepted":
            decoded_accepted += 1
        elif status == "rejected":
            decoded_rejected += 1
        else:
            raise PolyesterResponseContractError(
                "BatchCancelOrders", f"batch cancel response has unknown status: {item.status}"
            )

    results = [
        BatchCancelResultItem(
            status=_batch_cancel_item_status(item.status),
            order_id=format_uint64_id(item.order_id) if item.order_id else "",
            client_order_id=item.client_order_id,
            code=item.code,
            rate_limit=(
                rate_limit_detail_from_proto(item.error.rate_limit)
                if item.HasField("error") and item.error.HasField("rate_limit")
                else None
            ),
            violations=_field_violations_from_proto(item.error),
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
            f"rejected={rejected_count}/{decoded_rejected} results={len(results)}",
        )
    return BatchCancelOrdersResult(
        results=results,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        ts_ns=paired_ts_ns(msg, "ts_ns", "ts"),
    )


def cancel_all_after_from_proto(msg: orders_pb2.CancelAllAfterResponse) -> CancelAllAfterResult:
    status = _cancel_all_after_status(msg.status)
    if not status:
        raise PolyesterResponseContractError(
            "CancelAllAfter", f"invalid CancelAllAfter response: unknown status {msg.status!r}"
        )
    return CancelAllAfterResult(
        status=status,
        effective_timeout_sec=int(msg.effective_timeout_sec),
        expires_at_ts_ns=ts_ns_string_from_response(
            msg.expires_at_ts_ns,
            context="CancelAllAfter",
            field_name="expires_at_ts_ns",
            empty_when_zero=True,
        ),
        effective_scope=(
            _dead_man_switch_scope_from_proto(msg.effective_scope)
            if msg.HasField("effective_scope")
            else None
        ),
        ts_ns=paired_ts_ns(msg, "ts_ns", "ts"),
    )


def _dead_man_switch_scope_from_proto(msg: orders_pb2.DeadManSwitchScope) -> DeadManSwitchScope:
    return DeadManSwitchScope(
        account_id=format_uint64_id(msg.account_id) if msg.account_id else "",
        symbol_id=int(msg.symbol_id),
        side=proto_enum_name(orders_pb2.Side, msg.side),
    )
