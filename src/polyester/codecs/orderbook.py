import operator
from typing import SupportsIndex

from polyester.errors import PolyesterValidationError
from polyester.gen.polyester.type.v1 import depth_tier_pb2

# Depths the server publishes on the delta stream, a subset of the snapshot
# tiers; it refuses a subscription at any other depth.
ORDERBOOK_STREAM_DEPTHS = (1, 20, 50, 200, 500)

# The depth a snapshot request of 0 (unset) selects.
ORDERBOOK_SNAPSHOT_DEFAULT_DEPTH = 50

# Levels per side of every ``DepthTier`` a snapshot is served at, ascending,
# read from the contract's enum.
ORDERBOOK_SNAPSHOT_DEPTHS = tuple(
    sorted(
        int(name.removeprefix("DEPTH_"))
        for name in depth_tier_pb2.DepthTier.DESCRIPTOR.values_by_name
        if name.removeprefix("DEPTH_").isdigit()
    )
)


def exact_int(value: object) -> int | None:
    """``value`` as a plain ``int`` when it is an exact integer, else ``None``.

    An exact integer implements ``__index__`` (``operator.index``), as ``int`` and NumPy
    integers do. ``bool`` implements it too but is refused, and ``float``, ``Decimal`` and
    ``str`` don't implement it.
    """
    if isinstance(value, bool) or not isinstance(value, SupportsIndex):
        return None
    return operator.index(value)


def orderbook_snapshot_tier(depth: int) -> depth_tier_pb2.DepthTier:
    """``depth`` as ``orderbook.get`` sends it: the ``DepthTier`` of that many
    levels per side, one of ``ORDERBOOK_SNAPSHOT_DEPTHS``; 0 sends no tier,
    which the server serves at 50. A level count that is no tier, a negative
    one, or a value that is not an integer, is refused: the contract takes
    only defined tiers.
    """
    value = exact_int(depth)
    if value == 0:
        return depth_tier_pb2.DEPTH_UNSPECIFIED
    if value is None or value not in ORDERBOOK_SNAPSHOT_DEPTHS:
        raise PolyesterValidationError(
            "orderbook depth must be one of "
            f"{', '.join(map(str, ORDERBOOK_SNAPSHOT_DEPTHS))} levels per side, or 0 for the "
            f"default of {ORDERBOOK_SNAPSHOT_DEFAULT_DEPTH}; got {depth!r}"
        )
    return depth_tier_value(value)


def orderbook_snapshot_depth(depth: int) -> int:
    """Levels per side a snapshot of ``depth`` holds at most: ``depth``, or 50 for 0.

    Refuses what :func:`orderbook_snapshot_tier` refuses.
    """
    orderbook_snapshot_tier(depth)
    return exact_int(depth) or ORDERBOOK_SNAPSHOT_DEFAULT_DEPTH


def depth_tier_value(levels: int) -> depth_tier_pb2.DepthTier:
    """The ``DepthTier`` of ``levels`` per side, which must be a tier."""
    return depth_tier_pb2.DepthTier.Value(f"DEPTH_{levels}")


def depth_tier_levels(tier: int) -> int | None:
    """Levels per side of a ``DepthTier``; ``None`` for no tier or one this SDK
    does not know."""
    try:
        name = str(depth_tier_pb2.DepthTier.Name(tier))
    except ValueError:
        return None
    count = name.removeprefix("DEPTH_")
    return int(count) if count.isdigit() else None


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
        f"({top}); use orderbook.get for a deeper snapshot, up to "
        f"{ORDERBOOK_SNAPSHOT_DEPTHS[-1]} levels per side"
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
