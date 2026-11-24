"""Shared by the ``polyester/pure_models.py`` tests: the file loaded as a
restricted runtime loads it, generated ``Order`` and ``Trigger`` messages, and
a canonical form to compare decoded models field for field.

The generator walks the messages' descriptors, so a field the contract adds is
generated too: if the SDK decodes it and the file does not (or the other way
round), the equivalence tests fail.
"""

from __future__ import annotations

import dataclasses
import random
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import msgspec
from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from polyester import pure
from polyester.codecs.decode.orders import scaled_order_from_proto
from polyester.codecs.decode.triggers import scaled_trigger_from_proto
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2

PURE_PATH = Path(pure.__file__)
MODELS_PATH = PURE_PATH.with_name("pure_models.py")
PURE_SOURCE = PURE_PATH.read_text(encoding="utf-8")
SOURCE = MODELS_PATH.read_text(encoding="utf-8")

SYMBOL_ID = 7
SPEC = {
    "symbol": "BTC-USDT",
    "symbolId": SYMBOL_ID,
    "baseQuantityScale": 8,
    "quoteQuantityScale": 6,
}
OTHER_SYMBOL_ID = 99

_U64 = 2**64 - 1
_I64 = 2**63 - 1
# Years 1 to 9999, as a Timestamp holds them.
_SECONDS = [0, 1, -1, 1_763_164_740, -62_135_596_800, 253_402_300_799, 946_684_800, -2_208_988_800]
_NANOS = [0, 0, 1, 1_000, 123_000_000, 123_456_000, 123_456_789, 999_999_999]


def load(extra: str = "") -> dict[str, Any]:
    """One namespace holding pure.py, then this file, then ``extra``, as the
    runtime loads them. Compiled under their paths, so coverage counts them."""
    namespace: dict[str, Any] = {}
    exec(compile(PURE_SOURCE, str(PURE_PATH), "exec"), namespace)  # noqa: S102
    exec(compile(SOURCE, str(MODELS_PATH), "exec"), namespace)  # noqa: S102
    if extra:
        exec(compile(extra, "extra", "exec"), namespace)  # noqa: S102
    return namespace


def _int(field: FieldDescriptor, rng: random.Random, negative: float) -> int:
    kind = field.type
    if kind in (FieldDescriptor.TYPE_UINT64, FieldDescriptor.TYPE_FIXED64):
        return rng.choice([0, 1, 7, 58, 2**63 + 5, _U64, rng.randrange(_U64)])
    if kind in (FieldDescriptor.TYPE_UINT32, FieldDescriptor.TYPE_FIXED32):
        return rng.choice([0, 1, 7, 150, 2**32 - 1, rng.randrange(2**32)])
    if kind in (FieldDescriptor.TYPE_INT32, FieldDescriptor.TYPE_SINT32):
        value = rng.choice([0, 1, 5, 150, 9999, 10000, 2**31 - 1])
        return -value if rng.random() < negative else value
    value = rng.choice([0, 1, 9, 100_000_000, 64_000_500_000_000, _I64, rng.randrange(_I64)])
    return -value if rng.random() < negative else value


def _fill(message: Message, rng: random.Random, depth: int, negative: float) -> None:
    descriptor = message.DESCRIPTOR
    if descriptor.full_name == "google.protobuf.Timestamp":
        message.seconds = rng.choice(_SECONDS)  # type: ignore[attr-defined]
        message.nanos = rng.choice(_NANOS)  # type: ignore[attr-defined]
        return
    chosen = {
        oneof.name: rng.choice(oneof.fields).name if rng.random() < 0.75 else None
        for oneof in descriptor.oneofs
    }
    for field in descriptor.fields:
        oneof = field.containing_oneof
        if oneof is not None:
            if chosen[oneof.name] != field.name:
                continue
        elif rng.random() < 0.3:
            continue
        _set(message, field, rng, depth, negative)


def _set(
    message: Message, field: FieldDescriptor, rng: random.Random, depth: int, negative: float
) -> None:
    name = field.name
    if field.type == FieldDescriptor.TYPE_MESSAGE:
        child = getattr(message, name)
        child.SetInParent()
        if depth < 5:
            _fill(child, rng, depth + 1, negative)
    elif field.type == FieldDescriptor.TYPE_ENUM:
        numbers = [value.number for value in field.enum_type.values]
        setattr(message, name, rng.choice([*numbers, 0, 999]))
    elif field.type == FieldDescriptor.TYPE_BOOL:
        setattr(message, name, rng.random() < 0.5)
    elif field.type == FieldDescriptor.TYPE_STRING:
        setattr(message, name, rng.choice(["", "cid-1", "x" * 36, "bot-é"]))
    else:
        setattr(message, name, _int(field, rng, negative))


