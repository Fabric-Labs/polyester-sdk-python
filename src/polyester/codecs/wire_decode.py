from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, TypeVar

import msgspec
from google.protobuf.message import Message

from polyester.codecs.decode.balances import ledger_amount
from polyester.codecs.decode.invariants import (
    ts_ns_string_from_response,
)
from polyester.codecs.decode.lifecycle import (
    FLOW_ENUM_LABELS,
    flow_summary_from_proto,
)
from polyester.codecs.decode.market_data import _decode_price_field, _decode_volume_field
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2
from polyester.gen.ledger.v1 import catalog_pb2
from polyester.models.market import (
    Candle,
    CandlesResult,
    MarketOverviewEntry,
    MarketOverviewList,
    MarketOverviewSparkline,
    MarketTrade,
)
from polyester.models.trading import (
    ApiKeysList,
    ApiKeySummary,
    AssetBalance,
    BalanceHistory,
    BalanceHistorySeries,
    BalancesList,
    BatchCancelOrdersResult,
    BatchCreateOrdersResult,
    BatchReplaceOrdersResult,
    BatchReplaceStatusResult,
    BucketTransferResult,
    CancelAllAfterResult,
    CancelAllOrdersResult,
    DepositAddress,
    DepositAddressesList,
    EquityHistory,
    EquityHistorySeries,
    GetOrderResult,
    InternalTransferResult,
    LedgerTransfer,
    LifecycleFlowsList,
    LifecycleFlowSummary,
    ModifyOrderResult,
    Order,
    OrderMutationResult,
    OrdersList,
    ResolvedAccount,
    ResolvedAccountsList,
    TransferDestination,
    TransferDestinationsList,
    TransferSide,
    TransfersList,
    Trigger,
    TriggerEvent,
    TriggerEventsList,
    TriggerMutationResult,
    TriggersList,
    UserTrade,
    UserTradesList,
    WithdrawIntentResult,
)

if TYPE_CHECKING:
    from polyester.codecs.decode.orders import OrderScales

_M = TypeVar("_M", bound=Message)


