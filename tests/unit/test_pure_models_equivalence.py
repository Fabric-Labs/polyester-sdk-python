"""``polyester/pure_models.py`` decodes an order or trigger as the SDK does.

Every generated ``Order`` and ``Trigger`` (``pure_models_support.matrix``) is
decoded twice: by the SDK's protobuf decoder, and by the file from its
proto-JSON (``MessageToDict``, canonical and with every field written). Both
give the same models, field for field: names, types and values, prices and
quantities bound to the same market, or the same refusal. The models' fields
are the SDK models' fields, so a field added to one and not the other fails.
"""

from __future__ import annotations

import copy
import dataclasses
import typing
from typing import Any

import msgspec
import pytest
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import models as sdk_models
from polyester.codecs.proto_helpers import timestamp_to_rfc3339
from polyester.errors import PolyesterResponseContractError
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from tests.unit import pure_models_support as support
from tests.unit.pure_models_support import SPEC, SYMBOL_ID, file_decode, sdk_decode

NAMESPACE = support.load()
MODELS: Any = NAMESPACE["polyester_models"]
PURE: Any = NAMESPACE["polyester"]
MATRIX = support.matrix()

MODEL_NAMES = [
    "Order",
    "OrderFeeTotal",
    "OrderLineage",
    "OrderOrigin",
    "AttachedRisk",
    "AttachedRiskLegState",
    "RiskLeg",
    "TrailingStop",
    "Trigger",
    "TriggerDetails",
    "TriggerStopDetails",
    "TriggerTrailingDetails",
    "TriggerTwapDetails",
    "TriggerLadderDetails",
]


def _mismatches(messages: list[Message], *, all_fields: bool) -> list[Any]:
    found = []
    for message in messages:
        bound = support.binds(message)
        want = sdk_decode(message, bound)
        have = file_decode(MODELS, message, bound, all_fields=all_fields)
        if want != have:
            found.append((support.to_dict(message), want, have))
    return found


@pytest.mark.parametrize("all_fields", [False, True], ids=["canonical", "every-field"])
def test_generated_orders_and_triggers_decode_as_the_sdk(all_fields: bool) -> None:
    assert _mismatches(MATRIX, all_fields=all_fields) == []


def test_the_matrix_is_broad() -> None:
    """Every field of both messages, nested ones included, is set by some
    case; messages decode bound and unbound, and some are refused."""
    for message_type in (orders_read_pb2.Order, triggers_pb2.Trigger):
        set_paths: set[str] = set()
        for message in MATRIX:
            if isinstance(message, message_type):
                set_paths |= support.set_paths(message)
        paths = {path for path, _ in support.field_paths(message_type.DESCRIPTOR)}
        assert paths - set_paths == set()
    results = [sdk_decode(message, support.binds(message))[0] for message in MATRIX]
    assert {"Order", "Trigger", "error"} <= set(results)
    assert results.count("error") < len(results) // 5
    assert {int(message.symbol_id) for message in MATRIX} == {  # type: ignore[attr-defined]
        0,
        SYMBOL_ID,
        support.OTHER_SYMBOL_ID,
    }


def _enum_cases() -> list[tuple[str, Message, int]]:
    """For every enum field in both messages, and every value it has (and an
    unknown one), a decodable generated message with the field set to it."""
    cases = []
    for message_type in (orders_read_pb2.Order, triggers_pb2.Trigger):
        bases = [
            message
            for message in MATRIX
            if isinstance(message, message_type)
            and sdk_decode(message, support.binds(message))[0] != "error"
        ]
        for path, field in support.field_paths(message_type.DESCRIPTOR):
            if field.type != FieldDescriptor.TYPE_ENUM:
                continue
            base = next(message for message in bases if path in support.set_paths(message))
            for number in [value.number for value in field.enum_type.values] + [999]:
                message = copy.deepcopy(base)
                _set_path(message, path, number)
                cases.append((f"{message_type.DESCRIPTOR.name}.{path}={number}", message, number))
    return cases


def _set_path(message: Message, path: str, value: int) -> None:
    *parents, leaf = path.split(".")
    for name in parents:
        message = getattr(message, name)
    setattr(message, leaf, value)


def test_every_enum_value_decodes_as_the_sdk() -> None:
    cases = _enum_cases()
    # Every value of every enum of both messages: ErrorCode alone has 200 and more.
    assert len(cases) > 400
    found = []
    for name, message, _ in cases:
        bound = support.binds(message)
        want, have = sdk_decode(message, bound), file_decode(MODELS, message, bound)
        if want != have:
            found.append((name, want, have))
    assert found == []


def _sdk_class(name: str) -> type[msgspec.Struct]:
    cls: type[msgspec.Struct] = getattr(sdk_models, name)
    return cls


