from __future__ import annotations

from polyester.errors import PolyesterValidationError

MAX_BPS = 10_000


def validate_bps(
    value: object,
    field_name: str,
    *,
    allow_clear: bool = False,
) -> int:
    """Validate a basis-point field before assigning it to protobuf."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise PolyesterValidationError(f"{field_name} must be an integer")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise PolyesterValidationError(f"{field_name} must be an integer") from exc
    if allow_clear and parsed == 0:
        return parsed
    if parsed < 1 or parsed > MAX_BPS:
        raise PolyesterValidationError(f"{field_name} must be between 1 and {MAX_BPS}")
    return parsed
