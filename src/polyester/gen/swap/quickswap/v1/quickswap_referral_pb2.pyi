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

class ReferralPartnerStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PARTNER_STATUS_UNSPECIFIED: _ClassVar[ReferralPartnerStatus]
    PARTNER_PENDING: _ClassVar[ReferralPartnerStatus]
    PARTNER_ACTIVE: _ClassVar[ReferralPartnerStatus]
    PARTNER_DISABLED: _ClassVar[ReferralPartnerStatus]

class ReferralCodeAvailability(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CODE_AVAILABILITY_UNSPECIFIED: _ClassVar[ReferralCodeAvailability]
    CODE_AVAILABLE: _ClassVar[ReferralCodeAvailability]
    CODE_CURRENT: _ClassVar[ReferralCodeAvailability]
    CODE_TAKEN: _ClassVar[ReferralCodeAvailability]
    CODE_RESERVED: _ClassVar[ReferralCodeAvailability]
    CODE_INVALID: _ClassVar[ReferralCodeAvailability]

class ReferralCommissionBasis(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    COMMISSION_BASIS_UNSPECIFIED: _ClassVar[ReferralCommissionBasis]
    PRE_DISCOUNT_FEE: _ClassVar[ReferralCommissionBasis]
PARTNER_STATUS_UNSPECIFIED: ReferralPartnerStatus
PARTNER_PENDING: ReferralPartnerStatus
PARTNER_ACTIVE: ReferralPartnerStatus
PARTNER_DISABLED: ReferralPartnerStatus
CODE_AVAILABILITY_UNSPECIFIED: ReferralCodeAvailability
CODE_AVAILABLE: ReferralCodeAvailability
CODE_CURRENT: ReferralCodeAvailability
CODE_TAKEN: ReferralCodeAvailability
CODE_RESERVED: ReferralCodeAvailability
CODE_INVALID: ReferralCodeAvailability
COMMISSION_BASIS_UNSPECIFIED: ReferralCommissionBasis
PRE_DISCOUNT_FEE: ReferralCommissionBasis

class ReferralRates(_message.Message):
    __slots__ = ("discount_bps", "commission_bps")
    DISCOUNT_BPS_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_BPS_FIELD_NUMBER: _ClassVar[int]
    discount_bps: int
    commission_bps: int
    def __init__(self, discount_bps: _Optional[int] = ..., commission_bps: _Optional[int] = ...) -> None: ...

class ReferralProgram(_message.Message):
    __slots__ = ("normal", "stablecoin", "bridging")
    NORMAL_FIELD_NUMBER: _ClassVar[int]
    STABLECOIN_FIELD_NUMBER: _ClassVar[int]
    BRIDGING_FIELD_NUMBER: _ClassVar[int]
    normal: ReferralRates
    stablecoin: ReferralRates
    bridging: ReferralRates
    def __init__(self, normal: _Optional[_Union[ReferralRates, _Mapping]] = ..., stablecoin: _Optional[_Union[ReferralRates, _Mapping]] = ..., bridging: _Optional[_Union[ReferralRates, _Mapping]] = ...) -> None: ...

class ReferralPartner(_message.Message):
    __slots__ = ("partner_id", "display_name", "status", "earnings_subaccount_id", "code", "link_path", "program", "created_at", "code_changes_remaining")
    PARTNER_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EARNINGS_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    LINK_PATH_FIELD_NUMBER: _ClassVar[int]
    PROGRAM_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    CODE_CHANGES_REMAINING_FIELD_NUMBER: _ClassVar[int]
    partner_id: int
    display_name: str
    status: ReferralPartnerStatus
    earnings_subaccount_id: int
    code: str
    link_path: str
    program: ReferralProgram
    created_at: _timestamp_pb2.Timestamp
    code_changes_remaining: int
    def __init__(self, partner_id: _Optional[int] = ..., display_name: _Optional[str] = ..., status: _Optional[_Union[ReferralPartnerStatus, str]] = ..., earnings_subaccount_id: _Optional[int] = ..., code: _Optional[str] = ..., link_path: _Optional[str] = ..., program: _Optional[_Union[ReferralProgram, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., code_changes_remaining: _Optional[int] = ...) -> None: ...

class EnrollReferralPartnerRequest(_message.Message):
    __slots__ = ("earnings_subaccount_id", "display_name")
    EARNINGS_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    earnings_subaccount_id: int
    display_name: str
    def __init__(self, earnings_subaccount_id: _Optional[int] = ..., display_name: _Optional[str] = ...) -> None: ...

class EnrollReferralPartnerResponse(_message.Message):
    __slots__ = ("partner",)
    PARTNER_FIELD_NUMBER: _ClassVar[int]
    partner: ReferralPartner
    def __init__(self, partner: _Optional[_Union[ReferralPartner, _Mapping]] = ...) -> None: ...

class GetReferralPartnerRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetReferralPartnerResponse(_message.Message):
    __slots__ = ("partner",)
    PARTNER_FIELD_NUMBER: _ClassVar[int]
    partner: ReferralPartner
    def __init__(self, partner: _Optional[_Union[ReferralPartner, _Mapping]] = ...) -> None: ...

class CheckReferralCodeRequest(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: str
    def __init__(self, code: _Optional[str] = ...) -> None: ...

class CheckReferralCodeResponse(_message.Message):
    __slots__ = ("code", "availability")
    CODE_FIELD_NUMBER: _ClassVar[int]
    AVAILABILITY_FIELD_NUMBER: _ClassVar[int]
    code: str
    availability: ReferralCodeAvailability
    def __init__(self, code: _Optional[str] = ..., availability: _Optional[_Union[ReferralCodeAvailability, str]] = ...) -> None: ...

class SetReferralCodeRequest(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: str
    def __init__(self, code: _Optional[str] = ...) -> None: ...

class SetReferralCodeResponse(_message.Message):
    __slots__ = ("partner",)
    PARTNER_FIELD_NUMBER: _ClassVar[int]
    partner: ReferralPartner
    def __init__(self, partner: _Optional[_Union[ReferralPartner, _Mapping]] = ...) -> None: ...

class ReferralCommission(_message.Message):
    __slots__ = ("asset_id", "amount")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    amount: _quickswap_pb2.TokenAmount
    def __init__(self, asset_id: _Optional[int] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class ReferralCredit(_message.Message):
    __slots__ = ("asset_id", "amount", "accrued_at")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    ACCRUED_AT_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    amount: _quickswap_pb2.TokenAmount
    accrued_at: _timestamp_pb2.Timestamp
    def __init__(self, asset_id: _Optional[int] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., accrued_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ReferredQuickSwap(_message.Message):
    __slots__ = ("swap_id", "status", "is_terminal", "created_at", "terminal_at", "source_zipped_asset_id", "destination_zipped_asset_id", "quoted_source_amount", "quoted_destination_amount", "source_amount", "destination_amount", "base_fee_bps", "charged_fee_bps", "commission_bps", "commission")
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    IS_TERMINAL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    TERMINAL_AT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    QUOTED_SOURCE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    QUOTED_DESTINATION_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    BASE_FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    CHARGED_FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_BPS_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    status: _quickswap_pb2.QuickSwapStatus
    is_terminal: bool
    created_at: _timestamp_pb2.Timestamp
    terminal_at: _timestamp_pb2.Timestamp
    source_zipped_asset_id: int
    destination_zipped_asset_id: int
    quoted_source_amount: _quickswap_pb2.TokenAmount
    quoted_destination_amount: _quickswap_pb2.TokenAmount
    source_amount: _quickswap_pb2.TokenAmount
    destination_amount: _quickswap_pb2.TokenAmount
    base_fee_bps: int
    charged_fee_bps: int
    commission_bps: int
    commission: _containers.RepeatedCompositeFieldContainer[ReferralCommission]
    def __init__(self, swap_id: _Optional[int] = ..., status: _Optional[_Union[_quickswap_pb2.QuickSwapStatus, str]] = ..., is_terminal: _Optional[bool] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., terminal_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., source_zipped_asset_id: _Optional[int] = ..., destination_zipped_asset_id: _Optional[int] = ..., quoted_source_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., quoted_destination_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., source_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., destination_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., base_fee_bps: _Optional[int] = ..., charged_fee_bps: _Optional[int] = ..., commission_bps: _Optional[int] = ..., commission: _Optional[_Iterable[_Union[ReferralCommission, _Mapping]]] = ...) -> None: ...

class ReferralCommissionValue(_message.Message):
    __slots__ = ("usd", "as_of")
    USD_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    usd: str
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, usd: _Optional[str] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ReferralBreakdown(_message.Message):
    __slots__ = ("base_fee_bps", "charged_fee_bps", "discount_bps", "commission_bps", "basis", "credited", "credited_truncated", "commission_value")
    BASE_FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    CHARGED_FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    DISCOUNT_BPS_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_BPS_FIELD_NUMBER: _ClassVar[int]
    BASIS_FIELD_NUMBER: _ClassVar[int]
    CREDITED_FIELD_NUMBER: _ClassVar[int]
    CREDITED_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    COMMISSION_VALUE_FIELD_NUMBER: _ClassVar[int]
    base_fee_bps: int
    charged_fee_bps: int
    discount_bps: int
    commission_bps: int
    basis: ReferralCommissionBasis
    credited: _containers.RepeatedCompositeFieldContainer[ReferralCredit]
    credited_truncated: bool
    commission_value: ReferralCommissionValue
    def __init__(self, base_fee_bps: _Optional[int] = ..., charged_fee_bps: _Optional[int] = ..., discount_bps: _Optional[int] = ..., commission_bps: _Optional[int] = ..., basis: _Optional[_Union[ReferralCommissionBasis, str]] = ..., credited: _Optional[_Iterable[_Union[ReferralCredit, _Mapping]]] = ..., credited_truncated: _Optional[bool] = ..., commission_value: _Optional[_Union[ReferralCommissionValue, _Mapping]] = ...) -> None: ...

class ListReferredQuickSwapsRequest(_message.Message):
    __slots__ = ("start_time", "end_time", "statuses", "limit", "page_token")
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    statuses: _containers.RepeatedScalarFieldContainer[_quickswap_pb2.QuickSwapStatus]
    limit: int
    page_token: str
    def __init__(self, start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., statuses: _Optional[_Iterable[_Union[_quickswap_pb2.QuickSwapStatus, str]]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListReferredQuickSwapsResponse(_message.Message):
    __slots__ = ("quick_swaps", "next_page_token")
    QUICK_SWAPS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    quick_swaps: _containers.RepeatedCompositeFieldContainer[ReferredQuickSwap]
    next_page_token: str
    def __init__(self, quick_swaps: _Optional[_Iterable[_Union[ReferredQuickSwap, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetReferredQuickSwapRequest(_message.Message):
    __slots__ = ("swap_id",)
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    def __init__(self, swap_id: _Optional[int] = ...) -> None: ...

class GetReferredQuickSwapResponse(_message.Message):
    __slots__ = ("quick_swap", "breakdown")
    QUICK_SWAP_FIELD_NUMBER: _ClassVar[int]
    BREAKDOWN_FIELD_NUMBER: _ClassVar[int]
    quick_swap: ReferredQuickSwap
    breakdown: ReferralBreakdown
    def __init__(self, quick_swap: _Optional[_Union[ReferredQuickSwap, _Mapping]] = ..., breakdown: _Optional[_Union[ReferralBreakdown, _Mapping]] = ...) -> None: ...
