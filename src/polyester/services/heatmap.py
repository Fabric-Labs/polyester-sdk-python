from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.heatmap import heatmap_from_proto
from polyester.codecs.heatmap import (
    heatmap_depth,
    heatmap_interval_channel_label,
    resolve_heatmap_interval,
    resolve_heatmap_quantity_mode,
)
from polyester.codecs.orderbook import depth_tier_value
from polyester.codecs.proto_helpers import datetime_to_timestamp
from polyester.codecs.realtime_decode import decode_heatmap_live_bucket_bytes
from polyester.codecs.scalars import (
    TIMESTAMP_MAX_SECONDS,
    TIMESTAMP_MIN_SECONDS,
    aware_datetime,
    exact_integer,
    timestamp_parts_to_datetime,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1.heatmap_connect import HeatmapServiceClient
from polyester.gen.marketdata.v1.heatmap_pb2 import (
    GetOrderbookHeatmapRequest,
    HeatmapTimeRange,
)
from polyester.models import ApiData
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService, CatalogWait
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
        wait_for_catalogs: CatalogWait | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._realtime = realtime
        self._wait_for_catalogs = wait_for_catalogs

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
        before the end) to ``end_time``, or to now without one. ``from_ts_sec`` is
        an integer of Unix seconds (negative before 1970); ``start_time`` and ``end_time`` are
        timezone-aware ``datetime`` objects. Any other type, or a naive datetime,
        raises :class:`~polyester.errors.PolyesterValidationError` before any request.

        ``interval`` is ``"1s"``, ``"1m"``, ``"5m"`` or ``"1h"`` (or ``"INTERVAL_1M"``),
        ``quantity_mode`` is ``"close"`` or ``"peak"``. ``depth`` is requested as itself
        when it is a supported depth (1, 5, 10, 20, 50, 100, 200, 500, 1000), else as the
        smallest supported depth covering it, and 0 as 50; the response's ``depth`` names
        the tier served, and a reply naming none, or another tier, raises
        :class:`~polyester.errors.PolyesterResponseContractError`. A depth below 0 or above
        1000 is refused.

        The page's chain replays the top ``depth`` levels per side: start from
        ``chain.base_keyframe`` and apply each ``chain.deltas`` bucket oldest
        first, setting each listed level and deleting a level whose quantity is
        ``0``, with no clipping. A ``0`` means the level left the top ``depth``
        levels, not only that it left the book; a level that enters them is
        listed even when the bucket did not change it. The replay after each
        bucket is the same at every page ``limit``. In ``"peak"`` mode the base
        keyframe is only the replay's starting point, not a bucket: do not
        render it.
        """
        validated_limit = validate_limit(limit, GetOrderbookHeatmapRequest)
        # A malformed time is refused before the catalog wait or any request.
        time_range = _time_range(from_ts_sec, start_time, end_time, continuation=bool(page_token))
        if symbol:
            await self._ensure_catalogs()
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="heatmap.get",
        )
        interval_enum = resolve_heatmap_interval(interval)
        depth_levels = heatmap_depth(depth)
        depth_enum = depth_tier_value(depth_levels)
        qty_enum = resolve_heatmap_quantity_mode(quantity_mode)

        request = GetOrderbookHeatmapRequest(
            symbol_id=resolved_symbol_id,
            interval=interval_enum,
            depth=depth_enum,
            limit=validated_limit,
            quantity_mode=qty_enum,
            page_token=page_token,
        )
        if time_range is not None:
            request.time_range.CopyFrom(time_range)

        return await unary_public_decoded(
            self._transport,
            HeatmapServiceClient,
            lambda client, req: client.get_orderbook_heatmap(req),
            request,
            lambda msg: heatmap_from_proto(msg, depth=depth_levels),
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

        Key buckets by ``ts_sec``. Replace a stored bucket with one of a
        higher ``book_seq_end``, final or not, and at an equal
        ``book_seq_end`` with a final one (``is_final``) over a provisional
        one; never replace a bucket with a lower ``book_seq_end``. Updates of a
        bucket still open are best effort: a later update or the final payload
        supersedes them. A finalized bucket can be published again with later
        updates and a higher ``book_seq_end``, and the same final payload can
        arrive more than once (after a service restart, for example): a repeat
        changes nothing.
        """
        label = heatmap_interval_channel_label(interval)
        if symbol:
            await self._ensure_catalogs()
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


def _time_range(
    from_ts_sec: object,
    start_time: object,
    end_time: object,
    *,
    continuation: bool,
) -> HeatmapTimeRange | None:
    """The request's time range, every bound checked. A continuation sends
    only the bounds given (none: no range); a first page defaults the end to
    now and the start to 5 minutes before the end. ``from_ts_sec`` wins over
    ``start_time``."""
    start = None if start_time is None else aware_datetime(start_time, "start_time")
    end = None if end_time is None else aware_datetime(end_time, "end_time")
    start_name = "start_time"
    if from_ts_sec is not None:
        seconds = exact_integer(
            from_ts_sec,
            "from_ts_sec",
            min_value=TIMESTAMP_MIN_SECONDS,
            max_value=TIMESTAMP_MAX_SECONDS,
        )
        start, start_name = timestamp_parts_to_datetime(seconds, 0), "from_ts_sec"
    if not continuation:
        if end is None:
            end = datetime.now(UTC)
        if start is None:
            try:
                start = end - timedelta(minutes=5)
            except OverflowError:
                raise PolyesterValidationError(
                    "end_time is outside the supported range (years 1 to 9999 in UTC)"
                ) from None
    if start is None and end is None:
        return None
    time_range = HeatmapTimeRange()
    if start is not None:
        time_range.start_time.CopyFrom(datetime_to_timestamp(start, start_name))
    if end is not None:
        time_range.end_time.CopyFrom(datetime_to_timestamp(end, "end_time"))
    return time_range
