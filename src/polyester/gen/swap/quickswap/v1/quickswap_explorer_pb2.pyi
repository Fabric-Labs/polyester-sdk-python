import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.swap.quickswap.v1 import quickswap_pb2 as _quickswap_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class QuickSwapStatsWindow(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATS_WINDOW_UNSPECIFIED: _ClassVar[QuickSwapStatsWindow]
    LAST_24_HOURS: _ClassVar[QuickSwapStatsWindow]
    LAST_7_DAYS: _ClassVar[QuickSwapStatsWindow]
    LAST_30_DAYS: _ClassVar[QuickSwapStatsWindow]
    LAST_90_DAYS: _ClassVar[QuickSwapStatsWindow]
    LAST_26_WEEKS: _ClassVar[QuickSwapStatsWindow]

class QuickSwapStatsBucketSize(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BUCKET_SIZE_UNSPECIFIED: _ClassVar[QuickSwapStatsBucketSize]
    HOURLY: _ClassVar[QuickSwapStatsBucketSize]
    DAILY: _ClassVar[QuickSwapStatsBucketSize]
    WEEKLY: _ClassVar[QuickSwapStatsBucketSize]
STATS_WINDOW_UNSPECIFIED: QuickSwapStatsWindow
LAST_24_HOURS: QuickSwapStatsWindow
LAST_7_DAYS: QuickSwapStatsWindow
LAST_30_DAYS: QuickSwapStatsWindow
LAST_90_DAYS: QuickSwapStatsWindow
LAST_26_WEEKS: QuickSwapStatsWindow
BUCKET_SIZE_UNSPECIFIED: QuickSwapStatsBucketSize
HOURLY: QuickSwapStatsBucketSize
DAILY: QuickSwapStatsBucketSize
WEEKLY: QuickSwapStatsBucketSize

class ExplorerRouteLeg(_message.Message):
    __slots__ = ("symbol_id",)
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    def __init__(self, symbol_id: _Optional[int] = ...) -> None: ...

class ExplorerDeposit(_message.Message):
    __slots__ = ("tx_hash", "address")
    TX_HASH_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    tx_hash: str
    address: str
    def __init__(self, tx_hash: _Optional[str] = ..., address: _Optional[str] = ...) -> None: ...

class ExplorerWithdrawal(_message.Message):
    __slots__ = ("tx_hash", "address")
    TX_HASH_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    tx_hash: str
    address: str
    def __init__(self, tx_hash: _Optional[str] = ..., address: _Optional[str] = ...) -> None: ...

class ExplorerQuickSwap(_message.Message):
    __slots__ = ("swap_id", "completed_at", "source_zipped_asset_id", "destination_zipped_asset_id", "source_amount", "destination_amount", "legs", "deposits", "withdrawals", "source_value_usd", "destination_value_usd")
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    LEGS_FIELD_NUMBER: _ClassVar[int]
    DEPOSITS_FIELD_NUMBER: _ClassVar[int]
    WITHDRAWALS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    completed_at: _timestamp_pb2.Timestamp
    source_zipped_asset_id: int
    destination_zipped_asset_id: int
    source_amount: _quickswap_pb2.TokenAmount
    destination_amount: _quickswap_pb2.TokenAmount
    legs: _containers.RepeatedCompositeFieldContainer[ExplorerRouteLeg]
    deposits: _containers.RepeatedCompositeFieldContainer[ExplorerDeposit]
    withdrawals: _containers.RepeatedCompositeFieldContainer[ExplorerWithdrawal]
    source_value_usd: _quickswap_pb2.TokenAmount
    destination_value_usd: _quickswap_pb2.TokenAmount
    def __init__(self, swap_id: _Optional[int] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., source_zipped_asset_id: _Optional[int] = ..., destination_zipped_asset_id: _Optional[int] = ..., source_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., destination_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., legs: _Optional[_Iterable[_Union[ExplorerRouteLeg, _Mapping]]] = ..., deposits: _Optional[_Iterable[_Union[ExplorerDeposit, _Mapping]]] = ..., withdrawals: _Optional[_Iterable[_Union[ExplorerWithdrawal, _Mapping]]] = ..., source_value_usd: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., destination_value_usd: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class ListCompletedQuickSwapsRequest(_message.Message):
    __slots__ = ("source_zipped_asset_ids", "destination_zipped_asset_ids", "limit", "page_token", "source_asset_ids", "destination_asset_ids", "min_source_value_usd", "max_source_value_usd")
    SOURCE_ZIPPED_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ZIPPED_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    MIN_SOURCE_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    MAX_SOURCE_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    source_zipped_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    destination_zipped_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    limit: int
    page_token: str
    source_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    destination_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    min_source_value_usd: str
    max_source_value_usd: str
    def __init__(self, source_zipped_asset_ids: _Optional[_Iterable[int]] = ..., destination_zipped_asset_ids: _Optional[_Iterable[int]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ..., source_asset_ids: _Optional[_Iterable[int]] = ..., destination_asset_ids: _Optional[_Iterable[int]] = ..., min_source_value_usd: _Optional[str] = ..., max_source_value_usd: _Optional[str] = ...) -> None: ...

class ListCompletedQuickSwapsResponse(_message.Message):
    __slots__ = ("quick_swaps", "next_page_token")
    QUICK_SWAPS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    quick_swaps: _containers.RepeatedCompositeFieldContainer[ExplorerQuickSwap]
    next_page_token: str
    def __init__(self, quick_swaps: _Optional[_Iterable[_Union[ExplorerQuickSwap, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetCompletedQuickSwapRequest(_message.Message):
    __slots__ = ("swap_id",)
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    def __init__(self, swap_id: _Optional[int] = ...) -> None: ...

class GetCompletedQuickSwapResponse(_message.Message):
    __slots__ = ("quick_swap",)
    QUICK_SWAP_FIELD_NUMBER: _ClassVar[int]
    quick_swap: ExplorerQuickSwap
    def __init__(self, quick_swap: _Optional[_Union[ExplorerQuickSwap, _Mapping]] = ...) -> None: ...

class QuickSwapStatsTotals(_message.Message):
    __slots__ = ("swap_count", "unvalued_count", "source_volume_usd", "destination_volume_usd", "fees_usd", "source_volume", "destination_volume", "fees", "fees_usd_by_asset", "fees_unvalued_count")
    SWAP_COUNT_FIELD_NUMBER: _ClassVar[int]
    UNVALUED_COUNT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VOLUME_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_VOLUME_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_BY_ASSET_FIELD_NUMBER: _ClassVar[int]
    FEES_UNVALUED_COUNT_FIELD_NUMBER: _ClassVar[int]
    swap_count: int
    unvalued_count: int
    source_volume_usd: str
    destination_volume_usd: str
    fees_usd: str
    source_volume: _containers.RepeatedScalarFieldContainer[str]
    destination_volume: _containers.RepeatedScalarFieldContainer[str]
    fees: _containers.RepeatedScalarFieldContainer[str]
    fees_usd_by_asset: _containers.RepeatedScalarFieldContainer[str]
    fees_unvalued_count: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, swap_count: _Optional[int] = ..., unvalued_count: _Optional[int] = ..., source_volume_usd: _Optional[str] = ..., destination_volume_usd: _Optional[str] = ..., fees_usd: _Optional[str] = ..., source_volume: _Optional[_Iterable[str]] = ..., destination_volume: _Optional[_Iterable[str]] = ..., fees: _Optional[_Iterable[str]] = ..., fees_usd_by_asset: _Optional[_Iterable[str]] = ..., fees_unvalued_count: _Optional[_Iterable[int]] = ...) -> None: ...

class QuickSwapStatsBuckets(_message.Message):
    __slots__ = ("swap_count", "unvalued_count", "source_volume_usd", "destination_volume_usd", "fees_usd", "fees_unvalued_count")
    SWAP_COUNT_FIELD_NUMBER: _ClassVar[int]
    UNVALUED_COUNT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_USD_FIELD_NUMBER: _ClassVar[int]
    FEES_UNVALUED_COUNT_FIELD_NUMBER: _ClassVar[int]
    swap_count: _containers.RepeatedScalarFieldContainer[int]
    unvalued_count: _containers.RepeatedScalarFieldContainer[int]
    source_volume_usd: _containers.RepeatedScalarFieldContainer[str]
    destination_volume_usd: _containers.RepeatedScalarFieldContainer[str]
    fees_usd: _containers.RepeatedScalarFieldContainer[str]
    fees_unvalued_count: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, swap_count: _Optional[_Iterable[int]] = ..., unvalued_count: _Optional[_Iterable[int]] = ..., source_volume_usd: _Optional[_Iterable[str]] = ..., destination_volume_usd: _Optional[_Iterable[str]] = ..., fees_usd: _Optional[_Iterable[str]] = ..., fees_unvalued_count: _Optional[_Iterable[int]] = ...) -> None: ...

class QuickSwapStatsRoutes(_message.Message):
    __slots__ = ("source_zipped_asset_ids", "destination_zipped_asset_ids", "swap_count", "unvalued_count", "source_volume", "destination_volume", "source_volume_usd", "destination_volume_usd")
    SOURCE_ZIPPED_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ZIPPED_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    SWAP_COUNT_FIELD_NUMBER: _ClassVar[int]
    UNVALUED_COUNT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VOLUME_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_VOLUME_FIELD_NUMBER: _ClassVar[int]
    SOURCE_VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_VOLUME_USD_FIELD_NUMBER: _ClassVar[int]
    source_zipped_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    destination_zipped_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    swap_count: _containers.RepeatedScalarFieldContainer[int]
    unvalued_count: _containers.RepeatedScalarFieldContainer[int]
    source_volume: _containers.RepeatedScalarFieldContainer[str]
    destination_volume: _containers.RepeatedScalarFieldContainer[str]
    source_volume_usd: _containers.RepeatedScalarFieldContainer[str]
    destination_volume_usd: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, source_zipped_asset_ids: _Optional[_Iterable[int]] = ..., destination_zipped_asset_ids: _Optional[_Iterable[int]] = ..., swap_count: _Optional[_Iterable[int]] = ..., unvalued_count: _Optional[_Iterable[int]] = ..., source_volume: _Optional[_Iterable[str]] = ..., destination_volume: _Optional[_Iterable[str]] = ..., source_volume_usd: _Optional[_Iterable[str]] = ..., destination_volume_usd: _Optional[_Iterable[str]] = ...) -> None: ...

class GetQuickSwapStatsRequest(_message.Message):
    __slots__ = ("window",)
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    window: QuickSwapStatsWindow
    def __init__(self, window: _Optional[_Union[QuickSwapStatsWindow, str]] = ...) -> None: ...

class GetQuickSwapStatsResponse(_message.Message):
    __slots__ = ("window", "start_time", "end_time", "bucket_size", "zipped_asset_ids", "zipped_asset_decimals", "fee_asset_ids", "totals", "previous_totals", "buckets", "routes", "as_of")
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    BUCKET_SIZE_FIELD_NUMBER: _ClassVar[int]
    ZIPPED_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    ZIPPED_ASSET_DECIMALS_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    TOTALS_FIELD_NUMBER: _ClassVar[int]
    PREVIOUS_TOTALS_FIELD_NUMBER: _ClassVar[int]
    BUCKETS_FIELD_NUMBER: _ClassVar[int]
    ROUTES_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    window: QuickSwapStatsWindow
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    bucket_size: QuickSwapStatsBucketSize
    zipped_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    zipped_asset_decimals: _containers.RepeatedScalarFieldContainer[int]
    fee_asset_ids: _containers.RepeatedScalarFieldContainer[int]
    totals: QuickSwapStatsTotals
    previous_totals: QuickSwapStatsTotals
    buckets: QuickSwapStatsBuckets
    routes: QuickSwapStatsRoutes
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, window: _Optional[_Union[QuickSwapStatsWindow, str]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bucket_size: _Optional[_Union[QuickSwapStatsBucketSize, str]] = ..., zipped_asset_ids: _Optional[_Iterable[int]] = ..., zipped_asset_decimals: _Optional[_Iterable[int]] = ..., fee_asset_ids: _Optional[_Iterable[int]] = ..., totals: _Optional[_Union[QuickSwapStatsTotals, _Mapping]] = ..., previous_totals: _Optional[_Union[QuickSwapStatsTotals, _Mapping]] = ..., buckets: _Optional[_Union[QuickSwapStatsBuckets, _Mapping]] = ..., routes: _Optional[_Union[QuickSwapStatsRoutes, _Mapping]] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
