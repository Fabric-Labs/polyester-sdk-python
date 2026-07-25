from __future__ import annotations

from datetime import datetime

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.market_data import (
    candles_columns_from_proto,
    candles_from_proto,
    market_trades_from_proto,
)
from polyester.codecs.realtime_decode import decode_candle_point_bytes
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1.marketdata_connect import MarketDataServiceClient
from polyester.gen.marketdata.v1.marketdata_pb2 import (
    GetCandlesRequest,
    GetSpotConfigRequest,
    GetTradesRequest,
)
from polyester.models import Candle, CandlesResult, MarketTradesResult, SpotConfig
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_public, unary_public_decoded
from polyester.services._realtime_subscribe import subscribe_public_proto
from polyester.services._symbols import resolve_symbol_id

TIMEFRAME_ALIASES: dict[str, str] = {
    "1s": "SEC_1",
    "1m": "MIN_1",
    "5m": "MIN_5",
    "15m": "MIN_15",
    "30m": "MIN_30",
    "1h": "HOUR_1",
    "4h": "HOUR_4",
    "12h": "HOUR_12",
    "1d": "DAY_1",
    "1w": "WEEK_1",
    "1mo": "MONTH_1",
}

# Live Centrifugo channels use human labels (`1m`), not REST enum names (`MIN_1`).
_CHANNEL_TIMEFRAME_ALIASES: dict[str, str] = {}
for _label, _enum_name in TIMEFRAME_ALIASES.items():
    _CHANNEL_TIMEFRAME_ALIASES[_label] = _label
    _CHANNEL_TIMEFRAME_ALIASES[_enum_name] = _label
    _CHANNEL_TIMEFRAME_ALIASES[_enum_name.lower()] = _label
    _CHANNEL_TIMEFRAME_ALIASES[_enum_name.replace("_", "").lower()] = _label


class AsyncMarketDataService(BaseService):
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

    async def get_spot_config(self) -> SpotConfig:
        data = await unary_public(
            self._transport,
            MarketDataServiceClient,
            lambda client, request: client.get_spot_config(request),
            GetSpotConfigRequest(),
        )
        return SpotConfig(raw=data)

    async def get_trades(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        limit: int = 100,
        from_match_id: int | None = None,
    ) -> MarketTradesResult:
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="get_trades",
        )
        request = GetTradesRequest(symbol_id=resolved_symbol_id, limit=limit)
        if from_match_id is not None:
            request.from_match_id = from_match_id
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_trades(req),
            request,
            market_trades_from_proto,
        )

    async def get_current_candle(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
    ) -> Candle:
        result = await self.get_candles(
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
            limit=1,
            include_incomplete=True,
        )
        if result.candles:
            return result.candles[-1]
        return Candle(ts_sec=0)

    async def get_candles(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        include_incomplete: bool = False,
    ) -> CandlesResult:
        request = _build_candles_request(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            include_incomplete=include_incomplete,
        )
        volume_scale = _volume_scale_for_symbol_id(self._catalogs, request.symbol_id)
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_candles(req),
            request,
            lambda msg: candles_from_proto(msg, volume_scale=volume_scale),
        )

    async def get_candles_columns(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        include_incomplete: bool = False,
    ) -> CandlesResult:
        request = _build_candles_request(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            include_incomplete=include_incomplete,
        )
        volume_scale = _volume_scale_for_symbol_id(self._catalogs, request.symbol_id)
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_candles_columns(req),
            request,
            lambda msg: candles_columns_from_proto(msg, volume_scale=volume_scale),
        )

    def subscribe_trades(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ):
        if self._realtime is None:
            from polyester.errors import PolyesterRealtimeError

            raise PolyesterRealtimeError(
                "Realtime client is not configured on this Polyester instance"
            )
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="subscribe_trades",
        )
        return self._realtime.subscribe_market_trades(resolved_symbol_id)

    async def subscribe_candles(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
    ) -> AsyncSubscription[Candle]:
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="subscribe_candles",
        )
        channel_timeframe = _resolve_candle_channel_timeframe(timeframe)
        channel = f"public:spot:market:candles:{channel_timeframe}:{resolved_symbol_id}:proto"
        volume_scale = _volume_scale_for_symbol_id(self._catalogs, resolved_symbol_id)
        return await subscribe_public_proto(
            self._realtime,
            channel=channel,
            decode=decode_candle_point_bytes(
                symbol_id=resolved_symbol_id,
                timeframe=channel_timeframe,
                volume_scale=volume_scale,
            ),
        )


def _resolve_candle_channel_timeframe(timeframe: str) -> str:
    """Normalize user timeframe aliases to the live channel label (e.g. MIN_1 → 1m)."""
    label = _CHANNEL_TIMEFRAME_ALIASES.get(timeframe)
    if label is None:
        label = _CHANNEL_TIMEFRAME_ALIASES.get(timeframe.upper())
    if label is None:
        label = _CHANNEL_TIMEFRAME_ALIASES.get(timeframe.lower().replace("_", ""))
    if label is None:
        raise PolyesterValidationError(
            f"Unknown candle timeframe {timeframe!r}; use aliases like '1m', '1h', '1d'"
        )
    return label


def _build_candles_request(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None,
    timeframe: str,
    limit: int,
    start_time: datetime | None,
    end_time: datetime | None,
    include_incomplete: bool,
) -> GetCandlesRequest:
    from polyester.gen.marketdata.v1 import marketdata_pb2

    resolved_symbol_id = resolve_symbol_id(
        catalogs,
        symbol=symbol,
        symbol_id=symbol_id,
        label="get_candles",
    )
    timeframe_name = TIMEFRAME_ALIASES.get(timeframe, timeframe.upper())
    timeframe_enum = getattr(marketdata_pb2, timeframe_name, None)
    if timeframe_enum is None:
        raise PolyesterValidationError(
            f"Unknown candle timeframe {timeframe!r}; use aliases like '1m', '1h', '1d'"
        )

    request = GetCandlesRequest(
        symbol_id=resolved_symbol_id,
        timeframe=timeframe_enum,
        limit=limit,
        include_incomplete=include_incomplete,
    )
    if start_time is not None:
        request.start_time.CopyFrom(_datetime_to_timestamp(start_time))
    if end_time is not None:
        request.end_time.CopyFrom(_datetime_to_timestamp(end_time))
    return request


def _datetime_to_timestamp(value: datetime) -> Timestamp:
    ts = Timestamp()
    ts.FromDatetime(value)
    return ts


def _volume_scale_for_symbol_id(catalogs: CatalogManager | None, symbol_id: int) -> int:
    if catalogs is None:
        return 8
    # Decode-only fallback when the spot catalog has not resolved this id yet.
    return catalogs.base_quantity_scale_for_symbol_id(symbol_id) or 8
