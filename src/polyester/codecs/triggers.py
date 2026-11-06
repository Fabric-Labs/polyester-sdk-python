from __future__ import annotations

from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.bps import (
    MAX_SELL_SLIPPAGE_BPS,
    max_slippage_bps_for_side,
    validate_bps,
)
from polyester.codecs.correlation_id import optional_client_id
from polyester.codecs.scalars import id_to_int, tick_count
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
}
# Spot markets have no mark price; the backend rejects it.
_UNSUPPORTED_SPOT_PRICE_SOURCES = frozenset({"mark", "mark_price"})


def trigger_price_source_to_proto(
    value: object, field_name: str = "trigger_price_source"
) -> orders_pb2.TriggerPriceSource:
    """Map ``last`` or ``index`` (as trigger reads report it) to the wire enum.

    ``None`` or an empty string leaves the source unset; the server then uses
    the last trade price. Spot markets do not support ``mark``.
    """
    if value is None or value == "":
        return orders_pb2.TRIGGER_PRICE_SOURCE_UNSPECIFIED
    key = value.strip().lower() if isinstance(value, str) else ""
    if key in _UNSUPPORTED_SPOT_PRICE_SOURCES:
        raise PolyesterValidationError(
            f"{field_name} mark is not supported on spot markets; use last or index"
        )
    if key not in TRIGGER_PRICE_SOURCE_TO_PROTO:
        raise PolyesterValidationError(f"{field_name} must be last or index")
    return getattr(orders_pb2, TRIGGER_PRICE_SOURCE_TO_PROTO[key])


FEE_ASSET_TO_PROTO = {
    "quote": "QUOTE",
    "base": "BASE",
}
SELF_TRADE_PREVENTION_MODE_TO_PROTO = {
    "expire_taker": "EXPIRE_TAKER",
    "expire_maker": "EXPIRE_MAKER",
    "expire_both": "EXPIRE_BOTH",
}


def self_trade_prevention_mode_to_proto(value: str) -> orders_pb2.SelfTradePreventionMode:
    """Wire value of ``expire_taker``, ``expire_maker`` or ``expire_both`` (any case)."""
    key = value.lower() if isinstance(value, str) else ""
    if key not in SELF_TRADE_PREVENTION_MODE_TO_PROTO:
        raise PolyesterValidationError(
            "self_trade_prevention_mode must be expire_taker, expire_maker, or expire_both"
        )
    return getattr(orders_pb2, SELF_TRADE_PREVENTION_MODE_TO_PROTO[key])


LADDER_DISTRIBUTION_TO_PROTO = {
    "linear": "LINEAR",
    "geometric": "GEOMETRIC",
    "weighted_favorable": "WEIGHTED_FAVORABLE",
}


