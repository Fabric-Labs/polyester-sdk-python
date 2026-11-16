from __future__ import annotations

from typing import Literal, overload

from polyester.codecs.orderbook import exact_int
from polyester.codecs.scalars import UINT64_MAX, exact_integer
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


def validate_time_range(
    label: str,
    start_ts_ns: int | None,
    end_ts_ns: int | None,
) -> tuple[int | None, int | None]:
    """The contract's optional inclusive time range, in Unix nanoseconds.

    Each bound is ``None`` (not sent) or an exact uint64 integer; an explicit
    ``0`` is kept, and an ``end_ts_ns`` of 0 returns an empty page. As the
    contract's ``ordered_time_range`` rule requires, a ``start_ts_ns`` after a
    non-zero ``end_ts_ns`` is refused before sending.
    """
    start = (
        None
        if start_ts_ns is None
        else exact_integer(start_ts_ns, f"{label} start_ts_ns", min_value=0, max_value=UINT64_MAX)
    )
    end = (
        None
        if end_ts_ns is None
        else exact_integer(end_ts_ns, f"{label} end_ts_ns", min_value=0, max_value=UINT64_MAX)
    )
    if start is not None and end is not None and end != 0 and start > end:
        raise PolyesterValidationError(
            f"{label} start_ts_ns ({start}) must be <= end_ts_ns ({end}) when both are set"
        )
    return start, end
