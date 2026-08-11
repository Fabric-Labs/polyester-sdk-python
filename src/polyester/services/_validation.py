from __future__ import annotations

from typing import Literal, overload

from polyester.errors import PolyesterValidationError

MAX_LIST_LIMIT = 1_000


@overload
def validate_limit(
    limit: int,
    *,
    label: str = "limit",
    allow_none: Literal[False] = False,
) -> int: ...


@overload
def validate_limit(
    limit: int | None,
    *,
    label: str = "limit",
    allow_none: Literal[True],
) -> int | None: ...


def validate_limit(
    limit: int | None,
    *,
    label: str = "limit",
    allow_none: bool = False,
) -> int | None:
    """Validate an SDK pagination limit without materializing omitted defaults."""
    if limit is None:
        if allow_none:
            return None
        raise PolyesterValidationError(f"{label} must be an integer from 1 to {MAX_LIST_LIMIT}")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise PolyesterValidationError(f"{label} must be an integer from 1 to {MAX_LIST_LIMIT}")
    if limit < 1 or limit > MAX_LIST_LIMIT:
        raise PolyesterValidationError(f"{label} must be from 1 to {MAX_LIST_LIMIT}")
    return limit
