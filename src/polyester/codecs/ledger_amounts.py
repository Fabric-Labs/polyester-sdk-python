from __future__ import annotations

from polyester.codecs.scalars import MAX_PROTOCOL_SCALE, format_qty_scaled, validate_protocol_scale
from polyester.errors import PolyesterValidationError

# Matches @repo/polyester-client ledger-catalog (u128 balances use 18-decimal scale).
LEDGER_SCALE = 18


def format_ledger_u128(raw: str | int, *, scale: int = LEDGER_SCALE) -> str:
    """Format a ledger u128 wire value (decimal string or int) to a human decimal.

    ``scale`` defaults to the 18-decimal ledger scale. Any other scale, including
    0 (whole units), is used as given. It is validated against
    ``MAX_PROTOCOL_SCALE`` before any padding or ``10**scale`` work so
    pathological catalog scales cannot DoS the process.
    """
    validate_protocol_scale(scale)
    if isinstance(raw, bool):
        raise PolyesterValidationError("ledger amount must be a decimal string or int")
    if isinstance(raw, int):
        if raw < 0:
            raise PolyesterValidationError("ledger amount must be non-negative")
        return format_qty_scaled(raw, scale)
    text = str(raw or "0").strip()
    if not text or not text.isdecimal():
        raise PolyesterValidationError("ledger amount must be a non-negative decimal string")
    return format_qty_scaled(int(text), scale)


__all__ = [
    "LEDGER_SCALE",
    "MAX_PROTOCOL_SCALE",
    "format_ledger_u128",
]
