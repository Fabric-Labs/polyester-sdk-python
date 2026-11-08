from __future__ import annotations

from datetime import UTC, datetime, timedelta

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.heatmap import heatmap_from_proto
from polyester.codecs.heatmap import (
    heatmap_depth,
    heatmap_interval_channel_label,
    resolve_heatmap_interval,
    resolve_heatmap_quantity_mode,
)
from polyester.codecs.realtime_decode import decode_heatmap_live_bucket_bytes
from polyester.gen.marketdata.v1.heatmap_connect import HeatmapServiceClient
from polyester.gen.marketdata.v1.heatmap_pb2 import (
    GetOrderbookHeatmapRequest,
    HeatmapDepth,
    HeatmapTimeRange,
)
from polyester.models import ApiData
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded
from polyester.services._realtime_subscribe import subscribe_public_proto
from polyester.services._symbols import resolve_symbol_id
from polyester.services._validation import validate_limit


class AsyncHeatmapService(BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager | None = None,
        *,
        realtime: AsyncRealtimeClient | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._realtime = realtime

    async def get(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        interval: str = "1s",
        depth: int = 50,
        limit: int = 100,
        quantity_mode: str = "close",
        from_ts_sec: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page_token: str = "",
    ) -> ApiData:
        """Read history, continuing with the returned opaque token and same filters.

        A continuation omits the default time window. If a range is supplied
        with a token, only its explicit bounds are sent; repeat the original range.
        The first page runs from ``from_ts_sec`` (or ``start_time``, else 5 minutes
        before the end) to ``end_time``, or to now without one.

        ``interval`` is ``"1s"``, ``"1m"``, ``"5m"`` or ``"1h"`` (or ``"INTERVAL_1M"``),
        ``quantity_mode`` is ``"close"`` or ``"peak"``. ``depth`` is requested as itself
        when it is a supported depth (1, 5, 10, 20, 50, 100, 200, 500, 1000), else as the
        smallest supported depth covering it, and 0 as 50; the response's ``depth`` names
        the depth requested. A depth below 0 or above 1000 is refused.
        """
        validated_limit = validate_limit(limit)
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="heatmap.get",
        )
        interval_enum = resolve_heatmap_interval(interval)
        depth_enum = HeatmapDepth.Value(f"DEPTH_{heatmap_depth(depth)}")
        qty_enum = resolve_heatmap_quantity_mode(quantity_mode)

        request = GetOrderbookHeatmapRequest(
            symbol_id=resolved_symbol_id,
            interval=interval_enum,
            depth=depth_enum,
            limit=validated_limit,
            quantity_mode=qty_enum,
            page_token=page_token,
        )
        if page_token:
            if from_ts_sec is not None or start_time is not None or end_time is not None:
                time_range = HeatmapTimeRange()
                if from_ts_sec is not None:
                    time_range.start_time.CopyFrom(
                        _datetime_to_timestamp(datetime.fromtimestamp(from_ts_sec, tz=UTC))
                    )
                elif start_time is not None:
                    time_range.start_time.CopyFrom(_datetime_to_timestamp(start_time))
                if end_time is not None:
                    time_range.end_time.CopyFrom(_datetime_to_timestamp(end_time))
                request.time_range.CopyFrom(time_range)
        else:
            end = end_time or datetime.now(UTC)
            if from_ts_sec is not None:
                start = datetime.fromtimestamp(from_ts_sec, tz=UTC)
            else:
                start = start_time or (end - timedelta(minutes=5))
            time_range = HeatmapTimeRange()
            time_range.start_time.CopyFrom(_datetime_to_timestamp(start))
            time_range.end_time.CopyFrom(_datetime_to_timestamp(end))
            request.time_range.CopyFrom(time_range)

        return await unary_public_decoded(
            self._transport,
            HeatmapServiceClient,
            lambda client, req: client.get_orderbook_heatmap(req),
            request,
            heatmap_from_proto,
        )

    async def subscribe_live(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        interval: str = "1s",
    ) -> AsyncSubscription[ApiData]:
        """Stream live buckets from the channel the server publishes ``interval`` on.

        ``interval`` is ``"1s"``, ``"1m"``, ``"5m"`` or ``"1h"`` (or ``"INTERVAL_1S"``);
        any other value is refused before connecting.
        """
        label = heatmap_interval_channel_label(interval)
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="heatmap.subscribe_live",
        )
        channel = f"public:spot:market:heatmap:{label}:{resolved_symbol_id}:proto"
        return await subscribe_public_proto(
            self._realtime,
            channel=channel,
            decode=decode_heatmap_live_bucket_bytes,
        )


def _datetime_to_timestamp(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts
