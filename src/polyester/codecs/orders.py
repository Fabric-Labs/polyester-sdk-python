from __future__ import annotations

import uuid
from typing import Any, cast

import msgspec
from google.protobuf.json_format import ParseDict

from polyester.catalogs import CatalogManager
from polyester.codecs.correlation_id import (
    optional_client_id,
    optional_request_id,
    required_client_id,
)
from polyester.codecs.scalars import id_to_int, omit_none
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CreateOrderRequest
from polyester.models.order_key import ClientOrderId, OrderId, OrderKey
from polyester.types.money import Quantity, resolve_price_ticks, resolve_qty_scaled

ORDER_SIDE_TO_PROTO = {"buy": "BUY", "sell": "SELL"}
ORDER_TYPE_TO_PROTO = {"limit": "LIMIT", "market": "MARKET"}
TIF_TO_PROTO = {"gtc": "GTC", "ioc": "IOC", "fok": "FOK"}
MODIFY_BEHAVIOR_TO_PROTO = {
    "amend_or_replace": "AMEND_OR_REPLACE",
    "amend_only": "AMEND_ONLY",
    "replace_only": "REPLACE_ONLY",
}


def require_order_key(key: OrderKey, op: str) -> OrderKey:
    """Validate a typed OrderKey for ``op`` (get/cancel/modify/batch)."""
    if isinstance(key, OrderId):
        if key.value is None or (isinstance(key.value, str) and key.value.strip() == ""):
            raise PolyesterValidationError(f"{op} requires a non-empty OrderId")
        return key
    if isinstance(key, ClientOrderId):
        if not str(key.value).strip():
            raise PolyesterValidationError(f"{op} requires a non-empty ClientOrderId")
        return key
    raise PolyesterValidationError(
        f"{op} requires an OrderKey (OrderId or ClientOrderId)"
    )


def set_order_key(target: Any, key: OrderKey, *, op: str) -> None:
    """Set proto ``order_id`` / ``client_order_id`` oneof from a typed OrderKey."""
    key = require_order_key(key, op)
    if isinstance(key, OrderId):
        target.order_id = id_to_int(key.value, "order_id")
    else:
        target.client_order_id = required_client_id(key.value, "client_order_id")


def _item_order_key(item: dict[str, Any], *, label: str) -> OrderKey:
    if "order_id" in item or "client_order_id" in item:
        raise PolyesterValidationError(
            f"{label} items use key=OrderId(...) or key=ClientOrderId(...); "
            "order_id/client_order_id fields are not accepted"
        )
    return require_order_key(item.get("key"), label)  # type: ignore[arg-type]


def normalize_create_order_request(
    request: CreateOrderRequest | None = None,
    **kwargs: Any,
) -> CreateOrderRequest:
    if request is not None and kwargs:
        raise PolyesterValidationError("Pass either request or keyword arguments, not both")
    data = request if request is not None else kwargs
    try:
        normalized = msgspec.convert(data, type=CreateOrderRequest)
    except (msgspec.ValidationError, TypeError) as exc:
        raise PolyesterValidationError("Invalid orders.create request") from exc
    # Reject floats even when qty is typed as Any for dual-path inputs.
    for field_name in ("qty", "price", "market_client_ref_price"):
        value = getattr(normalized, field_name, None)
        if isinstance(value, float):
            raise PolyesterValidationError(
                f"{field_name} must be a decimal string, Decimal, or typed scaled value "
                "(floats are not allowed)"
            )
    return normalized


def _codec_quantity_scale(value: object | None, quantity_scale: int | None) -> int:
    if quantity_scale is not None:
        return quantity_scale
    if isinstance(value, Quantity):
        return value.scale if value.scale is not None else 0
    raise PolyesterValidationError(
        "decimal quantity encoding requires an explicit quantity_scale resolved from catalogs"
    )


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
        raise PolyesterValidationError("tif must be one of 'gtc', 'ioc', or 'fok'")

    payload = {
        "symbol": request.symbol,
        "symbol_id": request.symbol_id,
        "side": ORDER_SIDE_TO_PROTO[request.side],
        "order_type": ORDER_TYPE_TO_PROTO[request.order_type],
        "timeInForce": TIF_TO_PROTO.get(request.tif) if request.tif else None,
        "qty_scaled": resolve_qty_scaled(
            request.qty,
            _codec_quantity_scale(request.qty, quantity_scale),
            symbol=request.symbol,
        ),
        "limit_price_ticks": (
            resolve_price_ticks(request.price, "price", symbol=request.symbol)
            if request.price
            else None
        ),
        "sub_account_id": request.sub_account_id or None,
        "client_order_id": optional_client_id(request.client_order_id),
    }
    return omit_none(payload)


