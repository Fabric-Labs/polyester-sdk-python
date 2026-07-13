from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import base58

from polyester.errors import PolyesterValidationError

UINT64_MAX = 2**64 - 1
INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)
PRICE_TICK_SCALE = 6

# Strict non-negative decimal: digits with optional fractional part (TS-aligned).
_STRICT_DECIMAL = re.compile(r"^\d+(?:\.\d+)?$")


def _decimal_string_from_input(raw: str | Decimal, field_name: str) -> str:
    if isinstance(raw, (bool, float)):
        raise PolyesterValidationError(f"{field_name} must be a decimal string or Decimal")
    if isinstance(raw, Decimal):
        if not raw.is_finite():
            raise PolyesterValidationError(f"{field_name} must be a finite decimal")
        if raw < 0:
            raise PolyesterValidationError(f"{field_name} must be non-negative")
        text = format(raw, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"
    if not isinstance(raw, str):
        raise PolyesterValidationError(f"{field_name} must be a decimal string or Decimal")
    text = raw.strip()
    if not text or not _STRICT_DECIMAL.match(text):
        raise PolyesterValidationError(f"{field_name} must be a valid decimal string")
    return text


def try_decimal_to_scaled(decimal: str, scale: int) -> tuple[bool, int | None, str | None]:
    """Strict decimal→scaled. Returns (ok, scaled, failure_reason). Never rounds."""
    raw = decimal.strip()
    if not _STRICT_DECIMAL.match(raw):
        return False, None, "invalid"
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
    text = _decimal_string_from_input(raw, field_name)
    ok, scaled, reason = try_decimal_to_scaled(text, scale)
    if not ok or scaled is None:
        if reason == "precision":
            raise PolyesterValidationError(
                f"{field_name} supports at most {scale} decimal places: {text}"
            )
        raise PolyesterValidationError(f"{field_name} must be a valid decimal string")
    return scaled


def parse_price_ticks(raw: str | Decimal, field_name: str = "price") -> int:
    scaled = decimal_to_scaled(raw, PRICE_TICK_SCALE, field_name)
    if scaled < 0:
        raise PolyesterValidationError(f"{field_name} must be non-negative")
    if scaled > INT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds int64 range")
    return scaled


def format_price_ticks(ticks: int) -> str:
    """Convert int6 price ticks to a decimal string (inverse of parse_price_ticks)."""
    neg = ticks < 0
    digits = str(abs(int(ticks)))
    padded = digits.zfill(PRICE_TICK_SCALE + 1)
    head = padded[:-PRICE_TICK_SCALE]
    tail = padded[-PRICE_TICK_SCALE:]
    raw = f"{head}.{tail}"
    trimmed = raw.rstrip("0").rstrip(".") or "0"
    return f"-{trimmed}" if neg else trimmed


def format_qty_scaled(qty_scaled: int, scale: int) -> str:
    """Convert scaled integer quantity to a decimal string."""
    if scale <= 0:
        return str(int(qty_scaled))
    neg = qty_scaled < 0
    digits = str(abs(int(qty_scaled)))
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


def parse_required_uint64_decimal(raw: str, field_name: str) -> int:
    if not raw or not raw.isdecimal():
        raise PolyesterValidationError(f"{field_name} must be a uint64 decimal string")
    value = int(raw)
    if value > UINT64_MAX:
        raise PolyesterValidationError(f"{field_name} exceeds uint64 range")
    return value


def id_to_int(value: str | int, label: str = "id") -> int:
    if isinstance(value, bool):
        raise PolyesterValidationError(f"{label} must be base58 or decimal uint64")
    if isinstance(value, int):
        parsed = value
    elif value.isdecimal():
        parsed = int(value)
    else:
        try:
            parsed = int.from_bytes(base58.b58decode(value), "big")
        except ValueError as exc:
            raise PolyesterValidationError(f"{label} must be base58 or decimal uint64") from exc
    if parsed < 0 or parsed > UINT64_MAX:
        raise PolyesterValidationError(f"{label} exceeds uint64 range")
    return parsed


def format_id(value: str | int) -> str:
    parsed = id_to_int(value)
    if parsed == 0:
        return "1"
    return base58.b58encode_int(parsed).decode("ascii")


def datetime_to_timestamp_dict(value: datetime) -> dict[str, int]:
    if value.tzinfo is None:
        raise PolyesterValidationError("datetime values must be timezone-aware")
    utc = value.astimezone(UTC)
    seconds = int(utc.timestamp())
    nanos = utc.microsecond * 1000
    return {"seconds": seconds, "nanos": nanos}


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
    return datetime.fromtimestamp(int(seconds) + int(nanos) / 1_000_000_000, tz=UTC)


def omit_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}
