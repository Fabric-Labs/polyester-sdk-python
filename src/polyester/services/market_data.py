from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.contract_limits import contract_repeated_items, contract_uint32_items_range
from polyester.codecs.decode.asset_info import asset_info_list_from_proto
from polyester.codecs.decode.market_data import (
    candles_columns_from_proto,
    candles_from_proto,
    index_price_candles_from_proto,
    market_trades_from_proto,
)
from polyester.codecs.proto_helpers import optional_datetime_to_timestamp
from polyester.codecs.realtime_decode import decode_candle_point_bytes
from polyester.codecs.scalars import UINT64_MAX
from polyester.codecs.spot_config import spot_config_from_dict
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import asset_info_pb2, marketdata_pb2
from polyester.gen.marketdata.v1.marketdata_connect import MarketDataServiceClient
from polyester.gen.marketdata.v1.marketdata_pb2 import (
    GetCandlesRequest,
    GetIndexPriceCandlesRequest,
    GetSpotConfigRequest,
    GetTradesRequest,
)
from polyester.models import (
    Candle,
    CandlesResult,
    IndexPriceCandlesResult,
    MarketTradesResult,
    SpotConfig,
)
from polyester.models.asset_info import AssetInfo
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService, CatalogWait
from polyester.services._generated import unary_public, unary_public_decoded
from polyester.services._realtime_subscribe import subscribe_public_proto
from polyester.services._symbols import resolve_symbol_id
from polyester.services._validation import validate_limit

# Each asset ID ``list_asset_info`` takes (1 to 2147483647) and how many it
# takes (at most 1000), from the contract's rule on
# ``ListAssetInfoRequest.asset_ids``.
ASSET_ID_MIN, ASSET_ID_MAX = contract_uint32_items_range(
    asset_info_pb2.ListAssetInfoRequest, "asset_ids"
)
_, ASSET_IDS_MAX = contract_repeated_items(asset_info_pb2.ListAssetInfoRequest, "asset_ids")

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
    "3m": "MIN_3",
    "2h": "HOUR_2",
    "6h": "HOUR_6",
    "8h": "HOUR_8",
    "3d": "DAY_3",
}

_TRADE_SIDE_FILTERS: dict[str, marketdata_pb2.SideFilter] = {
    "buy": marketdata_pb2.BUY,
    "sell": marketdata_pb2.SELL,
}
# Every accepted candle timeframe, exactly as written, with its live channel
# label: a documented label ("1s", "1m", "3m", ... "1w", "1mo") or a
# ``Timeframe`` enum name ("SEC_1", "MIN_1", ... "MONTH_1"). No other case or
# spelling is read, so "1M" is never taken for "1m" (one minute) nor for "1mo"
# (one month). Live Centrifugo channels use the label (`1m`), not the enum name.
_CANDLE_TIMEFRAMES: dict[str, str] = {
    **{label: label for label in TIMEFRAME_ALIASES},
    **{enum_name: label for label, enum_name in TIMEFRAME_ALIASES.items()},
}