def order_intent_from_request(
    request: CreateOrderRequest,
    *,
    quantity_scale: int | None = None,
) -> orders_pb2.OrderIntent:
    """Build an :class:`OrderIntent` from the flat public request shape.

    The flat ``order_type``/``tif``/``post_only`` inputs are mapped onto the
    explicit execution oneof (``market_ioc``/``limit_gtc``/``limit_ioc``/
    ``limit_fok``) introduced in POLY-3701.
    """
    if request.symbol is None and request.symbol_id is None:
        raise PolyesterValidationError("orders.create requires symbol or symbol_id")
    if request.side not in ORDER_SIDE_TO_PROTO:
        raise PolyesterValidationError("side must be 'buy' or 'sell'")
    if request.order_type not in ORDER_TYPE_TO_PROTO:
        raise PolyesterValidationError("order_type must be 'limit' or 'market'")
    if request.tif is not None and request.tif not in TIF_TO_PROTO:
        raise PolyesterValidationError("tif must be one of 'gtc', 'ioc', or 'fok'")

    intent = orders_pb2.OrderIntent(
        symbol=request.symbol or "",
        side=orders_pb2.BUY if request.side == "buy" else orders_pb2.SELL,
        qty_scaled=resolve_qty_scaled(
            request.qty,
            _codec_quantity_scale(request.qty, quantity_scale),
            symbol=request.symbol,
        ),
    )
    client_order_id = optional_client_id(request.client_order_id)
    if client_order_id:
        intent.client_order_id = client_order_id

    price_ticks = (
        resolve_price_ticks(request.price, "price", symbol=request.symbol)
        if request.price is not None
        else None
    )
    if request.order_type == "market":
        if request.post_only:
            raise PolyesterValidationError("post_only is only valid for limit GTC orders")
        if request.price is not None:
            raise PolyesterValidationError(
                "price is not valid for market orders; "
                "use market_client_ref_price for a reservation reference"
            )
        market = intent.market_ioc
        market.SetInParent()
        if request.market_client_ref_price is not None:
            market.client_ref_price_ticks = resolve_price_ticks(
                request.market_client_ref_price,
                "market_client_ref_price",
                symbol=request.symbol,
            )
    else:
        tif = request.tif or "gtc"
        if tif == "gtc":
            intent.limit_gtc.SetInParent()
            if price_ticks is not None:
                intent.limit_gtc.price_ticks = price_ticks
            if request.post_only:
                intent.limit_gtc.post_only = True
        else:
            if request.post_only:
                raise PolyesterValidationError("post_only is only valid for limit GTC orders")
            if tif == "ioc":
                intent.limit_ioc.SetInParent()
                if price_ticks is not None:
                    intent.limit_ioc.price_ticks = price_ticks
            else:  # fok
                intent.limit_fok.SetInParent()
                if price_ticks is not None:
                    intent.limit_fok.price_ticks = price_ticks

    risk = risk_policy_from_dict(request.attached_risk)
    if risk is not None:
        intent.attached_risk.CopyFrom(risk)
    return intent


def create_order_to_proto(
    request: CreateOrderRequest,
    *,
    quantity_scale: int | None = None,
) -> orders_pb2.CreateOrderRequest:
    proto = orders_pb2.CreateOrderRequest(
        order=order_intent_from_request(request, quantity_scale=quantity_scale)
    )
    if request.sub_account_id:
        proto.subaccount_id = id_to_int(request.sub_account_id, "sub_account_id")
    return proto


def risk_policy_from_dict(data: dict[str, Any] | None) -> orders_pb2.RiskPolicy | None:
    if not data:
        return None
    stack: list[object] = [data]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"trigger_price_source", "triggerPriceSource"}:
                    raise PolyesterValidationError(
                        "attached risk always uses last trade; "
                        "trigger_price_source cannot be supplied"
                    )
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
    risk = orders_pb2.RiskPolicy()
    ParseDict(data, risk, ignore_unknown_fields=True)
    return risk


