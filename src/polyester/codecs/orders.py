from __future__ import annotations

import uuid
from typing import Any

import msgspec
from google.protobuf.json_format import ParseDict

from polyester.catalogs import CatalogManager
from polyester.codecs.scalars import id_to_int, omit_none, parse_price_ticks, parse_qty_scaled
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CreateOrderRequest

ORDER_SIDE_TO_PROTO = {"buy": "BUY", "sell": "SELL"}
ORDER_TYPE_TO_PROTO = {"limit": "LIMIT", "market": "MARKET"}
TIF_TO_PROTO = {"gtc": "GTC", "ioc": "IOC", "fok": "FOK"}
MODIFY_BEHAVIOR_TO_PROTO = {
    "amend_or_replace": "AMEND_OR_REPLACE",
    "amend_only": "AMEND_ONLY",
    "replace_only": "REPLACE_ONLY",
}


def normalize_create_order_request(
    request: CreateOrderRequest | None = None,
    **kwargs: Any,
) -> CreateOrderRequest:
    if request is not None and kwargs:
        raise PolyesterValidationError("Pass either request or keyword arguments, not both")
    data = request if request is not None else kwargs
    try:
        return msgspec.convert(data, type=CreateOrderRequest)
    except (msgspec.ValidationError, TypeError) as exc:
        raise PolyesterValidationError("Invalid orders.create request") from exc


def create_order_to_wire(
    request: CreateOrderRequest,
    *,
    quantity_scale: int = 8,
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
        "qty_scaled": parse_qty_scaled(request.qty, quantity_scale),
        "limit_price_ticks": parse_price_ticks(request.price, "price") if request.price else None,
        "sub_account_id": request.sub_account_id or None,
        "client_order_id": request.client_order_id,
    }
    return omit_none(payload)


def create_order_to_proto(
    request: CreateOrderRequest,
    *,
    quantity_scale: int = 8,
) -> orders_pb2.CreateOrderRequest:
    if request.symbol is None and request.symbol_id is None:
        raise PolyesterValidationError("orders.create requires symbol or symbol_id")
    if request.side not in ORDER_SIDE_TO_PROTO:
        raise PolyesterValidationError("side must be 'buy' or 'sell'")
    if request.order_type not in ORDER_TYPE_TO_PROTO:
        raise PolyesterValidationError("order_type must be 'limit' or 'market'")
    if request.tif is not None and request.tif not in TIF_TO_PROTO:
        raise PolyesterValidationError("tif must be one of 'gtc', 'ioc', or 'fok'")

    proto = orders_pb2.CreateOrderRequest(
        symbol=request.symbol or "",
        side=orders_pb2.BUY if request.side == "buy" else orders_pb2.SELL,
        order_type=(
            orders_pb2.LIMIT if request.order_type == "limit" else orders_pb2.MARKET
        ),
        qty_scaled=parse_qty_scaled(request.qty, quantity_scale),
    )
    if request.price is not None:
        proto.price_ticks = parse_price_ticks(request.price, "price")
    if request.tif:
        proto.time_in_force = getattr(orders_pb2, TIF_TO_PROTO[request.tif])
    if request.sub_account_id:
        proto.subaccount_id = id_to_int(request.sub_account_id, "sub_account_id")
    if request.client_order_id:
        proto.client_order_id = request.client_order_id
    if request.post_only:
        proto.post_only = True
    if request.market_client_ref_price is not None:
        proto.market_client_ref_price_ticks = parse_price_ticks(
            request.market_client_ref_price, "market_client_ref_price"
        )
    if request.attached_risk:
        risk = orders_pb2.RiskPolicy()
        ParseDict(request.attached_risk, risk, ignore_unknown_fields=True)
        proto.attached_risk.CopyFrom(risk)
    return proto


def risk_policy_from_dict(data: dict[str, Any] | None) -> orders_pb2.RiskPolicy | None:
    if not data:
        return None
    risk = orders_pb2.RiskPolicy()
    ParseDict(data, risk, ignore_unknown_fields=True)
    return risk


def batch_modify_item_to_proto(
    item: dict[str, Any],
    *,
    quantity_scale: int,
) -> orders_pb2.BatchModifyItem:
    order_id = item.get("order_id")
    client_order_id = item.get("client_order_id")
    has_order_id = order_id is not None
    has_client_order_id = bool(client_order_id)
    if has_order_id == has_client_order_id:
        raise PolyesterValidationError(
            "each batch item requires exactly one of order_id or client_order_id"
        )
    new_price = item.get("new_price")
    new_qty = item.get("new_qty")
    new_attached_risk = item.get("new_attached_risk")
    if not new_price and not new_qty and not new_attached_risk:
        raise PolyesterValidationError(
            "each batch item requires new_price, new_qty, and/or new_attached_risk"
        )
    proto = orders_pb2.BatchModifyItem()
    if order_id is not None:
        proto.order_id = id_to_int(order_id, "order_id")
    if client_order_id:
        proto.client_order_id = str(client_order_id)
    if new_price is not None:
        proto.new_price_ticks = parse_price_ticks(str(new_price), "new_price")
    if new_qty is not None:
        proto.new_qty_scaled = parse_qty_scaled(str(new_qty), quantity_scale, "new_qty")
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
        proto.new_client_order_id = str(item["new_client_order_id"])
    return proto


