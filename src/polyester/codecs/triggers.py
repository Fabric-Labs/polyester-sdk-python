from __future__ import annotations

from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.correlation_id import optional_client_id
from polyester.codecs.scalars import id_to_int
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.types.money import resolve_price_ticks, resolve_qty_scaled

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
FEE_ASSET_TO_PROTO = {
    "quote": "QUOTE",
    "base": "BASE",
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


def _conditional_child(
    *,
    order_type: str,
    tif: str,
    limit_price: Any | None,
    post_only: bool,
    symbol: str,
) -> triggers_pb2.ConditionalChildExecution:
    """Map flat order_type/tif/post_only onto a conditional child execution.

    market -> market_ioc; limit+gtc -> limit_gtc; limit+ioc -> limit_ioc;
    limit+fok -> limit_fok. ``post_only`` is only valid for limit GTC.
    """
    child = triggers_pb2.ConditionalChildExecution()
    if order_type == "market":
        if post_only:
            raise PolyesterValidationError("post_only is only valid for limit GTC executions")
        child.market_ioc.SetInParent()
        return child
    price_ticks = (
        resolve_price_ticks(limit_price, "limit_price", symbol=symbol)  # type: ignore[arg-type]
        if limit_price is not None
        else None
    )
    tif_key = tif.lower()
    if tif_key == "gtc":
        child.limit_gtc.SetInParent()
        if price_ticks is not None:
            child.limit_gtc.price_ticks = price_ticks
        if post_only:
            child.limit_gtc.post_only = True
    elif tif_key == "ioc":
        if post_only:
            raise PolyesterValidationError("post_only is only valid for limit GTC executions")
        child.limit_ioc.SetInParent()
        if price_ticks is not None:
            child.limit_ioc.price_ticks = price_ticks
    elif tif_key == "fok":
        if post_only:
            raise PolyesterValidationError("post_only is only valid for limit GTC executions")
        child.limit_fok.SetInParent()
        if price_ticks is not None:
            child.limit_fok.price_ticks = price_ticks
    else:
        raise PolyesterValidationError("tif must be one of 'gtc', 'ioc', or 'fok'")
    return child


def create_trigger_to_proto(
    *,
    symbol: str,
    trigger_type: str,
    side: str,
    qty: object,
    trigger_price: Any | None = None,
    order_type: str = "market",
    limit_price: Any | None = None,
    trigger_price_source: str = "last",
    tif: str = "gtc",
    sub_account_id: str | int | None = None,
    client_trigger_id: str | None = None,
    post_only: bool = False,
    fee_asset: str | None = None,
    self_trade_prevention_mode: str | None = None,
    trailing_distance_ticks: int | None = None,
    trailing_distance_bps: int | None = None,
    activation_price: Any | None = None,
    max_slippage_ticks: int | None = None,
    max_slippage_bps: int | None = None,
    twap_duration_ms: int | None = None,
    twap_slice_interval_ms: int | None = None,
    ladder_price_min: Any | None = None,
    ladder_price_max: Any | None = None,
    ladder_levels: int | None = None,
    ladder_distribution: str | None = None,
    quantity_scale: int,
) -> triggers_pb2.CreateTriggerRequest:
    type_key = trigger_type.lower().replace("-", "_")
    if type_key not in TRIGGER_TYPE_TO_PROTO:
        raise PolyesterValidationError(
            "trigger_type must be stop_loss, take_profit, trailing_stop, twap, or ladder"
        )
    side_key = side.lower()
    if side_key not in ("buy", "sell"):
        raise PolyesterValidationError("side must be buy or sell")
    order_key = order_type.lower()
    if order_key not in ("limit", "market"):
        raise PolyesterValidationError("order_type must be limit or market")
    side_proto = orders_pb2.BUY if side_key == "buy" else orders_pb2.SELL

    intent = triggers_pb2.TriggerIntent(
        symbol=symbol,
        qty_scaled=resolve_qty_scaled(qty, quantity_scale, "qty", symbol=symbol),  # type: ignore[arg-type]
    )
    validated_trigger_id = optional_client_id(client_trigger_id, "client_trigger_id")
    if validated_trigger_id:
        intent.client_trigger_id = validated_trigger_id
    if fee_asset is not None:
        fee_key = fee_asset.lower()
        if fee_key not in FEE_ASSET_TO_PROTO:
            raise PolyesterValidationError("fee_asset must be quote or base")
        intent.fee_asset = getattr(orders_pb2, FEE_ASSET_TO_PROTO[fee_key])
    if self_trade_prevention_mode is not None:
        stp_key = self_trade_prevention_mode.lower()
        if stp_key not in SELF_TRADE_PREVENTION_MODE_TO_PROTO:
            raise PolyesterValidationError(
                "self_trade_prevention_mode must be expire_taker, expire_maker, or expire_both"
            )
        intent.self_trade_prevention_mode = getattr(
            orders_pb2, SELF_TRADE_PREVENTION_MODE_TO_PROTO[stp_key]
        )

    # trigger_price_source is no longer part of the conditional/trailing wire
    # shape in POLY-3701; the argument is accepted but ignored.
    _ = trigger_price_source

    if type_key in ("stop_loss", "take_profit"):
        conditional = triggers_pb2.ConditionalTrigger(side=side_proto)
        if trigger_price is not None:
            conditional.trigger_price_ticks = resolve_price_ticks(
                trigger_price, "trigger_price", symbol=symbol
            )  # type: ignore[arg-type]
        conditional.child.CopyFrom(
            _conditional_child(
                order_type=order_key,
                tif=tif,
                limit_price=limit_price,
                post_only=post_only,
                symbol=symbol,
            )
        )
        getattr(intent, type_key).CopyFrom(conditional)
    elif type_key == "trailing_stop":
        # Standalone trailing create remains sell-only; the wire always
        # populates the wire ``side`` field (attached trailing may use either).
        if side_key != "sell":
            raise PolyesterValidationError("trailing_stop only supports side=sell")
        trailing = intent.trailing_stop
        trailing.SetInParent()
        trailing.side = side_proto
        if trailing_distance_ticks is not None:
            trailing.trailing_distance_ticks = trailing_distance_ticks
        if trailing_distance_bps is not None:
            trailing.trailing_distance_bps = trailing_distance_bps
        if activation_price is not None:
            trailing.activation_price_ticks = resolve_price_ticks(
                activation_price, "activation_price", symbol=symbol
            )  # type: ignore[arg-type]
        if max_slippage_ticks is not None:
            trailing.max_slippage_ticks = max_slippage_ticks
        if max_slippage_bps is not None:
            trailing.max_slippage_bps = max_slippage_bps
    elif type_key == "twap":
        twap = intent.twap
        twap.side = side_proto
        if twap_duration_ms is not None:
            twap.duration_ms = twap_duration_ms
        if twap_slice_interval_ms is not None:
            twap.slice_interval_ms = twap_slice_interval_ms
        # TWAP children are market-IOC or limit-GTC only.
        if order_key == "limit":
            if limit_price is not None:
                twap.limit_gtc.price_ticks = resolve_price_ticks(
                    limit_price, "limit_price", symbol=symbol
                )  # type: ignore[arg-type]
            else:
                twap.limit_gtc.SetInParent()
        else:
            twap.market_ioc.SetInParent()
    else:  # ladder
        if ladder_distribution is not None and ladder_distribution.lower() != "linear":
            raise PolyesterValidationError("ladder_distribution must be linear")
        ladder = intent.ladder
        ladder.side = side_proto
        ladder.SetInParent()
        if ladder_price_min is not None:
            ladder.price_min_ticks = resolve_price_ticks(
                ladder_price_min, "ladder_price_min", symbol=symbol
            )  # type: ignore[arg-type]
        if ladder_price_max is not None:
            ladder.price_max_ticks = resolve_price_ticks(
                ladder_price_max, "ladder_price_max", symbol=symbol
            )  # type: ignore[arg-type]
        if ladder_levels is not None:
            ladder.levels = ladder_levels
        if post_only:
            ladder.post_only = True

    proto = triggers_pb2.CreateTriggerRequest(trigger=intent)
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
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
            "await client.wait_for_catalogs() before creating triggers, "
            "or pass a scaled Quantity"
        )
    return scale


def modify_trigger_to_proto(
    *,
    trigger_id: str | int,
    sub_account_id: str | int | None = None,
    trigger_price: Any | None = None,
    limit_price: Any | None = None,
    trailing_distance_ticks: int | None = None,
    trailing_distance_bps: int | None = None,
    activation_price: Any | None = None,
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
        proto.trigger_price_ticks = resolve_price_ticks(trigger_price, "trigger_price")  # type: ignore[arg-type]
    if limit_price is not None:
        proto.limit_price_ticks = resolve_price_ticks(limit_price, "limit_price")  # type: ignore[arg-type]
    if trailing_distance_ticks is not None:
        proto.trailing_distance_ticks = trailing_distance_ticks
    if trailing_distance_bps is not None:
        proto.trailing_distance_bps = trailing_distance_bps
    if activation_price is not None:
        proto.activation_price_ticks = resolve_price_ticks(activation_price, "activation_price")  # type: ignore[arg-type]
    if max_slippage_ticks is not None:
        proto.max_slippage_ticks = max_slippage_ticks
    if max_slippage_bps is not None:
        proto.max_slippage_bps = max_slippage_bps
    return proto
