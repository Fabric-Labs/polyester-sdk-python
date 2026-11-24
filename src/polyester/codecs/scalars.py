from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from polyester.codecs.pure_bridge import FractionalDigitsError as FractionalDigitsError
from polyester.codecs.pure_bridge import call, exact_index, pure
from polyester.errors import PolyesterValidationError

UINT64_MAX = 2**64 - 1
UINT32_MAX = 2**32 - 1
INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)
PRICE_TICK_SCALE = 9
# Maximum accepted quantity/ledger scale for public formatters and catalog hydration.
# Values above this are rejected instead of allocating pathological padding (scale ≥ 65535).
MAX_PROTOCOL_SCALE = 36


_ITEM_SCOPE_KEYS = ("sub_account_id", "subaccount_id", "subaccountId", "account")


def market_id(value: object, label: str) -> int:
    """Return a market (``symbol_id``) as the integer the wire carries.

    Only an integer from 0 to 2**32 - 1 is a market ID. A bool, float,
    Decimal, str or bytes is refused instead of cast, so ``8.9`` or ``True``
    cannot select market 8 or 1.
    """
    return call(pure._market_id, _exact_index(value), label)


_exact_index = exact_index


def market_ids(values: object, label: str) -> list[int]:
    """Return a list of markets, each checked by :func:`market_id`.

    A str or bytes is refused rather than iterated, so ``"12"`` cannot select
    markets 1 and 2; a mapping is refused rather than read for its keys.
    """
    if isinstance(values, str | bytes | bytearray | Mapping) or not isinstance(values, Iterable):
        raise PolyesterValidationError(
            f"{label} must be a list of integer market IDs, not {type(values).__name__}"
        )
    return [market_id(value, label) for value in values]


def refuse_item_scope(item: Any, label: str) -> None:
    """Refuse a batch item that names its own account: the wire scope is batch-level."""
    if any(item.get(key) is not None for key in _ITEM_SCOPE_KEYS):
        raise PolyesterValidationError(
            f"{label} item scope is unsupported; use the batch-level sub_account_id"
        )


def validate_protocol_scale(scale: int, *, field_name: str = "scale") -> int:
    """Reject scales that would panic or allocate pathological padding."""
    return call(pure._scale, scale, field_name)


def _error_value(text: str) -> str:
    return str(pure._shown(text))


def _check_decimal_size(raw: Decimal, scale: int, field_name: str) -> None:
    """Refuse a Decimal too precise or too large for ``scale`` before expanding it."""
    call(pure._check_decimal_size, raw, scale, field_name)


def _decimal_string_from_input(raw: str | Decimal, field_name: str, scale: int) -> str:
    return call(pure._decimal_text, raw, field_name, scale)


def _trim_trailing_frac_zeros(raw: str) -> str:
    """Drop insignificant trailing zeros so formatters like toFixed() survive scale checks."""
    return str(pure._trim_zeros(raw))


def try_decimal_to_scaled(decimal: str, scale: int) -> tuple[bool, int | None, str | None]:
    """Strict decimal→scaled. Returns (ok, scaled, failure_reason). Never rounds."""
    ok, scaled, reason = pure._try_scaled(decimal, scale)
    return ok, scaled, reason


def decimal_to_scaled(raw: str | Decimal, scale: int, field_name: str) -> int:
    return call(pure._to_scaled, raw, scale, field_name)


def exact_integer(
    value: object,
    field_name: str,
    *,
    min_value: int,
    max_value: int,
    allow_str: bool = False,
) -> int:
    """Return ``value`` as the exact integer it is, or refuse it.

    Accepts a :class:`numbers.Integral` other than ``bool`` (``int`` and its
    subclasses, and NumPy integers) and, with ``allow_str``, a string of ASCII
    decimal digits. Everything else is refused with
    :class:`PolyesterValidationError`, never converted: a ``bool``, a ``float``
    (even ``2.0``, and a float subclass with ``__index__``), a ``Decimal``, an
    object that only implements ``__index__``, and any other string
    (``"42.0"``, ``"0x10"``, ``" 42"``, ``"-1"``). So a signed or sent value is
    always the one the caller gave. Values outside ``min_value..max_value``
    are refused.
    """
    return call(
        pure._exact_integer, _exact_index(value), field_name, min_value, max_value, allow_str
    )


def tick_count(value: object, field_name: str, *, allow_zero: bool = False) -> int:
    """Validate a caller-supplied integer tick count for an int64 wire field.

    Accepts an ``int`` or a base-10 integer string; rejects booleans, values
    below 1 (below 0 with ``allow_zero``, where zero clears a cap) and values
    above ``INT64_MAX``.
    """
    return call(pure._tick_count, value, field_name, allow_zero)


def parse_price_ticks(raw: str | Decimal, field_name: str = "price") -> int:
    return call(pure._parse_price_ticks, raw, field_name)


def format_price_ticks(ticks: int) -> str:
    """Convert Q9 price ticks to a decimal string (inverse of parse_price_ticks)."""
    return call(pure._format_scaled, ticks, PRICE_TICK_SCALE)


def format_qty_scaled(qty_scaled: int, scale: int) -> str:
    """Convert scaled integer quantity to a decimal string.

    Raises PolyesterValidationError when ``scale`` exceeds ``MAX_PROTOCOL_SCALE``.
    """
    return call(pure._format_qty_scaled, qty_scaled, scale)


def format_scaled(value: int, scale: int) -> str:
    """Convert ``value / 10**scale`` to a decimal string, for a non-negative scale.

    Unlike :func:`format_qty_scaled` it does not cap ``scale``: use it for a
    scale derived from validated ones, such as a notional at base scale + 9.
    A negative scale raises :class:`PolyesterValidationError`.
    """
    return call(pure._format_scaled, value, scale)


def align_price_ticks(price_ticks: int, tick_size: str) -> int:
    step = parse_price_ticks(tick_size, "tick_size")
    if step <= 0:
        return max(price_ticks, 1)
    aligned = (price_ticks // step) * step
    return max(aligned, step)


def parse_qty_scaled(raw: str | Decimal, scale: int, field_name: str = "qty") -> int:
    return call(pure._parse_qty_scaled, raw, scale, field_name)


def ascii_int(value: str) -> int:
    """``int(value)`` for a string of ASCII characters only.

    ``int()`` also reads other scripts' digits (``"٥"`` is 5), so a string
    with any non-ASCII character raises ``ValueError`` instead.
    """
    return int(pure._ascii_int(value))


def parse_required_uint64_decimal(raw: str, field_name: str) -> int:
    if not raw or not raw.isascii() or not raw.isdecimal():
        raise PolyesterValidationError(f"{field_name} must be a uint64 decimal string")
    value = int(raw)
    if value > UINT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds uint64 range")
    return value


def _encode_id(parsed: int) -> str:
    """Encode a uint64 id as canonical SDK base58 (0 maps to '1')."""
    return str(pure._encode_id(parsed))


_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_DIGITS = {char: digit for digit, char in enumerate(_BASE58_ALPHABET)}


def id_to_int(value: str | int, label: str = "id") -> int:
    """Decode a public ID, refusing one that decodes to 0.

    A string is base58 only, read character by character as the server reads
    it: a digit-only string is base58 too (``"23"`` is 60), and anything
    outside the base58 alphabet is refused, ``0``, whitespace and non-ASCII
    characters included; nothing is trimmed. Only the canonical spelling, as
    :func:`format_id` writes it, is accepted: a leading ``1`` is a base58
    zero, so ``"123"`` would name the same ID as ``"23"``, and is refused. An
    ``int`` names the ID it is.
    On the wire 0 is unset and names nothing, so ``"1"`` (``format_id(0)``)
    or ``0`` would send a request for an ID the caller did not mean.
    """
    return call(pure._id_to_int, value, label)


def _parse_id(value: str | int, label: str) -> int:
    return call(pure._parse_id, value, label)


def parse_account_id(value: str | int, label: str) -> int:
    """Decode an account or sub-account ID as ``id_to_int`` does, which refuses 0.

    On the wire 0 is unset: a sub-account ID of 0 is the main account, and an
    account ID of 0 names no account. So ``"1"`` (``format_id(0)``), ``"11"``
    or ``0`` would address another account than the one named. Omit a
    sub-account ID to address the main account.
    """
    return id_to_int(value, label)


def format_id(value: str | int) -> str:
    """The canonical base58 public ID of an integer ID, or of a base58 string.
    A string that is not a canonical base58 public ID is refused, as
    :func:`id_to_int` refuses it."""
    return _encode_id(_parse_id(value, "id"))


_UNIX_EPOCH = datetime(1970, 1, 1)
_UNIX_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=UTC)


