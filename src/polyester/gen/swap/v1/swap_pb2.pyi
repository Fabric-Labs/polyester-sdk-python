import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.polyester.type.v1 import u128_pb2 as _u128_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Side(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIDE_UNSPECIFIED: _ClassVar[Side]
    BUY: _ClassVar[Side]
    SELL: _ClassVar[Side]

class SwapStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUS_UNSPECIFIED: _ClassVar[SwapStatus]
    EXECUTING: _ClassVar[SwapStatus]
    COMPLETED: _ClassVar[SwapStatus]
    PARTIALLY_COMPLETED: _ClassVar[SwapStatus]
    FAILED: _ClassVar[SwapStatus]
    RECONCILING: _ClassVar[SwapStatus]
    CANCELING: _ClassVar[SwapStatus]
    CANCELED: _ClassVar[SwapStatus]

class SwapReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REASON_UNSPECIFIED: _ClassVar[SwapReason]
    INSUFFICIENT_BALANCE: _ClassVar[SwapReason]
    PRICE_PROTECTION: _ClassVar[SwapReason]
    MARKET_UNAVAILABLE: _ClassVar[SwapReason]
    ORDER_SIZE_OUT_OF_RANGE: _ClassVar[SwapReason]
    RATE_LIMITED: _ClassVar[SwapReason]
    ORDER_REJECTED: _ClassVar[SwapReason]
    EXPIRED: _ClassVar[SwapReason]
    MINIMUM_NOT_MET: _ClassVar[SwapReason]
    MAX_ORDER_QUANTITY: _ClassVar[SwapReason]
    INTERMEDIATE_BELOW_MINIMUM: _ClassVar[SwapReason]
    USER_CANCELED: _ClassVar[SwapReason]

class SwapOrderStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_STATUS_UNSPECIFIED: _ClassVar[SwapOrderStatus]
    PLACING: _ClassVar[SwapOrderStatus]
    PLACED: _ClassVar[SwapOrderStatus]
    REFUSED: _ClassVar[SwapOrderStatus]
    NOT_PLACED: _ClassVar[SwapOrderStatus]
    UNCONFIRMED: _ClassVar[SwapOrderStatus]

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_UNSPECIFIED: _ClassVar[ErrorCode]
    ROUTE_UNSUPPORTED: _ClassVar[ErrorCode]
    AMOUNT_OUT_OF_RANGE: _ClassVar[ErrorCode]
    QUOTE_UNAVAILABLE: _ClassVar[ErrorCode]
    PROTECTION_UNACHIEVABLE: _ClassVar[ErrorCode]
    QUOTE_EXPIRED: _ClassVar[ErrorCode]
    IDEMPOTENCY_CONFLICT: _ClassVar[ErrorCode]
    SWAP_NOT_FOUND: _ClassVar[ErrorCode]
    INVALID_SUBACCOUNT_ID: _ClassVar[ErrorCode]
    SUBACCOUNT_NOT_FOUND: _ClassVar[ErrorCode]
    SUBACCOUNT_INACTIVE: _ClassVar[ErrorCode]
    SWAP_NOT_PERMITTED: _ClassVar[ErrorCode]
    SERVICE_UNAVAILABLE: _ClassVar[ErrorCode]
    DIRECTION_UNSUPPORTED: _ClassVar[ErrorCode]
    SWAP_ALREADY_FINAL: _ClassVar[ErrorCode]
    SWAP_NOT_CANCELABLE: _ClassVar[ErrorCode]
SIDE_UNSPECIFIED: Side
BUY: Side
SELL: Side
STATUS_UNSPECIFIED: SwapStatus
EXECUTING: SwapStatus
COMPLETED: SwapStatus
PARTIALLY_COMPLETED: SwapStatus
FAILED: SwapStatus
RECONCILING: SwapStatus
CANCELING: SwapStatus
CANCELED: SwapStatus
REASON_UNSPECIFIED: SwapReason
INSUFFICIENT_BALANCE: SwapReason
PRICE_PROTECTION: SwapReason
MARKET_UNAVAILABLE: SwapReason
ORDER_SIZE_OUT_OF_RANGE: SwapReason
RATE_LIMITED: SwapReason
ORDER_REJECTED: SwapReason
EXPIRED: SwapReason
MINIMUM_NOT_MET: SwapReason
MAX_ORDER_QUANTITY: SwapReason
INTERMEDIATE_BELOW_MINIMUM: SwapReason
USER_CANCELED: SwapReason
ORDER_STATUS_UNSPECIFIED: SwapOrderStatus
PLACING: SwapOrderStatus
PLACED: SwapOrderStatus
REFUSED: SwapOrderStatus
NOT_PLACED: SwapOrderStatus
UNCONFIRMED: SwapOrderStatus
ERROR_UNSPECIFIED: ErrorCode
ROUTE_UNSUPPORTED: ErrorCode
AMOUNT_OUT_OF_RANGE: ErrorCode
QUOTE_UNAVAILABLE: ErrorCode
PROTECTION_UNACHIEVABLE: ErrorCode
QUOTE_EXPIRED: ErrorCode
IDEMPOTENCY_CONFLICT: ErrorCode
SWAP_NOT_FOUND: ErrorCode
INVALID_SUBACCOUNT_ID: ErrorCode
SUBACCOUNT_NOT_FOUND: ErrorCode
SUBACCOUNT_INACTIVE: ErrorCode
SWAP_NOT_PERMITTED: ErrorCode
SERVICE_UNAVAILABLE: ErrorCode
DIRECTION_UNSUPPORTED: ErrorCode
SWAP_ALREADY_FINAL: ErrorCode
SWAP_NOT_CANCELABLE: ErrorCode

class SwapTerms(_message.Message):
    __slots__ = ("subaccount_id", "source_asset_id", "destination_asset_id", "amount_e18", "execution")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    source_asset_id: int
    destination_asset_id: int
    amount_e18: _u128_pb2.U128
    execution: Execution
    def __init__(self, subaccount_id: _Optional[int] = ..., source_asset_id: _Optional[int] = ..., destination_asset_id: _Optional[int] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., execution: _Optional[_Union[Execution, _Mapping]] = ...) -> None: ...

class MarketExecution(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TwapExecution(_message.Message):
    __slots__ = ("duration_ms", "slice_interval_ms")
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    SLICE_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    duration_ms: int
    slice_interval_ms: int
    def __init__(self, duration_ms: _Optional[int] = ..., slice_interval_ms: _Optional[int] = ...) -> None: ...

class Execution(_message.Message):
    __slots__ = ("market", "twap")
    MARKET_FIELD_NUMBER: _ClassVar[int]
    TWAP_FIELD_NUMBER: _ClassVar[int]
    market: MarketExecution
    twap: TwapExecution
    def __init__(self, market: _Optional[_Union[MarketExecution, _Mapping]] = ..., twap: _Optional[_Union[TwapExecution, _Mapping]] = ...) -> None: ...

class SwapQuoteLeg(_message.Message):
    __slots__ = ("symbol_id", "side", "average_price", "price_impact_bps", "taker_fee_rate_percent", "fee_e18", "fee_asset_id")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_PRICE_FIELD_NUMBER: _ClassVar[int]
    PRICE_IMPACT_BPS_FIELD_NUMBER: _ClassVar[int]
    TAKER_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    FEE_E18_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    side: Side
    average_price: str
    price_impact_bps: int
    taker_fee_rate_percent: str
    fee_e18: _u128_pb2.U128
    fee_asset_id: int
    def __init__(self, symbol_id: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., average_price: _Optional[str] = ..., price_impact_bps: _Optional[int] = ..., taker_fee_rate_percent: _Optional[str] = ..., fee_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., fee_asset_id: _Optional[int] = ...) -> None: ...

class SwapQuote(_message.Message):
    __slots__ = ("terms", "legs", "expected_amount_out_e18", "min_amount_out_e18", "quoted_at", "expires_at", "intermediate_asset_id", "price_impact_bps", "total_slices")
    TERMS_FIELD_NUMBER: _ClassVar[int]
    LEGS_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_AMOUNT_OUT_E18_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_OUT_E18_FIELD_NUMBER: _ClassVar[int]
    QUOTED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    INTERMEDIATE_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_IMPACT_BPS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SLICES_FIELD_NUMBER: _ClassVar[int]
    terms: SwapTerms
    legs: _containers.RepeatedCompositeFieldContainer[SwapQuoteLeg]
    expected_amount_out_e18: _u128_pb2.U128
    min_amount_out_e18: _u128_pb2.U128
    quoted_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    intermediate_asset_id: int
    price_impact_bps: int
    total_slices: int
    def __init__(self, terms: _Optional[_Union[SwapTerms, _Mapping]] = ..., legs: _Optional[_Iterable[_Union[SwapQuoteLeg, _Mapping]]] = ..., expected_amount_out_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., min_amount_out_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., quoted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., intermediate_asset_id: _Optional[int] = ..., price_impact_bps: _Optional[int] = ..., total_slices: _Optional[int] = ...) -> None: ...

class SwapOrder(_message.Message):
    __slots__ = ("order_id", "symbol_id", "side", "leg", "status", "limit_price_ticks", "spent_e18", "received_e18", "fee_e18", "slice")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    LEG_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    SPENT_E18_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_E18_FIELD_NUMBER: _ClassVar[int]
    FEE_E18_FIELD_NUMBER: _ClassVar[int]
    SLICE_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    symbol_id: int
    side: Side
    leg: int
    status: SwapOrderStatus
    limit_price_ticks: int
    spent_e18: _u128_pb2.U128
    received_e18: _u128_pb2.U128
    fee_e18: _u128_pb2.U128
    slice: int
    def __init__(self, order_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., leg: _Optional[int] = ..., status: _Optional[_Union[SwapOrderStatus, str]] = ..., limit_price_ticks: _Optional[int] = ..., spent_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., received_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., fee_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., slice: _Optional[int] = ...) -> None: ...

class SwapLeg(_message.Message):
    __slots__ = ("leg", "symbol_id", "side", "spent_e18", "received_e18", "fee_e18", "fee_asset_id")
    LEG_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    SPENT_E18_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_E18_FIELD_NUMBER: _ClassVar[int]
    FEE_E18_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    leg: int
    symbol_id: int
    side: Side
    spent_e18: _u128_pb2.U128
    received_e18: _u128_pb2.U128
    fee_e18: _u128_pb2.U128
    fee_asset_id: int
    def __init__(self, leg: _Optional[int] = ..., symbol_id: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., spent_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., received_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., fee_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., fee_asset_id: _Optional[int] = ...) -> None: ...

class SwapSlice(_message.Message):
    __slots__ = ("index", "planned_at", "executed_at", "finished_at", "state", "reason", "completed", "input_traded_e18", "output_received_e18", "second_leg_input_e18", "intermediate_carried_e18", "carry_reason")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATE_UNSPECIFIED: _ClassVar[SwapSlice.State]
        PLANNED: _ClassVar[SwapSlice.State]
        EXECUTING: _ClassVar[SwapSlice.State]
        TRADED: _ClassVar[SwapSlice.State]
        PARTLY_TRADED: _ClassVar[SwapSlice.State]
        SKIPPED: _ClassVar[SwapSlice.State]
        FAILED: _ClassVar[SwapSlice.State]
    STATE_UNSPECIFIED: SwapSlice.State
    PLANNED: SwapSlice.State
    EXECUTING: SwapSlice.State
    TRADED: SwapSlice.State
    PARTLY_TRADED: SwapSlice.State
    SKIPPED: SwapSlice.State
    FAILED: SwapSlice.State
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SLICE_REASON_UNSPECIFIED: _ClassVar[SwapSlice.Reason]
        SLOT_MISSED: _ClassVar[SwapSlice.Reason]
        DEADLINE_REACHED: _ClassVar[SwapSlice.Reason]
        MARKET_CLOSED: _ClassVar[SwapSlice.Reason]
        BELOW_MINIMUM: _ClassVar[SwapSlice.Reason]
        ABOVE_MAXIMUM: _ClassVar[SwapSlice.Reason]
        PROTECTION_NOT_MET: _ClassVar[SwapSlice.Reason]
        REFUSED: _ClassVar[SwapSlice.Reason]
        INSUFFICIENT_LIQUIDITY: _ClassVar[SwapSlice.Reason]
        EXECUTION_ENDED: _ClassVar[SwapSlice.Reason]
        CANCELED: _ClassVar[SwapSlice.Reason]
    SLICE_REASON_UNSPECIFIED: SwapSlice.Reason
    SLOT_MISSED: SwapSlice.Reason
    DEADLINE_REACHED: SwapSlice.Reason
    MARKET_CLOSED: SwapSlice.Reason
    BELOW_MINIMUM: SwapSlice.Reason
    ABOVE_MAXIMUM: SwapSlice.Reason
    PROTECTION_NOT_MET: SwapSlice.Reason
    REFUSED: SwapSlice.Reason
    INSUFFICIENT_LIQUIDITY: SwapSlice.Reason
    EXECUTION_ENDED: SwapSlice.Reason
    CANCELED: SwapSlice.Reason
    INDEX_FIELD_NUMBER: _ClassVar[int]
    PLANNED_AT_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_FIELD_NUMBER: _ClassVar[int]
    INPUT_TRADED_E18_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_RECEIVED_E18_FIELD_NUMBER: _ClassVar[int]
    SECOND_LEG_INPUT_E18_FIELD_NUMBER: _ClassVar[int]
    INTERMEDIATE_CARRIED_E18_FIELD_NUMBER: _ClassVar[int]
    CARRY_REASON_FIELD_NUMBER: _ClassVar[int]
    index: int
    planned_at: _timestamp_pb2.Timestamp
    executed_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    state: SwapSlice.State
    reason: SwapSlice.Reason
    completed: bool
    input_traded_e18: _u128_pb2.U128
    output_received_e18: _u128_pb2.U128
    second_leg_input_e18: _u128_pb2.U128
    intermediate_carried_e18: _u128_pb2.U128
    carry_reason: SwapSlice.Reason
    def __init__(self, index: _Optional[int] = ..., planned_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., executed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., state: _Optional[_Union[SwapSlice.State, str]] = ..., reason: _Optional[_Union[SwapSlice.Reason, str]] = ..., completed: _Optional[bool] = ..., input_traded_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., output_received_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., second_leg_input_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., intermediate_carried_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., carry_reason: _Optional[_Union[SwapSlice.Reason, str]] = ...) -> None: ...

class SwapProgress(_message.Message):
    __slots__ = ("completed_slices", "total_slices", "started_at", "deadline", "slices", "slices_truncated")
    COMPLETED_SLICES_FIELD_NUMBER: _ClassVar[int]
    TOTAL_SLICES_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_FIELD_NUMBER: _ClassVar[int]
    SLICES_FIELD_NUMBER: _ClassVar[int]
    SLICES_TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    completed_slices: int
    total_slices: int
    started_at: _timestamp_pb2.Timestamp
    deadline: _timestamp_pb2.Timestamp
    slices: _containers.RepeatedCompositeFieldContainer[SwapSlice]
    slices_truncated: bool
    def __init__(self, completed_slices: _Optional[int] = ..., total_slices: _Optional[int] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deadline: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., slices: _Optional[_Iterable[_Union[SwapSlice, _Mapping]]] = ..., slices_truncated: _Optional[bool] = ...) -> None: ...

class Swap(_message.Message):
    __slots__ = ("swap_id", "idempotency_key", "subaccount_id", "source_asset_id", "destination_asset_id", "amount_e18", "min_amount_out_e18", "status", "reason", "is_terminal", "executed_amount_e18", "unspent_amount_e18", "received_amount_e18", "orders", "created_at", "execution", "intermediate_asset_id", "intermediate_remainder_e18", "legs", "progress", "cancel_requested_at")
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_OUT_E18_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    IS_TERMINAL_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    UNSPENT_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    RECEIVED_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    EXECUTION_FIELD_NUMBER: _ClassVar[int]
    INTERMEDIATE_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    INTERMEDIATE_REMAINDER_E18_FIELD_NUMBER: _ClassVar[int]
    LEGS_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    CANCEL_REQUESTED_AT_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    idempotency_key: str
    subaccount_id: int
    source_asset_id: int
    destination_asset_id: int
    amount_e18: _u128_pb2.U128
    min_amount_out_e18: _u128_pb2.U128
    status: SwapStatus
    reason: SwapReason
    is_terminal: bool
    executed_amount_e18: _u128_pb2.U128
    unspent_amount_e18: _u128_pb2.U128
    received_amount_e18: _u128_pb2.U128
    orders: _containers.RepeatedCompositeFieldContainer[SwapOrder]
    created_at: _timestamp_pb2.Timestamp
    execution: Execution
    intermediate_asset_id: int
    intermediate_remainder_e18: _u128_pb2.U128
    legs: _containers.RepeatedCompositeFieldContainer[SwapLeg]
    progress: SwapProgress
    cancel_requested_at: _timestamp_pb2.Timestamp
    def __init__(self, swap_id: _Optional[int] = ..., idempotency_key: _Optional[str] = ..., subaccount_id: _Optional[int] = ..., source_asset_id: _Optional[int] = ..., destination_asset_id: _Optional[int] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., min_amount_out_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., status: _Optional[_Union[SwapStatus, str]] = ..., reason: _Optional[_Union[SwapReason, str]] = ..., is_terminal: _Optional[bool] = ..., executed_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., unspent_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., received_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., orders: _Optional[_Iterable[_Union[SwapOrder, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., execution: _Optional[_Union[Execution, _Mapping]] = ..., intermediate_asset_id: _Optional[int] = ..., intermediate_remainder_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., legs: _Optional[_Iterable[_Union[SwapLeg, _Mapping]]] = ..., progress: _Optional[_Union[SwapProgress, _Mapping]] = ..., cancel_requested_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class QuoteSwapRequest(_message.Message):
    __slots__ = ("terms", "max_slippage_bps")
    TERMS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    terms: SwapTerms
    max_slippage_bps: int
    def __init__(self, terms: _Optional[_Union[SwapTerms, _Mapping]] = ..., max_slippage_bps: _Optional[int] = ...) -> None: ...

class QuoteSwapResponse(_message.Message):
    __slots__ = ("quote",)
    QUOTE_FIELD_NUMBER: _ClassVar[int]
    quote: SwapQuote
    def __init__(self, quote: _Optional[_Union[SwapQuote, _Mapping]] = ...) -> None: ...

class CreateSwapRequest(_message.Message):
    __slots__ = ("idempotency_key", "terms", "min_amount_out_e18", "quote_expires_at")
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    TERMS_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_OUT_E18_FIELD_NUMBER: _ClassVar[int]
    QUOTE_EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    idempotency_key: str
    terms: SwapTerms
    min_amount_out_e18: _u128_pb2.U128
    quote_expires_at: _timestamp_pb2.Timestamp
    def __init__(self, idempotency_key: _Optional[str] = ..., terms: _Optional[_Union[SwapTerms, _Mapping]] = ..., min_amount_out_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., quote_expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateSwapResponse(_message.Message):
    __slots__ = ("swap",)
    SWAP_FIELD_NUMBER: _ClassVar[int]
    swap: Swap
    def __init__(self, swap: _Optional[_Union[Swap, _Mapping]] = ...) -> None: ...

class GetSwapRequest(_message.Message):
    __slots__ = ("swap_id", "idempotency_key")
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    idempotency_key: str
    def __init__(self, swap_id: _Optional[int] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class GetSwapResponse(_message.Message):
    __slots__ = ("swap",)
    SWAP_FIELD_NUMBER: _ClassVar[int]
    swap: Swap
    def __init__(self, swap: _Optional[_Union[Swap, _Mapping]] = ...) -> None: ...

class CancelSwapRequest(_message.Message):
    __slots__ = ("swap_id",)
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    def __init__(self, swap_id: _Optional[int] = ...) -> None: ...

class CancelSwapResponse(_message.Message):
    __slots__ = ("swap",)
    SWAP_FIELD_NUMBER: _ClassVar[int]
    swap: Swap
    def __init__(self, swap: _Optional[_Union[Swap, _Mapping]] = ...) -> None: ...

class ListSwapsRequest(_message.Message):
    __slots__ = ("subaccount_id", "open_only", "limit", "page_token")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    OPEN_ONLY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    open_only: bool
    limit: int
    page_token: str
    def __init__(self, subaccount_id: _Optional[int] = ..., open_only: _Optional[bool] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListSwapsResponse(_message.Message):
    __slots__ = ("swaps", "next_page_token")
    SWAPS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    swaps: _containers.RepeatedCompositeFieldContainer[Swap]
    next_page_token: str
    def __init__(self, swaps: _Optional[_Iterable[_Union[Swap, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ErrorDetail(_message.Message):
    __slots__ = ("code", "swap_id", "min_amount_e18", "max_amount_e18")
    CODE_FIELD_NUMBER: _ClassVar[int]
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    MAX_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    swap_id: int
    min_amount_e18: _u128_pb2.U128
    max_amount_e18: _u128_pb2.U128
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ..., swap_id: _Optional[int] = ..., min_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., max_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ...) -> None: ...