def batch_modify_item_to_proto(
    item: dict[str, Any],
    *,
    quantity_scale: int,
) -> orders_pb2.BatchModifyItem:
    key = _item_order_key(item, label="each batch modify item")
    new_price = item.get("new_price")
    new_qty = item.get("new_qty")
    new_attached_risk = item.get("new_attached_risk")
    if not new_price and not new_qty and not new_attached_risk:
        raise PolyesterValidationError(
            "each batch item requires new_price, new_qty, and/or new_attached_risk"
        )
    proto = orders_pb2.BatchModifyItem()
    set_order_key(proto, key, op="each batch modify item")
    if new_price is not None:
        proto.new_price_ticks = resolve_price_ticks(new_price, "new_price")
    if new_qty is not None:
        proto.new_qty_scaled = resolve_qty_scaled(new_qty, quantity_scale, "new_qty")
    risk = risk_policy_from_dict(new_attached_risk)
    if risk is not None:
        proto.new_attached_risk.CopyFrom(risk)
    behavior = item.get("behavior")
    if behavior:
        key = str(behavior).lower()
        if key not in MODIFY_BEHAVIOR_TO_PROTO:
            raise PolyesterValidationError(
                "behavior must be amend_or_replace, amend_only, or replace_only"
            )
        proto.behavior = getattr(orders_pb2, MODIFY_BEHAVIOR_TO_PROTO[key])
    if item.get("new_client_order_id"):
        proto.new_client_order_id = required_client_id(
            str(item["new_client_order_id"]), "new_client_order_id"
        )
    return proto


