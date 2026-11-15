import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.polyester.type.v1 import u128_pb2 as _u128_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as _internal_transfer_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DustAssetEligibility(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DUST_ASSET_ELIGIBILITY_UNSPECIFIED: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_ELIGIBLE: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_TARGET_ASSET: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_TRADABLE: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_ABOVE_VALUE_LIMIT: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_NO_PRICE: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_UNSUPPORTED_ASSET: _ClassVar[DustAssetEligibility]
    DUST_ASSET_ELIGIBILITY_SOURCE_LIMIT: _ClassVar[DustAssetEligibility]

class DustConversionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DUST_CONVERSION_STATE_UNSPECIFIED: _ClassVar[DustConversionState]
    DUST_CONVERSION_STATE_PROCESSING: _ClassVar[DustConversionState]
    DUST_CONVERSION_STATE_COMPLETED: _ClassVar[DustConversionState]
    DUST_CONVERSION_STATE_REFUSED: _ClassVar[DustConversionState]
DUST_ASSET_ELIGIBILITY_UNSPECIFIED: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_ELIGIBLE: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_TARGET_ASSET: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_TRADABLE: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_ABOVE_VALUE_LIMIT: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_NO_PRICE: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_UNSUPPORTED_ASSET: DustAssetEligibility
DUST_ASSET_ELIGIBILITY_SOURCE_LIMIT: DustAssetEligibility
DUST_CONVERSION_STATE_UNSPECIFIED: DustConversionState
DUST_CONVERSION_STATE_PROCESSING: DustConversionState
DUST_CONVERSION_STATE_COMPLETED: DustConversionState
DUST_CONVERSION_STATE_REFUSED: DustConversionState

class DustBalance(_message.Message):
    __slots__ = ("asset_id", "amount_e18", "eligibility", "usd_value_e18")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    ELIGIBILITY_FIELD_NUMBER: _ClassVar[int]
    USD_VALUE_E18_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    amount_e18: _u128_pb2.U128
    eligibility: DustAssetEligibility
    usd_value_e18: _u128_pb2.U128
    def __init__(self, asset_id: _Optional[int] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., eligibility: _Optional[_Union[DustAssetEligibility, str]] = ..., usd_value_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ...) -> None: ...

class DustAssetPrice(_message.Message):
    __slots__ = ("asset_id", "price_ticks", "price_scale", "as_of")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    PRICE_SCALE_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    price_ticks: int
    price_scale: int
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, asset_id: _Optional[int] = ..., price_ticks: _Optional[int] = ..., price_scale: _Optional[int] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DustSource(_message.Message):
    __slots__ = ("asset_id", "amount_e18")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    amount_e18: _u128_pb2.U128
    def __init__(self, asset_id: _Optional[int] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ...) -> None: ...

class DustConversion(_message.Message):
    __slots__ = ("conversion_id", "quote_id", "state", "refusal_code", "target_asset_id", "sources", "payout_e18", "quoted_payout_e18", "fee_e18", "fee_bps", "created_at", "completed_at")
    CONVERSION_ID_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REFUSAL_CODE_FIELD_NUMBER: _ClassVar[int]
    TARGET_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    PAYOUT_E18_FIELD_NUMBER: _ClassVar[int]
    QUOTED_PAYOUT_E18_FIELD_NUMBER: _ClassVar[int]
    FEE_E18_FIELD_NUMBER: _ClassVar[int]
    FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    conversion_id: str
    quote_id: str
    state: DustConversionState
    refusal_code: _internal_transfer_pb2.ErrorCode
    target_asset_id: int
    sources: _containers.RepeatedCompositeFieldContainer[DustSource]
    payout_e18: _u128_pb2.U128
    quoted_payout_e18: _u128_pb2.U128
    fee_e18: _u128_pb2.U128
    fee_bps: int
    created_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    def __init__(self, conversion_id: _Optional[str] = ..., quote_id: _Optional[str] = ..., state: _Optional[_Union[DustConversionState, str]] = ..., refusal_code: _Optional[_Union[_internal_transfer_pb2.ErrorCode, str]] = ..., target_asset_id: _Optional[int] = ..., sources: _Optional[_Iterable[_Union[DustSource, _Mapping]]] = ..., payout_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., quoted_payout_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., fee_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., fee_bps: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListDustBalancesRequest(_message.Message):
    __slots__ = ("subaccount_id", "target_asset_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    target_asset_id: int
    def __init__(self, subaccount_id: _Optional[int] = ..., target_asset_id: _Optional[int] = ...) -> None: ...

class ListDustBalancesResponse(_message.Message):
    __slots__ = ("target_asset_id", "targets", "fee_bps", "balances", "gross_usd_e18", "payout_e18", "target_available")
    TARGET_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    TARGETS_FIELD_NUMBER: _ClassVar[int]
    FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    BALANCES_FIELD_NUMBER: _ClassVar[int]
    GROSS_USD_E18_FIELD_NUMBER: _ClassVar[int]
    PAYOUT_E18_FIELD_NUMBER: _ClassVar[int]
    TARGET_AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    target_asset_id: int
    targets: _containers.RepeatedScalarFieldContainer[int]
    fee_bps: int
    balances: _containers.RepeatedCompositeFieldContainer[DustBalance]
    gross_usd_e18: _u128_pb2.U128
    payout_e18: _u128_pb2.U128
    target_available: bool
    def __init__(self, target_asset_id: _Optional[int] = ..., targets: _Optional[_Iterable[int]] = ..., fee_bps: _Optional[int] = ..., balances: _Optional[_Iterable[_Union[DustBalance, _Mapping]]] = ..., gross_usd_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., payout_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., target_available: _Optional[bool] = ...) -> None: ...

class QuoteDustConversionRequest(_message.Message):
    __slots__ = ("subaccount_id", "target_asset_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    target_asset_id: int
    def __init__(self, subaccount_id: _Optional[int] = ..., target_asset_id: _Optional[int] = ...) -> None: ...

class QuoteDustConversionResponse(_message.Message):
    __slots__ = ("quote_id", "expires_at", "target_asset_id", "fee_bps", "gross_usd_e18", "payout_e18", "balances", "prices")
    QUOTE_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    TARGET_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    GROSS_USD_E18_FIELD_NUMBER: _ClassVar[int]
    PAYOUT_E18_FIELD_NUMBER: _ClassVar[int]
    BALANCES_FIELD_NUMBER: _ClassVar[int]
    PRICES_FIELD_NUMBER: _ClassVar[int]
    quote_id: str
    expires_at: _timestamp_pb2.Timestamp
    target_asset_id: int
    fee_bps: int
    gross_usd_e18: _u128_pb2.U128
    payout_e18: _u128_pb2.U128
    balances: _containers.RepeatedCompositeFieldContainer[DustBalance]
    prices: _containers.RepeatedCompositeFieldContainer[DustAssetPrice]
    def __init__(self, quote_id: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., target_asset_id: _Optional[int] = ..., fee_bps: _Optional[int] = ..., gross_usd_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., payout_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., balances: _Optional[_Iterable[_Union[DustBalance, _Mapping]]] = ..., prices: _Optional[_Iterable[_Union[DustAssetPrice, _Mapping]]] = ...) -> None: ...

class CreateDustConversionRequest(_message.Message):
    __slots__ = ("subaccount_id", "idempotency_key", "quote_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    idempotency_key: str
    quote_id: str
    def __init__(self, subaccount_id: _Optional[int] = ..., idempotency_key: _Optional[str] = ..., quote_id: _Optional[str] = ...) -> None: ...

class CreateDustConversionResponse(_message.Message):
    __slots__ = ("conversion",)
    CONVERSION_FIELD_NUMBER: _ClassVar[int]
    conversion: DustConversion
    def __init__(self, conversion: _Optional[_Union[DustConversion, _Mapping]] = ...) -> None: ...

class GetDustConversionRequest(_message.Message):
    __slots__ = ("subaccount_id", "conversion_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSION_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    conversion_id: str
    def __init__(self, subaccount_id: _Optional[int] = ..., conversion_id: _Optional[str] = ...) -> None: ...

class GetDustConversionResponse(_message.Message):
    __slots__ = ("conversion",)
    CONVERSION_FIELD_NUMBER: _ClassVar[int]
    conversion: DustConversion
    def __init__(self, conversion: _Optional[_Union[DustConversion, _Mapping]] = ...) -> None: ...

class ListDustConversionsRequest(_message.Message):
    __slots__ = ("subaccount_id", "limit", "page_token")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    limit: int
    page_token: str
    def __init__(self, subaccount_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListDustConversionsResponse(_message.Message):
    __slots__ = ("conversions", "next_page_token")
    CONVERSIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    conversions: _containers.RepeatedCompositeFieldContainer[DustConversion]
    next_page_token: str
    def __init__(self, conversions: _Optional[_Iterable[_Union[DustConversion, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