def timestamp_parts_to_datetime(seconds: int, nanos: int) -> datetime:
    """Aware UTC datetime for protobuf ``Timestamp`` fields, exact to the microsecond.

    Integer arithmetic, as protobuf's ``ToDatetime``: the nanoseconds below a
    microsecond are truncated. A float of ``seconds + nanos / 1e9`` would
    round a time in the last nanoseconds of a second up to the next second.
    """
    return _UNIX_EPOCH_UTC + timedelta(seconds=int(seconds), microseconds=int(nanos) // 1000)


def unix_ms_to_datetime(value: int) -> datetime | None:
    """Aware UTC datetime for a time sent in milliseconds since the epoch.

    0 is the contract's "no time" and reads None, as does a value past what
    ``datetime`` holds (after the year 9999).
    """
    if int(value) <= 0:
        return None
    try:
        return _UNIX_EPOCH_UTC + timedelta(milliseconds=int(value))
    except OverflowError:
        return None


# The seconds a protobuf ``Timestamp`` holds: 0001-01-01T00:00:00Z to
# 9999-12-31T23:59:59Z, as a datetime does.
TIMESTAMP_MIN_SECONDS = -62_135_596_800
TIMESTAMP_MAX_SECONDS = 253_402_300_799


def aware_datetime(value: object, field_name: str) -> datetime:
    """``value`` if it is a timezone-aware :class:`~datetime.datetime` that
    names an instant from year 1 to 9999 in UTC, else refused.

    A time parameter takes nothing else: an int or float (seconds or
    milliseconds?), a string, a ``date`` and a naive datetime (local time or
    UTC?) are each refused with :class:`PolyesterValidationError` naming
    ``field_name``, the expected type and the type received, never guessed.
    An offset that moves the time before year 1 or after year 9999 in UTC is
    refused under the same name.
    """
    return call(pure._aware, value, field_name)


def datetime_to_timestamp_dict(value: datetime, field_name: str = "value") -> dict[str, int]:
    """Exact protobuf ``Timestamp`` fields for an aware datetime.

    ``value`` is checked with :func:`aware_datetime` at run time, so any other
    value, a naive datetime or a time outside years 1 to 9999 in UTC raises
    :class:`PolyesterValidationError` naming ``field_name``. Integer
    arithmetic, as protobuf's ``FromDatetime``: ``seconds`` rounds toward
    negative infinity and ``nanos`` is never negative, for every datetime
    from year 1 to 9999.
    """
    utc = aware_datetime(value, field_name).astimezone(UTC)
    since_epoch = utc.replace(tzinfo=None) - _UNIX_EPOCH
    seconds = since_epoch.days * 86_400 + since_epoch.seconds
    return {"seconds": seconds, "nanos": since_epoch.microseconds * 1000}


def timestamp_dict_to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    seconds = getattr(value, "seconds", None)
    nanos = getattr(value, "nanos", 0)
    if isinstance(value, dict):
        seconds = value.get("seconds")
        nanos = value.get("nanos", 0)
    if seconds is None:
        return None
    return timestamp_parts_to_datetime(int(seconds), int(nanos or 0))


def omit_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}