def batch_create_orders_to_proto(
    *,
    items: list[CreateOrderRequest | dict[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    allow_partial: bool = False,
    quantity_scale: int | None = None,
) -> orders_pb2.BatchCreateOrdersRequest:
    # ``allow_partial`` was removed from the wire in POLY-3701; it is accepted
    # for backwards compatibility but ignored.
    if not items:
        raise PolyesterValidationError("batch_create requires at least one item")
    proto = orders_pb2.BatchCreateOrdersRequest(
        request_id=optional_request_id(request_id) or f"batch-create-{uuid.uuid4().hex[:12]}",
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    for item in items:
        if isinstance(item, CreateOrderRequest):
            normalized = item
        else:
            normalized = normalize_create_order_request(cast(Any, item))
        proto.items.append(order_intent_from_request(normalized, quantity_scale=quantity_scale))
    return proto


def batch_cancel_item_to_proto(item: dict[str, Any]) -> orders_pb2.BatchCancelItem:
    key = _item_order_key(item, label="each batch cancel item")
    symbol_id = item.get("symbol_id")
    proto = orders_pb2.BatchCancelItem()
    set_order_key(proto, key, op="each batch cancel item")
    if symbol_id is not None:
        proto.symbol_id = int(symbol_id)
    return proto


def batch_cancel_orders_to_proto(
    *,
    items: list[dict[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
) -> orders_pb2.BatchCancelOrdersRequest:
    if not items:
        raise PolyesterValidationError("batch_cancel requires at least one item")
    proto = orders_pb2.BatchCancelOrdersRequest(
        request_id=optional_request_id(request_id) or f"batch-cancel-{uuid.uuid4().hex[:12]}",
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    for item in items:
        proto.items.append(batch_cancel_item_to_proto(item))
    return proto


def cancel_all_after_to_proto(
    *,
    sub_account_id: str | int | None = None,
    timeout_sec: int,
    symbol: str | None = None,
    side: str | None = None,
    request_id: str | None = None,
) -> orders_pb2.CancelAllAfterRequest:
    proto = orders_pb2.CancelAllAfterRequest(
        request_id=optional_request_id(request_id) or f"cancel-after-{uuid.uuid4().hex[:12]}",
        timeout_sec=timeout_sec,
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if symbol:
        proto.symbol = symbol
    if side:
        key = side.lower()
        if key not in ORDER_SIDE_TO_PROTO:
            raise PolyesterValidationError("side must be buy or sell")
        proto.side = getattr(orders_pb2, ORDER_SIDE_TO_PROTO[key])
    return proto


def batch_modify_orders_to_proto(
    *,
    items: list[dict[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    behavior_default: str | None = None,
    allow_partial: bool = False,
    quantity_scale: int | None = None,
) -> orders_pb2.BatchModifyOrdersRequest:
    if not items:
        raise PolyesterValidationError("batch_modify requires at least one item")
    proto = orders_pb2.BatchModifyOrdersRequest(
        request_id=optional_request_id(request_id) or f"batch-mod-{uuid.uuid4().hex[:12]}",
        allow_partial=allow_partial,
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if behavior_default:
        key = behavior_default.lower()
        if key not in MODIFY_BEHAVIOR_TO_PROTO:
            raise PolyesterValidationError(
                "behavior_default must be amend_or_replace, amend_only, or replace_only"
            )
        proto.behavior_default = getattr(orders_pb2, MODIFY_BEHAVIOR_TO_PROTO[key])
    for item in items:
        new_qty = item.get("new_qty")
        item_scale = _codec_quantity_scale(new_qty, quantity_scale) if new_qty is not None else 0
        proto.items.append(batch_modify_item_to_proto(item, quantity_scale=item_scale))
    return proto


def modify_order_to_proto(
    *,
    symbol: str,
    key: OrderKey,
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    new_price: object | None = None,
    new_qty: object | None = None,
    new_attached_risk: dict[str, Any] | None = None,
    behavior: str | None = None,
    new_client_order_id: str | None = None,
    quantity_scale: int | None = None,
) -> orders_pb2.ModifyOrderRequest:
    if not new_price and not new_qty and not new_attached_risk:
        raise PolyesterValidationError(
            "modify requires new_price, new_qty, and/or new_attached_risk"
        )

    proto = orders_pb2.ModifyOrderRequest(
        request_id=optional_request_id(request_id) or f"mod-{uuid.uuid4().hex[:12]}",
    )
    set_order_key(proto, key, op="modify")
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if new_price is not None:
        proto.new_price_ticks = resolve_price_ticks(new_price, "new_price")  # type: ignore[arg-type]
    if new_qty is not None:
        proto.new_qty_scaled = resolve_qty_scaled(
            new_qty,  # type: ignore[arg-type]
            _codec_quantity_scale(new_qty, quantity_scale),
            "new_qty",
        )
    if behavior:
        key = behavior.lower()
        if key not in MODIFY_BEHAVIOR_TO_PROTO:
            raise PolyesterValidationError(
                "behavior must be amend_or_replace, amend_only, or replace_only"
            )
        proto.behavior = getattr(orders_pb2, MODIFY_BEHAVIOR_TO_PROTO[key])
    if new_client_order_id:
        proto.new_client_order_id = required_client_id(
            new_client_order_id, "new_client_order_id"
        )
    risk = risk_policy_from_dict(new_attached_risk)
    if risk is not None:
        proto.new_attached_risk.CopyFrom(risk)
    return proto


def cancel_all_orders_to_proto(
    *,
    sub_account_id: str | int | None = None,
    symbol: str | None = None,
    side: str | None = None,
    dry_run: bool = False,
    request_id: str | None = None,
) -> orders_pb2.CancelAllOrdersRequest:
    proto = orders_pb2.CancelAllOrdersRequest(
        request_id=optional_request_id(request_id) or f"cancel-all-{uuid.uuid4().hex[:12]}",
        dry_run=dry_run,
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if symbol:
        proto.symbol = symbol
    if side:
        key = side.lower()
        if key not in ORDER_SIDE_TO_PROTO:
            raise PolyesterValidationError("side must be buy or sell")
        proto.side = getattr(orders_pb2, ORDER_SIDE_TO_PROTO[key])
    return proto


def quantity_scale_for_symbol(catalogs: CatalogManager | None, symbol: str | None) -> int:
    if not symbol or catalogs is None:
        raise PolyesterValidationError(
            "quantity scale requires symbol and catalogs "
            "(or pass a scaled Quantity / explicit quantity_scale)"
        )
    scale = catalogs.base_quantity_scale_for_symbol(symbol)
    if scale is None:
        raise PolyesterValidationError(
            f"quantity scale for {symbol!r} is unavailable; "
            "await client.wait_for_catalogs() before placing orders, "
            "or pass a scaled Quantity"
        )
    return scale


def resolve_quantity_scale(
    catalogs: CatalogManager | None,
    symbol: str | None,
    *values: object | None,
) -> int:
    """Resolve base quantity scale for decimal qty inputs.

    Scaled :class:`Quantity` values do not require catalogs/symbol. Decimal
    strings/Decimals hard-error when scale cannot be resolved.
    """
    needs_catalog_scale = any(
        value is not None and not isinstance(value, Quantity) for value in values
    )
    if not needs_catalog_scale:
        if symbol and catalogs is not None:
            scale = catalogs.base_quantity_scale_for_symbol(symbol)
            if scale is not None:
                return scale
        for value in values:
            if isinstance(value, Quantity) and value.scale is not None:
                return value.scale
        return 0
    return quantity_scale_for_symbol(catalogs, symbol)


def parse_optional_subaccount_id(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return id_to_int(value, "sub_account_id")
