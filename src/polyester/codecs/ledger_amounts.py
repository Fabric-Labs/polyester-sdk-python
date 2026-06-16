from __future__ import annotations

from decimal import Decimal

# Matches @repo/polyester-client ledger-catalog (u128 balances use 18-decimal scale).
LEDGER_SCALE = 18


def format_ledger_u128(raw: str | int, *, scale: int = LEDGER_SCALE) -> str:
    """Format a ledger u128 wire string (hi/lo encoded as decimal string) to a decimal."""
    value = Decimal(str(raw or "0")) / Decimal(10**scale)
    if value == 0:
        return "0"
    normalized = format(value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized
