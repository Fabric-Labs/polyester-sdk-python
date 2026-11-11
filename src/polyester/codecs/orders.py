from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import msgspec
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.bps import (
    MAX_SELL_SLIPPAGE_BPS,
    max_slippage_bps_for_side,
    validate_bps,
)
from polyester.codecs.correlation_id import (
    optional_client_id,
    optional_request_id,
    required_client_id,
)
from polyester.codecs.scalars import (
    FractionalDigitsError,
    id_to_int,
    market_id,
    market_ids,
    omit_none,
    parse_account_id,
    refuse_item_scope,
    tick_count,
)
from polyester.codecs.triggers import (
    self_trade_prevention_mode_to_proto,
    trigger_price_source_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import BatchReplaceItem, CreateOrderRequest
from polyester.models.order_key import ClientOrderId, OrderId, OrderKey
from polyester.models.trading import AttachedRisk, OrderFieldViolation, RiskLeg, TrailingStop
from polyester.types.money import (
    Quantity,
    resolve_price_ticks,
    resolve_qty_scaled,
    resolve_quote_qty_scaled,
)

ORDER_SIDE_TO_PROTO = {"buy": "BUY", "sell": "SELL"}
ORDER_TYPE_TO_PROTO = {"limit": "LIMIT", "market": "MARKET"}
TIF_TO_PROTO = {"gtc": "GTC", "ioc": "IOC", "fok": "FOK", "gtd": "GTD"}
FEE_ASSET_TO_PROTO = {"quote": "QUOTE", "base": "BASE"}
_GTD_MIN_OFFSET = timedelta(seconds=1)
_GTD_MAX_OFFSET = timedelta(days=30)
_TIF_VALUES = "', '".join(TIF_TO_PROTO)
MODIFY_BEHAVIOR_TO_PROTO = {
    "amend_or_replace": "AMEND_OR_REPLACE",
    "amend_only": "AMEND_ONLY",
    "replace_only": "REPLACE_ONLY",
}


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

QTY_STEP_SIZE = "ERROR_CODE_QTY_STEP_SIZE"
PRICE_TICK_SIZE = "ERROR_CODE_PRICE_TICK_SIZE"
_GRID_RULES = {
    QTY_STEP_SIZE: ("step_size", "quantity does not align with the pair step size"),
    PRICE_TICK_SIZE: ("tick_size", "price does not align with the pair tick size"),
}


@contextmanager
def _on_grid(code: str, field_path: str) -> Iterator[None]:
    """Report a decimal finer than its scale as the server does.

    A nonzero digit beyond the scale is off the pair's step (quantity) or tick
    (limit, trigger, activation and attached-exit prices), whatever the pair:
    the server answers ``QTY_STEP_SIZE`` or ``PRICE_TICK_SIZE`` with the
    violation at ``field_path``. Zeros beyond the scale parse.
    """
    try:
        yield
    except FractionalDigitsError as exc:
        rule_id, message = _GRID_RULES[code]
        raise PolyesterValidationError(
            str(exc),
            code=code,
            violations=[
                OrderFieldViolation(field_path=field_path, rule_id=rule_id, message=message)
            ],
        ) from exc


def _limit_price_path(tif: str | None) -> str:
    execution = {"gtd": "limit_gtd", "ioc": "limit_ioc", "fok": "limit_fok"}.get(
        tif or "gtc", "limit_gtc"
    )
    return f"order.{execution}.price_ticks"


def parse_gtd_expire_at(
    value: str,
    *,
    now: datetime | None = None,
) -> Timestamp:
    """Parse a UTC RFC3339 ``expires_at`` and enforce the 1s–30d GTD window."""
    text = value.strip()
    if not text:
        raise PolyesterValidationError("tif='gtd' requires expires_at")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise PolyesterValidationError("expires_at must be an RFC3339 UTC timestamp") from exc
    if parsed.tzinfo is None:
        raise PolyesterValidationError("expires_at must be timezone-aware UTC")
    parsed = parsed.astimezone(UTC)
    current = (now or datetime.now(UTC)).astimezone(UTC)
    delta = parsed - current
    if delta < _GTD_MIN_OFFSET or delta > _GTD_MAX_OFFSET:
        raise PolyesterValidationError(
            "expires_at must be between 1 second and 30 days after validation"
        )
    ts = Timestamp()
    ts.FromDatetime(parsed)
    return ts


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
    if isinstance(key, OrderId):
        if key.value is None or (isinstance(key.value, str) and key.value.strip() == ""):
            raise PolyesterValidationError(f"{op} requires a non-empty OrderId")
        return key
    if isinstance(key, ClientOrderId):
        if not str(key.value).strip():
            raise PolyesterValidationError(f"{op} requires a non-empty ClientOrderId")
        return key
    raise PolyesterValidationError(f"{op} requires an OrderKey (OrderId or ClientOrderId)")


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


_CREATE_ORDER_FIELDS = frozenset(f.name for f in msgspec.structs.fields(CreateOrderRequest))


def normalize_create_order_request(
    request: CreateOrderRequest | Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> CreateOrderRequest:
    if request is not None and kwargs:
        raise PolyesterValidationError("Pass either request or keyword arguments, not both")
    data = request if request is not None else kwargs
    if isinstance(data, Mapping):
        unknown = sorted(str(key) for key in data if key not in _CREATE_ORDER_FIELDS)
        if unknown:
            raise PolyesterValidationError(
                "unsupported create order argument(s): " + ", ".join(unknown)
            )
    try:
        normalized = msgspec.convert(data, type=CreateOrderRequest)
    except (msgspec.ValidationError, TypeError) as exc:
        raise PolyesterValidationError("Invalid orders.create request") from exc
    # Reject floats even when qty is typed as Any for dual-path inputs.
    for field_name in ("qty", "max_quote_debit", "price", "market_client_ref_price"):
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
        raise PolyesterValidationError(f"tif must be one of '{_TIF_VALUES}'")

    payload = {
        "symbol": request.symbol,
        "symbol_id": request.symbol_id,
        "side": ORDER_SIDE_TO_PROTO[request.side],
        "order_type": ORDER_TYPE_TO_PROTO[request.order_type],
        "timeInForce": TIF_TO_PROTO.get(request.tif) if request.tif else None,
        "expireAt": request.expires_at if (request.tif or "gtc") == "gtd" else None,
        "qty_scaled": resolve_qty_scaled(
            cast(Any, request.qty),
            _codec_quantity_scale(request.qty, quantity_scale),
            symbol=request.symbol,
            symbol_id=request.symbol_id,
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
    quote_quantity_scale: int | None = None,
) -> orders_pb2.OrderIntent:
    """Build an :class:`OrderIntent` from the flat public request shape.

    The flat ``order_type``/``tif``/``post_only`` inputs are mapped onto the
    explicit execution oneof (``market_ioc``/``limit_gtc``/``limit_ioc``/
    ``limit_fok``/``limit_gtd``) introduced in POLY-3701.
    """
    if request.symbol is None and request.symbol_id is None:
        raise PolyesterValidationError("orders.create requires symbol or symbol_id")
    if request.side not in ORDER_SIDE_TO_PROTO:
        raise PolyesterValidationError("side must be 'buy' or 'sell'")
    if request.order_type not in ORDER_TYPE_TO_PROTO:
        raise PolyesterValidationError("order_type must be 'limit' or 'market'")
    if request.tif is not None and request.tif not in TIF_TO_PROTO:
        raise PolyesterValidationError(f"tif must be one of '{_TIF_VALUES}'")

    if (request.qty is None) == (request.max_quote_debit is None):
        raise PolyesterValidationError(
            "orders.create requires exactly one of qty or max_quote_debit"
        )
    if request.max_quote_debit is not None and (
        request.side != "buy" or (request.order_type == "limit" and (request.tif or "gtc") != "ioc")
    ):
        raise PolyesterValidationError(
            "max_quote_debit is only valid for buy market or limit IOC orders"
        )
    if request.symbol_id is None or int(request.symbol_id) == 0:
        raise PolyesterValidationError(
            "orders.create requires a resolved symbol_id; pass symbol_id or wait for catalogs"
        )
    intent = orders_pb2.OrderIntent(
        symbol_id=int(request.symbol_id),
        side=orders_pb2.BUY if request.side == "buy" else orders_pb2.SELL,
    )
    if request.qty is not None:
        with _on_grid(QTY_STEP_SIZE, "order.base_qty_scaled"):
            intent.base_qty_scaled = resolve_qty_scaled(
                request.qty,
                _codec_quantity_scale(request.qty, quantity_scale),
                symbol=request.symbol,
                symbol_id=request.symbol_id,
            )
    else:
        if request.side != "buy":
            raise PolyesterValidationError("max_quote_debit is only valid for buy orders")
        if quote_quantity_scale is None:
            raise PolyesterValidationError(
                "quote quantity scale is required for max_quote_debit; "
                "await client.wait_for_catalogs() or pass quote_quantity_scale"
            )
        intent.max_quote_debit_scaled = resolve_quote_qty_scaled(
            cast(Any, request.max_quote_debit),
            quote_quantity_scale,
            "max_quote_debit",
            symbol=request.symbol,
            symbol_id=request.symbol_id,
        )
    client_order_id = optional_client_id(request.client_order_id)
    if client_order_id:
        intent.client_order_id = client_order_id
    if request.fee_asset is not None:
        fee_asset = request.fee_asset.lower()
        if fee_asset not in FEE_ASSET_TO_PROTO:
            raise PolyesterValidationError("fee_asset must be quote or base")
        if request.side == "sell" and fee_asset != "quote":
            raise PolyesterValidationError("sell orders must use fee_asset=quote")
        intent.fee_asset = getattr(orders_pb2, FEE_ASSET_TO_PROTO[fee_asset])
    if request.self_trade_prevention_mode is not None:
        # Attached take-profit, stop-loss and trailing-stop exits use this mode.
        intent.self_trade_prevention_mode = self_trade_prevention_mode_to_proto(
            request.self_trade_prevention_mode
        )

    with _on_grid(PRICE_TICK_SIZE, _limit_price_path(request.tif)):
        price_ticks = (
            resolve_price_ticks(request.price, "price", symbol=request.symbol)
            if request.price is not None
            else None
        )
    tif = request.tif or "gtc"
    if request.expires_at and tif != "gtd":
        raise PolyesterValidationError("expires_at is only valid for limit GTD orders")
    if request.order_type == "market":
        # The contract's only market execution is market_ioc: market orders
        # always execute immediate-or-cancel. Any other requested tif is
        # refused, never sent as IOC.
        if request.tif is not None and request.tif != "ioc":
            raise PolyesterValidationError(f"tif='{request.tif}' is only valid for limit orders")
        if request.post_only:
            raise PolyesterValidationError("post_only is only valid for limit GTC or GTD orders")
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
        _set_market_max_slippage(
            market,
            ticks=request.max_slippage_ticks,
            bps=request.max_slippage_bps,
            side=request.side,
        )
    else:
        if request.max_slippage_ticks is not None or request.max_slippage_bps is not None:
            raise PolyesterValidationError(
                "max_slippage_ticks and max_slippage_bps are only valid for market orders"
            )
        if request.market_client_ref_price is not None:
            raise PolyesterValidationError(
                "market_client_ref_price is only valid for market orders"
            )
        if tif == "gtc":
            intent.limit_gtc.SetInParent()
            if price_ticks is not None:
                intent.limit_gtc.price_ticks = price_ticks
            if request.post_only:
                intent.limit_gtc.post_only = True
        elif tif == "gtd":
            if not request.expires_at:
                raise PolyesterValidationError("tif='gtd' requires expires_at")
            intent.limit_gtd.SetInParent()
            if price_ticks is not None:
                intent.limit_gtd.price_ticks = price_ticks
            if request.post_only:
                intent.limit_gtd.post_only = True
            intent.limit_gtd.expire_at.CopyFrom(parse_gtd_expire_at(request.expires_at))
        else:
            if request.post_only:
                raise PolyesterValidationError(
                    "post_only is only valid for limit GTC or GTD orders"
                )
            if tif == "ioc":
                intent.limit_ioc.SetInParent()
                if price_ticks is not None:
                    intent.limit_ioc.price_ticks = price_ticks
            else:  # fok
                intent.limit_fok.SetInParent()
                if price_ticks is not None:
                    intent.limit_fok.price_ticks = price_ticks

    risk = risk_policy_from_dict(request.attached_risk, symbol=request.symbol, side=request.side)
    if risk is not None:
        intent.attached_risk.CopyFrom(risk)
    return intent


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
    if request.sub_account_id is not None and request.sub_account_id != "":
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
    if request.sub_account_id is not None and request.sub_account_id != "":
        proto.subaccount_id = parse_account_id(request.sub_account_id, "sub_account_id")
    return proto


_RISK_POLICY_KEYS = frozenset(
    {"take_profit", "takeProfit", "stop_loss", "stopLoss", "trailing_stop", "trailingStop", "oco"}
)
_RISK_LEG_KEYS = frozenset(
    {
        "trigger_price",
        "triggerPrice",
        "order_type",
        "orderType",
        "limit_price",
        "limitPrice",
        "trigger_price_source",
        "triggerPriceSource",
        "trigger_price_ticks",
        "triggerPriceTicks",
        "child",
    }
)
_RISK_CHILD_KEYS = frozenset({"market_ioc", "marketIoc", "limit_gtc", "limitGtc"})
_RISK_LIMIT_GTC_KEYS = frozenset({"price_ticks", "priceTicks", "price"})
_TRAILING_STOP_KEYS = frozenset(
    {
        "trailing_distance_ticks",
        "trailingDistanceTicks",
        "trailing_distance_bps",
        "trailingDistanceBps",
        "distance_ticks",
        "distance_bps",
        "max_slippage_ticks",
        "maxSlippageTicks",
        "max_slippage_bps",
        "maxSlippageBps",
        "activation_price",
        "activationPrice",
        "activation_price_ticks",
        "activationPriceTicks",
        "limit_price",
        "limitPrice",
        "limit_price_ticks",
        "limitPriceTicks",
        "order_type",
        "orderType",
        "trigger_price_source",
        "triggerPriceSource",
    }
)


def _mapping_get(data: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in data and data[name] is not None:
            return data[name]
    return None


def _mapping_has(data: dict[str, Any], *names: str) -> bool:
    return any(name in data for name in names)


def _reject_unknown_keys(data: dict[str, Any], allowed: frozenset[str], *, field_name: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise PolyesterValidationError(
            f"{field_name} has unsupported fields: {', '.join(sorted(unknown))}"
        )


def _attached_trigger_price_source(
    data: dict[str, Any], *, field_name: str
) -> orders_pb2.TriggerPriceSource:
    return trigger_price_source_to_proto(
        _mapping_get(data, "trigger_price_source", "triggerPriceSource"),
        f"{field_name}.trigger_price_source",
    )


def _set_market_max_slippage(
    market: orders_pb2.MarketIoc,
    *,
    ticks: int | None,
    bps: int | None,
    side: str,
) -> None:
    if ticks is not None and bps is not None:
        raise PolyesterValidationError(
            "market_ioc allows at most one of max_slippage_ticks or max_slippage_bps"
        )
    if ticks is not None:
        market.max_slippage_ticks = tick_count(ticks, "max_slippage_ticks")
    elif bps is not None:
        # The backend rejects 10000 bps on a market order that sells.
        market.max_slippage_bps = validate_bps(
            bps, "max_slippage_bps", max_value=max_slippage_bps_for_side(side)
        )


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


def _resolve_optional_price_ticks(
    value: object,
    field_name: str,
    *,
    symbol: str | None,
    field_path: str,
) -> int:
    """Resolve an attached-exit price; ``field_path`` is its wire path for a
    ``PRICE_TICK_SIZE`` refusal."""
    with _on_grid(PRICE_TICK_SIZE, field_path):
        return resolve_price_ticks(value, field_name, symbol=symbol)  # type: ignore[arg-type]


def _risk_execution_from_friendly(
    *,
    order_type: object | None,
    limit_price: object | None,
    field_name: str,
    symbol: str | None,
    field_path: str,
) -> orders_pb2.RiskExecution:
    child = orders_pb2.RiskExecution()
    label = str(order_type).strip().lower() if order_type is not None else "market"
    if label in {"market", "market_ioc"}:
        if limit_price is not None:
            raise PolyesterValidationError(f"{field_name} MARKET child must not set limit_price")
        child.market_ioc.SetInParent()
        return child
    if label in {"limit", "limit_gtc"}:
        if limit_price is None:
            raise PolyesterValidationError(f"{field_name} LIMIT child requires limit_price")
        child.limit_gtc.price_ticks = _resolve_optional_price_ticks(
            limit_price,
            f"{field_name}.limit_price",
            symbol=symbol,
            field_path=f"{field_path}.child.limit_gtc.price_ticks",
        )
        return child
    raise PolyesterValidationError(
        f"{field_name} order_type must be 'market' or 'limit' (got {order_type!r})"
    )


def _risk_execution_from_child(
    child: object,
    *,
    field_name: str,
    symbol: str | None,
    field_path: str,
) -> orders_pb2.RiskExecution:
    if not isinstance(child, dict):
        raise PolyesterValidationError(f"{field_name}.child must be an object")
    if _mapping_has(child, "execution"):
        raise PolyesterValidationError(
            f"{field_name}.child.execution is not a wire field; set child.market_ioc "
            "or child.limit_gtc (limit_ioc and limit_fok are not attached-risk children)"
        )
    _reject_unknown_keys(child, _RISK_CHILD_KEYS, field_name=f"{field_name}.child")
    has_market = _mapping_has(child, "market_ioc", "marketIoc")
    has_limit = _mapping_has(child, "limit_gtc", "limitGtc")
    if has_market and has_limit:
        raise PolyesterValidationError(
            f"{field_name}.child must set exactly one of market_ioc or limit_gtc"
        )
    execution = orders_pb2.RiskExecution()
    if has_limit:
        limit = _mapping_get(child, "limit_gtc", "limitGtc")
        if not isinstance(limit, dict):
            raise PolyesterValidationError(f"{field_name}.child.limit_gtc must be an object")
        _reject_unknown_keys(
            limit, _RISK_LIMIT_GTC_KEYS, field_name=f"{field_name}.child.limit_gtc"
        )
        price = _mapping_get(limit, "price")
        ticks = _mapping_get(limit, "price_ticks", "priceTicks")
        if price is not None and ticks is not None:
            raise PolyesterValidationError(
                f"{field_name}.child.limit_gtc accepts price or price_ticks, not both"
            )
        if price is not None:
            execution.limit_gtc.price_ticks = _resolve_optional_price_ticks(
                price,
                f"{field_name}.child.limit_gtc.price",
                symbol=symbol,
                field_path=f"{field_path}.child.limit_gtc.price_ticks",
            )
        elif ticks is not None:
            execution.limit_gtc.price_ticks = tick_count(
                ticks, f"{field_name}.child.limit_gtc.price_ticks"
            )
        else:
            raise PolyesterValidationError(f"{field_name} LIMIT child requires limit_price")
        return execution
    if has_market:
        market = _mapping_get(child, "market_ioc", "marketIoc")
        if market not in (None, {}):
            if not isinstance(market, dict):
                raise PolyesterValidationError(f"{field_name}.child.market_ioc must be an object")
            if market:
                raise PolyesterValidationError(
                    f"{field_name}.child.market_ioc does not accept extra fields"
                )
        execution.market_ioc.SetInParent()
        return execution
    execution.market_ioc.SetInParent()
    return execution


def _risk_leg_from_dict(
    data: object,
    *,
    field_name: str,
    symbol: str | None,
    risk_field: str = "order.attached_risk",
) -> orders_pb2.TakeProfitPolicy:
    if not isinstance(data, dict):
        raise PolyesterValidationError(f"{field_name} must be an object")
    _reject_unknown_keys(data, _RISK_LEG_KEYS, field_name=field_name)
    price_source = _attached_trigger_price_source(data, field_name=field_name)
    leg_path = f"{risk_field}.{field_name}"

    trigger_price = _mapping_get(data, "trigger_price", "triggerPrice")
    trigger_ticks = _mapping_get(data, "trigger_price_ticks", "triggerPriceTicks")
    if trigger_price is not None and trigger_ticks is not None:
        raise PolyesterValidationError(
            f"{field_name} accepts trigger_price or trigger_price_ticks, not both"
        )
    if trigger_price is not None:
        ticks = _resolve_optional_price_ticks(
            trigger_price,
            f"{field_name}.trigger_price",
            symbol=symbol,
            field_path=f"{leg_path}.trigger_price_ticks",
        )
    elif trigger_ticks is not None:
        ticks = tick_count(trigger_ticks, f"{field_name}.trigger_price_ticks")
    else:
        raise PolyesterValidationError(f"{field_name} requires trigger_price")

    order_type = _mapping_get(data, "order_type", "orderType")
    limit_price = _mapping_get(data, "limit_price", "limitPrice")
    child_data = data.get("child") if "child" in data else None
    if child_data is not None and (order_type is not None or limit_price is not None):
        raise PolyesterValidationError(
            f"{field_name} accepts friendly order_type/limit_price or child, not both"
        )
    if child_data is not None:
        child = _risk_execution_from_child(
            child_data, field_name=field_name, symbol=symbol, field_path=leg_path
        )
    else:
        child = _risk_execution_from_friendly(
            order_type=order_type,
            limit_price=limit_price,
            field_name=field_name,
            symbol=symbol,
            field_path=leg_path,
        )

    policy = orders_pb2.TakeProfitPolicy(
        trigger_price_ticks=ticks, trigger_price_source=price_source
    )
    policy.child.CopyFrom(child)
    return policy


def _trailing_stop_from_dict(
    data: object,
    *,
    symbol: str | None,
    risk_field: str = "order.attached_risk",
) -> orders_pb2.TrailingStopPolicy:
    if not isinstance(data, dict):
        raise PolyesterValidationError("attached_risk.trailing_stop must be an object")
    _reject_unknown_keys(data, _TRAILING_STOP_KEYS, field_name="attached_risk.trailing_stop")
    if _mapping_has(data, "order_type", "orderType"):
        raise PolyesterValidationError(
            "attached trailing_stop takes no order_type: its child is a limit IOC at "
            "limit_price when the order sells, and a market order when it buys"
        )

    dist_ticks = _mapping_get(
        data, "trailing_distance_ticks", "trailingDistanceTicks", "distance_ticks"
    )
    dist_bps = _mapping_get(data, "trailing_distance_bps", "trailingDistanceBps", "distance_bps")
    if dist_ticks is None and dist_bps is None:
        raise PolyesterValidationError(
            "trailing_stop requires trailing_distance_ticks or trailing_distance_bps"
        )
    if dist_ticks is not None and dist_bps is not None:
        raise PolyesterValidationError(
            "trailing_stop requires exactly one of trailing_distance_ticks or trailing_distance_bps"
        )

    proto = orders_pb2.TrailingStopPolicy(
        trigger_price_source=_attached_trigger_price_source(
            data, field_name="attached_risk.trailing_stop"
        )
    )
    if dist_ticks is not None:
        proto.trailing_distance_ticks = tick_count(dist_ticks, "trailing_distance_ticks")
    else:
        proto.trailing_distance_bps = validate_bps(dist_bps, "trailing_distance_bps")

    slip_ticks = _mapping_get(data, "max_slippage_ticks", "maxSlippageTicks")
    slip_bps = _mapping_get(data, "max_slippage_bps", "maxSlippageBps")
    if slip_ticks is not None and slip_bps is not None:
        raise PolyesterValidationError(
            "trailing_stop allows at most one of max_slippage_ticks or max_slippage_bps"
        )
    if slip_ticks is not None:
        proto.max_slippage_ticks = tick_count(slip_ticks, "max_slippage_ticks")
    if slip_bps is not None:
        # An attached trailing stop takes at most 9999 bps on either side.
        proto.max_slippage_bps = validate_bps(
            slip_bps, "max_slippage_bps", max_value=MAX_SELL_SLIPPAGE_BPS
        )

    activation = _mapping_get(data, "activation_price", "activationPrice")
    activation_ticks = _mapping_get(data, "activation_price_ticks", "activationPriceTicks")
    if activation is not None and activation_ticks is not None:
        raise PolyesterValidationError(
            "trailing_stop accepts activation_price or activation_price_ticks, not both"
        )
    if activation is not None:
        proto.activation_price_ticks = _resolve_optional_price_ticks(
            activation,
            "attached_risk.trailing_stop.activation_price",
            symbol=symbol,
            field_path=f"{risk_field}.trailing_stop.activation_price_ticks",
        )
    elif activation_ticks is not None:
        proto.activation_price_ticks = tick_count(activation_ticks, "activation_price_ticks")

    # The most a buy-back exit pays per unit; the parent order's side decides
    # whether it is required (see risk_policy_from_dict).
    limit = _mapping_get(data, "limit_price", "limitPrice")
    limit_ticks = _mapping_get(data, "limit_price_ticks", "limitPriceTicks")
    if limit is not None and limit_ticks is not None:
        raise PolyesterValidationError(
            "trailing_stop accepts limit_price or limit_price_ticks, not both"
        )
    if limit is not None:
        proto.limit_price_ticks = _resolve_optional_price_ticks(
            limit,
            "attached_risk.trailing_stop.limit_price",
            symbol=symbol,
            field_path=f"{risk_field}.trailing_stop.limit_price_ticks",
        )
        if proto.limit_price_ticks <= 0:
            raise _trailing_limit_error(
                "attached_risk.trailing_stop.limit_price must be positive",
                code="ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT",
                rule_id="buy_required",
                risk_field=risk_field,
            )
    elif limit_ticks is not None:
        proto.limit_price_ticks = tick_count(limit_ticks, "limit_price_ticks")
    if proto.limit_price_ticks and proto.activation_price_ticks > proto.limit_price_ticks:
        raise _trailing_limit_error(
            "attached_risk.trailing_stop.limit_price must be at least activation_price",
            code="ERROR_CODE_BAD_PRICE",
            rule_id="buy_at_least_activation",
            risk_field=risk_field,
        )
    return proto


def _trailing_limit_error(
    message: str, *, code: str, rule_id: str, risk_field: str
) -> PolyesterValidationError:
    """A refused attached trailing-stop maximum, with the code, rule ID and
    field path the server answers for the same mistake."""
    return PolyesterValidationError(
        message,
        code=code,
        violations=[
            OrderFieldViolation(
                field_path=f"{risk_field}.trailing_stop.limit_price_ticks",
                rule_id=rule_id,
                message=message,
            )
        ],
    )


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
    if data is None:
        return None
    if isinstance(data, AttachedRisk):
        data = _attached_risk_to_dict(data)
        if not data:
            raise PolyesterValidationError("attached_risk requires take_profit and/or a stop leg")
    elif not isinstance(data, dict):
        raise PolyesterValidationError("attached_risk must be an object or AttachedRisk")
    if not data:
        return None
    _reject_unknown_keys(data, _RISK_POLICY_KEYS, field_name="attached_risk")

    take_profit = _mapping_get(data, "take_profit", "takeProfit")
    stop_loss = _mapping_get(data, "stop_loss", "stopLoss")
    trailing_stop = _mapping_get(data, "trailing_stop", "trailingStop")
    if stop_loss is not None and trailing_stop is not None:
        raise PolyesterValidationError(
            "attached_risk allows at most one of stop_loss or trailing_stop"
        )
    if take_profit is None and stop_loss is None and trailing_stop is None:
        raise PolyesterValidationError("attached_risk requires take_profit and/or a stop leg")

    risk = orders_pb2.RiskPolicy()
    if _mapping_has(data, "oco"):
        oco = data.get("oco")
        if not isinstance(oco, bool):
            raise PolyesterValidationError("attached_risk.oco must be a boolean")
        if oco and (take_profit is None or (stop_loss is None and trailing_stop is None)):
            message = (
                "oco requires take_profit and exactly one stop leg (stop_loss or trailing_stop)"
            )
            raise PolyesterValidationError(
                message,
                violations=[
                    OrderFieldViolation(
                        field_path=risk_field,
                        rule_id="risk_policy.oco_requires_tp_and_one_stop",
                        message=message,
                    )
                ],
            )
        risk.oco = oco
    if take_profit is not None:
        tp = _risk_leg_from_dict(
            take_profit, field_name="take_profit", symbol=symbol, risk_field=risk_field
        )
        risk.take_profit.CopyFrom(tp)
    if stop_loss is not None:
        sl = _risk_leg_from_dict(
            stop_loss, field_name="stop_loss", symbol=symbol, risk_field=risk_field
        )
        risk.stop_loss.CopyFrom(
            orders_pb2.StopLossPolicy(
                trigger_price_ticks=sl.trigger_price_ticks,
                child=sl.child,
                trigger_price_source=sl.trigger_price_source,
            )
        )
    if trailing_stop is not None:
        trailing = _trailing_stop_from_dict(trailing_stop, symbol=symbol, risk_field=risk_field)
        if side == "sell" and not trailing.limit_price_ticks:
            raise _trailing_limit_error(
                "attached_risk.trailing_stop.limit_price is required when the order sells: "
                "the trailing stop buys back and pays at most this price",
                code="ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT",
                rule_id="buy_required",
                risk_field=risk_field,
            )
        if side == "buy" and trailing.limit_price_ticks:
            raise _trailing_limit_error(
                "attached_risk.trailing_stop.limit_price must be unset when the order buys",
                code="ERROR_CODE_BAD_PRICE",
                rule_id="sell_unset",
                risk_field=risk_field,
            )
        risk.trailing_stop.CopyFrom(trailing)
    return risk


# Fields a batch item dictionary may carry. Account scope and order_id /
# client_order_id keys are refused earlier with their own messages.
_BATCH_REPLACE_ITEM_KEYS = frozenset(
    {"key", "new_price", "new_qty", "new_client_order_id", "new_attached_risk"}
)
_BATCH_CANCEL_ITEM_KEYS = frozenset({"key", "symbol_id"})


def batch_replace_item_to_proto(
    item: BatchReplaceItem | dict[str, Any],
    *,
    quantity_scale: int,
    symbol: str | None = None,
    symbol_id: int | None = None,
) -> orders_pb2.BatchReplaceOrderItem:
    if isinstance(item, BatchReplaceItem):
        item = {
            "key": item.key,
            "new_price": item.new_price,
            "new_qty": item.new_qty,
            "new_client_order_id": item.new_client_order_id,
            "new_attached_risk": item.new_attached_risk,
        }
    refuse_item_scope(item, "batch_replace")
    key = _item_order_key(item, label="each batch replace item")
    _reject_unknown_keys(item, _BATCH_REPLACE_ITEM_KEYS, field_name="batch_replace item")
    new_price = item.get("new_price")
    new_qty = item.get("new_qty")
    new_attached_risk = item.get("new_attached_risk")
    if new_price is None and new_qty is None and new_attached_risk is None:
        raise PolyesterValidationError(
            "each batch item requires new_price, new_qty, and/or new_attached_risk"
        )
    proto = orders_pb2.BatchReplaceOrderItem()
    set_order_key(proto, key, op="each batch replace item")
    if new_price is not None:
        with _on_grid(PRICE_TICK_SIZE, "new_price_ticks"):
            proto.new_price_ticks = resolve_price_ticks(new_price, "new_price", symbol=symbol)
    if new_qty is not None:
        with _on_grid(QTY_STEP_SIZE, "new_qty_scaled"):
            proto.new_qty_scaled = resolve_qty_scaled(
                new_qty, quantity_scale, "new_qty", symbol=symbol, symbol_id=symbol_id
            )
    if item.get("new_client_order_id"):
        proto.new_client_order_id = required_client_id(
            str(item["new_client_order_id"]), "new_client_order_id"
        )
    # The item carries no side: the server applies the side rule to a trailing
    # stop's maximum and answers ERROR_CODE_BAD_PRICE.
    risk = risk_policy_from_dict(new_attached_risk, symbol=symbol, risk_field="new_attached_risk")
    if risk is not None:
        proto.new_attached_risk.CopyFrom(risk)
    return proto


def batch_create_orders_to_proto(
    *,
    items: Sequence[CreateOrderRequest | Mapping[str, Any]],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
    allow_partial: bool = False,
    quantity_scale: int | None = None,
    item_scales: Sequence[tuple[int, int]] | None = None,
) -> orders_pb2.BatchCreateOrdersRequest:
    # ``allow_partial`` was removed from the wire in POLY-3701; it is accepted
    # for backwards compatibility but ignored.
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


def cancel_all_after_to_proto(
    *,
    sub_account_id: str | int | None = None,
    timeout_sec: int,
    symbol_id: int | None = None,
    side: str | None = None,
    request_id: str | None = None,
) -> orders_pb2.CancelAllAfterRequest:
    proto = orders_pb2.CancelAllAfterRequest(
        request_id=optional_request_id(request_id) or f"cancel-after-{uuid.uuid4().hex[:12]}",
        timeout_sec=timeout_sec,
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
    for item in items:
        new_qty = item.new_qty if isinstance(item, BatchReplaceItem) else item.get("new_qty")
        item_scale = _codec_quantity_scale(new_qty, quantity_scale) if new_qty is not None else 0
        proto.items.append(
            batch_replace_item_to_proto(
                item, quantity_scale=item_scale, symbol=symbol, symbol_id=symbol_id
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
) -> orders_pb2.ModifyOrderRequest:
    if not new_price and not new_qty and not new_attached_risk:
        raise PolyesterValidationError(
            "modify requires new_price, new_qty, and/or new_attached_risk"
        )

    if symbol_id <= 0:
        raise PolyesterValidationError("modify requires a resolved symbol_id")
    proto = orders_pb2.ModifyOrderRequest(
        request_id=optional_request_id(request_id) or f"mod-{uuid.uuid4().hex[:12]}",
        symbol_id=int(symbol_id),
    )
    set_order_key(proto, key, op="modify")
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    if new_price is not None:
        with _on_grid(PRICE_TICK_SIZE, "new_price_ticks"):
            proto.new_price_ticks = resolve_price_ticks(
                new_price,  # type: ignore[arg-type]
                "new_price",
                symbol=symbol,
            )
    if new_qty is not None:
        with _on_grid(QTY_STEP_SIZE, "new_qty_scaled"):
            proto.new_qty_scaled = resolve_qty_scaled(
                new_qty,  # type: ignore[arg-type]
                _codec_quantity_scale(new_qty, quantity_scale),
                "new_qty",
                symbol=symbol,
                symbol_id=symbol_id,
            )
    if behavior:
        behavior_key = behavior.lower()
        if behavior_key not in MODIFY_BEHAVIOR_TO_PROTO:
            raise PolyesterValidationError(
                "behavior must be amend_or_replace, amend_only, or replace_only"
            )
        proto.behavior = getattr(orders_pb2, MODIFY_BEHAVIOR_TO_PROTO[behavior_key])
    if new_client_order_id:
        proto.new_client_order_id = required_client_id(new_client_order_id, "new_client_order_id")
    # The modify request carries no side: the server applies the side rule to
    # the trailing stop's maximum and answers ERROR_CODE_BAD_PRICE.
    risk = risk_policy_from_dict(new_attached_risk, symbol=symbol, risk_field="new_attached_risk")
    if risk is not None:
        proto.new_attached_risk.CopyFrom(risk)
    return proto


def cancel_all_orders_to_proto(
    *,
    sub_account_id: str | int | None = None,
    symbol_id: int | None = None,
    symbol_ids: list[int] | None = None,
    side: str | None = None,
    dry_run: bool = False,
    request_id: str | None = None,
) -> orders_pb2.CancelAllOrdersRequest:
    proto = orders_pb2.CancelAllOrdersRequest(
        request_id=optional_request_id(request_id) or f"cancel-all-{uuid.uuid4().hex[:12]}",
        dry_run=dry_run,
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
    or for a pair they do not list. Reads never wait for the catalogs.
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
    for value in values:
        if isinstance(value, Quantity) and value.scale is not None and value.scale != scale:
            raise PolyesterValidationError(
                f"quantity scale mismatch: value scale is {value.scale}, destination is {scale}"
            )
    return scale


def resolve_quote_quantity_scale(
    catalogs: CatalogManager | None,
    symbol: str | None,
    value: object | None,
    *,
    symbol_id: int | None = None,
) -> int:
    """Resolve and validate the catalog scale for a quote-debit budget."""
    if value is None:
        return 0
    catalog_scale = quote_quantity_scale_for_symbol(catalogs, symbol, symbol_id=symbol_id)
    if isinstance(value, Quantity):
        if value.scale is None:
            raise PolyesterValidationError(
                "quote amount scale is required; use Quantity.from_quote_scaled/from_quote_decimal"
            )
        if value.scale != catalog_scale:
            raise PolyesterValidationError(
                f"quantity scale mismatch: value scale is {value.scale}, "
                f"destination is {catalog_scale}"
            )
    return catalog_scale


def parse_optional_subaccount_id(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return parse_account_id(value, "sub_account_id")
