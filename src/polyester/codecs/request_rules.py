"""Check outgoing requests against the contract's integer field ranges.

The public contract states each integer field's range with ``buf.validate``
rules (for example a page ``limit`` of at most 1000, or a positive
``symbol_id``). The API enforces them; checking them before sending turns an
out-of-range value into a :class:`PolyesterValidationError` that names the
field, and keeps the ranges derived from the contract instead of copied into
the SDK.

Only values the SDK sets are checked: integer scalars (including repeated
ones and their item count), in set nested messages. Other rule kinds (strings,
message-level expressions) stay with the server. Each message type's rules
are compiled once into a plan.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message

from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2

_INTEGER_RULES = {
    FieldDescriptor.TYPE_INT32: "int32",
    FieldDescriptor.TYPE_INT64: "int64",
    FieldDescriptor.TYPE_UINT32: "uint32",
    FieldDescriptor.TYPE_UINT64: "uint64",
    FieldDescriptor.TYPE_SINT32: "sint32",
    FieldDescriptor.TYPE_SINT64: "sint64",
    FieldDescriptor.TYPE_FIXED32: "fixed32",
    FieldDescriptor.TYPE_FIXED64: "fixed64",
    FieldDescriptor.TYPE_SFIXED32: "sfixed32",
    FieldDescriptor.TYPE_SFIXED64: "sfixed64",
}
_SYMBOLS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


@dataclass(frozen=True)
class _IntRule:
    const: int | None
    lower_kind: str | None
    lower: int | None
    upper_kind: str | None
    upper: int | None
    allowed: frozenset[int]
    refused: frozenset[int]

    def check(self, path: str, value: int) -> None:
        if self.const is not None and value != self.const:
            raise PolyesterValidationError(f"{path} must be {self.const}")
        above = self.lower is None or (
            value > self.lower if self.lower_kind == "gt" else value >= self.lower
        )
        below = self.upper is None or (
            value < self.upper if self.upper_kind == "lt" else value <= self.upper
        )
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            # An exclusive range: the value must lie outside upper..lower.
            if not (above or below):
                raise PolyesterValidationError(f"{path} {self._describe(' or ')}")
        elif not (above and below):
            raise PolyesterValidationError(f"{path} {self._describe(' and ')}")
        if self.allowed and value not in self.allowed:
            raise PolyesterValidationError(f"{path} must be one of {sorted(self.allowed)}")
        if value in self.refused:
            raise PolyesterValidationError(f"{path} must not be one of {sorted(self.refused)}")

    def _describe(self, joiner: str) -> str:
        parts = []
        if self.lower_kind is not None:
            parts.append(f"{_SYMBOLS[self.lower_kind]} {self.lower}")
        if self.upper_kind is not None:
            parts.append(f"{_SYMBOLS[self.upper_kind]} {self.upper}")
        return f"must be {joiner.join(parts)}"


@dataclass(frozen=True)
class _FieldPlan:
    name: str
    repeated: bool
    message: tuple[_FieldPlan, ...] | None = None
    rule: _IntRule | None = None
    skip_zero: bool = False
    max_items: int | None = None
    min_items: int | None = None
    unique: bool = False


_PLANS: dict[str, tuple[_FieldPlan, ...]] = {}


def check_request_ranges(request: Message) -> None:
    """Raise PolyesterValidationError when a set integer breaks its contract range."""
    _check(request, _plan(request.DESCRIPTOR), "")


def _check(message: Message, plan: tuple[_FieldPlan, ...], prefix: str) -> None:
    for field in plan:
        path = f"{prefix}{field.name}"
        if field.repeated:
            values = getattr(message, field.name)
            if not values:
                continue
            if field.message is not None:
                for index, item in enumerate(values):
                    _check(item, field.message, f"{path}[{index}].")
                continue
            if field.max_items is not None and len(values) > field.max_items:
                raise PolyesterValidationError(
                    f"{path} accepts at most {field.max_items} values, got {len(values)}"
                )
            if field.min_items is not None and len(values) < field.min_items:
                raise PolyesterValidationError(
                    f"{path} needs at least {field.min_items} values"
                )
            if field.unique and len(set(values)) != len(values):
                raise PolyesterValidationError(f"{path} values must be unique")
            if field.rule is not None:
                for index, value in enumerate(values):
                    field.rule.check(f"{path}[{index}]", value)
            continue
        if field.message is not None:
            if message.HasField(field.name):
                _check(getattr(message, field.name), field.message, f"{path}.")
            continue
        value = getattr(message, field.name)
        # A scalar the SDK left at its default is not sent; only set values are checked.
        if value == 0 and not _presence_set(message, field.name):
            continue
        if field.skip_zero and value == 0:
            continue
        if field.rule is not None:
            field.rule.check(path, value)


def _presence_set(message: Message, name: str) -> bool:
    try:
        return message.HasField(name)
    except ValueError:
        # A field without presence: its zero value is the default and is not sent.
        return False


def _plan(descriptor: Descriptor) -> tuple[_FieldPlan, ...]:
    key = descriptor.full_name
    if key not in _PLANS:
        # A recursive message type sees an empty plan while its own is built.
        _PLANS[key] = ()
        _PLANS[key] = tuple(
            plan for field in descriptor.fields if (plan := _field_plan(field)) is not None
        )
    return _PLANS[key]


def _field_plan(field: FieldDescriptor) -> _FieldPlan | None:
    if field.type == FieldDescriptor.TYPE_MESSAGE:
        if field.message_type.GetOptions().map_entry:
            return None
        nested = _plan(field.message_type)
        if not nested:
            return None
        return _FieldPlan(name=field.name, repeated=field.is_repeated, message=nested)
    kind = _INTEGER_RULES.get(field.type)
    if kind is None:
        return None
    options = field.GetOptions()
    if not options.HasExtension(validate_pb2.field):
        return None
    rules = options.Extensions[validate_pb2.field]
    if rules.ignore == validate_pb2.IGNORE_ALWAYS:
        return None
    if field.is_repeated:
        if rules.WhichOneof("type") != "repeated":
            return None
        repeated = rules.repeated
        repeated_plan = _FieldPlan(
            name=field.name,
            repeated=True,
            rule=_int_rule(repeated.items, kind) if repeated.HasField("items") else None,
            max_items=repeated.max_items if repeated.HasField("max_items") else None,
            min_items=repeated.min_items if repeated.HasField("min_items") else None,
            unique=repeated.unique,
        )
        has_checks = (
            repeated_plan.rule is not None
            or repeated_plan.max_items is not None
            or repeated_plan.min_items is not None
            or repeated_plan.unique
        )
        return repeated_plan if has_checks else None
    rule = _int_rule(rules, kind)
    if rule is None:
        return None
    return _FieldPlan(
        name=field.name,
        repeated=False,
        rule=rule,
        skip_zero=rules.ignore == validate_pb2.IGNORE_IF_ZERO_VALUE,
    )


def _int_rule(rules: validate_pb2.FieldRules, kind: str) -> _IntRule | None:
    if rules.WhichOneof("type") != kind:
        return None
    numeric = getattr(rules, kind)
    lower_kind = numeric.WhichOneof("greater_than")
    upper_kind = numeric.WhichOneof("less_than")
    rule = _IntRule(
        const=int(numeric.const) if numeric.HasField("const") else None,
        lower_kind=lower_kind,
        lower=int(getattr(numeric, lower_kind)) if lower_kind else None,
        upper_kind=upper_kind,
        upper=int(getattr(numeric, upper_kind)) if upper_kind else None,
        allowed=frozenset(int(value) for value in getattr(numeric, "in")),
        refused=frozenset(int(value) for value in numeric.not_in),
    )
    has_checks = (
        rule.const is not None
        or lower_kind is not None
        or upper_kind is not None
        or rule.allowed
        or rule.refused
    )
    return rule if has_checks else None
