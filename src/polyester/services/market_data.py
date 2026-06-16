from __future__ import annotations

from datetime import datetime

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.wire_decode import (
    decode_candles_list,
    decode_market_trades_list,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1.marketdata_connect import MarketDataServiceClient
from polyester.gen.marketdata.v1.marketdata_pb2 import (
    GetCandlesRequest,
    GetSpotConfigRequest,
    GetTradesRequest,
)
from polyester.models import Candle, CandlesResult, MarketTradesResult, SpotConfig
from polyester.realtime.client import AsyncRealtimeClient
from polyester.services._base import BaseService
from polyester.services._generated import unary_public
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
        data = await unary_public(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_trades(req),
            request,
        )
        return decode_market_trades_list(data)

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
        data = await unary_public(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_candles(req),
            request,
        )
        return decode_candles_list(data)

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
        data = await unary_public(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_candles_columns(req),
            request,
        )
        return decode_candles_list(data)

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
