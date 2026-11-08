from __future__ import annotations

from polyester.codecs.orderbook import DEPTH_TO_PROTO, covering_snapshot_depth
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import heatmap_pb2

ORDERBOOK_SUPPORTED_DEPTHS = (1, 5, 10, 20, 50, 100, 200, 500, 1000)

INTERVAL_ALIASES: dict[str, str] = {
    "1s": "INTERVAL_1S",
    "1m": "INTERVAL_1M",
    "5m": "INTERVAL_5M",
    "1h": "INTERVAL_1H",
}

# Interval segments the server publishes live heatmap buckets on.
INTERVAL_CHANNEL_LABELS: dict[str, str] = {name: alias for alias, name in INTERVAL_ALIASES.items()}

QTY_MODE_ALIASES: dict[str, str] = {
    "close": "CLOSE",
    "peak": "PEAK",
}


def resolve_heatmap_interval(interval: str) -> heatmap_pb2.HeatmapInterval:
    """``HeatmapInterval`` value for an alias (``"1m"``) or an interval name (``"INTERVAL_1M"``).

    Only names of ``HeatmapInterval`` are accepted: a quantity mode or any other value is refused.
    """
    name = INTERVAL_ALIASES.get(interval, interval.upper()) if isinstance(interval, str) else ""
    if name not in INTERVAL_CHANNEL_LABELS:
        raise PolyesterValidationError(
            f"Unknown heatmap interval {interval!r}; use '1s', '1m', '5m', or '1h'"
        )
    return heatmap_pb2.HeatmapInterval.Value(name)


def heatmap_interval_channel_label(interval: str) -> str:
    """Interval segment of the live heatmap channel: ``"1s"``, ``"1m"``, ``"5m"`` or ``"1h"``."""
    name = heatmap_pb2.HeatmapInterval.Name(resolve_heatmap_interval(interval))
    return INTERVAL_CHANNEL_LABELS[name]


def resolve_heatmap_quantity_mode(quantity_mode: str) -> heatmap_pb2.HeatmapQuantityMode:
    """``HeatmapQuantityMode`` value for ``"close"`` or ``"peak"`` (any case); nothing else."""
    name = QTY_MODE_ALIASES.get(quantity_mode.lower(), "") if isinstance(quantity_mode, str) else ""
    if not name:
        raise PolyesterValidationError("quantity_mode must be 'close' or 'peak'")
    return heatmap_pb2.HeatmapQuantityMode.Value(name)


def heatmap_depth(depth: int) -> int:
    """Depth ``heatmap.get`` requests for ``depth``, by the rule of ``orderbook_snapshot_depth``.

    ``depth`` itself when it is a supported depth, else the smallest one covering it; 0 is the
    default 50. A depth below 0 or above 1000, or not an integer, is refused.
    """
    return covering_snapshot_depth(depth, "heatmap depth")


def depth_to_proto_name(depth: int) -> str:
    """Wire depth name for ``depth``, by the rule of :func:`heatmap_depth`."""
    return DEPTH_TO_PROTO[heatmap_depth(depth)]
