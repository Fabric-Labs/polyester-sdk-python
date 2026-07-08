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
FEE_SOURCE_TO_PROTO = {
    "quote": "QUOTE",
    "received": "RECEIVED",
}
SELF_TRADE_PREVENTION_MODE_TO_PROTO = {
    "expire_taker": "EXPIRE_TAKER",
    "expire_maker": "EXPIRE_MAKER",
    "expire_both": "EXPIRE_BOTH",
}
LADDER_DISTRIBUTION_TO_PROTO = {
    "linear": "LINEAR",
    "geometric": "GEOMETRIC",
    "weighted_favorable": "WEIGHTED_FAVORABLE",
}


def create_trigger_to_proto(
    *,
    symbol: str,
    trigger_type: str,
    side: str,
    qty: str,
    trigger_price: str | None = None,
    order_type: str = "market",
    limit_price: str | None = None,
    trigger_price_source: str = "last",
    tif: str = "gtc",
    sub_account_id: str | int | None = None,
    client_trigger_id: str | None = None,
    post_only: bool = False,
    fee_source: str | None = None,
    self_trade_prevention_mode: str | None = None,
    trailing_distance_ticks: int | None = None,
    trailing_distance_bps: int | None = None,
    activation_price: str | None = None,
    max_slippage_ticks: int | None = None,
    max_slippage_bps: int | None = None,
    twap_duration_ms: int | None = None,
    twap_slice_interval_ms: int | None = None,
    ladder_price_min: str | None = None,
    ladder_price_max: str | None = None,
    ladder_levels: int | None = None,
    ladder_distribution: str | None = None,
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
        side=orders_pb2.BUY if side.lower() == "buy" else orders_pb2.SELL,
        order_type=orders_pb2.LIMIT if order_key == "limit" else orders_pb2.MARKET,
        qty_scaled=parse_qty_scaled(qty, quantity_scale, "qty"),
        post_only=post_only,
    )
    if trigger_price is not None:
        proto.trigger_price_ticks = parse_price_ticks(trigger_price, "trigger_price")
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
    if fee_source is not None:
        fee_key = fee_source.lower()
        if fee_key not in FEE_SOURCE_TO_PROTO:
            raise PolyesterValidationError("fee_source must be quote or received")
        proto.fee_source = getattr(orders_pb2, FEE_SOURCE_TO_PROTO[fee_key])
    if self_trade_prevention_mode is not None:
        stp_key = self_trade_prevention_mode.lower()
        if stp_key not in SELF_TRADE_PREVENTION_MODE_TO_PROTO:
            raise PolyesterValidationError(
                "self_trade_prevention_mode must be expire_taker, expire_maker, or expire_both"
            )
        proto.self_trade_prevention_mode = getattr(
            orders_pb2, SELF_TRADE_PREVENTION_MODE_TO_PROTO[stp_key]
        )
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
    if twap_duration_ms is not None:
        proto.twap_duration_ms = twap_duration_ms
    if twap_slice_interval_ms is not None:
        proto.twap_slice_interval_ms = twap_slice_interval_ms
    if ladder_price_min is not None:
        proto.ladder_price_min_ticks = parse_price_ticks(ladder_price_min, "ladder_price_min")
    if ladder_price_max is not None:
        proto.ladder_price_max_ticks = parse_price_ticks(ladder_price_max, "ladder_price_max")
    if ladder_levels is not None:
        proto.ladder_levels = ladder_levels
    if ladder_distribution is not None:
        ladder_key = ladder_distribution.lower()
        if ladder_key not in LADDER_DISTRIBUTION_TO_PROTO:
            raise PolyesterValidationError(
                "ladder_distribution must be linear, geometric, or weighted_favorable"
            )
        proto.ladder_distribution = getattr(triggers_pb2, LADDER_DISTRIBUTION_TO_PROTO[ladder_key])
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