def generate(message_type: type[Message], seed: int, *, negative: float = 0.02) -> Message:
    """A random message: each field set or left out, each oneof one member or
    none, enums any known value, 0 or an unknown 999, integers to their limits."""
    rng = random.Random(seed)
    message = message_type()
    _fill(message, rng, 0, negative)
    # Most messages name the market the tests bind; some no pair, some another.
    message.symbol_id = rng.choice([SYMBOL_ID] * 6 + [0, OTHER_SYMBOL_ID])  # type: ignore[attr-defined]
    return message


def field_paths(descriptor: Descriptor, prefix: str = "") -> list[tuple[str, FieldDescriptor]]:
    """Every field under ``descriptor`` by dotted path (Timestamp and U128 as leaves)."""
    paths: list[tuple[str, FieldDescriptor]] = []
    for field in descriptor.fields:
        path = f"{prefix}{field.name}"
        paths.append((path, field))
        message = field.message_type
        if message is not None and message.full_name not in (
            "google.protobuf.Timestamp",
            "polyester.type.v1.U128",
        ):
            paths.extend(field_paths(message, f"{path}."))
    return paths


def set_paths(message: Message, prefix: str = "") -> set[str]:
    """The dotted paths of every field ``message`` sets."""
    paths: set[str] = set()
    for field, value in message.ListFields():
        path = f"{prefix}{field.name}"
        paths.add(path)
        if field.message_type is not None:
            paths |= set_paths(value, f"{path}.")
    return paths


def to_dict(message: Message, *, all_fields: bool = False) -> dict[str, Any]:
    """Canonical proto-JSON, or with every field that has no presence written."""
    return MessageToDict(message, always_print_fields_with_no_presence=all_fields)


def canon(value: Any) -> Any:
    """A model as nested tuples of class name, field names, value types and
    values: a SDK model and the file's model compare equal only when every
    field has the same name, type and value."""
    if isinstance(value, msgspec.Struct):
        names: tuple[str, ...] = value.__struct_fields__
        return (type(value).__name__, tuple((name, canon(getattr(value, name))) for name in names))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        kind = type(value).__name__
        if kind == "Price":
            return ("Price", value.ticks, value.symbol)  # type: ignore[attr-defined]
        if kind == "Quantity":
            return (
                "Quantity",
                value.scaled,  # type: ignore[attr-defined]
                value.scale,  # type: ignore[attr-defined]
                str(value.domain),  # type: ignore[attr-defined]
                value.symbol,  # type: ignore[attr-defined]
                value.symbol_id,  # type: ignore[attr-defined]
            )
        fields = dataclasses.fields(value)
        return (kind, tuple((item.name, canon(getattr(value, item.name))) for item in fields))
    if isinstance(value, Decimal):
        return ("Decimal", str(value))
    if isinstance(value, datetime):
        return ("datetime", value.isoformat(), str(value.tzinfo))
    return (type(value).__name__, value)


def _scales(symbol_id: int) -> tuple[int | None, int | None]:
    return (8, 6) if symbol_id == SYMBOL_ID else (None, None)


def _symbols(symbol_id: int) -> str:
    return "BTC-USDT" if symbol_id == SYMBOL_ID else ""


def sdk_decode(message: Message, bound: bool) -> Any:
    """The SDK's decode, with the catalogs listing the market (``bound``) or none."""
    scales = _scales if bound else None
    symbols = _symbols if bound else None
    try:
        if isinstance(message, orders_read_pb2.Order):
            return canon(scaled_order_from_proto(message, scales, symbols))
        return canon(scaled_trigger_from_proto(message, scales, symbols))
    except Exception as exc:  # noqa: BLE001 - the error is the result compared
        return ("error", str(exc))


def file_decode(models: Any, message: Message, bound: bool, *, all_fields: bool = False) -> Any:
    """The file's decode of the message's proto-JSON, given the market or none."""
    decode = models.order if isinstance(message, orders_read_pb2.Order) else models.trigger
    try:
        return canon(decode(to_dict(message, all_fields=all_fields), SPEC if bound else None))
    except ValueError as exc:
        return ("error", str(exc))


def binds(message: Message) -> bool:
    """Whether the tests decode ``message`` with the market: not when it names another."""
    return int(message.symbol_id) != OTHER_SYMBOL_ID  # type: ignore[attr-defined]


ORDER_COUNT = 1500
TRIGGER_COUNT = 1500


def matrix() -> list[Message]:
    """The generated messages: orders, then triggers; a few carry negative values."""
    orders = [generate(orders_read_pb2.Order, seed) for seed in range(ORDER_COUNT)]
    triggers = [generate(triggers_pb2.Trigger, 100_000 + seed) for seed in range(TRIGGER_COUNT)]
    return [*orders, *triggers]
