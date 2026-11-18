"""Limits read from the public contract's validation rules.

Each helper reads a ``buf.validate`` rule from the generated descriptor of a
request field, so a limit the contract changes changes here with the next
regeneration, never by editing a literal.
"""

from __future__ import annotations

from typing import Any

from polyester.gen.buf.validate import validate_pb2


def _rules(message: Any, name: str) -> Any:
    field = message.DESCRIPTOR.fields_by_name[name]
    return field.GetOptions().Extensions[validate_pb2.field]


def contract_uint32_max(message: Any, name: str) -> int:
    """The ``lte`` (or ``lt`` - 1) the contract sets on a ``uint32`` field."""
    rules = _rules(message, name).uint32
    if rules.HasField("lte"):
        return int(rules.lte)
    if rules.HasField("lt"):
        return int(rules.lt) - 1
    raise LookupError(f"{message.DESCRIPTOR.full_name}.{name} has no upper bound")


def contract_uint32_range(message: Any, name: str) -> tuple[int, int]:
    """The inclusive range the contract sets on a ``uint32`` field.

    ``gte`` (or ``gt`` + 1) is the lower bound and ``lte`` (or ``lt`` - 1) the
    upper; a bound the contract leaves out is the wire type's own, 0 or
    2**32 - 1.
    """
    return _uint32_bounds(_rules(message, name).uint32)


def contract_uint32_items_range(message: Any, name: str) -> tuple[int, int]:
    """The inclusive range the contract sets on each item of a repeated
    ``uint32`` field, read as :func:`contract_uint32_range` reads a field's."""
    return _uint32_bounds(_rules(message, name).repeated.items.uint32)


def _uint32_bounds(rules: Any) -> tuple[int, int]:
    low = 0
    if rules.HasField("gte"):
        low = int(rules.gte)
    elif rules.HasField("gt"):
        low = int(rules.gt) + 1
    high = 2**32 - 1
    if rules.HasField("lte"):
        high = int(rules.lte)
    elif rules.HasField("lt"):
        high = int(rules.lt) - 1
    return low, high


def contract_string_length(message: Any, name: str) -> tuple[int, int]:
    """The ``min_len`` and ``max_len`` the contract sets on a string field."""
    rules = _rules(message, name).string
    if not rules.HasField("max_len"):
        raise LookupError(f"{message.DESCRIPTOR.full_name}.{name} has no max_len")
    return int(rules.min_len), int(rules.max_len)


def contract_string_max_bytes(message: Any, name: str) -> int:
    """The ``max_bytes`` the contract sets on a string field."""
    rules = _rules(message, name).string
    if not rules.HasField("max_bytes"):
        raise LookupError(f"{message.DESCRIPTOR.full_name}.{name} has no max_bytes")
    return int(rules.max_bytes)


def contract_string_pattern(message: Any, name: str) -> str:
    """The regular expression the contract sets on a string field."""
    rules = _rules(message, name).string
    if not rules.HasField("pattern"):
        raise LookupError(f"{message.DESCRIPTOR.full_name}.{name} has no pattern")
    return str(rules.pattern)


def contract_repeated_items(message: Any, name: str) -> tuple[int, int]:
    """The ``min_items`` and ``max_items`` the contract sets on a repeated field."""
    rules = _rules(message, name).repeated
    if not rules.HasField("max_items"):
        raise LookupError(f"{message.DESCRIPTOR.full_name}.{name} has no max_items")
    return int(rules.min_items), int(rules.max_items)
