from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.scalars import id_to_int, parse_price_ticks, parse_qty_scaled
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2

TRIGGER_TYPE_TO_PROTO = {
    "stop_loss": "STOP_LOSS",
    "take_profit": "TAKE_PROFIT",
    "trailing_stop": "TRAILING_STOP",
    "twap": "TWAP",
    "ladder": "LADDER",
}
TRIGGER_PRICE_SOURCE_TO_PROTO = {
    "last": "LAST_PRICE",
    "last_price": "LAST_PRICE",
    "index": "INDEX_PRICE",
    "index_price": "INDEX_PRICE",
    "mark": "MARK_PRICE",
    "mark_price": "MARK_PRICE",
}


def create_trigger_to_proto(
    *,
    symbol: str,
    trigger_type: str,
    trigger_price: str,
    side: str,
    qty: str,
    order_type: str = "market",
    limit_price: str | None = None,
    trigger_price_source: str = "last",
    tif: str = "gtc",
    sub_account_id: str | int | None = None,
    client_trigger_id: str | None = None,
    post_only: bool = False,
    quantity_scale: int = 8,
) -> triggers_pb2.CreateTriggerRequest:
    type_key = trigger_type.lower().replace("-", "_")
    if type_key not in TRIGGER_TYPE_TO_PROTO:
        raise PolyesterValidationError(
            "trigger_type must be stop_loss, take_profit, trailing_stop, twap, or ladder"
        )
    if side.lower() not in ("buy", "sell"):
        raise PolyesterValidationError("side must be buy or sell")
    order_key = order_type.lower()
    if order_key not in ("limit", "market"):
        raise PolyesterValidationError("order_type must be limit or market")

    proto = triggers_pb2.CreateTriggerRequest(
        symbol=symbol,
        trigger_type=getattr(triggers_pb2, TRIGGER_TYPE_TO_PROTO[type_key]),
        trigger_price_ticks=parse_price_ticks(trigger_price, "trigger_price"),
        side=orders_pb2.BUY if side.lower() == "buy" else orders_pb2.SELL,
        order_type=orders_pb2.LIMIT if order_key == "limit" else orders_pb2.MARKET,
        qty_scaled=parse_qty_scaled(qty, quantity_scale, "qty"),
        post_only=post_only,
    )
    source_key = trigger_price_source.lower()
    if source_key in TRIGGER_PRICE_SOURCE_TO_PROTO:
        proto.trigger_price_source = getattr(
            orders_pb2, TRIGGER_PRICE_SOURCE_TO_PROTO[source_key]
        )
    if tif.lower() == "gtc":
        proto.time_in_force = orders_pb2.GTC
    elif tif.lower() == "ioc":
        proto.time_in_force = orders_pb2.IOC
    elif tif.lower() == "fok":
        proto.time_in_force = orders_pb2.FOK
    if limit_price is not None:
        proto.limit_price_ticks = parse_price_ticks(limit_price, "limit_price")
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if client_trigger_id:
        proto.client_trigger_id = client_trigger_id
    return proto


def quantity_scale_for_symbol(catalogs: CatalogManager | None, symbol: str | None) -> int:
    if symbol and catalogs is not None:
        return catalogs.base_quantity_scale_for_symbol(symbol)
    return 8


def modify_trigger_to_proto(
    *,
    trigger_id: str | int,
    sub_account_id: str | int | None = None,
    trigger_price: str | None = None,
    limit_price: str | None = None,
    trailing_distance_ticks: int | None = None,
    trailing_distance_bps: int | None = None,
    activation_price: str | None = None,
    max_slippage_ticks: int | None = None,
    max_slippage_bps: int | None = None,
) -> triggers_pb2.ModifyTriggerRequest:
    if not any(
        (
            trigger_price,
            limit_price,
            trailing_distance_ticks is not None,
            trailing_distance_bps is not None,
            activation_price,
            max_slippage_ticks is not None,
            max_slippage_bps is not None,
        )
    ):
        raise PolyesterValidationError(
            "modify requires at least one of trigger_price, limit_price, "
            "trailing_distance_ticks, trailing_distance_bps, activation_price, "
            "max_slippage_ticks, or max_slippage_bps"
        )
    proto = triggers_pb2.ModifyTriggerRequest(
        trigger_id=id_to_int(trigger_id, "trigger_id"),
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if trigger_price is not None:
        proto.trigger_price_ticks = parse_price_ticks(trigger_price, "trigger_price")
    if limit_price is not None:
        proto.limit_price_ticks = parse_price_ticks(limit_price, "limit_price")
    if trailing_distance_ticks is not None:
        proto.trailing_distance_ticks = trailing_distance_ticks
    if trailing_distance_bps is not None:
        proto.trailing_distance_bps = trailing_distance_bps
    if activation_price is not None:
        proto.activation_price_ticks = parse_price_ticks(activation_price, "activation_price")
    if max_slippage_ticks is not None:
        proto.max_slippage_ticks = max_slippage_ticks
    if max_slippage_bps is not None:
        proto.max_slippage_bps = max_slippage_bps
    return proto