def _conditional_child(
    *,
    side: str,
    order_type: str,
    tif: str,
    limit_price: Any | None,
    post_only: bool,
    symbol: str,
    max_slippage_ticks: int | None = None,
    max_slippage_bps: int | None = None,
) -> triggers_pb2.ConditionalChildExecution:
    """Map flat order_type/tif/post_only onto a conditional child execution.

    market -> market_ioc; limit+gtc -> limit_gtc; limit+ioc -> limit_ioc;
    limit+fok -> limit_fok. ``post_only`` is only valid for limit GTC. A
    market child takes at most one slippage cap (``max_slippage_ticks`` or
    ``max_slippage_bps``: 1 to 10000 to buy, 1 to 9999 to sell); without one
    the pair's default applies.
    """
    child = triggers_pb2.ConditionalChildExecution()
    if order_type == "market":
        if post_only:
            raise PolyesterValidationError("post_only is only valid for limit GTC executions")
        market = child.market_ioc
        market.SetInParent()
        if max_slippage_ticks is not None and max_slippage_bps is not None:
            raise PolyesterValidationError(
                "a market child allows at most one of max_slippage_ticks or max_slippage_bps"
            )
        if max_slippage_ticks is not None:
            market.max_slippage_ticks = tick_count(max_slippage_ticks, "max_slippage_ticks")
        elif max_slippage_bps is not None:
            market.max_slippage_bps = validate_bps(
                max_slippage_bps, "max_slippage_bps", max_value=max_slippage_bps_for_side(side)
            )
        return child
    if max_slippage_ticks is not None or max_slippage_bps is not None:
        raise PolyesterValidationError(
            "max_slippage_ticks and max_slippage_bps apply to a market child only; "
            "a limit child is capped by its limit price"
        )
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
    symbol_id: int,
    trigger_type: str,
    side: str,
    qty: object,
    trigger_price: Any | None = None,
    order_type: str = "market",
    limit_price: Any | None = None,
    trigger_price_source: str | None = None,
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
    if symbol_id <= 0:
        raise PolyesterValidationError("create trigger requires a resolved symbol_id")
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
    # Validate presence, including explicit zero values, before selecting a
    # strategy. A field outside its strategy must never disappear silently.
    for option, value, supported in (
        ("trailing_distance_ticks", trailing_distance_ticks, ("trailing_stop",)),
        ("trailing_distance_bps", trailing_distance_bps, ("trailing_stop",)),
        ("activation_price", activation_price, ("trailing_stop",)),
        ("twap_duration_ms", twap_duration_ms, ("twap",)),
        ("twap_slice_interval_ms", twap_slice_interval_ms, ("twap",)),
        ("ladder_price_min", ladder_price_min, ("ladder",)),
        ("ladder_price_max", ladder_price_max, ("ladder",)),
        ("ladder_levels", ladder_levels, ("ladder",)),
        ("ladder_distribution", ladder_distribution, ("ladder",)),
        ("trigger_price", trigger_price, ("stop_loss", "take_profit")),
    ):
        if value is not None and type_key not in supported:
            raise PolyesterValidationError(f"{option} applies only to {' or '.join(supported)}")
    if post_only and type_key in ("trailing_stop", "twap"):
        raise PolyesterValidationError("post_only applies only to limit GTC stops or ladder")
    if limit_price is not None and (
        type_key == "ladder" or (type_key != "trailing_stop" and order_key == "market")
    ):
        raise PolyesterValidationError(
            "limit_price applies only to limit children or a buy trailing_stop"
        )
    if (type_key == "ladder" or (type_key == "twap" and order_key == "limit")) and (
        max_slippage_ticks is not None or max_slippage_bps is not None
    ):
        raise PolyesterValidationError(
            "max_slippage_ticks and max_slippage_bps apply only to market children or trailing_stop"
        )
    if not isinstance(tif, str):
        raise PolyesterValidationError("tif must be one of 'gtc', 'ioc', or 'fok'")
    tif_key = tif.lower()
    if tif_key not in ("gtc", "ioc", "fok"):
        raise PolyesterValidationError("tif must be one of 'gtc', 'ioc', or 'fok'")
    # gtc is the public helper's default. Fixed IOC executions also accept ioc.
    if type_key == "ladder" or (type_key == "twap" and order_key == "limit"):
        if tif_key != "gtc":
            raise PolyesterValidationError("tif must be gtc for ladder or twap limit slices")
    elif (type_key == "trailing_stop" or order_key == "market") and tif_key == "fok":
        raise PolyesterValidationError(
            "tif=fok applies only to stop_loss or take_profit limit children"
        )
    if type_key == "trailing_stop" and side_key == "sell" and order_key == "limit":
        raise PolyesterValidationError(
            "order_type=limit applies only to buy trailing_stop children"
        )
    side_proto = orders_pb2.BUY if side_key == "buy" else orders_pb2.SELL

    intent = triggers_pb2.TriggerIntent(
        symbol_id=symbol_id,
        qty_scaled=resolve_qty_scaled(
            qty, quantity_scale, "qty", symbol=symbol, symbol_id=symbol_id  # type: ignore[arg-type]
        ),
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
        intent.self_trade_prevention_mode = self_trade_prevention_mode_to_proto(
            self_trade_prevention_mode
        )

    price_source = trigger_price_source_to_proto(trigger_price_source)
    if price_source and type_key in ("twap", "ladder"):
        raise PolyesterValidationError(
            "trigger_price_source applies to stop_loss, take_profit and trailing_stop only"
        )

    if type_key in ("stop_loss", "take_profit"):
        conditional = triggers_pb2.ConditionalTrigger(
            side=side_proto, trigger_price_source=price_source
        )
        if trigger_price is not None:
            conditional.trigger_price_ticks = resolve_price_ticks(
                trigger_price, "trigger_price", symbol=symbol
            )  # type: ignore[arg-type]
        conditional.child.CopyFrom(
            _conditional_child(
                side=side_key,
                order_type=order_key,
                tif=tif,
                limit_price=limit_price,
                post_only=post_only,
                symbol=symbol,
                max_slippage_ticks=max_slippage_ticks,
                max_slippage_bps=max_slippage_bps,
            )
        )
        getattr(intent, type_key).CopyFrom(conditional)
    elif type_key == "trailing_stop":
        # A buy trailing stop needs its maximum price (the most its child pays
        # per unit); a sell trailing stop must not carry one.
        trailing = intent.trailing_stop
        trailing.SetInParent()
        trailing.side = side_proto
        trailing.trigger_price_source = price_source
        if side_key == "buy":
            if limit_price is None:
                raise PolyesterValidationError(
                    "trailing_stop with side=buy requires limit_price (the maximum price)"
                )
            trailing.limit_price_ticks = resolve_price_ticks(
                limit_price, "limit_price", symbol=symbol
            )  # type: ignore[arg-type]
        elif limit_price is not None:
            raise PolyesterValidationError(
                "trailing_stop with side=sell does not take limit_price; "
                "the maximum price applies to buys only"
            )
        if trailing_distance_ticks is not None and trailing_distance_bps is not None:
            raise PolyesterValidationError(
                "set at most one of trailing_distance_ticks or trailing_distance_bps"
            )
        if max_slippage_ticks is not None and max_slippage_bps is not None:
            raise PolyesterValidationError(
                "set at most one of max_slippage_ticks or max_slippage_bps"
            )
        if trailing_distance_ticks is not None:
            trailing.trailing_distance_ticks = tick_count(
                trailing_distance_ticks, "trailing_distance_ticks"
            )
        if trailing_distance_bps is not None:
            trailing.trailing_distance_bps = validate_bps(
                trailing_distance_bps, "trailing_distance_bps"
            )
        if activation_price is not None:
            trailing.activation_price_ticks = resolve_price_ticks(
                activation_price, "activation_price", symbol=symbol
            )  # type: ignore[arg-type]
            if side_key == "buy" and trailing.limit_price_ticks < trailing.activation_price_ticks:
                raise PolyesterValidationError(
                    "trailing_stop with side=buy requires limit_price at least activation_price"
                )
        if max_slippage_ticks is not None:
            trailing.max_slippage_ticks = tick_count(max_slippage_ticks, "max_slippage_ticks")
        if max_slippage_bps is not None:
            # Every trailing stop takes at most 9999 bps.
            trailing.max_slippage_bps = validate_bps(
                max_slippage_bps, "max_slippage_bps", max_value=MAX_SELL_SLIPPAGE_BPS
            )
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
            if max_slippage_ticks is not None and max_slippage_bps is not None:
                raise PolyesterValidationError(
                    "twap market_ioc allows at most one of max_slippage_ticks or max_slippage_bps"
                )
            if max_slippage_ticks is not None:
                twap.market_ioc.max_slippage_ticks = tick_count(
                    max_slippage_ticks, "max_slippage_ticks"
                )
            elif max_slippage_bps is not None:
                twap.market_ioc.max_slippage_bps = validate_bps(
                    max_slippage_bps, "max_slippage_bps"
                )
            else:
                twap.market_ioc.SetInParent()
    else:  # ladder
        if ladder_distribution is not None and ladder_distribution.lower() != "linear":
            raise PolyesterValidationError("ladder_distribution must be linear")
        ladder = intent.ladder
        ladder.side = side_proto
        ladder.SetInParent()
        price_min_ticks = None
        price_max_ticks = None
        if ladder_price_min is not None:
            price_min_ticks = resolve_price_ticks(
                ladder_price_min, "ladder_price_min", symbol=symbol
            )  # type: ignore[arg-type]
        if ladder_price_max is not None:
            price_max_ticks = resolve_price_ticks(
                ladder_price_max, "ladder_price_max", symbol=symbol
            )  # type: ignore[arg-type]
        if (
            price_min_ticks is not None
            and price_max_ticks is not None
            and price_min_ticks >= price_max_ticks
        ):
            raise PolyesterValidationError(
                "ladder_price_min must be strictly less than ladder_price_max"
            )
        if price_min_ticks is not None:
            ladder.price_min_ticks = price_min_ticks
        if price_max_ticks is not None:
            ladder.price_max_ticks = price_max_ticks
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
    symbol_id: int = 0,
    sub_account_id: str | int | None = None,
    trigger_price: Any | None = None,
    trailing_distance_ticks: int | None = None,
    trailing_distance_bps: int | None = None,
    activation_price: Any | None = None,
    max_slippage_ticks: int | None = None,
    max_slippage_bps: int | None = None,
) -> triggers_pb2.ModifyTriggerRequest:
    """Encode a trigger patch.

    ``symbol_id`` ``0`` targets the trigger's own market; when set, it must be
    that market (an API key limited to specific markets must set it). A child's
    limit price is fixed at creation: cancel the trigger and create a new one
    to change it. The patch does not say what it modifies, so
    ``max_slippage_bps`` takes the cap shared by trailing stops and sells,
    1 to 9999; ``0`` clears it.
    """
    if not any(
        (
            trigger_price is not None,
            trailing_distance_ticks is not None,
            trailing_distance_bps is not None,
            activation_price is not None,
            max_slippage_ticks is not None,
            max_slippage_bps is not None,
        )
    ):
        raise PolyesterValidationError(
            "modify requires at least one of trigger_price, "
            "trailing_distance_ticks, trailing_distance_bps, activation_price, "
            "max_slippage_ticks, or max_slippage_bps"
        )
    if symbol_id < 0:
        raise PolyesterValidationError("modify trigger symbol_id must not be negative")
    if trailing_distance_ticks is not None and trailing_distance_bps is not None:
        raise PolyesterValidationError(
            "set at most one of trailing_distance_ticks or trailing_distance_bps"
        )
    if max_slippage_ticks is not None and max_slippage_bps is not None:
        raise PolyesterValidationError(
            "set at most one of max_slippage_ticks or max_slippage_bps"
        )
    proto = triggers_pb2.ModifyTriggerRequest(
        trigger_id=id_to_int(trigger_id, "trigger_id"),
        symbol_id=int(symbol_id),
    )
    if sub_account_id is not None:
        proto.subaccount_id = id_to_int(sub_account_id, "sub_account_id")
    if trigger_price is not None:
        proto.trigger_price_ticks = resolve_price_ticks(trigger_price, "trigger_price")  # type: ignore[arg-type]
    if trailing_distance_ticks is not None:
        proto.trailing_distance_ticks = tick_count(
            trailing_distance_ticks, "trailing_distance_ticks"
        )
    if trailing_distance_bps is not None:
        proto.trailing_distance_bps = validate_bps(
            trailing_distance_bps,
            "trailing_distance_bps",
            allow_clear=True,
        )
    if activation_price is not None:
        proto.activation_price_ticks = resolve_price_ticks(activation_price, "activation_price")  # type: ignore[arg-type]
    if max_slippage_ticks is not None:
        # Zero clears the cap.
        proto.max_slippage_ticks = tick_count(
            max_slippage_ticks, "max_slippage_ticks", allow_zero=True
        )
    if max_slippage_bps is not None:
        proto.max_slippage_bps = validate_bps(
            max_slippage_bps,
            "max_slippage_bps",
            allow_clear=True,
            max_value=MAX_SELL_SLIPPAGE_BPS,
        )
    return proto