class AsyncMarketDataService(BaseService):
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

    async def get_spot_config(self) -> SpotConfig:
        data = await unary_public(
            self._transport,
            MarketDataServiceClient,
            lambda client, request: client.get_spot_config(request),
            GetSpotConfigRequest(),
        )
        return spot_config_from_dict(data)

    async def list_asset_info(self, asset_ids: Sequence[int] | None = None) -> list[AssetInfo]:
        """Team-maintained asset information: descriptions, official links and
        known launch dates and prices, ordered by ascending ``asset_id``.

        ``asset_ids`` (the ``ledger_id`` of the spot and deposit/withdraw
        configs) keeps those assets; ``None`` or empty returns every saved
        entry. The server ignores duplicate and unknown IDs. The contract
        takes at most 1000 IDs, each from 1 to 2147483647; more IDs or any
        other ID is refused with ``PolyesterValidationError`` before sending.
        Assets never edited are omitted. The result is complete: there is no
        paging. Public, never signed.
        """
        if isinstance(asset_ids, (str, bytes)):
            raise PolyesterValidationError("asset_ids must be a sequence of integers")
        ids: list[int] = []
        for value in asset_ids or ():
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not ASSET_ID_MIN <= value <= ASSET_ID_MAX
            ):
                raise PolyesterValidationError(
                    f"asset_ids: {value!r} is not an integer between "
                    f"{ASSET_ID_MIN} and {ASSET_ID_MAX}"
                )
            ids.append(value)
        if len(ids) > ASSET_IDS_MAX:
            raise PolyesterValidationError(
                f"asset_ids: {len(ids)} IDs is more than the {ASSET_IDS_MAX} allowed"
            )
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, request: client.list_asset_info(request),
            asset_info_pb2.ListAssetInfoRequest(asset_ids=ids),
            asset_info_list_from_proto,
        )

    async def get_trades(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        side: str | None = None,
        page_token: str | None = None,
        after_trade_id: int | None = None,
    ) -> MarketTradesResult:
        """List public trades for one market.

        By default trades come newest first; ``start_time`` / ``end_time``
        (inclusive), ``side`` (``"buy"`` or ``"sell"`` aggressor) and
        ``page_token`` (the previous result's ``next_page_token``) narrow and
        page them. ``start_time`` and ``end_time`` are timezone-aware
        ``datetime`` objects: an int, float, string or naive datetime raises
        :class:`~polyester.errors.PolyesterValidationError` before any request.

        With ``after_trade_id`` the call instead walks the market's trades by
        trade ID, oldest first and gap-free, to backfill trades a live stream
        missed: pass ``0`` to start from the first trade, then the result's
        ``next_after_trade_id``. Every trade up to ``complete_through_trade_id``
        is returned; when ``next_after_trade_id`` equals the ``after_trade_id``
        you sent, nothing newer is available yet, so retry later with backoff.
        ``after_trade_id`` cannot be combined with the time range, side or
        page token.
        """
        validated_limit = validate_limit(limit, GetTradesRequest)
        start_ts = optional_datetime_to_timestamp(start_time, "start_time")
        end_ts = optional_datetime_to_timestamp(end_time, "end_time")
        if after_trade_id is not None:
            if isinstance(after_trade_id, bool) or not isinstance(after_trade_id, int):
                raise PolyesterValidationError("get_trades after_trade_id must be an integer")
            if after_trade_id < 0 or after_trade_id > UINT64_MAX:
                raise PolyesterValidationError("get_trades after_trade_id exceeds uint64 range")
            if start_time is not None or end_time is not None or side or page_token:
                raise PolyesterValidationError(
                    "get_trades after_trade_id cannot be combined with "
                    "start_time, end_time, side or page_token"
                )
        # Trades are decoded with the pair's catalog quantity scale.
        await self._ensure_catalogs()
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="get_trades",
        )
        quantity_scale = _quantity_scale_for_symbol_id(
            self._catalogs, resolved_symbol_id, label="get_trades"
        )
        request = GetTradesRequest(symbol_id=resolved_symbol_id, limit=validated_limit)
        if start_ts is not None:
            request.start_time.CopyFrom(start_ts)
        if end_ts is not None:
            request.end_time.CopyFrom(end_ts)
        if side:
            side_key = side.lower()
            if side_key not in _TRADE_SIDE_FILTERS:
                raise PolyesterValidationError("get_trades side must be 'buy' or 'sell'")
            request.side = _TRADE_SIDE_FILTERS[side_key]
        if page_token:
            request.page_token = page_token
        if after_trade_id is not None:
            request.after_trade_id = after_trade_id
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_trades(req),
            request,
            lambda msg: market_trades_from_proto(msg, quantity_scale=quantity_scale),
        )

    async def get_current_candle(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
    ) -> Candle | None:
        result = await self.get_candles(
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
            limit=1,
            include_incomplete=True,
        )
        if result.candles:
            # GetCandles rows are newest-first; an open candle is prepended.
            return result.candles[0]
        return None

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
        include_reference: bool = False,
        page_token: str = "",
    ) -> CandlesResult:
        """One page of candles, newest-first (an incomplete open candle, when
        requested, comes first).

        ``start_time`` and ``end_time`` bound the page and are timezone-aware
        ``datetime`` objects: an int, float, string or naive datetime raises
        :class:`~polyester.errors.PolyesterValidationError` before any request.
        """
        # An unknown timeframe or time is refused before the catalog wait or any request.
        _candle_timeframe(timeframe)
        start_ts = optional_datetime_to_timestamp(start_time, "start_time")
        end_ts = optional_datetime_to_timestamp(end_time, "end_time")
        # Candles are decoded with the pair's catalog volume scale.
        await self._ensure_catalogs()
        request = _build_candles_request(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
            limit=limit,
            start_time=start_ts,
            end_time=end_ts,
            include_incomplete=include_incomplete,
            include_reference=include_reference,
            page_token=page_token,
        )
        volume_scale = _volume_scale_for_symbol_id(self._catalogs, request.symbol_id)
        reference_price_scale = _reference_price_scale_for_symbol_id(
            self._catalogs, request.symbol_id, required=include_reference
        )
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_candles(req),
            request,
            lambda msg: candles_from_proto(
                msg,
                volume_scale=volume_scale,
                reference_price_scale=reference_price_scale,
            ),
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
        include_reference: bool = False,
        page_token: str = "",
    ) -> CandlesResult:
        """One page of candles from the columnar call, oldest-first.

        Each primary candle's ``is_closed`` is the server's flag for its
        bucket, as :meth:`get_candles` reports it: with
        ``include_incomplete``, the open candle is appended last on a first
        page and is the only row that reads ``False``. Every reference row
        (always a closed bucket) reads ``True``. From a server that predates
        the flag, ``is_closed`` follows the request: on a first page (no
        ``page_token``) with ``include_incomplete`` the newest primary row
        reads ``False`` (not known to be closed), and every other row ``True``.

        ``start_time`` and ``end_time`` bound the page and are timezone-aware
        ``datetime`` objects: an int, float, string or naive datetime raises
        :class:`~polyester.errors.PolyesterValidationError` before any request.
        """
        # An unknown timeframe or time is refused before the catalog wait or any request.
        _candle_timeframe(timeframe)
        start_ts = optional_datetime_to_timestamp(start_time, "start_time")
        end_ts = optional_datetime_to_timestamp(end_time, "end_time")
        # Candles are decoded with the pair's catalog volume scale.
        await self._ensure_catalogs()
        request = _build_candles_request(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
            limit=limit,
            start_time=start_ts,
            end_time=end_ts,
            include_incomplete=include_incomplete,
            include_reference=include_reference,
            page_token=page_token,
        )
        volume_scale = _volume_scale_for_symbol_id(self._catalogs, request.symbol_id)
        reference_price_scale = _reference_price_scale_for_symbol_id(
            self._catalogs, request.symbol_id, required=include_reference
        )
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_candles_columns(req),
            request,
            lambda msg: candles_columns_from_proto(
                msg,
                volume_scale=volume_scale,
                reference_price_scale=reference_price_scale,
                include_incomplete=request.include_incomplete,
                page_token=request.page_token,
            ),
        )

    async def get_index_price_candles(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page_token: str = "",
    ) -> IndexPriceCandlesResult:
        """One page of a spot market's index price candles, closed only,
        newest first (``MarketDataService/GetIndexPriceCandles``).

        The series is continuous: composite reference candles before the
        bucket containing the market's listing time (``source="reference"``),
        index price candles from that bucket on (``source="index"``). Prices
        are decoded with the pair's ``reference_price_scale``; there is no
        volume. A missing bucket is a gap, never filled. ``timeframe`` is any
        candle timeframe except ``"1s"``, which the server refuses.

        ``start_time`` and ``end_time`` are inclusive bounds and
        timezone-aware ``datetime`` objects: an int, float, string or naive
        datetime raises :class:`~polyester.errors.PolyesterValidationError`
        before any request. Pass ``next_page_token`` back as ``page_token``
        with the same symbol, timeframe and bounds to read older candles; a
        token from :meth:`get_candles` is not accepted here.
        """
        # An unknown timeframe or time is refused before the catalog wait or any request.
        timeframe_enum = _candle_timeframe(timeframe)
        start_ts = optional_datetime_to_timestamp(start_time, "start_time")
        end_ts = optional_datetime_to_timestamp(end_time, "end_time")
        # Prices are decoded with the pair's catalog reference price scale.
        await self._ensure_catalogs()
        request = GetIndexPriceCandlesRequest(
            symbol_id=resolve_symbol_id(
                self._catalogs,
                symbol=symbol,
                symbol_id=symbol_id,
                label="get_index_price_candles",
            ),
            timeframe=timeframe_enum,
            limit=validate_limit(limit, GetIndexPriceCandlesRequest),
            page_token=page_token,
        )
        if start_ts is not None:
            request.start_time.CopyFrom(start_ts)
        if end_ts is not None:
            request.end_time.CopyFrom(end_ts)
        reference_price_scale = _index_price_scale_for_symbol_id(self._catalogs, request.symbol_id)
        return await unary_public_decoded(
            self._transport,
            MarketDataServiceClient,
            lambda client, req: client.get_index_price_candles(req),
            request,
            lambda msg: index_price_candles_from_proto(
                msg, reference_price_scale=reference_price_scale
            ),
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
        return self._subscribe_trades(self._realtime, symbol=symbol, symbol_id=symbol_id)

    async def _subscribe_trades(
        self,
        realtime: AsyncRealtimeClient,
        *,
        symbol: str | None,
        symbol_id: int | None,
    ) -> AsyncSubscription[Any]:
        # Trades are decoded with the pair's catalog quantity scale.
        await self._ensure_catalogs()
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="subscribe_trades",
        )
        quantity_scale = _quantity_scale_for_symbol_id(
            self._catalogs, resolved_symbol_id, label="subscribe_trades"
        )
        return await realtime.subscribe_market_trades(
            resolved_symbol_id, quantity_scale=quantity_scale
        )

    async def subscribe_candles(
        self,
        *,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
    ) -> AsyncSubscription[Candle]:
        # An unknown timeframe is refused before the catalog wait or subscribing.
        channel_timeframe = _resolve_candle_channel_timeframe(timeframe)
        # Candles are decoded with the pair's catalog volume scale.
        await self._ensure_catalogs()
        resolved_symbol_id = resolve_symbol_id(
            self._catalogs,
            symbol=symbol,
            symbol_id=symbol_id,
            label="subscribe_candles",
        )
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