@pytest.mark.parametrize("name", MODEL_NAMES)
def test_model_fields_are_the_sdks(name: str) -> None:
    """Same field names, in the same order, with the same defaults."""
    ours = [(item.name, item.default) for item in dataclasses.fields(getattr(MODELS, name))]
    theirs = [
        (item.name, dataclasses.MISSING if item.default is msgspec.NODEFAULT else item.default)
        for item in msgspec.structs.fields(_sdk_class(name))
    ]
    assert ours == theirs


def test_every_model_the_sdk_nests_is_mirrored() -> None:
    """The SDK models an Order or a Trigger holds, at any depth, are the file's models."""
    seen: set[str] = set()

    def walk(cls: type[msgspec.Struct]) -> None:
        if cls.__name__ in seen:
            return
        seen.add(cls.__name__)
        for hint in typing.get_type_hints(cls).values():
            for arg in [hint, *typing.get_args(hint)]:
                if isinstance(arg, type) and issubclass(arg, msgspec.Struct):
                    walk(arg)

    walk(sdk_models.Order)
    walk(sdk_models.Trigger)
    assert sorted(seen) == sorted(MODEL_NAMES)


def test_missing_fields_read_as_the_sdks_defaults() -> None:
    for message in (orders_read_pb2.Order(), triggers_pb2.Trigger()):
        assert sdk_decode(message, True) == file_decode(MODELS, message, True)
    order = MODELS.order({})
    assert (order.order_id, order.symbol_id, order.side) == ("0", None, None)
    assert order.attached_risk is None
    assert order.orig_qty == PURE.Quantity(0)
    trigger = MODELS.trigger({})
    assert (trigger.trigger_id, trigger.symbol, trigger.details, trigger.created_at) == (
        "0",
        "",
        None,
        None,
    )


def test_presence_is_kept() -> None:
    """A sent zero is not a missing field, where the contract tells them apart."""
    sent = MODELS.order({"submittedMaxQuoteDebitScaled": "0", "lineage": {"generation": 1}})
    assert sent.submitted_max_quote_debit_scaled == "0"
    assert sent.lineage == MODELS.OrderLineage("0", 1)
    assert MODELS.order({}).submitted_max_quote_debit_scaled == ""
    state = {"policy": {}, "state": {"status": "ARMED", "triggerId": "0"}}
    risk = MODELS.order({"attachedRisk": {"stopLoss": state}}).attached_risk
    assert risk.stop_loss.state.trigger_id == "0"
    assert risk.stop_loss.state.child_order_id == ""


def test_unknown_enum_values_and_fields_survive() -> None:
    order = MODELS.order(
        {
            "side": 7,
            "status": 99,
            "rejectReason": 9999,
            "cancelReason": 77,
            "origin": {"scope": 5},
            "aFieldFromANewerContract": {"x": 1},
        }
    )
    assert (order.side, order.status, order.reject_reason, order.cancel_reason) == (
        "7",
        "99",
        "UNKNOWN_ERROR_CODE(9999)",
        "UNKNOWN_CANCEL_REASON(77)",
    )
    assert order.origin.scope == "5"
    trigger = MODELS.trigger(
        {"status": 42, "stopLoss": {"triggerPriceSource": 8}, "ladderState": {"outcome": 6}}
    )
    assert (trigger.status, trigger.trigger_price_source, trigger.details.ladder.outcome) == (
        "42",
        "8",
        "6",
    )
    message = orders_read_pb2.Order(side=7, status=99, reject_reason=9999)  # type: ignore[arg-type]
    assert sdk_decode(message, False) == file_decode(MODELS, message, False)


@pytest.mark.parametrize(
    ("seconds", "nanos"),
    [
        (-62_135_596_800, 0),  # 0001-01-01
        (-62_135_596_800, 999_999_999),
        (253_402_300_799, 999_999_999),  # 9999-12-31T23:59:59.999999999
        (0, 0),  # the epoch reads as no time
        (0, 1),
        (-1, 500_000_000),
        (1_763_164_740, 120_000_000),
    ],
)
def test_extreme_timestamps(seconds: int, nanos: int) -> None:
    ts = Timestamp(seconds=seconds, nanos=nanos)
    order = orders_read_pb2.Order(order_id=5, symbol_id=SYMBOL_ID, expire_at=ts)
    trigger = triggers_pb2.Trigger(
        trigger_id=5,
        symbol_id=SYMBOL_ID,
        created_at=ts,
        updated_at=ts,
        armed_at=ts,
        completed_at=ts,
    )
    for message in (order, trigger):
        assert sdk_decode(message, True) == file_decode(MODELS, message, True)
        assert sdk_decode(message, True) == file_decode(MODELS, message, True, all_fields=True)


def test_sdk_expire_at_has_a_four_digit_year() -> None:
    """RFC 3339 on every platform: glibc's strftime wrote the year 1 as "1"."""
    assert timestamp_to_rfc3339(Timestamp(seconds=-62_135_596_800)) == "0001-01-01T00:00:00Z"
    assert (
        timestamp_to_rfc3339(Timestamp(seconds=-50_000_000_000, nanos=5_000))
        == "0385-07-25T07:06:40.000005000Z"
    )


