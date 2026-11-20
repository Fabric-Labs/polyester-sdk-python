from __future__ import annotations

import numbers
import operator
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import base58

from polyester.errors import PolyesterValidationError

UINT64_MAX = 2**64 - 1
UINT32_MAX = 2**32 - 1
INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)
PRICE_TICK_SCALE = 9
# Maximum accepted quantity/ledger scale for public formatters and catalog hydration.
# Values above this are rejected instead of allocating pathological padding (scale ≥ 65535).
MAX_PROTOCOL_SCALE = 36

# Strict non-negative decimal: ASCII digits with optional fractional part
# (TS-aligned). Not \d, which also matches other scripts' digits ("٥").
_STRICT_DECIMAL = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")


class FractionalDigitsError(PolyesterValidationError):
    """A decimal with a nonzero digit beyond its scale (zeros beyond it parse).

    Order encoders re-raise it for a quantity or tick-checked price with the
    step or tick code the server answers for the same value.
    """


_ITEM_SCOPE_KEYS = ("sub_account_id", "subaccount_id", "subaccountId", "account")


def market_id(value: object, label: str) -> int:
    """Return a market (``symbol_id``) as the integer the wire carries.

    Only an integer from 0 to 2**32 - 1 is a market ID. A bool, float,
    Decimal, str or bytes is refused instead of cast, so ``8.9`` or ``True``
    cannot select market 8 or 1.
    """
    if isinstance(value, bool):
        raise PolyesterValidationError(f"{label} must be an integer market ID, not bool")
    # numbers.Integral, not __index__: a float subclass may implement
    # __index__ and would select market 8 for 8.9.
    if not isinstance(value, numbers.Integral):
        raise PolyesterValidationError(
            f"{label} must be an integer market ID, not {type(value).__name__}"
        )
    # operator.index, not int(): an int subclass may override __int__.
    parsed = operator.index(value)
    if parsed < 0 or parsed > UINT32_MAX:
        raise PolyesterValidationError(f"{label} {parsed} is outside 0..{UINT32_MAX}")
    return parsed


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
    if isinstance(scale, bool) or not isinstance(scale, int):
        raise PolyesterValidationError(f"{field_name} must be an int")
    scale = operator.index(scale)
    if scale < 0:
        raise PolyesterValidationError(f"{field_name} must be non-negative")
    if scale > MAX_PROTOCOL_SCALE:
        raise PolyesterValidationError(
            f"{field_name} {scale} exceeds maximum protocol scale {MAX_PROTOCOL_SCALE}"
        )
    return scale


# Most digits a scaled value can have and still fit the widest wire field,
# 2**128 - 1, once rescaled down from MAX_PROTOCOL_SCALE.
_MAX_SCALED_DIGITS = len(str(2**128 - 1)) + MAX_PROTOCOL_SCALE
# Longest rejected value an error message repeats.
_MAX_ERROR_VALUE_CHARS = 64


def _error_value(text: str) -> str:
    if len(text) <= _MAX_ERROR_VALUE_CHARS:
        return text
    return f"{text[:_MAX_ERROR_VALUE_CHARS]}... ({len(text)} characters)"


def _check_decimal_size(raw: Decimal, scale: int, field_name: str) -> None:
    """Refuse a Decimal too precise or too large for ``scale`` before expanding it.

    ``format(raw, "f")`` writes every digit an exponent implies, so a short
    ``Decimal("1E-1000000")`` would otherwise allocate a million characters.
    """
    _, digits, exponent = raw.as_tuple()
    assert isinstance(exponent, int)  # finite
    significant = len(digits)
    while significant > 1 and digits[significant - 1] == 0 and exponent < 0:
        significant -= 1
        exponent += 1
    # Repeat the value as plain digits when that is short, else as written.
    shown = str(raw)
    if significant + abs(exponent) <= _MAX_ERROR_VALUE_CHARS:
        shown = _trim_trailing_frac_zeros(format(raw, "f"))
    if -exponent > scale:
        raise FractionalDigitsError(
            f"{field_name} supports at most {scale} decimal places: {_error_value(shown)}"
        )
    if significant + exponent + scale > _MAX_SCALED_DIGITS:
        raise PolyesterValidationError(f"{field_name} is too large: {_error_value(shown)}")


def _decimal_string_from_input(raw: str | Decimal, field_name: str, scale: int) -> str:
    if isinstance(raw, (bool, float)):
        raise PolyesterValidationError(f"{field_name} must be a decimal string or Decimal")
    if isinstance(raw, Decimal):
        if not raw.is_finite():
            raise PolyesterValidationError(f"{field_name} must be a finite decimal")
        if raw < 0:
            raise PolyesterValidationError(f"{field_name} must be non-negative")
        if raw.is_zero():
            return "0"
        _check_decimal_size(raw, scale, field_name)
        text = format(raw, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
    if not isinstance(raw, str):
        raise PolyesterValidationError(f"{field_name} must be a decimal string or Decimal")
    # Checked before trimming: str.strip() also strips non-ASCII spaces.
    if not raw.isascii():
        raise PolyesterValidationError(f"{field_name} must be a valid decimal string")
    text = raw.strip()
    if not text or not _STRICT_DECIMAL.match(text):
        raise PolyesterValidationError(f"{field_name} must be a valid decimal string")
    return text


def _trim_trailing_frac_zeros(raw: str) -> str:
    """Drop insignificant trailing zeros so formatters like toFixed() survive scale checks."""
    if "." not in raw:
        return raw
    int_part, frac_part = raw.split(".", 1)
    frac_part = frac_part.rstrip("0")
    if not frac_part:
        return int_part or "0"
    return f"{int_part}.{frac_part}"


def try_decimal_to_scaled(decimal: str, scale: int) -> tuple[bool, int | None, str | None]:
    """Strict decimal→scaled. Returns (ok, scaled, failure_reason). Never rounds."""
    if scale < 0 or scale > MAX_PROTOCOL_SCALE:
        return False, None, "scale"
    if not decimal.isascii():
        return False, None, "invalid"
    raw = decimal.strip()
    if not _STRICT_DECIMAL.match(raw):
        return False, None, "invalid"
    raw = _trim_trailing_frac_zeros(raw)
    int_part, _, frac_part = raw.partition(".")
    if len(frac_part) > scale:
        return False, None, "precision"
    digits = int_part + frac_part + ("0" * (scale - len(frac_part)))
    if not digits:
        digits = "0"
    try:
        scaled = int(digits)
    except ValueError:
        return False, None, "invalid"
    return True, scaled, None


def decimal_to_scaled(raw: str | Decimal, scale: int, field_name: str) -> int:
    validate_protocol_scale(scale, field_name=f"{field_name} scale")
    text = _decimal_string_from_input(raw, field_name, scale)
    ok, scaled, reason = try_decimal_to_scaled(text, scale)
    if not ok or scaled is None:
        if reason == "precision":
            raise FractionalDigitsError(
                f"{field_name} supports at most {scale} decimal places: {_error_value(text)}"
            )
        if reason == "scale":
            raise PolyesterValidationError(
                f"{field_name} scale {scale} exceeds maximum protocol scale {MAX_PROTOCOL_SCALE}"
            )
        raise PolyesterValidationError(f"{field_name} must be a valid decimal string")
    return scaled


_DECIMAL_INTEGER = re.compile(r"[0-9]+")


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
    expected = "an integer or a decimal-integer string" if allow_str else "an integer"
    if isinstance(value, bool):
        raise PolyesterValidationError(f"{field_name} must be {expected}, not bool")
    if isinstance(value, str):
        if not allow_str or _DECIMAL_INTEGER.fullmatch(value) is None:
            raise PolyesterValidationError(
                f"{field_name} must be {expected}, not {_error_value(repr(value))}"
            )
        digits = value.lstrip("0") or "0"
        if len(digits) > len(str(max_value)):
            raise PolyesterValidationError(
                f"{field_name} {_error_value(digits)} is outside {min_value}..{max_value}"
            )
        parsed = int(digits)
    elif isinstance(value, numbers.Integral):
        # operator.index, not int(): an int subclass may override __int__
        # (an override returning 1 would sign nonce 42 as nonce 1).
        parsed = operator.index(value)
    else:
        raise PolyesterValidationError(
            f"{field_name} must be {expected}, not {type(value).__name__}"
        )
    if parsed < min_value or parsed > max_value:
        # str() of a huge int is slow or refused, so a huge value is not repeated.
        shown = f" {_error_value(str(parsed))}" if parsed.bit_length() <= 512 else ""
        raise PolyesterValidationError(f"{field_name}{shown} is outside {min_value}..{max_value}")
    return parsed


def tick_count(value: object, field_name: str, *, allow_zero: bool = False) -> int:
    """Validate a caller-supplied integer tick count for an int64 wire field.

    Accepts an ``int`` or a base-10 integer string; rejects booleans, values
    below 1 (below 0 with ``allow_zero``, where zero clears a cap) and values
    above ``INT64_MAX``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise PolyesterValidationError(f"{field_name} must be an integer")
    try:
        parsed = operator.index(value) if isinstance(value, int) else ascii_int(value)
    except ValueError as exc:
        raise PolyesterValidationError(f"{field_name} must be an integer") from exc
    if parsed < 0 or (parsed == 0 and not allow_zero):
        qualifier = "non-negative" if allow_zero else "positive"
        raise PolyesterValidationError(f"{field_name} must be {qualifier}")
    if parsed > INT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds int64 range")
    return parsed


def parse_price_ticks(raw: str | Decimal, field_name: str = "price") -> int:
    scaled = decimal_to_scaled(raw, PRICE_TICK_SCALE, field_name)
    if scaled < 0:
        raise PolyesterValidationError(f"{field_name} must be non-negative")
    if scaled > INT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds int64 range")
    return scaled


def format_price_ticks(ticks: int) -> str:
    """Convert Q9 price ticks to a decimal string (inverse of parse_price_ticks)."""
    neg = ticks < 0
    digits = str(abs(int(ticks)))
    padded = digits.zfill(PRICE_TICK_SCALE + 1)
    head = padded[:-PRICE_TICK_SCALE]
    tail = padded[-PRICE_TICK_SCALE:]
    raw = f"{head}.{tail}"
    trimmed = raw.rstrip("0").rstrip(".") or "0"
    return f"-{trimmed}" if neg else trimmed


def format_qty_scaled(qty_scaled: int, scale: int) -> str:
    """Convert scaled integer quantity to a decimal string.

    Raises PolyesterValidationError when ``scale`` exceeds ``MAX_PROTOCOL_SCALE``.
    """
    validate_protocol_scale(scale)
    return format_scaled(qty_scaled, scale)


def format_scaled(value: int, scale: int) -> str:
    """Convert ``value / 10**scale`` to a decimal string, for a non-negative scale.

    Unlike :func:`format_qty_scaled` it does not cap ``scale``: use it for a
    scale derived from validated ones, such as a notional at base scale + 9.
    A negative scale raises :class:`PolyesterValidationError`.
    """
    if scale < 0:
        raise PolyesterValidationError("scale must be non-negative")
    if scale == 0:
        return str(int(value))
    neg = value < 0
    digits = str(abs(int(value)))
    padded = digits.zfill(scale + 1)
    head = padded[:-scale]
    tail = padded[-scale:]
    raw = f"{head}.{tail}"
    trimmed = raw.rstrip("0").rstrip(".") or "0"
    return f"-{trimmed}" if neg else trimmed


def align_price_ticks(price_ticks: int, tick_size: str) -> int:
    step = parse_price_ticks(tick_size, "tick_size")
    if step <= 0:
        return max(price_ticks, 1)
    aligned = (price_ticks // step) * step
    return max(aligned, step)


def parse_qty_scaled(raw: str | Decimal, scale: int, field_name: str = "qty") -> int:
    scaled = decimal_to_scaled(raw, scale, field_name)
    if scaled <= 0:
        raise PolyesterValidationError(f"{field_name} must be positive")
    # amount_e18 / ledger scale 18 may exceed int64 (U128 on the wire).
    if scale != 18 and scaled > INT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds int64 range")
    return scaled


def ascii_int(value: str) -> int:
    """``int(value)`` for a string of ASCII characters only.

    ``int()`` also reads other scripts' digits (``"٥"`` is 5), so a string
    with any non-ASCII character raises ``ValueError`` instead.
    """
    if not value.isascii():
        raise ValueError("not an ASCII integer")
    return int(value)


def parse_required_uint64_decimal(raw: str, field_name: str) -> int:
    if not raw or not raw.isascii() or not raw.isdecimal():
        raise PolyesterValidationError(f"{field_name} must be a uint64 decimal string")
    value = int(raw)
    if value > UINT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds uint64 range")
    return value


def _encode_id(parsed: int) -> str:
    """Encode a uint64 id as canonical SDK base58 (0 maps to '1')."""
    if parsed == 0:
        return "1"
    return base58.b58encode_int(parsed).decode("ascii")


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
    parsed = _parse_id(value, label)
    if parsed == 0:
        raise PolyesterValidationError(f"{label} must be a non-zero ID, not 0")
    return parsed


def _parse_id(value: str | int, label: str) -> int:
    if isinstance(value, bool):
        raise PolyesterValidationError(f"{label} must be a base58 string or an integer ID")
    if isinstance(value, int):
        parsed = operator.index(value)
        if parsed < 0 or parsed > UINT64_MAX:
            raise PolyesterValidationError(f"{label} exceeds uint64 range")
        return parsed
    if not isinstance(value, str):
        raise PolyesterValidationError(f"{label} must be a base58 string or an integer ID")
    if not value:
        raise PolyesterValidationError(f"{label} must be a base58 public ID, not empty")
    parsed = 0
    for char in value:
        digit = _BASE58_DIGITS.get(char)
        if digit is None:
            raise PolyesterValidationError(
                f"{label} must be a base58 public ID: {_error_value(repr(value))} has "
                f"{char!r}, which is not base58; pass an integer ID as an int"
            )
        parsed = parsed * 58 + digit
        if parsed > UINT64_MAX:
            raise PolyesterValidationError(f"{label} exceeds uint64 range")
    if _encode_id(parsed) != value:
        if parsed == 0:
            raise PolyesterValidationError(f"{label} must be a non-zero ID, not 0")
        raise PolyesterValidationError(
            f"{label} must be a public ID in canonical form, as the SDK writes it "
            "(no leading 1); use the ID as the SDK or the app shows it, or pass the integer"
        )
    return parsed


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


def datetime_to_timestamp_dict(value: datetime) -> dict[str, int]:
    """Exact protobuf ``Timestamp`` fields for an aware datetime.

    Integer arithmetic, as protobuf's ``FromDatetime``: ``seconds`` rounds
    toward negative infinity and ``nanos`` is never negative, for every
    datetime from year 1 to 9999.
    """
    if value.tzinfo is None:
        raise PolyesterValidationError("datetime values must be timezone-aware")
    since_epoch = value.astimezone(UTC).replace(tzinfo=None) - _UNIX_EPOCH
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