def _resolve_candle_channel_timeframe(timeframe: object) -> str:
    """A candle timeframe's live channel label (``MIN_1`` reads as ``1m``).

    Only a label or enum name exactly as written is accepted (see
    ``_CANDLE_TIMEFRAMES``); anything else raises ``PolyesterValidationError``.
    """
    label = _CANDLE_TIMEFRAMES.get(timeframe) if isinstance(timeframe, str) else None
    if label is None:
        raise PolyesterValidationError(
            f"Unknown candle timeframe {timeframe!r}; use a label such as '1m', '1h', "
            "'1d' or '1mo' (one month), or an enum name such as 'MIN_1'"
        )
    return label


def _candle_timeframe(timeframe: object) -> marketdata_pb2.Timeframe:
    """A candle timeframe's ``Timeframe`` value, read as
    :func:`_resolve_candle_channel_timeframe` reads it."""
    label = _resolve_candle_channel_timeframe(timeframe)
    return marketdata_pb2.Timeframe.Value(TIMEFRAME_ALIASES[label])


def _build_candles_request(
    catalogs: CatalogManager | None,
    *,
    symbol: str | None,
    symbol_id: int | None,
    timeframe: str,
    limit: int,
    start_time: Timestamp | None,
    end_time: Timestamp | None,
    include_incomplete: bool,
    include_reference: bool = False,
    page_token: str = "",
) -> GetCandlesRequest:
    resolved_symbol_id = resolve_symbol_id(
        catalogs,
        symbol=symbol,
        symbol_id=symbol_id,
        label="get_candles",
    )
    validated_limit = validate_limit(limit, GetCandlesRequest)
    timeframe_enum = _candle_timeframe(timeframe)

    request = GetCandlesRequest(
        symbol_id=resolved_symbol_id,
        timeframe=timeframe_enum,
        limit=validated_limit,
        include_incomplete=include_incomplete,
        include_reference=include_reference,
        page_token=page_token,
    )
    if start_time is not None:
        request.start_time.CopyFrom(start_time)
    if end_time is not None:
        request.end_time.CopyFrom(end_time)
    return request


