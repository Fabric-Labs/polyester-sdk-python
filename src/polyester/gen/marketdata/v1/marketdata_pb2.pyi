import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SideFilter(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIDE_UNSPECIFIED: _ClassVar[SideFilter]
    BUY: _ClassVar[SideFilter]
    SELL: _ClassVar[SideFilter]

class Timeframe(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TIMEFRAME_UNSPECIFIED: _ClassVar[Timeframe]
    SEC_1: _ClassVar[Timeframe]
    MIN_1: _ClassVar[Timeframe]
    MIN_5: _ClassVar[Timeframe]
    MIN_15: _ClassVar[Timeframe]
    MIN_30: _ClassVar[Timeframe]
    HOUR_1: _ClassVar[Timeframe]
    HOUR_4: _ClassVar[Timeframe]
    DAY_1: _ClassVar[Timeframe]
    HOUR_12: _ClassVar[Timeframe]
    WEEK_1: _ClassVar[Timeframe]
    MONTH_1: _ClassVar[Timeframe]
SIDE_UNSPECIFIED: SideFilter
BUY: SideFilter
SELL: SideFilter
TIMEFRAME_UNSPECIFIED: Timeframe
SEC_1: Timeframe
MIN_1: Timeframe
MIN_5: Timeframe
MIN_15: Timeframe
MIN_30: Timeframe
HOUR_1: Timeframe
HOUR_4: Timeframe
DAY_1: Timeframe
HOUR_12: Timeframe
WEEK_1: Timeframe
MONTH_1: Timeframe

class GetTradesRequest(_message.Message):
    __slots__ = ("symbol_id", "limit", "start_time", "end_time", "side", "from_match_id")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    FROM_MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    limit: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    side: SideFilter
    from_match_id: int
    def __init__(self, symbol_id: _Optional[int] = ..., limit: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., side: _Optional[_Union[SideFilter, str]] = ..., from_match_id: _Optional[int] = ...) -> None: ...

class MarketTrade(_message.Message):
    __slots__ = ("symbol_id", "match_id", "is_buy", "price_ticks", "qty_scaled", "ts_ns")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    IS_BUY_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    match_id: int
    is_buy: bool
    price_ticks: int
    qty_scaled: int
    ts_ns: int
    def __init__(self, symbol_id: _Optional[int] = ..., match_id: _Optional[int] = ..., is_buy: _Optional[bool] = ..., price_ticks: _Optional[int] = ..., qty_scaled: _Optional[int] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class GetTradesResponse(_message.Message):
    __slots__ = ("trades", "next_match_id")
    TRADES_FIELD_NUMBER: _ClassVar[int]
    NEXT_MATCH_ID_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[MarketTrade]
    next_match_id: int
    def __init__(self, trades: _Optional[_Iterable[_Union[MarketTrade, _Mapping]]] = ..., next_match_id: _Optional[int] = ...) -> None: ...

class GetCandlesRequest(_message.Message):
    __slots__ = ("symbol_id", "timeframe", "limit", "start_time", "end_time", "include_incomplete", "include_reference")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_INCOMPLETE_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_REFERENCE_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    timeframe: Timeframe
    limit: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    include_incomplete: bool
    include_reference: bool
    def __init__(self, symbol_id: _Optional[int] = ..., timeframe: _Optional[_Union[Timeframe, str]] = ..., limit: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., include_incomplete: _Optional[bool] = ..., include_reference: _Optional[bool] = ...) -> None: ...

class GetCandlesColumnsRequest(_message.Message):
    __slots__ = ("symbol_id", "timeframe", "limit", "start_time", "end_time", "include_incomplete", "include_reference")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_INCOMPLETE_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_REFERENCE_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    timeframe: Timeframe
    limit: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    include_incomplete: bool
    include_reference: bool
    def __init__(self, symbol_id: _Optional[int] = ..., timeframe: _Optional[_Union[Timeframe, str]] = ..., limit: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., include_incomplete: _Optional[bool] = ..., include_reference: _Optional[bool] = ...) -> None: ...

class CandlePoint(_message.Message):
    __slots__ = ("ts_sec", "open", "high", "low", "close", "volume", "is_closed")
    TS_SEC_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    IS_CLOSED_FIELD_NUMBER: _ClassVar[int]
    ts_sec: int
    open: int
    high: int
    low: int
    close: int
    volume: int
    is_closed: bool
    def __init__(self, ts_sec: _Optional[int] = ..., open: _Optional[int] = ..., high: _Optional[int] = ..., low: _Optional[int] = ..., close: _Optional[int] = ..., volume: _Optional[int] = ..., is_closed: _Optional[bool] = ...) -> None: ...

class GetCandlesResponse(_message.Message):
    __slots__ = ("symbol_id", "timeframe", "candles", "reference_candles")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    CANDLES_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_CANDLES_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    timeframe: Timeframe
    candles: _containers.RepeatedCompositeFieldContainer[CandlePoint]
    reference_candles: _containers.RepeatedCompositeFieldContainer[CandlePoint]
    def __init__(self, symbol_id: _Optional[int] = ..., timeframe: _Optional[_Union[Timeframe, str]] = ..., candles: _Optional[_Iterable[_Union[CandlePoint, _Mapping]]] = ..., reference_candles: _Optional[_Iterable[_Union[CandlePoint, _Mapping]]] = ...) -> None: ...

class GetCandlesColumnsResponse(_message.Message):
    __slots__ = ("symbol_id", "timeframe", "ts_sec", "open", "high", "low", "close", "volume", "reference_ts_sec", "reference_open", "reference_high", "reference_low", "reference_close", "reference_volume")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    TS_SEC_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_TS_SEC_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_OPEN_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_HIGH_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_LOW_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_CLOSE_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_VOLUME_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    timeframe: Timeframe
    ts_sec: _containers.RepeatedScalarFieldContainer[int]
    open: _containers.RepeatedScalarFieldContainer[int]
    high: _containers.RepeatedScalarFieldContainer[int]
    low: _containers.RepeatedScalarFieldContainer[int]
    close: _containers.RepeatedScalarFieldContainer[int]
    volume: _containers.RepeatedScalarFieldContainer[int]
    reference_ts_sec: _containers.RepeatedScalarFieldContainer[int]
    reference_open: _containers.RepeatedScalarFieldContainer[int]
    reference_high: _containers.RepeatedScalarFieldContainer[int]
    reference_low: _containers.RepeatedScalarFieldContainer[int]
    reference_close: _containers.RepeatedScalarFieldContainer[int]
    reference_volume: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, symbol_id: _Optional[int] = ..., timeframe: _Optional[_Union[Timeframe, str]] = ..., ts_sec: _Optional[_Iterable[int]] = ..., open: _Optional[_Iterable[int]] = ..., high: _Optional[_Iterable[int]] = ..., low: _Optional[_Iterable[int]] = ..., close: _Optional[_Iterable[int]] = ..., volume: _Optional[_Iterable[int]] = ..., reference_ts_sec: _Optional[_Iterable[int]] = ..., reference_open: _Optional[_Iterable[int]] = ..., reference_high: _Optional[_Iterable[int]] = ..., reference_low: _Optional[_Iterable[int]] = ..., reference_close: _Optional[_Iterable[int]] = ..., reference_volume: _Optional[_Iterable[int]] = ...) -> None: ...

class Candle(_message.Message):
    __slots__ = ("symbol_id", "timeframe", "ts_sec", "open", "high", "low", "close", "volume")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    TS_SEC_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    timeframe: Timeframe
    ts_sec: int
    open: int
    high: int
    low: int
    close: int
    volume: int
    def __init__(self, symbol_id: _Optional[int] = ..., timeframe: _Optional[_Union[Timeframe, str]] = ..., ts_sec: _Optional[int] = ..., open: _Optional[int] = ..., high: _Optional[int] = ..., low: _Optional[int] = ..., close: _Optional[int] = ..., volume: _Optional[int] = ...) -> None: ...

class AssetConfig(_message.Message):
    __slots__ = ("asset", "ledger_id", "name", "quantity_display_decimals", "quantity_scale")
    ASSET_FIELD_NUMBER: _ClassVar[int]
    LEDGER_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_DISPLAY_DECIMALS_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_SCALE_FIELD_NUMBER: _ClassVar[int]
    asset: str
    ledger_id: int
    name: str
    quantity_display_decimals: int
    quantity_scale: int
    def __init__(self, asset: _Optional[str] = ..., ledger_id: _Optional[int] = ..., name: _Optional[str] = ..., quantity_display_decimals: _Optional[int] = ..., quantity_scale: _Optional[int] = ...) -> None: ...

class PairMarketdataConfig(_message.Message):
    __slots__ = ("orderbook_price_buckets",)
    ORDERBOOK_PRICE_BUCKETS_FIELD_NUMBER: _ClassVar[int]
    orderbook_price_buckets: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, orderbook_price_buckets: _Optional[_Iterable[float]] = ...) -> None: ...

class PairConfig(_message.Message):
    __slots__ = ("symbol_id", "symbol", "base_asset", "quote_asset", "tick_size", "step_size", "min_notional_quote", "min_qty_base", "allow_buy_fee_from_received", "base_quantity_scale", "quote_quantity_scale", "marketdata", "listing_at", "delisting_at", "status", "default_market_slippage_bps_buy", "default_market_slippage_bps_sell", "max_client_ref_drift_bps")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    BASE_ASSET_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    TICK_SIZE_FIELD_NUMBER: _ClassVar[int]
    STEP_SIZE_FIELD_NUMBER: _ClassVar[int]
    MIN_NOTIONAL_QUOTE_FIELD_NUMBER: _ClassVar[int]
    MIN_QTY_BASE_FIELD_NUMBER: _ClassVar[int]
    ALLOW_BUY_FEE_FROM_RECEIVED_FIELD_NUMBER: _ClassVar[int]
    BASE_QUANTITY_SCALE_FIELD_NUMBER: _ClassVar[int]
    QUOTE_QUANTITY_SCALE_FIELD_NUMBER: _ClassVar[int]
    MARKETDATA_FIELD_NUMBER: _ClassVar[int]
    LISTING_AT_FIELD_NUMBER: _ClassVar[int]
    DELISTING_AT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_MARKET_SLIPPAGE_BPS_BUY_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_MARKET_SLIPPAGE_BPS_SELL_FIELD_NUMBER: _ClassVar[int]
    MAX_CLIENT_REF_DRIFT_BPS_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    symbol: str
    base_asset: str
    quote_asset: str
    tick_size: str
    step_size: str
    min_notional_quote: str
    min_qty_base: str
    allow_buy_fee_from_received: bool
    base_quantity_scale: int
    quote_quantity_scale: int
    marketdata: PairMarketdataConfig
    listing_at: _timestamp_pb2.Timestamp
    delisting_at: _timestamp_pb2.Timestamp
    status: str
    default_market_slippage_bps_buy: int
    default_market_slippage_bps_sell: int
    max_client_ref_drift_bps: int
    def __init__(self, symbol_id: _Optional[int] = ..., symbol: _Optional[str] = ..., base_asset: _Optional[str] = ..., quote_asset: _Optional[str] = ..., tick_size: _Optional[str] = ..., step_size: _Optional[str] = ..., min_notional_quote: _Optional[str] = ..., min_qty_base: _Optional[str] = ..., allow_buy_fee_from_received: _Optional[bool] = ..., base_quantity_scale: _Optional[int] = ..., quote_quantity_scale: _Optional[int] = ..., marketdata: _Optional[_Union[PairMarketdataConfig, _Mapping]] = ..., listing_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., delisting_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., status: _Optional[str] = ..., default_market_slippage_bps_buy: _Optional[int] = ..., default_market_slippage_bps_sell: _Optional[int] = ..., max_client_ref_drift_bps: _Optional[int] = ...) -> None: ...

class GetSpotConfigRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSpotConfigResponse(_message.Message):
    __slots__ = ("assets", "pairs", "ts_sec")
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    PAIRS_FIELD_NUMBER: _ClassVar[int]
    TS_SEC_FIELD_NUMBER: _ClassVar[int]
    assets: _containers.RepeatedCompositeFieldContainer[AssetConfig]
    pairs: _containers.RepeatedCompositeFieldContainer[PairConfig]
    ts_sec: int
    def __init__(self, assets: _Optional[_Iterable[_Union[AssetConfig, _Mapping]]] = ..., pairs: _Optional[_Iterable[_Union[PairConfig, _Mapping]]] = ..., ts_sec: _Optional[int] = ...) -> None: ...
