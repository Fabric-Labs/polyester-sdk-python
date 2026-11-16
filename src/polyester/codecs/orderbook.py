import operator
from typing import SupportsIndex

from polyester.errors import PolyesterValidationError

# Depths the server publishes on the delta stream. It also accepts a subscribe at
# any other depth, and then never sends anything on it.
ORDERBOOK_STREAM_DEPTHS = (1, 20, 50, 200, 500)

# The depth a snapshot request of 0 (unset) selects.
ORDERBOOK_SNAPSHOT_DEFAULT_DEPTH = 50

# The snapshot request's depth is a uint32 level count per side.
_UINT32_MAX = 2**32 - 1


def exact_int(value: object) -> int | None:
    """``value`` as a plain ``int`` when it is an exact integer, else ``None``.

    An exact integer implements ``__index__`` (``operator.index``), as ``int`` and NumPy
    integers do. ``bool`` implements it too but is refused, and ``float``, ``Decimal`` and
    ``str`` don't implement it.
    """
    if isinstance(value, bool) or not isinstance(value, SupportsIndex):
        return None
    return operator.index(value)


def orderbook_snapshot_wire_depth(depth: int) -> int:
    """``depth`` as ``orderbook.get`` sends it: a plain ``int`` level count per side.

    0 selects the server's default of 50. Any other value is sent unchanged: the largest
    depth the server accepts is the ``max_depth`` every snapshot reports, and a depth above
    it is refused by the server (``INVALID_ARGUMENT``), never truncated. A negative depth, a
    depth above the uint32 range, or a value that is not an integer, is refused.
    """
    value = exact_int(depth)
    if value is None or value < 0 or value > _UINT32_MAX:
        raise PolyesterValidationError(
            f"orderbook snapshot depth must be an integer from 0 to {_UINT32_MAX}, got {depth!r}"
        )
    return value


def orderbook_snapshot_depth(depth: int) -> int:
    """Levels per side a snapshot of ``depth`` holds at most: ``depth``, or 50 for 0.

    Refuses what :func:`orderbook_snapshot_wire_depth` refuses.
    """
    return orderbook_snapshot_wire_depth(depth) or ORDERBOOK_SNAPSHOT_DEFAULT_DEPTH


def orderbook_stream_tier(depth: int) -> int:
    """Smallest published stream depth covering ``depth``, for a view trimmed to ``depth``."""
    value = exact_int(depth)
    if value is None or value < 1:
        raise PolyesterValidationError(
            f"orderbook subscription depth must be a positive integer, got {depth!r}"
        )
    depth = value
    for tier in ORDERBOOK_STREAM_DEPTHS:
        if tier >= depth:
            return tier
    top = ORDERBOOK_STREAM_DEPTHS[-1]
    raise PolyesterValidationError(
        f"orderbook subscription depth {depth} is above the deepest published stream tier "
        f"({top}); use orderbook.get for a deeper snapshot, up to the max_depth it reports"
    )


def require_published_stream_depth(depth: int) -> int:
    """``depth`` itself when the server publishes it: raw deltas of a tier can't be trimmed."""
    value = exact_int(depth)
    if value is None or value not in ORDERBOOK_STREAM_DEPTHS:
        raise PolyesterValidationError(
            f"orderbook delta streams are published only at depths "
            f"{', '.join(map(str, ORDERBOOK_STREAM_DEPTHS))}, "
            f"got {depth!r}; use orderbook.create_subscription for a book trimmed to any depth "
            f"up to {ORDERBOOK_STREAM_DEPTHS[-1]}"
        )
    return value
