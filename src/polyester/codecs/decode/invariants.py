from __future__ import annotations

from typing import Any

from polyester.errors import PolyesterResponseContractError

_MIN_MILLISECOND_SHAPED_EPOCH = 1_000_000_000_000
_MAX_MILLISECOND_SHAPED_EPOCH = 999_999_999_999_999


def ts_ns_from_response(
    value: Any,
    *,
    context: str,
    field_name: str = "ts_ns",
) -> int:
    """Decode an epoch-nanosecond field and reject millisecond-shaped responses."""
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise PolyesterResponseContractError(
            context, f"{field_name} must be an unsigned epoch-nanosecond integer"
        ) from exc
    if parsed < 0:
        raise PolyesterResponseContractError(
            context, f"{field_name} must be an unsigned epoch-nanosecond integer"
        )
    if _MIN_MILLISECOND_SHAPED_EPOCH <= parsed <= _MAX_MILLISECOND_SHAPED_EPOCH:
        raise PolyesterResponseContractError(
            context,
            f"{field_name} is millisecond-shaped; expected epoch nanoseconds",
        )
    return parsed


def ts_ns_string_from_response(
    value: Any,
    *,
    context: str,
    field_name: str = "ts_ns",
    empty_when_zero: bool = False,
) -> str:
    parsed = ts_ns_from_response(value, context=context, field_name=field_name)
    if parsed == 0 and empty_when_zero:
        return ""
    return str(parsed)
