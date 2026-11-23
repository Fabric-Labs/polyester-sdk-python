from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from polyester.catalogs import CatalogManager
from polyester.codecs.contract_limits import contract_string_max_bytes
from polyester.codecs.correlation_id import (
    REQUEST_ID_MAX_LEN,
    check_correlation_id,
    optional_request_id,
)
from polyester.codecs.pure_bridge import call, message, pure
from polyester.codecs.scalars import (
    INT64_MAX,
    id_to_int,
    market_ids,
    parse_account_id,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2

TRIGGER_TYPE_TO_PROTO: dict[str, str] = pure._TRIGGER_TYPES
TRIGGER_PRICE_SOURCE_TO_PROTO: dict[str, str] = pure._PRICE_SOURCES


def _contract_int_range(message: Any, name: str, kind: str, wire_max: int) -> tuple[int, int]:
    """The ``gte``/``gt`` and ``lte``/``lt`` bounds the contract sets on an integer field.

    A bound the contract leaves out is the wire type's own.
    """
    field = message.DESCRIPTOR.fields_by_name[name]
    rules = getattr(field.GetOptions().Extensions[validate_pb2.field], kind)
    low = -wire_max - 1
    if rules.HasField("gte"):
        low = rules.gte
    elif rules.HasField("gt"):
        low = rules.gt + 1
    high = wire_max
    if rules.HasField("lte"):
        high = rules.lte
    elif rules.HasField("lt"):
        high = rules.lt - 1
    return low, high


_INT32_MAX = 2**31 - 1
# TWAP and ladder ranges, read from the contract's validation rules.
TWAP_DURATION_MS_MIN, TWAP_DURATION_MS_MAX = _contract_int_range(
    triggers_pb2.TwapTrigger, "duration_ms", "int64", INT64_MAX
)
TWAP_SLICE_INTERVAL_MS_MIN, TWAP_SLICE_INTERVAL_MS_MAX = _contract_int_range(
    triggers_pb2.TwapTrigger, "slice_interval_ms", "int64", INT64_MAX
)
LADDER_LEVELS_MIN, LADDER_LEVELS_MAX = _contract_int_range(
    triggers_pb2.LadderTrigger, "levels", "int32", _INT32_MAX
)

def _trigger_type_key(trigger_type: object) -> str:
    return call(pure._trigger_type_key, trigger_type)


def trigger_type_to_proto(trigger_type: str) -> triggers_pb2.TriggerType:
    """``ListTriggersRequest.trigger_type`` for a ``triggers.create`` label."""
    return getattr(triggers_pb2, TRIGGER_TYPE_TO_PROTO[_trigger_type_key(trigger_type)])


# Spot markets have no mark price; the backend rejects it.
def trigger_price_source_to_proto(
    value: object, field_name: str = "trigger_price_source"
) -> orders_pb2.TriggerPriceSource:
    """Map ``last`` or ``index`` (as trigger reads report it) to the wire enum.

    ``None`` or an empty string leaves the source unset; the server then uses
    the last trade price. Spot markets do not support ``mark``.
    """
    name = call(pure._price_source, value, field_name)
    return getattr(orders_pb2, name) if name else orders_pb2.TRIGGER_PRICE_SOURCE_UNSPECIFIED


FEE_ASSET_TO_PROTO: dict[str, str] = pure._FEE_ASSETS
SELF_TRADE_PREVENTION_MODE_TO_PROTO: dict[str, str] = pure._STP_MODES


def self_trade_prevention_mode_to_proto(value: str) -> orders_pb2.SelfTradePreventionMode:
    """Wire value of ``expire_taker``, ``expire_maker``, ``expire_both`` or
    ``decrement`` (any case).

    ``decrement`` reduces both orders by the quantity that would have traded,
    with no trade; the order left with no quantity is canceled with cancel
    reason ``stp_decrement``. Orders with attached exits and triggers take it
    too.
    """
    return getattr(orders_pb2, call(pure._stp_mode, value))


LADDER_DISTRIBUTION_TO_PROTO = {
    "linear": "LINEAR",
    "geometric": "GEOMETRIC",
    "weighted_favorable": "WEIGHTED_FAVORABLE",
}


def create_trigger_to_proto(
    *,
    symbol: str,
    symbol_id: int,
    trigger_type: str,
    side: str,
    qty: object,
    trigger_price: Any | None = None,
    order_type: str | None = None,
    limit_price: Any | None = None,
    trigger_price_source: str | None = None,
    tif: str | None = None,
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
    """Encode a standalone trigger create; the rules are ``polyester.pure``'s.

    ``client_trigger_id`` left out (``None``) is generated; an explicit one,
    even empty, is checked and sent unchanged.
    """
    built = call(
        pure._trigger_request,
        symbol,
        symbol_id,
        trigger_type,
        side,
        qty,
        quantity_scale,
        trigger_price=trigger_price,
        order_type=order_type,
        limit_price=limit_price,
        trigger_price_source=trigger_price_source,
        tif=tif,
        sub_account_id=sub_account_id,
        client_trigger_id=client_trigger_id,
        post_only=post_only,
        fee_asset=fee_asset,
        self_trade_prevention_mode=self_trade_prevention_mode,
        trailing_distance_ticks=trailing_distance_ticks,
        trailing_distance_bps=trailing_distance_bps,
        activation_price=activation_price,
        max_slippage_ticks=max_slippage_ticks,
        max_slippage_bps=max_slippage_bps,
        twap_duration_ms=twap_duration_ms,
        twap_slice_interval_ms=twap_slice_interval_ms,
        ladder_price_min=ladder_price_min,
        ladder_price_max=ladder_price_max,
        ladder_levels=ladder_levels,
        ladder_distribution=ladder_distribution,
    )
    if client_trigger_id is None:
        built["trigger"]["clientTriggerId"] = f"trg-{uuid.uuid4().hex[:12]}"
    return message(built, triggers_pb2.CreateTriggerRequest())


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
    symbol: str | None = None,
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
    that market (an API key limited to specific markets must set it).
    ``symbol`` is that market's name: a ``Price`` bound to another market is
    refused. A child's limit price is fixed at creation: cancel the trigger
    and create a new one to change it. ``max_slippage_bps`` is 1 to 10000, as
    the contract takes it: the patch does not say what it modifies, so the
    server decides by side and type (a buy stop-loss or take-profit with a
    market child accepts 10000; a sell or a trailing stop answers
    ``MAX_SLIPPAGE_INVALID``). ``0`` clears it.
    """
    built = call(
        pure._modify_trigger,
        trigger_id,
        symbol_id,
        symbol,
        sub_account_id,
        trigger_price,
        trailing_distance_ticks,
        trailing_distance_bps,
        activation_price,
        max_slippage_ticks,
        max_slippage_bps,
    )
    return message(built, triggers_pb2.ModifyTriggerRequest())


def _contract_max_trigger_ids() -> int:
    """The ``trigger_ids`` limit the public contract sets on a batch cancel."""
    field = triggers_pb2.BatchCancelTriggersRequest.DESCRIPTOR.fields_by_name["trigger_ids"]
    return int(field.GetOptions().Extensions[validate_pb2.field].repeated.max_items)


# Trigger IDs one BatchCancelTriggers request accepts, from the contract.
BATCH_CANCEL_TRIGGERS_MAX_IDS = _contract_max_trigger_ids()


def batch_cancel_triggers_to_proto(
    *,
    trigger_ids: Sequence[str | int],
    sub_account_id: str | int | None = None,
    request_id: str | None = None,
) -> triggers_pb2.BatchCancelTriggersRequest:
    """Encode a batch trigger cancel.

    ``trigger_ids`` takes 1 to 50 distinct non-zero trigger IDs (base58 or
    decimal), sent in the order given. ``request_id`` is the request's
    idempotency key; left out or empty, one is generated.
    """
    if isinstance(trigger_ids, (str, bytes)):
        raise PolyesterValidationError("trigger_ids must be a list of trigger IDs")
    count = len(trigger_ids)
    if count == 0:
        raise PolyesterValidationError("batch_cancel requires at least one trigger ID")
    if count > BATCH_CANCEL_TRIGGERS_MAX_IDS:
        raise PolyesterValidationError(
            f"batch_cancel accepts at most {BATCH_CANCEL_TRIGGERS_MAX_IDS} trigger IDs; "
            f"received {count}"
        )
    ids: list[int] = []
    for index, value in enumerate(trigger_ids):
        parsed = id_to_int(value, f"trigger_ids[{index}]")
        if parsed == 0:
            raise PolyesterValidationError(f"trigger_ids[{index}] must be a non-zero trigger ID")
        if parsed in ids:
            raise PolyesterValidationError(
                f"trigger_ids[{index}] repeats trigger ID {value!r}; trigger IDs must be distinct"
            )
        ids.append(parsed)
    proto = triggers_pb2.BatchCancelTriggersRequest(
        request_id=optional_request_id(request_id) or f"trg-cancel-{uuid.uuid4().hex[:12]}",
        trigger_ids=ids,
    )
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    return proto


def cancel_all_trigger_symbol_ids(values: object) -> list[int]:
    """``triggers.cancel_all``'s ``symbol_ids`` as pair IDs, or refused.

    A str, raw bytes (``memoryview`` included) or mapping is refused, never
    iterated, so ``b"\\x01"`` is not pair 1 and an empty buffer never widens
    the cancel to every pair.
    """
    if isinstance(values, memoryview):
        raise PolyesterValidationError(
            "triggers.cancel_all symbol_ids must be a list of integer market IDs, not memoryview"
        )
    return market_ids(values, "triggers.cancel_all symbol_ids")


# The contract's bounds on a CancelAllTriggers request.
CANCEL_ALL_TRIGGERS_MAX_SYMBOLS = 100
CANCEL_ALL_TRIGGERS_MAX_TYPES = 5


def cancel_all_triggers_to_proto(
    *,
    sub_account_id: str | int | None = None,
    symbol_ids: Sequence[int] = (),
    side: str | None = None,
    trigger_types: Sequence[str] | None = None,
    dry_run: bool = False,
    request_id: str | None = None,
) -> triggers_pb2.CancelAllTriggersRequest:
    """Encode a cancel of every matching trigger.

    ``symbol_ids`` are resolved pair IDs (empty matches every pair), ``side``
    is ``buy`` or ``sell`` (``None`` matches both) and ``trigger_types`` takes
    up to 5 ``triggers.create`` type labels (empty matches every type);
    repeats are sent once. ``request_id`` is the request's idempotency key,
    sent exactly as given: one that is not 1 to 64 of ``[A-Za-z0-9._:/-]``,
    an empty or padded one included, is refused, never replaced, so a retry
    cannot become a new cancel. Left out (``None``), one is generated.
    """
    if not isinstance(dry_run, bool):
        raise PolyesterValidationError("dry_run must be a bool")
    if request_id is None:
        key = f"trg-cancel-all-{uuid.uuid4().hex[:12]}"
    elif isinstance(request_id, str):
        key = check_correlation_id(request_id, "request_id", REQUEST_ID_MAX_LEN)
    else:
        raise PolyesterValidationError("request_id must be a string")
    proto = triggers_pb2.CancelAllTriggersRequest(request_id=key, dry_run=dry_run)
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    # A str, raw bytes or mapping is refused, never iterated: b"\x01" is not pair 1.
    unique_ids = list(dict.fromkeys(cancel_all_trigger_symbol_ids(symbol_ids)))
    if any(value <= 0 for value in unique_ids):
        raise PolyesterValidationError("triggers.cancel_all symbol_ids must be positive")
    if len(unique_ids) > CANCEL_ALL_TRIGGERS_MAX_SYMBOLS:
        raise PolyesterValidationError(
            f"triggers.cancel_all accepts at most {CANCEL_ALL_TRIGGERS_MAX_SYMBOLS} pairs"
        )
    proto.symbol_ids.extend(unique_ids)
    if side is not None:
        key = side.strip().lower() if isinstance(side, str) else ""
        if key not in ("buy", "sell"):
            raise PolyesterValidationError("side must be buy or sell")
        proto.side = orders_pb2.BUY if key == "buy" else orders_pb2.SELL
    if trigger_types is not None:
        if isinstance(
            trigger_types, str | bytes | bytearray | memoryview | Mapping
        ) or not isinstance(trigger_types, Iterable):
            raise PolyesterValidationError("trigger_types must be a list of trigger types")
        types = list(dict.fromkeys(trigger_type_to_proto(value) for value in trigger_types))
        if len(types) > CANCEL_ALL_TRIGGERS_MAX_TYPES:
            raise PolyesterValidationError(
                f"trigger_types takes at most {CANCEL_ALL_TRIGGERS_MAX_TYPES} distinct types"
            )
        proto.trigger_types.extend(types)
    return proto


# The contract's rule on TriggerIntent.client_trigger_id: 1 to 36 bytes of
# UTF-8, in any characters.
CLIENT_TRIGGER_ID_MAX_BYTES = contract_string_max_bytes(
    triggers_pb2.TriggerIntent, "client_trigger_id"
)


def _client_trigger_id(value: object) -> str:
    """``value`` unchanged when the contract takes it as a client trigger ID."""
    return call(pure._client_trigger_id, value)