def _field(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _contract_message(data: Any, message: _M, context: str) -> _M:
    """Parse protobuf JSON (camelCase or snake_case names; unknown fields are
    ignored) into ``message``, so the protobuf decoder reads it exactly as it
    reads the binary response. A dict that is not a valid ``context`` raises
    ``PolyesterResponseContractError``."""
    from google.protobuf.json_format import ParseDict, ParseError

    if not isinstance(data, dict):
        raise PolyesterResponseContractError(context, "response is not a JSON object")
    try:
        ParseDict(data, message, ignore_unknown_fields=True)
    except ParseError as exc:
        raise PolyesterResponseContractError(context, f"response is not valid: {exc}") from exc
    return message


def _optional_scaled_field(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if key in data and data[key] is not None and data[key] != "":
            return str(data[key])
    return None


_WIRE_ENUM_PREFIXES = (
    "SIDE_",
    "ORDER_TYPE_",
    "ORDER_STATUS_",
    "TIF_",
    "FLOW_STEP_",
    "FLOW_KIND_",
    "KIND_",
    "TIME_IN_FORCE_",
)


def _enum_name(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        name = value.strip()
        if not name:
            return ""
        for prefix in _WIRE_ENUM_PREFIXES:
            if name.startswith(prefix):
                return name[len(prefix) :].lower()
        # Already-normalized snake labels stay as-is; other SCREAMING names lower.
        if name == name.lower():
            return name
        return name.lower()
    return str(value)


def _id_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return format_id(int(value))
    except (TypeError, ValueError):
        return str(value)


def decode_order(
    data: dict[str, Any],
    *,
    quantity_scale: int | None = None,
    quote_quantity_scale: int | None = None,
) -> Order:
    """Decode an ``orders.v1.Order`` in its protobuf JSON form, exactly as
    ``order_from_proto`` decodes the binary message."""
    from polyester.codecs.decode.orders import order_from_proto
    from polyester.gen.orders.v1 import orders_read_pb2

    return order_from_proto(
        _contract_message(data, orders_read_pb2.Order(), "Order"),
        quantity_scale=quantity_scale,
        quote_quantity_scale=quote_quantity_scale,
    )


def decode_orders_list(data: dict[str, Any], *, scales: OrderScales | None = None) -> OrdersList:
    """Decode an open-orders or order-history page in its protobuf JSON form,
    exactly as ``orders_list_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import orders_list_from_proto
    from polyester.gen.orders.v1 import orders_read_pb2

    message = _contract_message(data, orders_read_pb2.GetOpenOrdersResponse(), "ListOrders")
    return orders_list_from_proto(message, scales=scales)


def decode_order_mutation(
    data: dict[str, Any], *, quantity_scale: int | None = None
) -> OrderMutationResult:
    """Decode a create or cancel answer in its protobuf JSON form, exactly as
    ``order_mutation_from_proto`` decodes the binary response. A cancel answer
    carries ``status``; a create answer does not."""
    from polyester.codecs.decode.orders import order_mutation_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message: orders_pb2.CreateOrderResponse | orders_pb2.CancelOrderResponse
    if isinstance(data, dict) and "status" in data:
        message = _contract_message(data, orders_pb2.CancelOrderResponse(), "CancelOrder")
    else:
        message = _contract_message(data, orders_pb2.CreateOrderResponse(), "CreateOrder")
    return order_mutation_from_proto(message, quantity_scale=quantity_scale)


def decode_get_order(data: dict[str, Any], *, scales: OrderScales | None = None) -> GetOrderResult:
    """Decode an order read in its protobuf JSON form, exactly as
    ``get_order_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import get_order_from_proto
    from polyester.gen.orders.v1 import orders_read_pb2

    message = _contract_message(data, orders_read_pb2.GetOrderResponse(), "GetOrder")
    return get_order_from_proto(message, scales=scales)


def decode_user_trade(data: dict[str, Any], *, quantity_scale: int | None = None) -> UserTrade:
    """Decode an ``orders.v1.UserTrade`` in its protobuf JSON form, exactly as
    ``user_trade_from_proto`` decodes the binary message."""
    from polyester.codecs.decode.orders import user_trade_from_proto
    from polyester.gen.orders.v1 import orders_read_pb2

    message = _contract_message(data, orders_read_pb2.UserTrade(), "UserTrade")
    return user_trade_from_proto(message, quantity_scale=quantity_scale)


def decode_user_trades_list(
    data: dict[str, Any], *, scales: OrderScales | None = None
) -> UserTradesList:
    """Decode a user trades page in its protobuf JSON form, exactly as
    ``user_trades_list_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import user_trades_list_from_proto
    from polyester.gen.orders.v1 import orders_read_pb2

    message = _contract_message(data, orders_read_pb2.GetUserTradesResponse(), "GetUserTrades")
    return user_trades_list_from_proto(message, scales=scales)


def decode_market_trade(data: dict[str, Any], *, quantity_scale: int) -> MarketTrade:
    from polyester.types.money import Price, Quantity

    symbol_id = int(_field(data, "symbolId", "symbol_id", default=0) or 0)
    qty_raw = _field(data, "qtyScaled", "qty_scaled", default=0) or 0
    price_raw = _field(data, "priceTicks", "price_ticks", default=0) or 0
    return MarketTrade(
        symbol_id=symbol_id,
        match_id=str(_field(data, "matchId", "match_id", default="") or ""),
        is_buy=bool(_field(data, "isBuy", "is_buy", default=False)),
        price=Price.from_ticks(int(price_raw)) if int(price_raw) else None,
        qty=Quantity.from_scaled(int(qty_raw), scale=quantity_scale, symbol_id=symbol_id),
        ts_ns=ts_ns_string_from_response(
            _field(data, "tsNs", "ts_ns", default=0) or 0,
            context="MarketTrade",
            empty_when_zero=True,
        ),
    )


def decode_candle(data: dict[str, Any], *, volume_scale: int) -> Candle:
    return Candle(
        ts_sec=int(_field(data, "tsSec", "ts_sec", default=0) or 0),
        open=_decode_price_field(_field(data, "open", default="") or ""),
        high=_decode_price_field(_field(data, "high", default="") or ""),
        low=_decode_price_field(_field(data, "low", default="") or ""),
        close=_decode_price_field(_field(data, "close", default="") or ""),
        volume=_decode_volume_field(
            _field(data, "volume", default="") or "",
            scale=volume_scale,
        ),
        quote_volume=str(_field(data, "quoteVolume", "quote_volume", default="") or ""),
        is_closed=bool(_field(data, "isClosed", "is_closed", default=False)),
    )


def decode_candles_list(data: dict[str, Any], *, volume_scale: int) -> CandlesResult:
    candles = [
        decode_candle(item, volume_scale=volume_scale)
        for item in _field(data, "candles", default=[]) or []
        if isinstance(item, dict)
    ]
    if not candles:
        candles = _decode_columnar_candles(data, volume_scale=volume_scale)
    return CandlesResult(
        next_page_token=str(_field(data, "nextPageToken", "next_page_token", default="") or ""),
        symbol_id=int(_field(data, "symbolId", "symbol_id", default=0) or 0),
        timeframe=str(_field(data, "timeframe", default="") or ""),
        candles=candles,
    )


def _decode_columnar_candles(data: dict[str, Any], *, volume_scale: int) -> list[Candle]:
    ts_list = _field(data, "tsSec", "ts_sec", default=[]) or []
    opens = _field(data, "open", default=[]) or []
    highs = _field(data, "high", default=[]) or []
    lows = _field(data, "low", default=[]) or []
    closes = _field(data, "close", default=[]) or []
    volumes = _field(data, "volume", default=[]) or []
    quote_volumes = _field(data, "quoteVolume", "quote_volume", default=[]) or []
    candles: list[Candle] = []
    for index, ts in enumerate(ts_list):
        candles.append(
            Candle(
                ts_sec=int(ts),
                open=_decode_price_field(opens[index]) if index < len(opens) else "",
                high=_decode_price_field(highs[index]) if index < len(highs) else "",
                low=_decode_price_field(lows[index]) if index < len(lows) else "",
                close=_decode_price_field(closes[index]) if index < len(closes) else "",
                volume=_decode_volume_field(
                    volumes[index] if index < len(volumes) else "",
                    scale=volume_scale,
                ),
                quote_volume=str(quote_volumes[index]) if index < len(quote_volumes) else "",
            )
        )
    return candles


def decode_market_overview_entry(data: dict[str, Any]) -> MarketOverviewEntry:
    from polyester.types.money import Price, Quantity

    ticks = _field(data, "lastPriceTicks", "last_price_ticks", default=0) or 0
    index_ticks = _field(data, "indexPriceTicks", "index_price_ticks", default=0) or 0
    symbol = str(_field(data, "symbol", default="") or "")
    symbol_id = int(_field(data, "symbolId", "symbol_id", default=0) or 0)

    def price(*keys: str) -> Price | None:
        value = int(_field(data, *keys, default=0) or 0)
        return Price.from_ticks(value, symbol=symbol or None) if value else None

    def book_side(side: str) -> tuple[Price | None, Quantity | None]:
        # An empty side sends neither its price nor its quantity.
        best = price(f"best{side.title()}Ticks", f"best_{side}_ticks")
        if best is None:
            return None, None
        scaled = _field(data, f"best{side.title()}QtyScaled", f"best_{side}_qty_scaled", default=0)
        return best, Quantity.from_scaled(
            int(scaled or 0), symbol=symbol or None, symbol_id=symbol_id
        )

    def ts_ns(*keys: str) -> str:
        return ts_ns_string_from_response(
            _field(data, *keys, default=0) or 0,
            context="MarketOverview",
            field_name=keys[-1],
            empty_when_zero=True,
        )

    best_bid, best_bid_qty = book_side("bid")
    best_ask, best_ask_qty = book_side("ask")
    return MarketOverviewEntry(
        symbol_id=symbol_id,
        symbol=symbol,
        last_price=Price.from_ticks(int(ticks), symbol=symbol or None) if int(ticks) else None,
        index_price=Price.from_ticks(int(index_ticks), symbol=symbol or None)
        if int(index_ticks)
        else None,
        change_24h_bp=str(
            _field(
                data, "change24hBps", "change_24h_bps", "change24hBp", "change_24h_bp", default=0
            )
            or 0
        ),
        volume_24h_base_scaled=_optional_scaled_field(
            data, "volume24hBaseScaled", "volume_24h_base_scaled"
        ),
        volume_24h_quote_scaled=_optional_scaled_field(
            data, "volume24hQuoteScaled", "volume_24h_quote_scaled"
        ),
        volume_24h_usd_scaled=_optional_scaled_field(
            data, "volume24hUsdScaled", "volume_24h_usd_scaled"
        ),
        sparklines=[
            _decode_market_overview_sparkline(item, symbol or None)
            for item in _field(data, "sparklines", default=[]) or []
            if isinstance(item, dict)
        ],
        high_24h=price("high24hTicks", "high_24h_ticks"),
        low_24h=price("low24hTicks", "low_24h_ticks"),
        best_bid=best_bid,
        best_bid_qty=best_bid_qty,
        best_ask=best_ask,
        best_ask_qty=best_ask_qty,
        last_trade_ts_ns=ts_ns("lastTradeTsNs", "last_trade_ts_ns"),
        listed_ts_ns=ts_ns("listedTsNs", "listed_ts_ns"),
    )


def _decode_market_overview_sparkline(
    data: dict[str, Any], symbol: str | None
) -> MarketOverviewSparkline:
    from polyester.gen.marketoverview.v1 import marketoverview_pb2
    from polyester.types.money import Price

    interval = _field(data, "interval", default=0) or 0
    if isinstance(interval, int) and interval in marketoverview_pb2.SparklineInterval.values():
        interval = marketoverview_pb2.SparklineInterval.Name(interval)
    ticks = _field(data, "closeTicks", "close_ticks", default=[]) or []
    return MarketOverviewSparkline(
        interval=str(interval),
        close_prices=[Price.from_ticks(int(tick), symbol=symbol) for tick in ticks],
    )


def decode_market_overview_list(data: dict[str, Any]) -> MarketOverviewList:
    markets = [
        decode_market_overview_entry(item)
        for item in _field(data, "markets", default=[]) or []
        if isinstance(item, dict)
    ]
    return MarketOverviewList(
        markets=markets,
        next_page_token=str(_field(data, "nextPageToken", "next_page_token", default="") or ""),
        total=len(markets),
    )


def _u128_str(data: dict[str, Any] | None) -> str:
    if not data:
        return "0"
    hi = int(_field(data, "hi", default=0) or 0)
    lo = int(_field(data, "lo", default=0) or 0)
    return str((hi << 64) + lo)


def decode_asset_balance(data: dict[str, Any]) -> AssetBalance:
    return AssetBalance(
        asset_id=int(_field(data, "assetId", "asset_id", default=0) or 0),
        trading=_u128_str(_field(data, "trading")),
        funding=_u128_str(_field(data, "funding")),
        reserved=_u128_str(_field(data, "reserved")),
        available=_u128_str(_field(data, "available")),
        trading_revision=int(_field(data, "tradingRevision", "trading_revision", default=0) or 0),
        funding_revision=int(_field(data, "fundingRevision", "funding_revision", default=0) or 0),
    )


def decode_balances_list(data: dict[str, Any]) -> BalancesList:
    balances = [
        decode_asset_balance(item)
        for item in _field(data, "balances", default=[]) or []
        if isinstance(item, dict)
    ]
    return BalancesList(balances=balances)


def _lifecycle_flow_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize list items (FlowSummaryView) and detail views (FlowDetailView.summary)."""
    summary = _field(data, "summary")
    if isinstance(summary, dict):
        return summary
    return data


_FLOW_SUMMARY = lifecycle_read_pb2.FlowSummaryView.DESCRIPTOR
# Names earlier answers used for a contract field; the contract name wins.
_LEGACY_FLOW_KEYS = {
    "intentId": "flow_id",
    "intent_id": "flow_id",
    "latestStep": "current_step",
    "latest_step": "current_step",
    "reasonCode": "lifecycle_reason",
    "reason_code": "lifecycle_reason",
}
# The LifecycleFlowSummary attribute of each FlowSummaryView enum field.
_FLOW_ENUM_ATTRS = {"current_step": "latest_step"}
_UNKNOWN_LABEL = re.compile(r"^unknown_[a-z_]+_([0-9]+)$")
_ENUM_VALUE_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")

# A path into the summary (field names, and list indexes) to the label of an
# enum value newer than this SDK, which the JSON names but cannot number.
_NewerLabels = dict[tuple[str | int, ...], str]


def _flow_enum_json(
    field: Any, value: Any, path: tuple[str | int, ...], newer: _NewerLabels
) -> Any:
    """A flow enum value as the contract parser takes it: its name or number
    as sent, or the number of the ``LifecycleFlowSummary`` label (such as
    ``"withdraw"`` or ``"unknown_reason_2001"``) or prefixed name it is. A name
    newer than this SDK parses as 0 and records its label, the name without
    the enum's prefix, lowercased; any other text is refused."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    enum_type = field.enum_type
    if text in enum_type.values_by_name:
        return text
    if text.isascii() and text.isdigit():
        return int(text)
    if not text:
        return 0
    unknown = _UNKNOWN_LABEL.match(text)
    if unknown:
        return int(unknown.group(1))
    prefix = enum_type.values_by_number[0].name.removesuffix("UNSPECIFIED")
    label_of = FLOW_ENUM_LABELS[enum_type.full_name]
    labels = {_enum_name(text), text.lower(), text.removeprefix(prefix).lower()}
    for candidate in enum_type.values:
        if label_of(candidate.number) in labels:
            return candidate.number
    if _ENUM_VALUE_NAME.match(text):
        newer[path] = text.removeprefix(prefix).lower()
        return 0
    raise PolyesterResponseContractError(
        "FlowSummaryView", f"{field.name} is not a {enum_type.name}: {value!r}"
    )


def _flow_json_enums(
    descriptor: Any, data: dict[str, Any], path: tuple[str | int, ...], newer: _NewerLabels
) -> dict[str, Any]:
    """``data`` (a message of ``descriptor`` in protobuf JSON) by field name,
    with every labelled flow enum read back, nested messages included. Keys
    that are not fields of the message are dropped, as the parser ignores
    them."""
    fields = {key: f for f in descriptor.fields for key in (f.name, f.json_name)}
    out: dict[str, Any] = {}
    for key, value in data.items():
        field = fields.get(key)
        if field is None:
            continue
        here = (*path, field.name)
        if field.enum_type is not None and field.enum_type.full_name in FLOW_ENUM_LABELS:
            value = _flow_enum_json(field, value, here, newer)
        elif field.message_type is not None and isinstance(value, dict):
            value = _flow_json_enums(field.message_type, value, here, newer)
        elif field.message_type is not None and isinstance(value, list):
            value = [
                _flow_json_enums(field.message_type, item, (*here, index), newer)
                if isinstance(item, dict)
                else item
                for index, item in enumerate(value)
            ]
        out[field.name] = value
    return out


def _with_newer_labels(flow: LifecycleFlowSummary, newer: _NewerLabels) -> LifecycleFlowSummary:
    """``flow`` with the labels of enum values newer than this SDK."""
    changes: dict[str, Any] = {}
    timeline = list(flow.progress_timeline)
    for path, label in newer.items():
        if len(path) == 1:
            name = str(path[0])
            changes[_FLOW_ENUM_ATTRS.get(name, name)] = label
        elif path[0] == "request_fee" and flow.request_fee is not None:
            fee = changes.get("request_fee", flow.request_fee)
            changes["request_fee"] = msgspec.structs.replace(fee, **{str(path[1]): label})
        elif path[0] == "progress_timeline" and isinstance(path[1], int):
            index = path[1]
            timeline[index] = msgspec.structs.replace(timeline[index], **{str(path[2]): label})
            changes["progress_timeline"] = timeline
    return msgspec.structs.replace(flow, **changes) if changes else flow


def decode_lifecycle_flow(data: dict[str, Any]) -> LifecycleFlowSummary:
    """Decode a flow summary (a list item, or a detail view's ``summary``) in
    its protobuf JSON form exactly as ``flow_summary_from_proto`` decodes the
    binary one. Earlier names (``intentId``, ``latestStep``, ``reasonCode``)
    and the labels this SDK returns (``"withdraw"``, ``"validation"``) are
    read too. An enum name newer than this SDK reads as the name without its
    prefix, lowercased. A value that breaks the contract raises
    ``PolyesterResponseContractError``."""
    payload = _lifecycle_flow_payload(data)
    contract = dict(payload)
    for key, name in _LEGACY_FLOW_KEYS.items():
        field = _FLOW_SUMMARY.fields_by_name[name]
        if key in payload and name not in payload and field.json_name not in payload:
            contract[name] = contract.pop(key)
    # Server provenance, not modelled: never refused.
    for key in ("latest_lifecycle_source", "latestLifecycleSource"):
        contract.pop(key, None)
    newer: _NewerLabels = {}
    view = _contract_message(
        _flow_json_enums(_FLOW_SUMMARY, contract, (), newer),
        lifecycle_read_pb2.FlowSummaryView(),
        "FlowSummaryView",
    )
    return _with_newer_labels(flow_summary_from_proto(view), newer)


def decode_lifecycle_flows_list(data: dict[str, Any]) -> LifecycleFlowsList:
    flows = [
        decode_lifecycle_flow(item)
        for item in _field(data, "flows", default=[]) or []
        if isinstance(item, dict)
    ]
    return LifecycleFlowsList(
        flows=flows,
        next_page_token=str(_field(data, "nextPageToken", "next_page_token", default="") or ""),
    )


def decode_modify_order_result(data: dict[str, Any]) -> ModifyOrderResult:
    """Decode a modify answer in its protobuf JSON form, exactly as
    ``modify_order_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import modify_order_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message = _contract_message(data, orders_pb2.ModifyOrderResponse(), "ModifyOrder")
    return modify_order_from_proto(message)


def decode_cancel_all_orders_result(data: dict[str, Any]) -> CancelAllOrdersResult:
    """Decode a cancel-all answer in its protobuf JSON form, exactly as
    ``cancel_all_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import cancel_all_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message = _contract_message(data, orders_pb2.CancelAllOrdersResponse(), "CancelAllOrders")
    return cancel_all_from_proto(message)


def decode_cancel_all_after_result(data: dict[str, Any]) -> CancelAllAfterResult:
    """Decode a cancel-all-after answer in its protobuf JSON form, exactly as
    ``cancel_all_after_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import cancel_all_after_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message = _contract_message(data, orders_pb2.CancelAllAfterResponse(), "CancelAllAfter")
    return cancel_all_after_from_proto(message)


def decode_batch_create_result(
    data: dict[str, Any], *, quantity_scales: Sequence[int | None] | None = None
) -> BatchCreateOrdersResult:
    """Decode a batch create answer in its protobuf JSON form, exactly as
    ``batch_create_from_proto`` decodes the binary response. ``quantity_scales``
    are the requested items' base quantity scales, in request order."""
    from polyester.codecs.decode.orders import batch_create_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message = _contract_message(data, orders_pb2.BatchCreateOrdersResponse(), "BatchCreateOrders")
    return batch_create_from_proto(message, quantity_scales=quantity_scales)


def decode_batch_cancel_result(data: dict[str, Any]) -> BatchCancelOrdersResult:
    """Decode a batch cancel answer in its protobuf JSON form, exactly as
    ``batch_cancel_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import batch_cancel_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message = _contract_message(data, orders_pb2.BatchCancelOrdersResponse(), "BatchCancelOrders")
    return batch_cancel_from_proto(message)


def decode_trigger(data: dict[str, Any]) -> Trigger:
    from polyester.types.money import Price, Quantity

    stop = _field(data, "stop")
    trigger_price_ticks = 0
    if isinstance(stop, dict):
        trigger_price_ticks = int(
            _field(stop, "triggerPriceTicks", "trigger_price_ticks", default=0) or 0
        )
    if not trigger_price_ticks:
        trigger_price_ticks = int(
            _field(data, "triggerPriceTicks", "trigger_price_ticks", default=0) or 0
        )
    symbol = str(_field(data, "symbol", default="") or "")
    symbol_id = int(_field(data, "symbolId", "symbol_id", default=0) or 0)
    qty_raw = int(_field(data, "qtyScaled", "qty_scaled", default=0) or 0)
    return Trigger(
        trigger_id=_id_str(_field(data, "triggerId", "trigger_id")),
        symbol_id=symbol_id,
        symbol=symbol,
        trigger_type=_enum_name(_field(data, "triggerType", "trigger_type")).lower(),
        status=_enum_name(_field(data, "status")).lower(),
        side=_enum_name(_field(data, "side")).lower(),
        qty=Quantity.from_scaled(qty_raw, symbol=symbol or None, symbol_id=symbol_id),
        trigger_price=Price.from_ticks(trigger_price_ticks, symbol=symbol or None)
        if trigger_price_ticks
        else None,
        client_trigger_id=str(
            _field(data, "clientTriggerId", "client_trigger_id", default="") or ""
        ),
        order_list_id=_id_str(_field(data, "orderListId", "order_list_id")),
        client_list_id=str(_field(data, "clientListId", "client_list_id", default="") or ""),
        cancel_reason=str(_field(data, "cancelReason", "cancel_reason", default="") or ""),
        failure_reason=str(_field(data, "failureReason", "failure_reason", default="") or ""),
    )


def decode_triggers_list(data: dict[str, Any]) -> TriggersList:
    triggers = [
        decode_trigger(item)
        for item in _field(data, "triggers", default=[]) or []
        if isinstance(item, dict)
    ]
    return TriggersList(
        triggers=triggers,
        total=int(_field(data, "total", default=0) or 0),
        next_page_token=str(_field(data, "nextPageToken", "next_page_token", default="") or ""),
    )


def decode_trigger_mutation(data: dict[str, Any]) -> TriggerMutationResult:
    return TriggerMutationResult(
        trigger_id=_id_str(_field(data, "triggerId", "trigger_id")),
        status=_enum_name(_field(data, "status")).lower(),
    )


def _decode_transfer_side(data: Any) -> TransferSide | None:
    if not isinstance(data, dict):
        return None
    kind = str(_field(data, "kind", default="") or "")
    account_id = str(_field(data, "accountId", "account_id", default="") or "")
    address = str(_field(data, "address", default="") or "")
    raw_chain = _field(data, "chainId", "chain_id")
    chain_id = int(raw_chain) if raw_chain not in (None, "") else None
    if not kind and not account_id and not address and chain_id is None:
        return None
    return TransferSide(kind=kind, account_id=account_id, address=address, chain_id=chain_id)


def _transfer_code(value: Any) -> int:
    """A ``ledger.v1.TransferCode`` number from its number or its name.

    JSON carries the uppercase enum name (``SYSTEM_ADJUSTMENT``), its
    lowercase label (``system_adjustment``) or the number. A name this SDK's
    contract does not define reads 0 (unspecified).
    """
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    try:
        return int(catalog_pb2.TransferCode.Value(text.upper()))
    except ValueError:
        return 0


def decode_ledger_transfer(data: dict[str, Any]) -> LedgerTransfer:
    return LedgerTransfer(
        asset_id=int(_field(data, "assetId", "asset_id", default=0) or 0),
        amount=_u128_str(_field(data, "amount")),
        transfer_type=_transfer_code(_field(data, "transferCode", "transfer_code", "type")),
        account_code=int(_field(data, "accountCode", "account_code", default=0) or 0),
        timestamp=int(_field(data, "timestamp", default=0) or 0),
        pending=bool(_field(data, "pending", default=False)),
        tx_id=str(_field(data, "txId", "tx_id", default="") or ""),
        is_debit=bool(_field(data, "isDebit", "is_debit", default=False)),
        source=_decode_transfer_side(_field(data, "source")),
        destination=_decode_transfer_side(_field(data, "destination")),
    )


def decode_transfers_list(data: dict[str, Any]) -> TransfersList:
    transfers = [
        decode_ledger_transfer(item)
        for item in _field(data, "transfers", default=[]) or []
        if isinstance(item, dict)
    ]
    return TransfersList(
        transfers=transfers,
        next_page_token=str(_field(data, "nextPageToken", "next_page_token", default="") or ""),
    )


def decode_internal_transfer_result(data: dict[str, Any]) -> InternalTransferResult:
    from polyester.types.money import AssetAmount, QuantityDomain

    asset_id = int(_field(data, "assetId", "asset_id", default=0) or 0)
    qty_raw = _field(
        data, "quantityScaled", "quantity_scaled", "qtyScaled", "qty_scaled", default=0
    )
    scaled = int(qty_raw or 0)
    return InternalTransferResult(
        request_id=str(_field(data, "requestId", "request_id", default="") or ""),
        transfer_id=str(_field(data, "transferId", "transfer_id", default="") or ""),
        asset_id=asset_id,
        asset_code=str(_field(data, "assetCode", "asset_code", default="") or ""),
        quantity=AssetAmount.from_scaled(scaled, domain=QuantityDomain.ASSET, asset_id=asset_id)
        if scaled
        else None,
        flow_id=str(_field(data, "flowId", "flow_id", default="") or ""),
    )


def decode_deposit_address(data: dict[str, Any]) -> DepositAddress:
    return DepositAddress(
        chain_id=int(_field(data, "chainId", "chain_id", default=0) or 0),
        deposit_address=str(_field(data, "depositAddress", "deposit_address", default="") or ""),
    )


def decode_deposit_addresses_list(data: dict[str, Any]) -> DepositAddressesList:
    addresses = [
        decode_deposit_address(item)
        for item in _field(data, "depositAddresses", "deposit_addresses", default=[]) or []
        if isinstance(item, dict)
    ]
    return DepositAddressesList(addresses=addresses)


def decode_trigger_event(data: dict[str, Any]) -> TriggerEvent:
    from polyester.types.money import Price

    fire_raw = (
        _field(
            data, "firePriceTicks", "fire_price_ticks", "firePxTicks", "fire_px_ticks", default=0
        )
        or 0
    )
    child_order_raw = _field(data, "childOrderId", "child_order_id", default=0) or 0
    return TriggerEvent(
        trigger_id=_id_str(_field(data, "triggerId", "trigger_id")),
        subaccount_id=_id_str(_field(data, "subaccountId", "subaccount_id")),
        symbol_id=int(_field(data, "symbolId", "symbol_id", default=0) or 0),
        trigger_type=_enum_name(_field(data, "triggerType", "trigger_type")).lower(),
        event_type=_enum_name(_field(data, "eventType", "event_type")).lower(),
        ts_ns=ts_ns_string_from_response(
            _field(data, "tsNs", "ts_ns", default=0) or 0,
            context="TriggerEvent",
            empty_when_zero=True,
        ),
        child_seq=int(_field(data, "childSeq", "child_seq", default=0) or 0),
        child_order_id=_id_str(child_order_raw) if int(child_order_raw) else "",
        fire_price=Price.from_ticks(int(fire_raw)) if int(fire_raw) else None,
        cancel_reason=str(_field(data, "cancelReason", "cancel_reason", default="") or ""),
        failure_reason=str(_field(data, "failureReason", "failure_reason", default="") or ""),
        # ConnectRPC JSON names the reason in full, REST without its prefix.
        fire_refusal_reason=str(
            _field(data, "fireRefusalReason", "fire_refusal_reason", default="") or ""
        )
        .removeprefix("TRIGGER_FAILURE_REASON_")
        .lower(),
    )


def decode_trigger_events_list(data: dict[str, Any]) -> TriggerEventsList:
    events = [
        decode_trigger_event(item)
        for item in _field(data, "events", default=[]) or []
        if isinstance(item, dict)
    ]
    return TriggerEventsList(
        events=events,
        next_page_token=str(_field(data, "nextPageToken", "next_page_token", default="") or ""),
    )


def _balance_range_label(value: Any) -> str:
    name = _enum_name(value).upper()
    mapping = {
        "DAY_1": "1d",
        "DAY_7": "7d",
        "DAY_30": "30d",
        "DAY_90": "90d",
        "DAY_180": "180d",
        "DAY_365": "365d",
    }
    return mapping.get(name, name.lower() or "")


def decode_balance_history_series(data: dict[str, Any]) -> BalanceHistorySeries:
    asset_id = int(_field(data, "assetId", "asset_id", default=0) or 0)
    balances = _field(data, "balance", default=[]) or []
    return BalanceHistorySeries(
        asset_id=asset_id,
        account_code=int(_field(data, "accountCode", "account_code", default=0) or 0),
        balance=[ledger_amount(_u128_json(item), asset_id) for item in balances],
    )


def _u128_json(value: Any) -> int:
    """A ``polyester.type.v1.U128`` in proto JSON (``{"hi": "..", "lo": ".."}``,
    zero halves omitted), as the exact integer it encodes."""
    if not isinstance(value, dict):
        raise PolyesterResponseContractError("U128", "expected an object with hi and lo")
    halves = []
    for key in ("hi", "lo"):
        raw = value.get(key, 0)
        if isinstance(raw, bool) or not isinstance(raw, int | str):
            raise PolyesterResponseContractError("U128", f"{key} is not an integer")
        text = str(raw)
        if not text.isascii() or not text.isdigit():
            raise PolyesterResponseContractError("U128", f"{key} is not an unsigned integer")
        half = int(text)
        if half >= 1 << 64:
            raise PolyesterResponseContractError("U128", f"{key} exceeds 64 bits")
        halves.append(half)
    return (halves[0] << 64) | halves[1]


def decode_balance_history(data: dict[str, Any]) -> BalanceHistory:
    series = [
        decode_balance_history_series(item)
        for item in _field(data, "series", default=[]) or []
        if isinstance(item, dict)
    ]
    points = int(_field(data, "points", default=0) or 0)
    for item in series:
        if len(item.balance) != points:
            raise PolyesterResponseContractError(
                "GetBalanceHistory",
                f"series of asset {item.asset_id} has {len(item.balance)} balances "
                f"for {points} points",
            )
    return BalanceHistory(
        range=_balance_range_label(_field(data, "range")),
        bucket=str(_field(data, "bucket", default="") or ""),
        start_ts_sec=int(_field(data, "startTsSec", "start_ts_sec", default=0) or 0),
        end_ts_sec=int(_field(data, "endTsSec", "end_ts_sec", default=0) or 0),
        points=points,
        series=series,
    )


def decode_equity_history_series(data: dict[str, Any]) -> EquityHistorySeries:
    account = _field(data, "account")
    asset = _field(data, "asset")
    portfolio = _field(data, "portfolioAccount", "portfolio_account")
    account_code = 0
    account_name = ""
    asset_id = 0
    asset_symbol = ""
    portfolio_account_id = ""
    portfolio_remaining = False
    if isinstance(account, dict):
        account_code = int(_field(account, "code", default=0) or 0)
        account_name = str(_field(account, "name", default="") or "")
    elif isinstance(asset, dict):
        asset_id = int(_field(asset, "id", default=0) or 0)
        asset_symbol = str(_field(asset, "symbol", default="") or "")
    elif isinstance(portfolio, dict):
        raw_account_id = _field(portfolio, "accountId", "account_id")
        if raw_account_id not in (None, ""):
            portfolio_account_id = _id_str(raw_account_id)
        portfolio_remaining = bool(_field(portfolio, "remaining", default=False))
    equity_q = _field(data, "equityQ", "equity_q", default=[]) or []
    return EquityHistorySeries(
        account_code=account_code,
        account_name=account_name,
        asset_id=asset_id,
        asset_symbol=asset_symbol,
        portfolio_account_id=portfolio_account_id,
        portfolio_remaining=portfolio_remaining,
        equity_q=[int(v) for v in equity_q],
    )


def decode_equity_history(data: dict[str, Any]) -> EquityHistory:
    series = [
        decode_equity_history_series(item)
        for item in _field(data, "series", default=[]) or []
        if isinstance(item, dict)
    ]
    return EquityHistory(
        range=_balance_range_label(_field(data, "range")),
        bucket=str(_field(data, "bucket", default="") or ""),
        start_ts_sec=int(_field(data, "startTsSec", "start_ts_sec", default=0) or 0),
        end_ts_sec=int(_field(data, "endTsSec", "end_ts_sec", default=0) or 0),
        quote_asset=str(_field(data, "quoteAsset", "quote_asset", default="") or ""),
        points=int(_field(data, "points", default=0) or 0),
        series=series,
        btc_prices_q=[int(v) for v in _field(data, "btcPricesQ", "btc_prices_q", default=[]) or []],
    )


def decode_bucket_transfer_result(data: dict[str, Any]) -> BucketTransferResult:
    return BucketTransferResult(
        transfer_id=str(_field(data, "transferId", "transfer_id", default="") or ""),
        timestamp_ns=str(_field(data, "timestamp", default="") or ""),
    )


def decode_market_trade_bytes(payload: bytes, *, quantity_scale: int) -> MarketTrade:
    from polyester._wire import protobuf_to_public_dict
    from polyester.gen.marketdata.v1.marketdata_pb2 import MarketTrade as MarketTradePb

    message = MarketTradePb()
    message.ParseFromString(payload)
    return decode_market_trade(protobuf_to_public_dict(message), quantity_scale=quantity_scale)


def decode_api_key(data: dict[str, Any]) -> ApiKeySummary:
    """Decode an ``auth.v1.ApiKey`` in its protobuf JSON form.

    It reads exactly as the binary decoder does: the dict is parsed into the
    generated message (camelCase or snake_case names; unknown fields are
    ignored) and decoded by ``api_key_from_proto``.
    """
    from google.protobuf.json_format import ParseDict, ParseError

    from polyester.codecs.decode.api_keys import api_key_from_proto
    from polyester.gen.auth.v1 import api_keys_pb2

    message = api_keys_pb2.ApiKey()
    try:
        ParseDict(data, message, ignore_unknown_fields=True)
    except ParseError as exc:
        raise PolyesterResponseContractError("ApiKey", f"API key is not valid: {exc}") from exc
    return api_key_from_proto(message)


def decode_api_keys_list(data: dict[str, Any]) -> ApiKeysList:
    keys = [
        decode_api_key(item)
        for item in _field(data, "apiKeys", "api_keys", default=[]) or []
        if isinstance(item, dict)
    ]
    return ApiKeysList(api_keys=keys)


def decode_resolved_account(data: dict[str, Any]) -> ResolvedAccount:
    return ResolvedAccount(
        smart_account_address=str(
            _field(data, "smartAccountAddress", "smart_account_address", default="") or ""
        ),
        kind=str(_field(data, "kind", default="") or ""),
        root_username=str(_field(data, "rootUsername", "root_username", default="") or ""),
        subaccount_label=str(_field(data, "subaccountLabel", "subaccount_label", default="") or ""),
        account_id=_id_str(_field(data, "accountId", "account_id")),
    )


def decode_resolved_accounts(data: dict[str, Any]) -> ResolvedAccountsList:
    matches = [
        decode_resolved_account(item)
        for item in _field(data, "matches", default=[]) or []
        if isinstance(item, dict)
    ]
    return ResolvedAccountsList(matches=matches)


def decode_transfer_destination(data: dict[str, Any]) -> TransferDestination:
    return TransferDestination(
        account_id=_id_str(_field(data, "accountId", "account_id")),
        subaccount_id=_id_str(_field(data, "subaccountId", "subaccount_id")),
        label=str(_field(data, "label", default="") or ""),
        smart_account_address=str(
            _field(data, "smartAccountAddress", "smart_account_address", default="") or ""
        ),
    )


def decode_transfer_destinations(data: dict[str, Any]) -> TransferDestinationsList:
    destinations = [
        decode_transfer_destination(item)
        for item in _field(data, "destinations", default=[]) or []
        if isinstance(item, dict)
    ]
    return TransferDestinationsList(destinations=destinations)


def decode_batch_replace_result(data: dict[str, Any]) -> BatchReplaceOrdersResult:
    """Decode a batch replace answer in its protobuf JSON form, exactly as
    ``batch_replace_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import batch_replace_from_proto
    from polyester.gen.orders.v1 import orders_pb2

    message = _contract_message(data, orders_pb2.BatchReplaceOrdersResponse(), "BatchReplaceOrders")
    return batch_replace_from_proto(message)


def decode_batch_replace_status(data: dict[str, Any]) -> BatchReplaceStatusResult:
    """Decode a batch replace status read in its protobuf JSON form, exactly as
    ``batch_replace_status_from_proto`` decodes the binary response."""
    from polyester.codecs.decode.orders import batch_replace_status_from_proto
    from polyester.gen.orders.v1 import orders_read_pb2

    message = _contract_message(
        data, orders_read_pb2.GetBatchReplaceStatusResponse(), "GetBatchReplaceStatus"
    )
    return batch_replace_status_from_proto(message)


def decode_withdraw_intent(data: dict[str, Any]) -> WithdrawIntentResult:
    return WithdrawIntentResult(
        intent_id=str(_field(data, "intentId", "intent_id", default="") or "")
    )
