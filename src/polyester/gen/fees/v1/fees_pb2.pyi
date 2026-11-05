import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SpotFeeRate(_message.Message):
    __slots__ = ("symbol_id", "maker_fee_rate_percent", "taker_fee_rate_percent", "vip_tier", "reserve_fee_rate_percent", "post_only_reserve_fee_rate_percent", "breakdown", "next_change_at")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    MAKER_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    TAKER_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    VIP_TIER_FIELD_NUMBER: _ClassVar[int]
    RESERVE_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_RESERVE_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    BREAKDOWN_FIELD_NUMBER: _ClassVar[int]
    NEXT_CHANGE_AT_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    maker_fee_rate_percent: str
    taker_fee_rate_percent: str
    vip_tier: int
    reserve_fee_rate_percent: str
    post_only_reserve_fee_rate_percent: str
    breakdown: SpotFeeRateBreakdown
    next_change_at: _timestamp_pb2.Timestamp
    def __init__(self, symbol_id: _Optional[int] = ..., maker_fee_rate_percent: _Optional[str] = ..., taker_fee_rate_percent: _Optional[str] = ..., vip_tier: _Optional[int] = ..., reserve_fee_rate_percent: _Optional[str] = ..., post_only_reserve_fee_rate_percent: _Optional[str] = ..., breakdown: _Optional[_Union[SpotFeeRateBreakdown, _Mapping]] = ..., next_change_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SpotFeeRateBreakdown(_message.Message):
    __slots__ = ("tier_maker_fee_rate_percent", "tier_taker_fee_rate_percent", "market_multiplier", "account_discounts", "referral_discount")
    TIER_MAKER_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    TIER_TAKER_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MARKET_MULTIPLIER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_DISCOUNTS_FIELD_NUMBER: _ClassVar[int]
    REFERRAL_DISCOUNT_FIELD_NUMBER: _ClassVar[int]
    tier_maker_fee_rate_percent: str
    tier_taker_fee_rate_percent: str
    market_multiplier: SpotFeeMultiplier
    account_discounts: _containers.RepeatedCompositeFieldContainer[SpotFeeDiscount]
    referral_discount: SpotFeeDiscount
    def __init__(self, tier_maker_fee_rate_percent: _Optional[str] = ..., tier_taker_fee_rate_percent: _Optional[str] = ..., market_multiplier: _Optional[_Union[SpotFeeMultiplier, _Mapping]] = ..., account_discounts: _Optional[_Iterable[_Union[SpotFeeDiscount, _Mapping]]] = ..., referral_discount: _Optional[_Union[SpotFeeDiscount, _Mapping]] = ...) -> None: ...

class SpotFeeMultiplier(_message.Message):
    __slots__ = ("maker_multiplier_percent", "taker_multiplier_percent", "effective_from", "effective_to")
    MAKER_MULTIPLIER_PERCENT_FIELD_NUMBER: _ClassVar[int]
    TAKER_MULTIPLIER_PERCENT_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_FROM_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_TO_FIELD_NUMBER: _ClassVar[int]
    maker_multiplier_percent: str
    taker_multiplier_percent: str
    effective_from: _timestamp_pb2.Timestamp
    effective_to: _timestamp_pb2.Timestamp
    def __init__(self, maker_multiplier_percent: _Optional[str] = ..., taker_multiplier_percent: _Optional[str] = ..., effective_from: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., effective_to: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SpotFeeDiscount(_message.Message):
    __slots__ = ("maker_discount_percent", "taker_discount_percent", "all_markets", "effective_from", "effective_to")
    MAKER_DISCOUNT_PERCENT_FIELD_NUMBER: _ClassVar[int]
    TAKER_DISCOUNT_PERCENT_FIELD_NUMBER: _ClassVar[int]
    ALL_MARKETS_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_FROM_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_TO_FIELD_NUMBER: _ClassVar[int]
    maker_discount_percent: str
    taker_discount_percent: str
    all_markets: bool
    effective_from: _timestamp_pb2.Timestamp
    effective_to: _timestamp_pb2.Timestamp
    def __init__(self, maker_discount_percent: _Optional[str] = ..., taker_discount_percent: _Optional[str] = ..., all_markets: _Optional[bool] = ..., effective_from: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., effective_to: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetSpotFeeRatesRequest(_message.Message):
    __slots__ = ("subaccount_id", "symbol_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol_id: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol_id: _Optional[_Iterable[int]] = ...) -> None: ...

class GetSpotFeeRatesResponse(_message.Message):
    __slots__ = ("fee_rates",)
    FEE_RATES_FIELD_NUMBER: _ClassVar[int]
    fee_rates: _containers.RepeatedCompositeFieldContainer[SpotFeeRate]
    def __init__(self, fee_rates: _Optional[_Iterable[_Union[SpotFeeRate, _Mapping]]] = ...) -> None: ...
