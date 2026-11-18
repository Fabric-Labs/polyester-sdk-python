import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AssetDataSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SOURCE_UNSPECIFIED: _ClassVar[AssetDataSource]
    COINMARKETCAP: _ClassVar[AssetDataSource]
    POLYESTER: _ClassVar[AssetDataSource]
SOURCE_UNSPECIFIED: AssetDataSource
COINMARKETCAP: AssetDataSource
POLYESTER: AssetDataSource

class AssetIssuePrice(_message.Message):
    __slots__ = ("amount", "currency")
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    amount: str
    currency: str
    def __init__(self, amount: _Optional[str] = ..., currency: _Optional[str] = ...) -> None: ...

class AssetEditorialInfo(_message.Message):
    __slots__ = ("description", "website_url", "whitepaper_url", "explorer_urls", "x_url", "telegram_url", "discord_url", "github_url", "issue_date", "issue_price")
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    WEBSITE_URL_FIELD_NUMBER: _ClassVar[int]
    WHITEPAPER_URL_FIELD_NUMBER: _ClassVar[int]
    EXPLORER_URLS_FIELD_NUMBER: _ClassVar[int]
    X_URL_FIELD_NUMBER: _ClassVar[int]
    TELEGRAM_URL_FIELD_NUMBER: _ClassVar[int]
    DISCORD_URL_FIELD_NUMBER: _ClassVar[int]
    GITHUB_URL_FIELD_NUMBER: _ClassVar[int]
    ISSUE_DATE_FIELD_NUMBER: _ClassVar[int]
    ISSUE_PRICE_FIELD_NUMBER: _ClassVar[int]
    description: str
    website_url: str
    whitepaper_url: str
    explorer_urls: _containers.RepeatedScalarFieldContainer[str]
    x_url: str
    telegram_url: str
    discord_url: str
    github_url: str
    issue_date: str
    issue_price: AssetIssuePrice
    def __init__(self, description: _Optional[str] = ..., website_url: _Optional[str] = ..., whitepaper_url: _Optional[str] = ..., explorer_urls: _Optional[_Iterable[str]] = ..., x_url: _Optional[str] = ..., telegram_url: _Optional[str] = ..., discord_url: _Optional[str] = ..., github_url: _Optional[str] = ..., issue_date: _Optional[str] = ..., issue_price: _Optional[_Union[AssetIssuePrice, _Mapping]] = ...) -> None: ...

class AssetMarketValue(_message.Message):
    __slots__ = ("value", "source", "as_of")
    VALUE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    value: str
    source: AssetDataSource
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, value: _Optional[str] = ..., source: _Optional[_Union[AssetDataSource, str]] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AssetMarketFlag(_message.Message):
    __slots__ = ("source", "as_of")
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    source: AssetDataSource
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, source: _Optional[_Union[AssetDataSource, str]] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AssetMarketStats(_message.Message):
    __slots__ = ("circulating_supply", "total_supply", "max_supply", "max_supply_unlimited", "market_cap_usd", "fully_diluted_market_cap_usd", "rank")
    CIRCULATING_SUPPLY_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SUPPLY_FIELD_NUMBER: _ClassVar[int]
    MAX_SUPPLY_FIELD_NUMBER: _ClassVar[int]
    MAX_SUPPLY_UNLIMITED_FIELD_NUMBER: _ClassVar[int]
    MARKET_CAP_USD_FIELD_NUMBER: _ClassVar[int]
    FULLY_DILUTED_MARKET_CAP_USD_FIELD_NUMBER: _ClassVar[int]
    RANK_FIELD_NUMBER: _ClassVar[int]
    circulating_supply: AssetMarketValue
    total_supply: AssetMarketValue
    max_supply: AssetMarketValue
    max_supply_unlimited: AssetMarketFlag
    market_cap_usd: AssetMarketValue
    fully_diluted_market_cap_usd: AssetMarketValue
    rank: AssetMarketValue
    def __init__(self, circulating_supply: _Optional[_Union[AssetMarketValue, _Mapping]] = ..., total_supply: _Optional[_Union[AssetMarketValue, _Mapping]] = ..., max_supply: _Optional[_Union[AssetMarketValue, _Mapping]] = ..., max_supply_unlimited: _Optional[_Union[AssetMarketFlag, _Mapping]] = ..., market_cap_usd: _Optional[_Union[AssetMarketValue, _Mapping]] = ..., fully_diluted_market_cap_usd: _Optional[_Union[AssetMarketValue, _Mapping]] = ..., rank: _Optional[_Union[AssetMarketValue, _Mapping]] = ...) -> None: ...

class AssetInfo(_message.Message):
    __slots__ = ("asset_id", "editorial", "editorial_updated_at", "market_stats")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    EDITORIAL_FIELD_NUMBER: _ClassVar[int]
    EDITORIAL_UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    MARKET_STATS_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    editorial: AssetEditorialInfo
    editorial_updated_at: _timestamp_pb2.Timestamp
    market_stats: AssetMarketStats
    def __init__(self, asset_id: _Optional[int] = ..., editorial: _Optional[_Union[AssetEditorialInfo, _Mapping]] = ..., editorial_updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., market_stats: _Optional[_Union[AssetMarketStats, _Mapping]] = ...) -> None: ...

class ListAssetInfoRequest(_message.Message):
    __slots__ = ("asset_ids",)
    ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    asset_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, asset_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class ListAssetInfoResponse(_message.Message):
    __slots__ = ("asset_info",)
    ASSET_INFO_FIELD_NUMBER: _ClassVar[int]
    asset_info: _containers.RepeatedCompositeFieldContainer[AssetInfo]
    def __init__(self, asset_info: _Optional[_Iterable[_Union[AssetInfo, _Mapping]]] = ...) -> None: ...
