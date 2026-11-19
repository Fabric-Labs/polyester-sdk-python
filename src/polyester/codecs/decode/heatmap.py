from __future__ import annotations

from polyester.codecs.decode.common import api_data_from_proto
from polyester.codecs.orderbook import require_served_tier
from polyester.gen.marketdata.v1 import heatmap_pb2
from polyester.models import ApiData


def heatmap_from_proto(msg: heatmap_pb2.GetOrderbookHeatmapResponse, *, depth: int) -> ApiData:
    """Decode a heatmap page requested at ``depth`` levels per side: the reply
    names the tier it served, which must be that one."""
    require_served_tier("GetOrderbookHeatmap", int(msg.depth), depth)
    return api_data_from_proto(msg)
