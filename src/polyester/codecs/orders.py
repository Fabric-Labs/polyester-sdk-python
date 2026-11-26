from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import msgspec
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.correlation_id import (
    REQUEST_ID_MAX_LEN,
    check_correlation_id,
    optional_client_id,
    optional_request_id,
    required_client_id,
)
from polyester.codecs.pure_bridge import call, message, pure
from polyester.codecs.scalars import (
    UINT32_MAX,
    exact_integer,
    market_id,
    market_ids,
    omit_none,
    parse_account_id,
    refuse_item_scope,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import BatchReplaceItem, CreateOrderRequest
from polyester.models.order_key import OrderKey
from polyester.models.trading import (
    AttachedRisk,
    OrderPeg,
    RiskLeg,
    TrailingStop,
)
from polyester.types.money import (
    resolve_positive_price_ticks,
    resolve_qty_scaled,
)

ORDER_SIDE_TO_PROTO: dict[str, str] = pure._SIDES
ORDER_TYPE_TO_PROTO: dict[str, str] = pure._ORDER_TYPES
TIF_TO_PROTO: dict[str, str] = pure._TIFS
FEE_ASSET_TO_PROTO: dict[str, str] = pure._FEE_ASSETS
PEG_REFERENCE_TO_PROTO: dict[str, str] = pure._PEG_REFERENCES
MODIFY_BEHAVIOR_TO_PROTO: dict[str, str] = pure._MODIFY_BEHAVIORS


def _contract_max_items(request: Any) -> int:
    """Return the ``items`` limit the public contract sets on a batch request."""
    options = request.DESCRIPTOR.fields_by_name["items"].GetOptions()
    return int(options.Extensions[validate_pb2.field].repeated.max_items)


# Items each batch operation accepts, from the contract's validation rules.
BATCH_MAX_ITEMS: dict[str, int] = {
    "batch_create": _contract_max_items(orders_pb2.BatchCreateOrdersRequest),
    "batch_cancel": _contract_max_items(orders_pb2.BatchCancelOrdersRequest),
    "batch_replace": _contract_max_items(orders_pb2.BatchReplaceOrdersRequest),
}

QTY_STEP_SIZE: str = pure._QTY_STEP_SIZE
PRICE_TICK_SIZE: str = pure._PRICE_TICK_SIZE
def gtd_expires_at_text(value: object) -> str | None:
    """A caller's ``expires_at``: ``None`` or an RFC3339 string. Any other
    type (an int of seconds or milliseconds, a ``datetime``) is refused by
    name rather than read."""
    return call(pure._gtd_text, value)


def parse_gtd_expire_at(
    value: object,
    *,
    now: datetime | None = None,
) -> Timestamp:
    """Parse a UTC RFC3339 ``expires_at`` and enforce the 1s–30d GTD window."""
    timestamp = Timestamp()
    timestamp.FromJsonString(call(pure._gtd_expire_at, value, now or datetime.now(UTC)))
    return timestamp


def validate_batch_size(operation: str, length: int) -> None:
    if length == 0:
        raise PolyesterValidationError(f"{operation} requires at least one item")
    limit = BATCH_MAX_ITEMS[operation]
    if length > limit:
        raise PolyesterValidationError(
            f"{operation} accepts at most {limit} items; received {length}"
        )


def require_order_key(key: OrderKey, op: str) -> OrderKey:
    """Validate a typed OrderKey for ``op`` (get/cancel/modify/batch)."""
    return call(pure._require_order_key, key, op)


def set_order_key(target: Any, key: OrderKey, *, op: str) -> None:
    """Set proto ``order_id`` / ``client_order_id`` oneof from a typed OrderKey."""
    built = call(pure._order_key, key, op)
    if "orderId" in built:
        target.order_id = int(built["orderId"])
    else:
        target.client_order_id = built["clientOrderId"]


def _item_order_key(item: dict[str, Any], *, label: str) -> OrderKey:
    if "order_id" in item or "client_order_id" in item:
        raise PolyesterValidationError(
            f"{label} items use key=OrderId(...) or key=ClientOrderId(...); "
            "order_id/client_order_id fields are not accepted"
        )
    return require_order_key(item.get("key"), label)  # type: ignore[arg-type]


_CREATE_ORDER_FIELDS = frozenset(f.name for f in msgspec.structs.fields(CreateOrderRequest))


def normalize_create_order_request(
    request: CreateOrderRequest | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> CreateOrderRequest:
    if request is not None and kwargs:
        raise PolyesterValidationError("Pass either request or keyword arguments, not both")
    data = request if request is not None else kwargs
    if isinstance(data, Mapping):
        # Unknown names, a non-string expires_at, wrong types and floats are
        # refused by name, before the conversion below.
        call(pure._normalize_create, dict(data))
    try:
        normalized = msgspec.convert(data, type=CreateOrderRequest)
    except (msgspec.ValidationError, TypeError) as exc:
        raise PolyesterValidationError("Invalid orders.create request") from exc
    gtd_expires_at_text(normalized.expires_at)
    call(pure._refuse_float_amounts, _create_fields(normalized))
    return normalized


def _codec_quantity_scale(value: object | None, quantity_scale: int | None) -> int:
    return call(pure._codec_scale, value, quantity_scale)


def _create_fields(request: CreateOrderRequest) -> dict[str, Any]:
    """The request's fields as the shared builder takes them: typed attached
    risk and peg models as dicts."""
    fields = {name: getattr(request, name) for name in _CREATE_ORDER_FIELDS}
    fields["attached_risk"] = _risk_input(fields["attached_risk"])
    peg = fields["peg"]
    if isinstance(peg, OrderPeg):
        fields["peg"] = {"reference": peg.reference, "offset_ticks": peg.offset_ticks}
    elif isinstance(peg, Mapping) and not isinstance(peg, dict):
        fields["peg"] = dict(peg)
    return fields


def _risk_input(value: object) -> object:
    return _attached_risk_to_dict(value) if isinstance(value, AttachedRisk) else value


def create_order_to_wire(
    request: CreateOrderRequest,
    *,
    quantity_scale: int | None = None,
) -> dict[str, Any]:
    if request.symbol is None and request.symbol_id is None:
        raise PolyesterValidationError("orders.create requires symbol or symbol_id")
    if request.side not in ORDER_SIDE_TO_PROTO:
        raise PolyesterValidationError("side must be 'buy' or 'sell'")
    if request.order_type not in ORDER_TYPE_TO_PROTO:
        raise PolyesterValidationError("order_type must be 'limit' or 'market'")
    if request.tif is not None and request.tif not in TIF_TO_PROTO:
        raise PolyesterValidationError(f"tif must be one of '{pure._TIF_VALUES}'")

    if request.sub_account_id is not None:
        parse_account_id(request.sub_account_id, "sub_account_id")
    payload = {
        "symbol": request.symbol,
        "symbol_id": request.symbol_id,
        "side": ORDER_SIDE_TO_PROTO[request.side],
        "order_type": ORDER_TYPE_TO_PROTO[request.order_type],
        "timeInForce": TIF_TO_PROTO.get(request.tif) if request.tif else None,
        "expireAt": (
            gtd_expires_at_text(request.expires_at) if (request.tif or "gtc") == "gtd" else None
        ),
        "qty_scaled": resolve_qty_scaled(
            cast(Any, request.qty),
            _codec_quantity_scale(request.qty, quantity_scale),
            symbol=request.symbol,
            symbol_id=request.symbol_id,
        ),
        "limit_price_ticks": (
            resolve_positive_price_ticks(request.price, "price", symbol=request.symbol)
            if request.price is not None
            else None
        ),
        # Checked above: only None leaves it out.
        "sub_account_id": request.sub_account_id,
        "client_order_id": optional_client_id(request.client_order_id),
    }
    return omit_none(payload)


def order_intent_from_request(
    request: CreateOrderRequest,
    *,
    quantity_scale: int | None = None,
    quote_quantity_scale: int | None = None,
) -> orders_pb2.OrderIntent:
    """Build an :class:`OrderIntent` from the flat public request shape.

    The flat ``order_type``/``tif``/``post_only`` inputs are mapped onto the
    explicit execution oneof (``market_ioc``/``limit_gtc``/``limit_ioc``/
    ``limit_fok``/``limit_gtd``). The rules are ``polyester.pure``'s.
    """
    built = call(
        pure._order_intent,
        _create_fields(request),
        quantity_scale,
        quote_quantity_scale,
        datetime.now(UTC),
    )
    return message(built, orders_pb2.OrderIntent())


def create_order_to_proto(
    request: CreateOrderRequest,
    *,
    quantity_scale: int | None = None,
    quote_quantity_scale: int | None = None,
) -> orders_pb2.CreateOrderRequest:
    proto = orders_pb2.CreateOrderRequest(
        order=order_intent_from_request(
            request,
            quantity_scale=quantity_scale,
            quote_quantity_scale=quote_quantity_scale,
        )
    )
    if request.sub_account_id is not None:
        proto.subaccount_id = parse_account_id(request.sub_account_id, "sub_account_id")
    return proto


def preview_order_to_proto(
    request: CreateOrderRequest,
    *,
    quantity_scale: int | None = None,
    quote_quantity_scale: int | None = None,
) -> orders_pb2.PreviewOrderRequest:
    """Build a preview request from the same public shape as ``create``.

    Wire reshape of ``PreviewOrderRequest`` to wrap an ``OrderIntent``
    (``subaccount_id`` + ``order``), matching ``CreateOrderRequest``.
    """
    proto = orders_pb2.PreviewOrderRequest(
        order=order_intent_from_request(
            request,
            quantity_scale=quantity_scale,
            quote_quantity_scale=quote_quantity_scale,
        )
    )
    if request.sub_account_id is not None:
        proto.subaccount_id = parse_account_id(request.sub_account_id, "sub_account_id")
    return proto


def _reject_unknown_keys(data: dict[str, Any], allowed: frozenset[str], *, field_name: str) -> None:
    call(pure._reject_unknown, data, allowed, field_name)


def _risk_leg_model_to_dict(leg: RiskLeg) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if leg.trigger_price is not None:
        out["trigger_price"] = leg.trigger_price
    if leg.order_type:
        out["order_type"] = leg.order_type
    if leg.limit_price is not None:
        out["limit_price"] = leg.limit_price
    if leg.trigger_price_source:
        out["trigger_price_source"] = leg.trigger_price_source
    return out


def _trailing_stop_model_to_dict(stop: TrailingStop) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if stop.distance_ticks:
        out["trailing_distance_ticks"] = stop.distance_ticks
    if stop.distance_bps:
        out["trailing_distance_bps"] = stop.distance_bps
    if stop.max_slippage_ticks:
        out["max_slippage_ticks"] = stop.max_slippage_ticks
    if stop.max_slippage_bps:
        out["max_slippage_bps"] = stop.max_slippage_bps
    if stop.activation_price is not None:
        out["activation_price"] = stop.activation_price
    if stop.limit_price is not None:
        out["limit_price"] = stop.limit_price
    if stop.trigger_price_source:
        out["trigger_price_source"] = stop.trigger_price_source
    if stop.order_type:
        out["order_type"] = stop.order_type
    return out


def _attached_risk_to_dict(risk: AttachedRisk) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if risk.take_profit is not None:
        out["take_profit"] = _risk_leg_model_to_dict(risk.take_profit)
    if risk.stop_loss is not None:
        out["stop_loss"] = _risk_leg_model_to_dict(risk.stop_loss)
    if risk.trailing_stop is not None:
        out["trailing_stop"] = _trailing_stop_model_to_dict(risk.trailing_stop)
    if risk.oco:
        out["oco"] = True
    return out


def risk_policy_from_dict(
    data: dict[str, Any] | AttachedRisk | None,
    *,
    symbol: str | None = None,
    side: str | None = None,
    risk_field: str = "order.attached_risk",
) -> orders_pb2.RiskPolicy | None:
    """Encode public attached-risk input onto the write ``RiskPolicy`` wire.

    Accepts ``AttachedRisk`` / ``RiskLeg`` models, friendly keys
    (``trigger_price``, ``order_type``, ``limit_price``), and proto-JSON
    (``trigger_price_ticks``, ``child.market_ioc`` / ``child.limit_gtc``).
    Unknown fields and the extra ``child.execution`` wrapper are rejected.

    ``side`` is the parent order's side when known. A selling order's trailing
    stop buys back, so it requires ``limit_price``; a buying order's must not
    set one. Without a side (modify), the server applies that rule and answers
    ``ERROR_CODE_BAD_PRICE`` with no violation either way.

    A refused trailing-stop maximum raises :class:`PolyesterValidationError`
    with the code and the violation (rule ID and ``field_path`` under
    ``risk_field``) the server answers for the same mistake: set on a buying
    order ``ERROR_CODE_BAD_PRICE`` / ``sell_unset``; missing or not positive
    on a selling order ``ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT`` /
    ``buy_required``; below the activation price ``ERROR_CODE_BAD_PRICE`` /
    ``buy_at_least_activation``.

    ``oco`` needs ``take_profit`` and one stop leg: a one-leg OCO policy
    raises :class:`PolyesterValidationError` with the contract's
    ``risk_policy.oco_requires_tp_and_one_stop`` violation at ``risk_field``.
    """
    built = call(pure._risk_policy, _risk_input(data), symbol, side, risk_field)
    return None if built is None else message(built, orders_pb2.RiskPolicy())


# Fields a batch item dictionary may carry. Account scope and order_id /
# client_order_id keys are refused earlier with their own messages.
_BATCH_REPLACE_ITEM_KEYS = frozenset(
    {
        "key",
        "new_price",
        "new_qty",
        "new_client_order_id",
        "new_attached_risk",
        "clear_attached_risk",
    }
)


def replacement_risk_policy(
    new_attached_risk: dict[str, Any] | AttachedRisk | None,
    clear_attached_risk: object,
    *,
    symbol: str | None,
    risk_field: str = "new_attached_risk",
) -> orders_pb2.RiskPolicy | None:
    """The ``new_attached_risk`` of a modify or a batch replace item.

    ``clear_attached_risk=True`` sends an empty ``RiskPolicy``, which removes
    the order's take-profit, stop-loss and trailing stop; with a
    ``new_attached_risk`` it raises. Otherwise ``None`` leaves the legs
    unchanged, and an empty risk raises. ``risk_field`` is the field path a
    refusal names: ``items[i].new_attached_risk`` for an item of a whole batch
    request.
    """
    built = call(
        pure._replacement_risk,
        _risk_input(new_attached_risk),
        clear_attached_risk,
        symbol,
        risk_field,
    )
    return None if built is None else message(built, orders_pb2.RiskPolicy())


_BATCH_CANCEL_ITEM_KEYS = frozenset({"key", "symbol_id"})


def batch_replace_item_to_proto(
    item: BatchReplaceItem | dict[str, Any],
    *,
    quantity_scale: int,
    symbol: str | None = None,
    symbol_id: int | None = None,
    risk_field: str = "new_attached_risk",
) -> orders_pb2.BatchReplaceOrderItem:
    """One batch replace item. Refusals of its ``new_attached_risk`` name
    ``risk_field``: the field alone by default, under the item's index when
    :func:`batch_replace_orders_to_proto` encodes a whole request."""
    if isinstance(item, BatchReplaceItem):
        item = {
            "key": item.key,
            "new_price": item.new_price,
            "new_qty": item.new_qty,
            "new_client_order_id": item.new_client_order_id,
            "new_attached_risk": item.new_attached_risk,
            "clear_attached_risk": item.clear_attached_risk,
        }
    refuse_item_scope(item, "batch_replace")
    key = _item_order_key(item, label="each batch replace item")
    _reject_unknown_keys(item, _BATCH_REPLACE_ITEM_KEYS, field_name="batch_replace item")
    new_price = item.get("new_price")
    new_qty = item.get("new_qty")
    new_attached_risk = item.get("new_attached_risk")
    clear_attached_risk = item.get("clear_attached_risk", False)
    if (
        new_price is None
        and new_qty is None
        and new_attached_risk is None
        and clear_attached_risk is False
    ):
        raise PolyesterValidationError(
            "each batch item requires new_price, new_qty, new_attached_risk, "
            "and/or clear_attached_risk"
        )
    proto = orders_pb2.BatchReplaceOrderItem()
    set_order_key(proto, key, op="each batch replace item")
    # The new price and quantity follow a modify's rules.
    if new_price is not None:
        proto.new_price_ticks = call(pure._new_price_ticks, new_price, symbol)
    if new_qty is not None:
        proto.new_qty_scaled = call(
            pure._new_qty_scaled, new_qty, quantity_scale, symbol, symbol_id
        )
    if item.get("new_client_order_id"):
        proto.new_client_order_id = required_client_id(
            str(item["new_client_order_id"]), "new_client_order_id"
        )
    risk = replacement_risk_policy(
        new_attached_risk, clear_attached_risk, symbol=symbol, risk_field=risk_field
    )
    if risk is not None:
        proto.new_attached_risk.CopyFrom(risk)
    return proto


def batch_create_orders_to_proto(
    *,
    items: Sequence[CreateOrderRequest | Mapping[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    quantity_scale: int | None = None,
    item_scales: Sequence[tuple[int, int]] | None = None,
) -> orders_pb2.BatchCreateOrdersRequest:
    validate_batch_size("batch_create", len(items))
    proto = orders_pb2.BatchCreateOrdersRequest(
        request_id=optional_request_id(request_id) or f"batch-create-{uuid.uuid4().hex[:12]}",
    )
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    if item_scales is not None and len(item_scales) != len(items):
        raise PolyesterValidationError("batch_create requires scales for every item")
    seen_client_order_ids: set[str] = set()
    for index, item in enumerate(items):
        if isinstance(item, CreateOrderRequest):
            normalized = item
        else:
            normalized = normalize_create_order_request(item)
        if normalized.sub_account_id is not None:
            raise PolyesterValidationError(
                "batch_create item scope is unsupported; use the batch-level sub_account_id"
            )
        base_scale, quote_scale = (
            item_scales[index] if item_scales is not None else (quantity_scale, None)
        )
        intent = order_intent_from_request(
            normalized, quantity_scale=base_scale, quote_quantity_scale=quote_scale
        )
        client_order_id = intent.client_order_id
        if client_order_id and client_order_id in seen_client_order_ids:
            raise PolyesterValidationError(
                f"batch_create has duplicate client_order_id {client_order_id!r}"
            )
        if client_order_id:
            seen_client_order_ids.add(client_order_id)
        proto.items.append(intent)
    return proto


def batch_cancel_item_to_proto(item: dict[str, Any]) -> orders_pb2.BatchCancelItem:
    refuse_item_scope(item, "batch_cancel")
    key = _item_order_key(item, label="each batch cancel item")
    _reject_unknown_keys(item, _BATCH_CANCEL_ITEM_KEYS, field_name="batch_cancel item")
    symbol_id = item.get("symbol_id")
    proto = orders_pb2.BatchCancelItem()
    set_order_key(proto, key, op="each batch cancel item")
    if symbol_id is not None:
        proto.symbol_id = market_id(symbol_id, "each batch cancel item symbol_id")
    return proto


def batch_cancel_orders_to_proto(
    *,
    items: list[dict[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
) -> orders_pb2.BatchCancelOrdersRequest:
    validate_batch_size("batch_cancel", len(items))
    proto = orders_pb2.BatchCancelOrdersRequest(
        request_id=optional_request_id(request_id) or f"batch-cancel-{uuid.uuid4().hex[:12]}",
    )
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    for item in items:
        proto.items.append(batch_cancel_item_to_proto(item))
    return proto


# Dead-man-switch timeouts the contract accepts besides 0 (which disarms it).
# The contract states the range only as a CEL rule on CancelAllAfterRequest;
# a unit test rebuilds that rule from these constants.
CANCEL_ALL_AFTER_MIN_TIMEOUT_SEC = 10
CANCEL_ALL_AFTER_MAX_TIMEOUT_SEC = 120


def _include_triggers(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise PolyesterValidationError(f"{label} include_triggers must be a bool")
    return value


def cancel_all_after_to_proto(
    *,
    sub_account_id: str | int | None = None,
    timeout_sec: int,
    symbol_id: int | None = None,
    side: str | None = None,
    request_id: str | None = None,
    include_triggers: bool = False,
) -> orders_pb2.CancelAllAfterRequest:
    timeout = exact_integer(
        timeout_sec,
        "cancel_all_after timeout_sec",
        min_value=0,
        max_value=UINT32_MAX,
    )
    if timeout != 0 and not (
        CANCEL_ALL_AFTER_MIN_TIMEOUT_SEC <= timeout <= CANCEL_ALL_AFTER_MAX_TIMEOUT_SEC
    ):
        raise PolyesterValidationError(
            f"cancel_all_after timeout_sec must be 0 or between "
            f"{CANCEL_ALL_AFTER_MIN_TIMEOUT_SEC} and {CANCEL_ALL_AFTER_MAX_TIMEOUT_SEC}; "
            f"received {timeout}"
        )
    proto = orders_pb2.CancelAllAfterRequest(
        request_id=optional_request_id(request_id) or f"cancel-after-{uuid.uuid4().hex[:12]}",
        timeout_sec=timeout,
        include_triggers=_include_triggers(include_triggers, "cancel_all_after"),
    )
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    if symbol_id is not None:
        # 0 means every market, as when omitted.
        proto.symbol_id = market_id(symbol_id, "cancel_all_after symbol_id")
    if side:
        key = side.lower()
        if key not in ORDER_SIDE_TO_PROTO:
            raise PolyesterValidationError("side must be buy or sell")
        proto.side = getattr(orders_pb2, ORDER_SIDE_TO_PROTO[key])
    return proto


def batch_replace_orders_to_proto(
    *,
    items: list[BatchReplaceItem | dict[str, Any]],
    symbol_id: int,
    symbol: str | None = None,
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    quantity_scale: int | None = None,
) -> orders_pb2.BatchReplaceOrdersRequest:
    validate_batch_size("batch_replace", len(items))
    if symbol_id <= 0:
        raise PolyesterValidationError("batch_replace requires a resolved symbol_id")
    proto = orders_pb2.BatchReplaceOrdersRequest(
        symbol_id=symbol_id,
        request_id=optional_request_id(request_id) or f"batch-replace-{uuid.uuid4().hex[:12]}",
    )
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    for index, item in enumerate(items):
        new_qty = item.new_qty if isinstance(item, BatchReplaceItem) else item.get("new_qty")
        item_scale = _codec_quantity_scale(new_qty, quantity_scale) if new_qty is not None else 0
        # A refusal of the whole request names the item's field under its
        # index, as the contract's FieldViolation.field_path does.
        proto.items.append(
            batch_replace_item_to_proto(
                item,
                quantity_scale=item_scale,
                symbol=symbol,
                symbol_id=symbol_id,
                risk_field=f"items[{index}].new_attached_risk",
            )
        )
    return proto


def modify_order_to_proto(
    *,
    symbol: str,
    symbol_id: int,
    key: OrderKey,
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    new_price: object | None = None,
    new_qty: object | None = None,
    new_attached_risk: dict[str, Any] | AttachedRisk | None = None,
    behavior: str | None = None,
    new_client_order_id: str | None = None,
    quantity_scale: int | None = None,
    clear_attached_risk: bool = False,
) -> orders_pb2.ModifyOrderRequest:
    built = call(
        pure._modify_order,
        symbol,
        symbol_id,
        key,
        sub_account_id,
        request_id,
        new_price,
        new_qty,
        _risk_input(new_attached_risk),
        behavior,
        new_client_order_id,
        quantity_scale,
        clear_attached_risk,
    )
    built.setdefault("requestId", f"mod-{uuid.uuid4().hex[:12]}")
    return message(built, orders_pb2.ModifyOrderRequest())


def cancel_all_orders_request_id(request_id: object) -> str:
    """``orders.cancel_all``'s idempotency key, sent exactly as given.

    One that is not 1 to 64 of ``[A-Za-z0-9._:/-]``, an empty or padded one
    included, is refused, never trimmed or replaced, so a retry cannot become
    a new cancel. Left out (``None``), one is generated.
    """
    if request_id is None:
        return f"cancel-all-{uuid.uuid4().hex[:12]}"
    if not isinstance(request_id, str):
        raise PolyesterValidationError("request_id must be a string")
    return check_correlation_id(request_id, "request_id", REQUEST_ID_MAX_LEN)


def cancel_all_orders_to_proto(
    *,
    sub_account_id: str | int | None = None,
    symbol_id: int | None = None,
    symbol_ids: list[int] | None = None,
    side: str | None = None,
    dry_run: bool = False,
    request_id: str | None = None,
    include_triggers: bool = False,
) -> orders_pb2.CancelAllOrdersRequest:
    """Encode a cancel-all of open orders.

    ``symbol_ids`` are resolved pair IDs (empty matches every pair).
    ``request_id`` is sent exactly as given (see
    :func:`cancel_all_orders_request_id`); left out, one is generated.
    """
    proto = orders_pb2.CancelAllOrdersRequest(
        request_id=cancel_all_orders_request_id(request_id),
        dry_run=dry_run,
        include_triggers=_include_triggers(include_triggers, "cancel_all"),
    )
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    if symbol_id and symbol_ids:
        raise PolyesterValidationError("cancel_all accepts only one of symbol_id or symbol_ids")
    resolved_ids: list[int] = []
    if symbol_ids is not None:
        resolved_ids = market_ids(symbol_ids, "cancel_all symbol_ids")
    if not resolved_ids and symbol_id is not None:
        # 0 means every market, as when omitted.
        single = market_id(symbol_id, "cancel_all symbol_id")
        resolved_ids = [single] if single else []
    seen: set[int] = set()
    unique_ids: list[int] = []
    for value in resolved_ids:
        if value <= 0:
            raise PolyesterValidationError("cancel_all symbol_ids must be positive")
        if value in seen:
            continue
        seen.add(value)
        unique_ids.append(value)
    if len(unique_ids) > 100:
        raise PolyesterValidationError("cancel_all accepts at most 100 symbol_ids")
    if unique_ids:
        proto.symbol_ids.extend(unique_ids)
    if side:
        key = side.lower()
        if key not in ORDER_SIDE_TO_PROTO:
            raise PolyesterValidationError("side must be buy or sell")
        proto.side = getattr(orders_pb2, ORDER_SIDE_TO_PROTO[key])
    return proto


def quantity_scale_for_symbol(
    catalogs: CatalogManager | None, symbol: str | None, *, symbol_id: int | None = None
) -> int:
    if catalogs is None or (symbol_id is None and not symbol):
        raise PolyesterValidationError("quantity scale requires symbol or symbol_id and catalogs")
    scale = (
        catalogs.base_quantity_scale_for_symbol_id(symbol_id)
        if symbol_id is not None
        else catalogs.base_quantity_scale_for_symbol(str(symbol))
    )
    if scale is None:
        raise PolyesterValidationError(
            f"quantity scale for {symbol_id if symbol_id is not None else symbol!r} "
            "is unavailable; "
            "await client.wait_for_catalogs() before placing orders"
        )
    return scale


def quote_quantity_scale_for_symbol(
    catalogs: CatalogManager | None, symbol: str | None, *, symbol_id: int | None = None
) -> int:
    if catalogs is not None and symbol_id is not None:
        symbol = catalogs.symbol_for_symbol_id(symbol_id)
    if not symbol or catalogs is None:
        raise PolyesterValidationError("quote quantity scale requires a catalog symbol")
    scale = catalogs.quote_quantity_scale_for_symbol(symbol)
    if scale is None:
        raise PolyesterValidationError(
            f"quote quantity scale for {symbol!r} is unavailable; "
            "await client.wait_for_catalogs() before placing orders"
        )
    return scale


def catalog_order_scales(
    catalogs: CatalogManager | None, symbol_id: int
) -> tuple[int | None, int | None]:
    """A pair's ``(base, quote)`` quantity scales from loaded catalogs.

    ``None`` for a scale the catalogs do not know, such as before they load
    or for a pair they do not list. Reads wait for a spot config load in
    progress; a failed one leaves the scales ``None``.
    """
    if catalogs is None:
        return None, None
    base = catalogs.base_quantity_scale_for_symbol_id(symbol_id)
    symbol = catalogs.symbol_for_symbol_id(symbol_id)
    quote = catalogs.quote_quantity_scale_for_symbol(symbol) if symbol else None
    return base, quote


def resolve_quantity_scale(
    catalogs: CatalogManager | None,
    symbol: str | None,
    *values: object | None,
    symbol_id: int | None = None,
) -> int:
    """Resolve the destination catalog scale, including for raw scaled inputs."""
    scale = quantity_scale_for_symbol(catalogs, symbol, symbol_id=symbol_id)
    return call(pure._value_scale, scale, *values)


def resolve_quote_quantity_scale(
    catalogs: CatalogManager | None,
    symbol: str | None,
    *values: object | None,
    symbol_id: int | None = None,
) -> int:
    """Resolve and validate the catalog scale for quote sizing (a BUY's
    ``max_quote_debit`` or a SELL's ``quote_proceeds``); 0 when none is set."""
    present = [value for value in values if value is not None]
    if not present:
        return 0
    catalog_scale = quote_quantity_scale_for_symbol(catalogs, symbol, symbol_id=symbol_id)
    return call(pure._quote_value_scale, catalog_scale, *present)


def parse_optional_subaccount_id(value: str | int | None) -> int | None:
    """A sub-account ID, or ``None`` for none. Only ``None`` means none: ``""``
    and whitespace are refused, never read as the main account."""
    if value is None:
        return None
    return parse_account_id(value, "sub_account_id")
