from __future__ import annotations

from typing import Any

from polyester.errors import PolyesterResponseContractError


def ts_ns_from_response(
    value: Any,
    *,
    context: str,
    field_name: str = "ts_ns",
) -> int:
    """Decode an epoch timestamp field as a non-negative integer.

    Does not guess units (ns vs ms); callers treat the value as epoch nanoseconds
    per the API contract, and the backend owns unit correctness.
    """
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


def paired_ts_ns(msg: Any, ts_ns_field: str, ts_field: str) -> int | None:
    """A response time in nanoseconds since the Unix epoch: the exact
    ``*_ts_ns`` field, or its paired ``Timestamp`` when the nanosecond field is
    unset; ``None`` when the server sent neither (or a time before the epoch).
    """
    exact = int(getattr(msg, ts_ns_field))
    if exact:
        return exact
    if not msg.HasField(ts_field):
        return None
    ts = getattr(msg, ts_field)
    nanos = int(ts.seconds) * 1_000_000_000 + int(ts.nanos)
    return nanos if nanos > 0 else None


def qty_scaled_from_response(value: Any, *, field: str) -> int:
    """A quantity's scaled wire value, such as ``Order.orig_qty_scaled``.

    0 is a zero quantity: a plain proto3 quantity the wire omits is 0 too. A
    negative value, which no quantity can be, breaks the response contract:
    it raises :class:`PolyesterResponseContractError` whose ``context`` is
    ``field``, never the :class:`~polyester.errors.PolyesterValidationError`
    of a caller's own bad input.
    """
    scaled = int(value)
    if scaled < 0:
        raise PolyesterResponseContractError(field, f"negative quantity {scaled}")
    return scaled