def test_values_are_bound_to_the_market() -> None:
    data = {
        "orderId": "9",
        "symbolId": SYMBOL_ID,
        "origQtyScaled": "25000000",
        "priceTicks": "64000500000000",
    }
    order = MODELS.order(data, SPEC)
    assert order.orig_qty == PURE.Quantity(25_000_000, 8, "order_base", "BTC-USDT", SYMBOL_ID)
    assert order.orig_qty.as_decimal() == PURE.Quantity(25_000_000, 8).as_decimal()
    assert order.price == PURE.market(SPEC).price("64000.5")
    assert order.quote_quantity_scale == 6
    # The market as polyester.market(pair) gives it, or as GetSpotConfig serves it.
    assert MODELS.order(data, PURE.market(SPEC)) == order
    assert MODELS.order(data, {**SPEC, "symbolId": str(SYMBOL_ID), "minQty": "1"}) == order
    # A pair-less message is never bound; an unbound decode carries the symbol ID only.
    assert MODELS.order({**data, "symbolId": 0}, SPEC).price == PURE.Price(64_000_500_000_000)
    assert MODELS.order(data).orig_qty == PURE.Quantity(25_000_000, symbol_id=SYMBOL_ID)
    trigger = MODELS.trigger({"symbolId": SYMBOL_ID, "qtyScaled": "5"}, SPEC)
    assert (trigger.symbol, trigger.qty.symbol, trigger.qty.scale) == ("BTC-USDT", "BTC-USDT", 8)
    assert MODELS.trigger({"qtyScaled": "5"}, SPEC).qty == PURE.Quantity(5, symbol_id=0)


@pytest.mark.parametrize(
    ("data", "market", "message"),
    [
        ({"symbolId": 3}, SPEC, "order symbol_id 3 is not the market's symbol_id 7"),
        ([], SPEC, "order must be a proto-JSON dict, not list"),
        ({}, {"symbolId": 7}, "market symbol must be a non-empty string"),
        ({}, "BTC-USDT", "market must be a GetSpotConfig pair dict, not str"),
        ({"expireAt": "2026-11-24T12:00:00+01:00"}, None, "timestamp must be an RFC 3339 UTC"),
        ({"priceTicks": "-1"}, None, "ticks must be non-negative"),
        ({"cumQtyScaled": "-1"}, None, "Order.cum_qty_scaled: negative quantity -1"),
    ],
)
def test_refusals(data: Any, market: Any, message: str) -> None:
    with pytest.raises(ValueError, match="^" + message.replace("(", r"\(")):
        MODELS.order(data, market)


@pytest.mark.parametrize(
    ("state", "message"),
    [
        ("twap_state", "Trigger.twap_state.executed_qty_scaled: negative quantity -2"),
        ("ladder_state", "Trigger.ladder_state.executed_qty_scaled: negative quantity -2"),
        (None, "Trigger.qty_scaled: negative quantity -2"),
    ],
)
def test_negative_trigger_quantities_are_refused_alike(state: str | None, message: str) -> None:
    """The protobuf decode, this file and the proto-JSON trigger decode refuse
    a negative trigger quantity, nested executed quantities included, with the
    same message."""
    from polyester.codecs.wire_decode import decode_trigger

    trigger = triggers_pb2.Trigger(trigger_id=1, symbol_id=SYMBOL_ID, qty_scaled=100)
    if state is None:
        trigger.qty_scaled = -2
    else:
        getattr(trigger, state).executed_qty_scaled = -2
    for bound in (True, False):
        assert sdk_decode(trigger, bound) == ("error", message)
        assert file_decode(MODELS, trigger, bound) == ("error", message)
    with pytest.raises(PolyesterResponseContractError, match="^" + message + "$"):
        decode_trigger(support.to_dict(trigger))


def test_a_trigger_for_another_market_is_refused() -> None:
    with pytest.raises(ValueError, match="trigger symbol_id 3 is not the market's symbol_id 7"):
        MODELS.trigger({"symbolId": 3}, SPEC)


def test_decoded_values_feed_the_builders() -> None:
    """A bot reads an order, then modifies it: the file's values are pure.py's own types."""
    order = MODELS.order(
        {
            "orderId": "9",
            "symbolId": SYMBOL_ID,
            "priceTicks": "64000500000000",
            "origQtyScaled": "25000000",
        },
        SPEC,
    )
    request = PURE.orders.modify(
        SPEC, key=PURE.OrderId(order.order_id), new_price=order.price, new_qty=order.orig_qty
    )
    assert (request["newPriceTicks"], request["newQtyScaled"]) == ("64000500000000", "25000000")
    other = {**SPEC, "symbol": "ETH-USDT", "symbolId": 8}
    with pytest.raises(ValueError, match="price symbol mismatch"):
        PURE.orders.modify(other, key=PURE.OrderId(order.order_id), new_price=order.price)
