from __future__ import annotations

from typing import Literal, overload

from google.protobuf.message import Message

from polyester.codecs.contract_limits import contract_uint32_range
from polyester.codecs.orderbook import exact_int
from polyester.codecs.scalars import UINT64_MAX, exact_integer
from polyester.errors import PolyesterValidationError


@overload
def validate_limit(
    limit: int,
    request: type[Message],
    *,
    label: str = "limit",
    allow_none: Literal[False] = False,
) -> int: ...


@overload
def validate_limit(
    limit: int | None,
    request: type[Message],
    *,
    label: str = "limit",
    allow_none: Literal[True],
) -> int | None: ...


def validate_limit(
    limit: int | None,
    request: type[Message],
    *,
    label: str = "limit",
    allow_none: bool = False,
) -> int | None:
    """A page limit as ``request`` takes it, refused before sending when the
    contract refuses it.

    Accepts any exact integer (``__index__``, as NumPy integers implement) and
    returns it as a plain ``int``; rejects ``bool`` and non-integers such as
    ``float`` so values cannot silently coerce on the wire. The value must be
    within the range the contract's validation rule on ``request.limit``
    sets, read from the generated descriptor: a limit above its maximum, or
    0 where the contract bounds it from 1, raises
    :class:`PolyesterValidationError`. ``None`` (with ``allow_none``) is
    omitted, so the server default applies.
    """
    if limit is None:
        if allow_none:
            return None
        raise PolyesterValidationError(f"{label} must be an integer")
    value = exact_int(limit)
    if value is None:
        raise PolyesterValidationError(f"{label} must be an integer")
    low, high = contract_uint32_range(request, "limit")
    if not low <= value <= high:
        raise PolyesterValidationError(f"{label} {value} is outside {low}..{high}")
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