def _volume_scale_for_symbol_id(catalogs: CatalogManager | None, symbol_id: int) -> int:
    scale = (
        catalogs.market_data_volume_scale_for_symbol_id(symbol_id) if catalogs is not None else None
    )
    if scale is None:
        raise PolyesterValidationError(
            f"candle volume requires a hydrated market_data_volume_scale for symbol_id {symbol_id}"
        )
    return scale


def _reference_price_scale_for_symbol_id(
    catalogs: CatalogManager | None, symbol_id: int, *, required: bool
) -> int | None:
    scale = (
        catalogs.reference_price_scale_for_symbol_id(symbol_id) if catalogs is not None else None
    )
    if scale is None and required:
        raise PolyesterValidationError(
            f"candle reference prices require reference_price_scale for symbol_id {symbol_id}"
        )
    return scale


def _index_price_scale_for_symbol_id(catalogs: CatalogManager | None, symbol_id: int) -> int:
    scale = (
        catalogs.reference_price_scale_for_symbol_id(symbol_id) if catalogs is not None else None
    )
    if scale is None:
        raise PolyesterValidationError(
            f"index price candles require reference_price_scale for symbol_id {symbol_id}"
        )
    return scale


def _quantity_scale_for_symbol_id(
    catalogs: CatalogManager | None, symbol_id: int, *, label: str
) -> int:
    scale = catalogs.base_quantity_scale_for_symbol_id(symbol_id) if catalogs is not None else None
    if scale is None:
        raise PolyesterValidationError(
            f"{label} requires a hydrated catalog quantity scale for symbol_id {symbol_id}"
        )
    return scale
