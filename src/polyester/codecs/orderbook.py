from polyester.errors import PolyesterValidationError

# Depths the snapshot API accepts. The delta stream publishes fewer: see below.
ORDERBOOK_SUPPORTED_DEPTHS = (1, 5, 10, 20, 50, 100, 200, 500, 1000)

# Depths the server publishes on the delta stream. It also accepts a subscribe at
# any other depth, and then never sends anything on it.
ORDERBOOK_STREAM_DEPTHS = (1, 20, 50, 200, 500)

DEPTH_TO_PROTO: dict[int, str] = {
    1: "DEPTH_1",
    5: "DEPTH_5",
    10: "DEPTH_10",
    20: "DEPTH_20",
    50: "DEPTH_50",
    100: "DEPTH_100",
    200: "DEPTH_200",
    500: "DEPTH_500",
    1000: "DEPTH_1000",
}


def depth_to_connect_enum(depth: int) -> str:
    if depth in DEPTH_TO_PROTO:
        return DEPTH_TO_PROTO[depth]
    closest = min(ORDERBOOK_SUPPORTED_DEPTHS, key=lambda value: abs(value - depth))
    return DEPTH_TO_PROTO[closest]


def _is_int(depth: object) -> bool:
    return isinstance(depth, int) and not isinstance(depth, bool)


def orderbook_stream_tier(depth: int) -> int:
    """Smallest published stream depth covering ``depth``, for a view trimmed to ``depth``."""
    if not _is_int(depth) or depth < 1:
        raise PolyesterValidationError(
            f"orderbook subscription depth must be a positive integer, got {depth!r}"
        )
    for tier in ORDERBOOK_STREAM_DEPTHS:
        if tier >= depth:
            return tier
    top = ORDERBOOK_STREAM_DEPTHS[-1]
    raise PolyesterValidationError(
        f"orderbook subscription depth {depth} is above the deepest published stream tier "
        f"({top}); use orderbook.get for a snapshot of up to "
        f"{ORDERBOOK_SUPPORTED_DEPTHS[-1]} levels"
    )


def require_published_stream_depth(depth: int) -> int:
    """``depth`` itself when the server publishes it: raw deltas of a tier can't be trimmed."""
    if not _is_int(depth) or depth not in ORDERBOOK_STREAM_DEPTHS:
        raise PolyesterValidationError(
            f"orderbook delta streams are published only at depths "
            f"{', '.join(map(str, ORDERBOOK_STREAM_DEPTHS))}, "
            f"got {depth!r}; use orderbook.create_subscription for a book trimmed to any depth "
            f"up to {ORDERBOOK_STREAM_DEPTHS[-1]}"
        )
    return depth
