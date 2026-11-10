from __future__ import annotations

from typing import Literal, overload

from polyester.codecs.orderbook import exact_int
from polyester.errors import PolyesterValidationError


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
    """Wire-safety for pagination limits (no SDK-wide max policy).

    Accepts any exact integer (``__index__``, as NumPy integers implement) and
    returns it as a plain ``int``; rejects ``bool`` and non-integers such as
    ``float`` so values cannot silently coerce on the wire. Endpoint/server
    protos remain the authority for allowed ranges. Optional limits omit when
    ``None`` so server defaults are preserved.
    """
    if limit is None:
        if allow_none:
            return None
        raise PolyesterValidationError(f"{label} must be an integer")
    value = exact_int(limit)
    if value is None:
        raise PolyesterValidationError(f"{label} must be an integer")
    return value