def batch_create_orders_to_proto(
    *,
    items: list[CreateOrderRequest | dict[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    allow_partial: bool = False,
    quantity_scale: int = 8,
) -> orders_pb2.BatchCreateOrdersRequest:
    if not items:
        raise PolyesterValidationError("batch_create requires at least one item")
    proto = orders_pb2.BatchCreateOrdersRequest(
        request_id=request_id or f"batch-create-{uuid.uuid4().hex[:12]}",
        allow_partial=allow_partial,
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    for item in items:
        if isinstance(item, CreateOrderRequest):
            normalized = item
        else:
            normalized = normalize_create_order_request(item)
        proto.items.append(create_order_to_proto(normalized, quantity_scale=quantity_scale))
    return proto


def batch_cancel_item_to_proto(item: dict[str, Any]) -> orders_pb2.BatchCancelItem:
    order_id = item.get("order_id")
    client_order_id = item.get("client_order_id")
    symbol_id = item.get("symbol_id")
    has_order_id = order_id is not None
    has_client_order_id = bool(client_order_id)
    if has_order_id == has_client_order_id:
        raise PolyesterValidationError(
            "each batch cancel item requires exactly one of order_id or client_order_id"
        )
    proto = orders_pb2.BatchCancelItem()
    if order_id is not None:
        proto.order_id = id_to_int(order_id, "order_id")
    if client_order_id:
        proto.client_order_id = str(client_order_id)
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
        request_id=request_id or f"batch-cancel-{uuid.uuid4().hex[:12]}",
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
        request_id=request_id or f"cancel-after-{uuid.uuid4().hex[:12]}",
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
    quantity_scale: int = 8,
) -> orders_pb2.BatchModifyOrdersRequest:
    if not items:
        raise PolyesterValidationError("batch_modify requires at least one item")
    proto = orders_pb2.BatchModifyOrdersRequest(
        request_id=request_id or f"batch-mod-{uuid.uuid4().hex[:12]}",
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
        proto.items.append(batch_modify_item_to_proto(item, quantity_scale=quantity_scale))
    return proto


def modify_order_to_proto(
    *,
    symbol: str,
    order_id: str | int | None = None,
    client_order_id: str | None = None,
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    new_price: str | None = None,
    new_qty: str | None = None,
    new_attached_risk: dict[str, Any] | None = None,
    behavior: str | None = None,
    new_client_order_id: str | None = None,
    quantity_scale: int = 8,
) -> orders_pb2.ModifyOrderRequest:
    has_order_id = order_id is not None
    has_client_order_id = bool(client_order_id)
    if has_order_id == has_client_order_id:
        raise PolyesterValidationError("modify requires exactly one of order_id or client_order_id")
    if not new_price and not new_qty and not new_attached_risk:
        raise PolyesterValidationError(
            "modify requires new_price, new_qty, and/or new_attached_risk"
        )

    proto = orders_pb2.ModifyOrderRequest(
        request_id=request_id or f"mod-{uuid.uuid4().hex[:12]}",
    )
    if order_id is not None:
        proto.order_id = id_to_int(order_id, "order_id")
    if client_order_id:
        proto.client_order_id = client_order_id
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if new_price is not None:
        proto.new_price_ticks = parse_price_ticks(new_price, "new_price")
    if new_qty is not None:
        proto.new_qty_scaled = parse_qty_scaled(new_qty, quantity_scale, "new_qty")
    if behavior:
        key = behavior.lower()
        if key not in MODIFY_BEHAVIOR_TO_PROTO:
            raise PolyesterValidationError(
                "behavior must be amend_or_replace, amend_only, or replace_only"
            )
        proto.behavior = getattr(orders_pb2, MODIFY_BEHAVIOR_TO_PROTO[key])
    if new_client_order_id:
        proto.new_client_order_id = new_client_order_id
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
        request_id=request_id or f"cancel-all-{uuid.uuid4().hex[:12]}",
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
    if symbol and catalogs is not None:
        return catalogs.base_quantity_scale_for_symbol(symbol)
    return 8


def parse_optional_subaccount_id(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return id_to_int(value, "sub_account_id")
