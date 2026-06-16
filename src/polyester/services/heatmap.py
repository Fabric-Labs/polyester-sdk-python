from __future__ import annotations

from datetime import UTC, datetime, timedelta

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.heatmap import (
    INTERVAL_ALIASES,
    QTY_MODE_ALIASES,
    depth_to_proto_name,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1.heatmap_connect import HeatmapServiceClient
from polyester.gen.marketdata.v1.heatmap_pb2 import (
    GetOrderbookHeatmapRequest,
    HeatmapTimeRange,
)
from polyester.models import ApiData
from polyester.services._base import BaseService
from polyester.services._generated import unary_public
from polyester.services._symbols import resolve_symbol_id


class AsyncHeatmapService(BaseService):
    def __init__(self, transport, catalogs: CatalogManager | None = None) -> None:
        super().__init__(transport)
        self._catalogs = catalogs

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
    ) -> ApiData:
        from polyester.gen.marketdata.v1 import heatmap_pb2

        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="heatmap.get",
        )
        interval_name = INTERVAL_ALIASES.get(interval, interval.upper())
        interval_enum = getattr(heatmap_pb2, interval_name, None)
        if interval_enum is None:
            raise PolyesterValidationError(
                f"Unknown heatmap interval {interval!r}; use '1s', '1m', '5m', or '1h'"
            )

        depth_name = depth_to_proto_name(depth)
        depth_enum = getattr(heatmap_pb2, depth_name, None)
        if depth_enum is None:
            raise PolyesterValidationError(f"Unsupported heatmap depth {depth}")

        qty_name = QTY_MODE_ALIASES.get(quantity_mode.lower(), quantity_mode.upper())
        qty_enum = getattr(heatmap_pb2, qty_name, None)
        if qty_enum is None:
            raise PolyesterValidationError("quantity_mode must be 'close' or 'peak'")

        request = GetOrderbookHeatmapRequest(
            symbol_id=resolved_symbol_id,
            interval=interval_enum,
            depth=depth_enum,
            limit=limit,
            quantity_mode=qty_enum,
        )
        if from_ts_sec is not None:
            now = datetime.now(UTC)
            start = datetime.fromtimestamp(from_ts_sec, tz=UTC)
            time_range = HeatmapTimeRange()
            time_range.start_time.CopyFrom(_datetime_to_timestamp(start))
            time_range.end_time.CopyFrom(_datetime_to_timestamp(now))
            request.time_range.CopyFrom(time_range)
        elif start_time is not None or end_time is not None:
            now = datetime.now(UTC)
            end = end_time or now
            start = start_time or (end - timedelta(minutes=5))
            time_range = HeatmapTimeRange()
            time_range.start_time.CopyFrom(_datetime_to_timestamp(start))
            time_range.end_time.CopyFrom(_datetime_to_timestamp(end))
            request.time_range.CopyFrom(time_range)
        else:
            now = datetime.now(UTC)
            end = now
            start = end - timedelta(minutes=5)
            time_range = HeatmapTimeRange()
            time_range.start_time.CopyFrom(_datetime_to_timestamp(start))
            time_range.end_time.CopyFrom(_datetime_to_timestamp(end))
            request.time_range.CopyFrom(time_range)

        data = await unary_public(
            self._transport,
            HeatmapServiceClient,
            lambda client, req: client.get_orderbook_heatmap(req),
            request,
        )
        return ApiData(raw=data)


def _datetime_to_timestamp(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts
