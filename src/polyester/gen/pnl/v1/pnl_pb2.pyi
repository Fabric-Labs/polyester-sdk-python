import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProfitAndLossWindow(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROFIT_AND_LOSS_WINDOW_UNSPECIFIED: _ClassVar[ProfitAndLossWindow]
    PROFIT_AND_LOSS_WINDOW_TODAY: _ClassVar[ProfitAndLossWindow]
    PROFIT_AND_LOSS_WINDOW_DAYS_7: _ClassVar[ProfitAndLossWindow]
    PROFIT_AND_LOSS_WINDOW_DAYS_30: _ClassVar[ProfitAndLossWindow]
    PROFIT_AND_LOSS_WINDOW_LIFETIME: _ClassVar[ProfitAndLossWindow]

class ProfitAndLossProduct(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROFIT_AND_LOSS_PRODUCT_UNSPECIFIED: _ClassVar[ProfitAndLossProduct]
    PROFIT_AND_LOSS_PRODUCT_SPOT: _ClassVar[ProfitAndLossProduct]

class ProfitAndLossNotice(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROFIT_AND_LOSS_NOTICE_UNSPECIFIED: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_PRICE_UNAVAILABLE: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_MARK_UNAVAILABLE: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_UNCLASSIFIED_TRANSFER: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_QUANTITY_SHORTFALL: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_EQUITY_UNAVAILABLE: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_FLOW_UNVALUED: _ClassVar[ProfitAndLossNotice]
    PROFIT_AND_LOSS_NOTICE_SHARPE_INSUFFICIENT_DAYS: _ClassVar[ProfitAndLossNotice]
PROFIT_AND_LOSS_WINDOW_UNSPECIFIED: ProfitAndLossWindow
PROFIT_AND_LOSS_WINDOW_TODAY: ProfitAndLossWindow
PROFIT_AND_LOSS_WINDOW_DAYS_7: ProfitAndLossWindow
PROFIT_AND_LOSS_WINDOW_DAYS_30: ProfitAndLossWindow
PROFIT_AND_LOSS_WINDOW_LIFETIME: ProfitAndLossWindow
PROFIT_AND_LOSS_PRODUCT_UNSPECIFIED: ProfitAndLossProduct
PROFIT_AND_LOSS_PRODUCT_SPOT: ProfitAndLossProduct
PROFIT_AND_LOSS_NOTICE_UNSPECIFIED: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_PRICE_UNAVAILABLE: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_MARK_UNAVAILABLE: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_UNCLASSIFIED_TRANSFER: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_QUANTITY_SHORTFALL: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_EQUITY_UNAVAILABLE: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_FLOW_UNVALUED: ProfitAndLossNotice
PROFIT_AND_LOSS_NOTICE_SHARPE_INSUFFICIENT_DAYS: ProfitAndLossNotice

class MarketProfitAndLoss(_message.Message):
    __slots__ = ("symbol_id", "product", "realized_pnl_usd", "fees_usd", "volume_usd", "trade_count")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    TRADE_COUNT_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    product: ProfitAndLossProduct
    realized_pnl_usd: str
    fees_usd: str
    volume_usd: str
    trade_count: int
    def __init__(self, symbol_id: _Optional[int] = ..., product: _Optional[_Union[ProfitAndLossProduct, str]] = ..., realized_pnl_usd: _Optional[str] = ..., fees_usd: _Optional[str] = ..., volume_usd: _Optional[str] = ..., trade_count: _Optional[int] = ...) -> None: ...

class HoldingProfitAndLoss(_message.Message):
    __slots__ = ("asset_id", "position_quantity", "untracked_quantity", "cost_usd", "entry_price_usd", "mark_price_usd", "unrealized_pnl_usd")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    POSITION_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    UNTRACKED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    COST_USD_FIELD_NUMBER: _ClassVar[int]
    ENTRY_PRICE_USD_FIELD_NUMBER: _ClassVar[int]
    MARK_PRICE_USD_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    position_quantity: str
    untracked_quantity: str
    cost_usd: str
    entry_price_usd: str
    mark_price_usd: str
    unrealized_pnl_usd: str
    def __init__(self, asset_id: _Optional[int] = ..., position_quantity: _Optional[str] = ..., untracked_quantity: _Optional[str] = ..., cost_usd: _Optional[str] = ..., entry_price_usd: _Optional[str] = ..., mark_price_usd: _Optional[str] = ..., unrealized_pnl_usd: _Optional[str] = ...) -> None: ...

class ProductProfitAndLoss(_message.Message):
    __slots__ = ("product", "realized_pnl_usd", "fees_usd", "volume_usd")
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    product: ProfitAndLossProduct
    realized_pnl_usd: str
    fees_usd: str
    volume_usd: str
    def __init__(self, product: _Optional[_Union[ProfitAndLossProduct, str]] = ..., realized_pnl_usd: _Optional[str] = ..., fees_usd: _Optional[str] = ..., volume_usd: _Optional[str] = ...) -> None: ...

class GetProfitAndLossRequest(_message.Message):
    __slots__ = ("subaccount_id", "window", "product", "symbol_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    window: ProfitAndLossWindow
    product: ProfitAndLossProduct
    symbol_id: int
    def __init__(self, subaccount_id: _Optional[int] = ..., window: _Optional[_Union[ProfitAndLossWindow, str]] = ..., product: _Optional[_Union[ProfitAndLossProduct, str]] = ..., symbol_id: _Optional[int] = ...) -> None: ...

class GetProfitAndLossResponse(_message.Message):
    __slots__ = ("window_start", "as_of", "mark_time", "pnl_usd", "realized_pnl_usd", "unrealized_pnl_change_usd", "unrealized_pnl_usd", "fees_usd", "volume_usd", "products", "markets", "holdings", "notices")
    WINDOW_START_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    MARK_TIME_FIELD_NUMBER: _ClassVar[int]
    PNL_USD_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_CHANGE_USD_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    PRODUCTS_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    HOLDINGS_FIELD_NUMBER: _ClassVar[int]
    NOTICES_FIELD_NUMBER: _ClassVar[int]
    window_start: _timestamp_pb2.Timestamp
    as_of: _timestamp_pb2.Timestamp
    mark_time: _timestamp_pb2.Timestamp
    pnl_usd: str
    realized_pnl_usd: str
    unrealized_pnl_change_usd: str
    unrealized_pnl_usd: str
    fees_usd: str
    volume_usd: str
    products: _containers.RepeatedCompositeFieldContainer[ProductProfitAndLoss]
    markets: _containers.RepeatedCompositeFieldContainer[MarketProfitAndLoss]
    holdings: _containers.RepeatedCompositeFieldContainer[HoldingProfitAndLoss]
    notices: _containers.RepeatedScalarFieldContainer[ProfitAndLossNotice]
    def __init__(self, window_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., mark_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pnl_usd: _Optional[str] = ..., realized_pnl_usd: _Optional[str] = ..., unrealized_pnl_change_usd: _Optional[str] = ..., unrealized_pnl_usd: _Optional[str] = ..., fees_usd: _Optional[str] = ..., volume_usd: _Optional[str] = ..., products: _Optional[_Iterable[_Union[ProductProfitAndLoss, _Mapping]]] = ..., markets: _Optional[_Iterable[_Union[MarketProfitAndLoss, _Mapping]]] = ..., holdings: _Optional[_Iterable[_Union[HoldingProfitAndLoss, _Mapping]]] = ..., notices: _Optional[_Iterable[_Union[ProfitAndLossNotice, str]]] = ...) -> None: ...

class DailyProfitAndLoss(_message.Message):
    __slots__ = ("day", "pnl_usd", "realized_pnl_usd", "unrealized_pnl_at_close_usd", "fees_usd", "volume_usd", "trade_count", "notices", "start_equity_usd", "end_equity_usd", "net_flow_usd")
    DAY_FIELD_NUMBER: _ClassVar[int]
    PNL_USD_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    UNREALIZED_PNL_AT_CLOSE_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    TRADE_COUNT_FIELD_NUMBER: _ClassVar[int]
    NOTICES_FIELD_NUMBER: _ClassVar[int]
    START_EQUITY_USD_FIELD_NUMBER: _ClassVar[int]
    END_EQUITY_USD_FIELD_NUMBER: _ClassVar[int]
    NET_FLOW_USD_FIELD_NUMBER: _ClassVar[int]
    day: _timestamp_pb2.Timestamp
    pnl_usd: str
    realized_pnl_usd: str
    unrealized_pnl_at_close_usd: str
    fees_usd: str
    volume_usd: str
    trade_count: int
    notices: _containers.RepeatedScalarFieldContainer[ProfitAndLossNotice]
    start_equity_usd: str
    end_equity_usd: str
    net_flow_usd: str
    def __init__(self, day: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pnl_usd: _Optional[str] = ..., realized_pnl_usd: _Optional[str] = ..., unrealized_pnl_at_close_usd: _Optional[str] = ..., fees_usd: _Optional[str] = ..., volume_usd: _Optional[str] = ..., trade_count: _Optional[int] = ..., notices: _Optional[_Iterable[_Union[ProfitAndLossNotice, str]]] = ..., start_equity_usd: _Optional[str] = ..., end_equity_usd: _Optional[str] = ..., net_flow_usd: _Optional[str] = ...) -> None: ...

class ListDailyProfitAndLossRequest(_message.Message):
    __slots__ = ("subaccount_id", "start_time", "end_time", "limit", "page_token")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    limit: int
    page_token: str
    def __init__(self, subaccount_id: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListDailyProfitAndLossResponse(_message.Message):
    __slots__ = ("days", "next_page_token", "as_of")
    DAYS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    days: _containers.RepeatedCompositeFieldContainer[DailyProfitAndLoss]
    next_page_token: str
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, days: _Optional[_Iterable[_Union[DailyProfitAndLoss, _Mapping]]] = ..., next_page_token: _Optional[str] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetTradingStatisticsRequest(_message.Message):
    __slots__ = ("subaccount_id", "window", "product", "symbol_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    window: ProfitAndLossWindow
    product: ProfitAndLossProduct
    symbol_id: int
    def __init__(self, subaccount_id: _Optional[int] = ..., window: _Optional[_Union[ProfitAndLossWindow, str]] = ..., product: _Optional[_Union[ProfitAndLossProduct, str]] = ..., symbol_id: _Optional[int] = ...) -> None: ...

class GetTradingStatisticsResponse(_message.Message):
    __slots__ = ("window_start", "as_of", "trade_count", "volume_usd", "fees_usd", "realized_pnl_usd", "notices", "return_pct", "max_drawdown_pct", "sharpe", "return_days")
    WINDOW_START_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    TRADE_COUNT_FIELD_NUMBER: _ClassVar[int]
    VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_USD_FIELD_NUMBER: _ClassVar[int]
    NOTICES_FIELD_NUMBER: _ClassVar[int]
    RETURN_PCT_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PCT_FIELD_NUMBER: _ClassVar[int]
    SHARPE_FIELD_NUMBER: _ClassVar[int]
    RETURN_DAYS_FIELD_NUMBER: _ClassVar[int]
    window_start: _timestamp_pb2.Timestamp
    as_of: _timestamp_pb2.Timestamp
    trade_count: int
    volume_usd: str
    fees_usd: str
    realized_pnl_usd: str
    notices: _containers.RepeatedScalarFieldContainer[ProfitAndLossNotice]
    return_pct: str
    max_drawdown_pct: str
    sharpe: str
    return_days: int
    def __init__(self, window_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., trade_count: _Optional[int] = ..., volume_usd: _Optional[str] = ..., fees_usd: _Optional[str] = ..., realized_pnl_usd: _Optional[str] = ..., notices: _Optional[_Iterable[_Union[ProfitAndLossNotice, str]]] = ..., return_pct: _Optional[str] = ..., max_drawdown_pct: _Optional[str] = ..., sharpe: _Optional[str] = ..., return_days: _Optional[int] = ...) -> None: ...
