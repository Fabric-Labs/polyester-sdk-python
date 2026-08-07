import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as _types_pb2
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

class OrderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_TYPE_UNSPECIFIED: _ClassVar[OrderType]
    LIMIT: _ClassVar[OrderType]
    MARKET: _ClassVar[OrderType]

class TimeInForce(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TIME_IN_FORCE_UNSPECIFIED: _ClassVar[TimeInForce]
    GTC: _ClassVar[TimeInForce]
    IOC: _ClassVar[TimeInForce]
    FOK: _ClassVar[TimeInForce]

class FeeAsset(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FEE_ASSET_UNSPECIFIED: _ClassVar[FeeAsset]
    QUOTE: _ClassVar[FeeAsset]
    BASE: _ClassVar[FeeAsset]

class SelfTradePreventionMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SELF_TRADE_PREVENTION_MODE_UNSPECIFIED: _ClassVar[SelfTradePreventionMode]
    EXPIRE_MAKER: _ClassVar[SelfTradePreventionMode]
    EXPIRE_TAKER: _ClassVar[SelfTradePreventionMode]
    EXPIRE_BOTH: _ClassVar[SelfTradePreventionMode]

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_CODE_UNSPECIFIED: _ClassVar[ErrorCode]
    ERROR_CODE_BAD_REQUEST: _ClassVar[ErrorCode]
    ERROR_CODE_INVALID_ARGUMENT: _ClassVar[ErrorCode]
    ERROR_CODE_INSUFFICIENT_FUNDS: _ClassVar[ErrorCode]
    ERROR_CODE_UNKNOWN_SYMBOL: _ClassVar[ErrorCode]
    ERROR_CODE_BAD_PRICE: _ClassVar[ErrorCode]
    ERROR_CODE_BAD_QTY: _ClassVar[ErrorCode]
    ERROR_CODE_MIN_NOTIONAL: _ClassVar[ErrorCode]
    ERROR_CODE_QTY_STEP_SIZE: _ClassVar[ErrorCode]
    ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID: _ClassVar[ErrorCode]
    ERROR_CODE_UNAVAILABLE: _ClassVar[ErrorCode]
    ERROR_CODE_UNAUTHENTICATED: _ClassVar[ErrorCode]
    ERROR_CODE_PERMISSION_DENIED: _ClassVar[ErrorCode]
    ERROR_CODE_NOT_FOUND: _ClassVar[ErrorCode]
    ERROR_CODE_UPSTREAM_ERROR: _ClassVar[ErrorCode]
    ERROR_CODE_FEE_ASSET_NOT_ALLOWED: _ClassVar[ErrorCode]
    ERROR_CODE_PAIR_DISABLED: _ClassVar[ErrorCode]
    ERROR_CODE_ORDER_UNKNOWN: _ClassVar[ErrorCode]
    ERROR_CODE_INTERNAL_ERROR: _ClassVar[ErrorCode]
    ERROR_CODE_SUBACCOUNT_INACTIVE: _ClassVar[ErrorCode]
    ERROR_CODE_POLICY_MARKET_DENY: _ClassVar[ErrorCode]
    ERROR_CODE_POLICY_MAX_NOTIONAL: _ClassVar[ErrorCode]
    ERROR_CODE_POLICY_TRADING_HALTED: _ClassVar[ErrorCode]
    ERROR_CODE_POLICY_SPOT_TRADE_DENY: _ClassVar[ErrorCode]
    ERROR_CODE_API_KEY_ROOT_SCOPE_ONLY: _ClassVar[ErrorCode]
    ERROR_CODE_API_KEY_SUB_SCOPE_ONLY: _ClassVar[ErrorCode]
    ERROR_CODE_API_KEY_SUBACCOUNT_MISMATCH: _ClassVar[ErrorCode]
    ERROR_CODE_API_KEY_POLICY_REQUIRED: _ClassVar[ErrorCode]
    ERROR_CODE_API_KEY_UNKNOWN: _ClassVar[ErrorCode]
    ERROR_CODE_API_KEY_MARKET_DENY: _ClassVar[ErrorCode]
    ERROR_CODE_PRICE_TICK_SIZE: _ClassVar[ErrorCode]
    ERROR_CODE_MIN_QTY: _ClassVar[ErrorCode]
    ERROR_CODE_POST_ONLY_LIMIT_ONLY: _ClassVar[ErrorCode]
    ERROR_CODE_BATCH_TOO_LARGE: _ClassVar[ErrorCode]
    ERROR_CODE_MODIFICATION_REQUIRES_REPLACE: _ClassVar[ErrorCode]
    ERROR_CODE_CONFLICT_IDEMPOTENCY_KEY_REUSE: _ClassVar[ErrorCode]
    ERROR_CODE_MARKET_PRICE_UNAVAILABLE: _ClassVar[ErrorCode]
    ERROR_CODE_PAIR_NOT_LISTED_YET: _ClassVar[ErrorCode]
    ERROR_CODE_PAIR_DELISTED: _ClassVar[ErrorCode]
    ERROR_CODE_PAIR_CANCEL_ONLY: _ClassVar[ErrorCode]
    ERROR_CODE_PAIR_POST_ONLY: _ClassVar[ErrorCode]
    ERROR_CODE_PAIR_REDUCE_ONLY: _ClassVar[ErrorCode]
    ERROR_CODE_RISK_LIMIT: _ClassVar[ErrorCode]
    ERROR_CODE_MARKET_HALTED: _ClassVar[ErrorCode]
    ERROR_CODE_ACCOUNT_UNKNOWN: _ClassVar[ErrorCode]
    ERROR_CODE_POST_ONLY_CROSS: _ClassVar[ErrorCode]
    ERROR_CODE_REDUCE_ONLY_BLOCKED: _ClassVar[ErrorCode]
    ERROR_CODE_PRICE_BAND_VIOLATION: _ClassVar[ErrorCode]
    ERROR_CODE_MARKET_CAP_VIOLATION: _ClassVar[ErrorCode]
    ERROR_CODE_EMPTY_BOOK: _ClassVar[ErrorCode]
    ERROR_CODE_FOK_INSUFFICIENT_LIQUIDITY: _ClassVar[ErrorCode]
    ERROR_CODE_ORDER_ALREADY_TERMINAL: _ClassVar[ErrorCode]
    ERROR_CODE_TRIGGER_PRICE_INVALID: _ClassVar[ErrorCode]
    ERROR_CODE_TRIGGER_PRICE_SOURCE_UNSUPPORTED: _ClassVar[ErrorCode]
    ERROR_CODE_TRAILING_DISTANCE_INVALID: _ClassVar[ErrorCode]
    ERROR_CODE_TRIGGER_NOT_FOUND: _ClassVar[ErrorCode]
    ERROR_CODE_TRIGGER_CANCEL_REJECTED: _ClassVar[ErrorCode]
    ERROR_CODE_TRIGGER_STATUS_INVALID: _ClassVar[ErrorCode]
    ERROR_CODE_TRIGGER_NOT_MODIFIABLE: _ClassVar[ErrorCode]
    ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_TRIGGER_ID: _ClassVar[ErrorCode]
    ERROR_CODE_MAX_SLIPPAGE_INVALID: _ClassVar[ErrorCode]
    ERROR_CODE_STALE_QUOTE: _ClassVar[ErrorCode]
    ERROR_CODE_VALIDATION_ERROR: _ClassVar[ErrorCode]
    ERROR_CODE_OVERLOADED: _ClassVar[ErrorCode]
    ERROR_CODE_MAX_QUOTE_DEBIT_TOO_SMALL: _ClassVar[ErrorCode]
    ERROR_CODE_RATE_LIMIT_EXCEEDED: _ClassVar[ErrorCode]

class TriggerPriceSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRIGGER_PRICE_SOURCE_UNSPECIFIED: _ClassVar[TriggerPriceSource]
    LAST_PRICE: _ClassVar[TriggerPriceSource]
    INDEX_PRICE: _ClassVar[TriggerPriceSource]
    MARK_PRICE: _ClassVar[TriggerPriceSource]

class TriggerDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRIGGER_DIRECTION_UNSPECIFIED: _ClassVar[TriggerDirection]
    ABOVE: _ClassVar[TriggerDirection]
    BELOW: _ClassVar[TriggerDirection]

class ModifyBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MODIFY_BEHAVIOR_UNSPECIFIED: _ClassVar[ModifyBehavior]
    AMEND_OR_REPLACE: _ClassVar[ModifyBehavior]
    AMEND_ONLY: _ClassVar[ModifyBehavior]
    REPLACE_ONLY: _ClassVar[ModifyBehavior]

class ModifyActionTaken(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MODIFY_ACTION_UNSPECIFIED: _ClassVar[ModifyActionTaken]
    AMENDED: _ClassVar[ModifyActionTaken]
    REPLACED: _ClassVar[ModifyActionTaken]

class BatchReplaceAdmissionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BATCH_REPLACE_ADMISSION_STATUS_UNSPECIFIED: _ClassVar[BatchReplaceAdmissionStatus]
    BATCH_REPLACE_ADMISSION_STATUS_ADMITTED: _ClassVar[BatchReplaceAdmissionStatus]
    BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED: _ClassVar[BatchReplaceAdmissionStatus]
    BATCH_REPLACE_ADMISSION_STATUS_REJECTED: _ClassVar[BatchReplaceAdmissionStatus]

class BatchReplaceItemAdmissionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BATCH_REPLACE_ITEM_ADMISSION_STATUS_UNSPECIFIED: _ClassVar[BatchReplaceItemAdmissionStatus]
    BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED: _ClassVar[BatchReplaceItemAdmissionStatus]
    BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED: _ClassVar[BatchReplaceItemAdmissionStatus]
SIDE_UNSPECIFIED: Side
BUY: Side
SELL: Side
ORDER_TYPE_UNSPECIFIED: OrderType
LIMIT: OrderType
MARKET: OrderType
TIME_IN_FORCE_UNSPECIFIED: TimeInForce
GTC: TimeInForce
IOC: TimeInForce
FOK: TimeInForce
FEE_ASSET_UNSPECIFIED: FeeAsset
QUOTE: FeeAsset
BASE: FeeAsset
SELF_TRADE_PREVENTION_MODE_UNSPECIFIED: SelfTradePreventionMode
EXPIRE_MAKER: SelfTradePreventionMode
EXPIRE_TAKER: SelfTradePreventionMode
EXPIRE_BOTH: SelfTradePreventionMode
ERROR_CODE_UNSPECIFIED: ErrorCode
ERROR_CODE_BAD_REQUEST: ErrorCode
ERROR_CODE_INVALID_ARGUMENT: ErrorCode
ERROR_CODE_INSUFFICIENT_FUNDS: ErrorCode
ERROR_CODE_UNKNOWN_SYMBOL: ErrorCode
ERROR_CODE_BAD_PRICE: ErrorCode
ERROR_CODE_BAD_QTY: ErrorCode
ERROR_CODE_MIN_NOTIONAL: ErrorCode
ERROR_CODE_QTY_STEP_SIZE: ErrorCode
ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_ORDER_ID: ErrorCode
ERROR_CODE_UNAVAILABLE: ErrorCode
ERROR_CODE_UNAUTHENTICATED: ErrorCode
ERROR_CODE_PERMISSION_DENIED: ErrorCode
ERROR_CODE_NOT_FOUND: ErrorCode
ERROR_CODE_UPSTREAM_ERROR: ErrorCode
ERROR_CODE_FEE_ASSET_NOT_ALLOWED: ErrorCode
ERROR_CODE_PAIR_DISABLED: ErrorCode
ERROR_CODE_ORDER_UNKNOWN: ErrorCode
ERROR_CODE_INTERNAL_ERROR: ErrorCode
ERROR_CODE_SUBACCOUNT_INACTIVE: ErrorCode
ERROR_CODE_POLICY_MARKET_DENY: ErrorCode
ERROR_CODE_POLICY_MAX_NOTIONAL: ErrorCode
ERROR_CODE_POLICY_TRADING_HALTED: ErrorCode
ERROR_CODE_POLICY_SPOT_TRADE_DENY: ErrorCode
ERROR_CODE_API_KEY_ROOT_SCOPE_ONLY: ErrorCode
ERROR_CODE_API_KEY_SUB_SCOPE_ONLY: ErrorCode
ERROR_CODE_API_KEY_SUBACCOUNT_MISMATCH: ErrorCode
ERROR_CODE_API_KEY_POLICY_REQUIRED: ErrorCode
ERROR_CODE_API_KEY_UNKNOWN: ErrorCode
ERROR_CODE_API_KEY_MARKET_DENY: ErrorCode
ERROR_CODE_PRICE_TICK_SIZE: ErrorCode
ERROR_CODE_MIN_QTY: ErrorCode
ERROR_CODE_POST_ONLY_LIMIT_ONLY: ErrorCode
ERROR_CODE_BATCH_TOO_LARGE: ErrorCode
ERROR_CODE_MODIFICATION_REQUIRES_REPLACE: ErrorCode
ERROR_CODE_CONFLICT_IDEMPOTENCY_KEY_REUSE: ErrorCode
ERROR_CODE_MARKET_PRICE_UNAVAILABLE: ErrorCode
ERROR_CODE_PAIR_NOT_LISTED_YET: ErrorCode
ERROR_CODE_PAIR_DELISTED: ErrorCode
ERROR_CODE_PAIR_CANCEL_ONLY: ErrorCode
ERROR_CODE_PAIR_POST_ONLY: ErrorCode
ERROR_CODE_PAIR_REDUCE_ONLY: ErrorCode
ERROR_CODE_RISK_LIMIT: ErrorCode
ERROR_CODE_MARKET_HALTED: ErrorCode
ERROR_CODE_ACCOUNT_UNKNOWN: ErrorCode
ERROR_CODE_POST_ONLY_CROSS: ErrorCode
ERROR_CODE_REDUCE_ONLY_BLOCKED: ErrorCode
ERROR_CODE_PRICE_BAND_VIOLATION: ErrorCode
ERROR_CODE_MARKET_CAP_VIOLATION: ErrorCode
ERROR_CODE_EMPTY_BOOK: ErrorCode
ERROR_CODE_FOK_INSUFFICIENT_LIQUIDITY: ErrorCode
ERROR_CODE_ORDER_ALREADY_TERMINAL: ErrorCode
ERROR_CODE_TRIGGER_PRICE_INVALID: ErrorCode
ERROR_CODE_TRIGGER_PRICE_SOURCE_UNSUPPORTED: ErrorCode
ERROR_CODE_TRAILING_DISTANCE_INVALID: ErrorCode
ERROR_CODE_TRIGGER_NOT_FOUND: ErrorCode
ERROR_CODE_TRIGGER_CANCEL_REJECTED: ErrorCode
ERROR_CODE_TRIGGER_STATUS_INVALID: ErrorCode
ERROR_CODE_TRIGGER_NOT_MODIFIABLE: ErrorCode
ERROR_CODE_CONFLICT_DUPLICATE_CLIENT_TRIGGER_ID: ErrorCode
ERROR_CODE_MAX_SLIPPAGE_INVALID: ErrorCode
ERROR_CODE_STALE_QUOTE: ErrorCode
ERROR_CODE_VALIDATION_ERROR: ErrorCode
ERROR_CODE_OVERLOADED: ErrorCode
ERROR_CODE_MAX_QUOTE_DEBIT_TOO_SMALL: ErrorCode
ERROR_CODE_RATE_LIMIT_EXCEEDED: ErrorCode
TRIGGER_PRICE_SOURCE_UNSPECIFIED: TriggerPriceSource
LAST_PRICE: TriggerPriceSource
INDEX_PRICE: TriggerPriceSource
MARK_PRICE: TriggerPriceSource
TRIGGER_DIRECTION_UNSPECIFIED: TriggerDirection
ABOVE: TriggerDirection
BELOW: TriggerDirection
MODIFY_BEHAVIOR_UNSPECIFIED: ModifyBehavior
AMEND_OR_REPLACE: ModifyBehavior
AMEND_ONLY: ModifyBehavior
REPLACE_ONLY: ModifyBehavior
MODIFY_ACTION_UNSPECIFIED: ModifyActionTaken
AMENDED: ModifyActionTaken
REPLACED: ModifyActionTaken
BATCH_REPLACE_ADMISSION_STATUS_UNSPECIFIED: BatchReplaceAdmissionStatus
BATCH_REPLACE_ADMISSION_STATUS_ADMITTED: BatchReplaceAdmissionStatus
BATCH_REPLACE_ADMISSION_STATUS_PARTIALLY_ADMITTED: BatchReplaceAdmissionStatus
BATCH_REPLACE_ADMISSION_STATUS_REJECTED: BatchReplaceAdmissionStatus
BATCH_REPLACE_ITEM_ADMISSION_STATUS_UNSPECIFIED: BatchReplaceItemAdmissionStatus
BATCH_REPLACE_ITEM_ADMISSION_STATUS_ADMITTED: BatchReplaceItemAdmissionStatus
BATCH_REPLACE_ITEM_ADMISSION_STATUS_REJECTED: BatchReplaceItemAdmissionStatus

class MarketIoc(_message.Message):
    __slots__ = ("max_slippage_ticks", "max_slippage_bps", "client_ref_price_ticks")
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_REF_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    max_slippage_ticks: int
    max_slippage_bps: int
    client_ref_price_ticks: int
    def __init__(self, max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ..., client_ref_price_ticks: _Optional[int] = ...) -> None: ...

class LimitGtc(_message.Message):
    __slots__ = ("price_ticks", "post_only")
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    post_only: bool
    def __init__(self, price_ticks: _Optional[int] = ..., post_only: _Optional[bool] = ...) -> None: ...

class LimitIoc(_message.Message):
    __slots__ = ("price_ticks",)
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    def __init__(self, price_ticks: _Optional[int] = ...) -> None: ...

class LimitFok(_message.Message):
    __slots__ = ("price_ticks",)
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    def __init__(self, price_ticks: _Optional[int] = ...) -> None: ...

class OrderIntent(_message.Message):
    __slots__ = ("symbol", "side", "base_qty_scaled", "max_quote_debit_scaled", "market_ioc", "limit_gtc", "limit_ioc", "limit_fok", "client_order_id", "fee_asset", "self_trade_prevention_mode", "attached_risk")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    BASE_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    MAX_QUOTE_DEBIT_SCALED_FIELD_NUMBER: _ClassVar[int]
    MARKET_IOC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_GTC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_IOC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FOK_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_PREVENTION_MODE_FIELD_NUMBER: _ClassVar[int]
    ATTACHED_RISK_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    side: Side
    base_qty_scaled: int
    max_quote_debit_scaled: int
    market_ioc: MarketIoc
    limit_gtc: LimitGtc
    limit_ioc: LimitIoc
    limit_fok: LimitFok
    client_order_id: str
    fee_asset: FeeAsset
    self_trade_prevention_mode: SelfTradePreventionMode
    attached_risk: RiskPolicy
    def __init__(self, symbol: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., base_qty_scaled: _Optional[int] = ..., max_quote_debit_scaled: _Optional[int] = ..., market_ioc: _Optional[_Union[MarketIoc, _Mapping]] = ..., limit_gtc: _Optional[_Union[LimitGtc, _Mapping]] = ..., limit_ioc: _Optional[_Union[LimitIoc, _Mapping]] = ..., limit_fok: _Optional[_Union[LimitFok, _Mapping]] = ..., client_order_id: _Optional[str] = ..., fee_asset: _Optional[_Union[FeeAsset, str]] = ..., self_trade_prevention_mode: _Optional[_Union[SelfTradePreventionMode, str]] = ..., attached_risk: _Optional[_Union[RiskPolicy, _Mapping]] = ...) -> None: ...

class CreateOrderRequest(_message.Message):
    __slots__ = ("subaccount_id", "order")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    order: OrderIntent
    def __init__(self, subaccount_id: _Optional[int] = ..., order: _Optional[_Union[OrderIntent, _Mapping]] = ...) -> None: ...

class CreateOrderResponse(_message.Message):
    __slots__ = ("order_id", "client_order_id", "accepted_at", "accepted_at_ts_ns", "resolved_base_qty_scaled", "submitted_max_quote_debit_scaled", "take_profit_trigger_id", "stop_loss_trigger_id", "trailing_stop_trigger_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_AT_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_AT_TS_NS_FIELD_NUMBER: _ClassVar[int]
    RESOLVED_BASE_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_MAX_QUOTE_DEBIT_SCALED_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    client_order_id: str
    accepted_at: _timestamp_pb2.Timestamp
    accepted_at_ts_ns: int
    resolved_base_qty_scaled: int
    submitted_max_quote_debit_scaled: int
    take_profit_trigger_id: int
    stop_loss_trigger_id: int
    trailing_stop_trigger_id: int
    def __init__(self, order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., accepted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., accepted_at_ts_ns: _Optional[int] = ..., resolved_base_qty_scaled: _Optional[int] = ..., submitted_max_quote_debit_scaled: _Optional[int] = ..., take_profit_trigger_id: _Optional[int] = ..., stop_loss_trigger_id: _Optional[int] = ..., trailing_stop_trigger_id: _Optional[int] = ...) -> None: ...

class PreviewOrderRequest(_message.Message):
    __slots__ = ("subaccount_id", "order")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    order: OrderIntent
    def __init__(self, subaccount_id: _Optional[int] = ..., order: _Optional[_Union[OrderIntent, _Mapping]] = ...) -> None: ...

class PreviewOrderResponse(_message.Message):
    __slots__ = ("admissible", "rejection", "resolved_base_qty_scaled", "protected_price_bound_ticks", "evaluated_at")
    ADMISSIBLE_FIELD_NUMBER: _ClassVar[int]
    REJECTION_FIELD_NUMBER: _ClassVar[int]
    RESOLVED_BASE_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    PROTECTED_PRICE_BOUND_TICKS_FIELD_NUMBER: _ClassVar[int]
    EVALUATED_AT_FIELD_NUMBER: _ClassVar[int]
    admissible: bool
    rejection: ErrorDetail
    resolved_base_qty_scaled: int
    protected_price_bound_ticks: int
    evaluated_at: _timestamp_pb2.Timestamp
    def __init__(self, admissible: _Optional[bool] = ..., rejection: _Optional[_Union[ErrorDetail, _Mapping]] = ..., resolved_base_qty_scaled: _Optional[int] = ..., protected_price_bound_ticks: _Optional[int] = ..., evaluated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CancelOrderRequest(_message.Message):
    __slots__ = ("order_id", "client_order_id", "symbol_id", "subaccount_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    client_order_id: str
    symbol_id: int
    subaccount_id: int
    def __init__(self, order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., symbol_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class CancelOrderResponse(_message.Message):
    __slots__ = ("status", "order_id", "ts", "ts_ns")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    status: str
    order_id: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, status: _Optional[str] = ..., order_id: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class FieldViolation(_message.Message):
    __slots__ = ("field_path", "rule_id", "message")
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    RULE_ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    field_path: str
    rule_id: str
    message: str
    def __init__(self, field_path: _Optional[str] = ..., rule_id: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ErrorDetail(_message.Message):
    __slots__ = ("code", "violations", "rate_limit")
    CODE_FIELD_NUMBER: _ClassVar[int]
    VIOLATIONS_FIELD_NUMBER: _ClassVar[int]
    RATE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    violations: _containers.RepeatedCompositeFieldContainer[FieldViolation]
    rate_limit: _types_pb2.RateLimitDetail
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ..., violations: _Optional[_Iterable[_Union[FieldViolation, _Mapping]]] = ..., rate_limit: _Optional[_Union[_types_pb2.RateLimitDetail, _Mapping]] = ...) -> None: ...

class RiskMarketIoc(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RiskLimitGtc(_message.Message):
    __slots__ = ("price_ticks",)
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    def __init__(self, price_ticks: _Optional[int] = ...) -> None: ...

class RiskExecution(_message.Message):
    __slots__ = ("market_ioc", "limit_gtc")
    MARKET_IOC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_GTC_FIELD_NUMBER: _ClassVar[int]
    market_ioc: RiskMarketIoc
    limit_gtc: RiskLimitGtc
    def __init__(self, market_ioc: _Optional[_Union[RiskMarketIoc, _Mapping]] = ..., limit_gtc: _Optional[_Union[RiskLimitGtc, _Mapping]] = ...) -> None: ...

class TakeProfitPolicy(_message.Message):
    __slots__ = ("trigger_price_ticks", "child")
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    CHILD_FIELD_NUMBER: _ClassVar[int]
    trigger_price_ticks: int
    child: RiskExecution
    def __init__(self, trigger_price_ticks: _Optional[int] = ..., child: _Optional[_Union[RiskExecution, _Mapping]] = ...) -> None: ...

class StopLossPolicy(_message.Message):
    __slots__ = ("trigger_price_ticks", "child")
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    CHILD_FIELD_NUMBER: _ClassVar[int]
    trigger_price_ticks: int
    child: RiskExecution
    def __init__(self, trigger_price_ticks: _Optional[int] = ..., child: _Optional[_Union[RiskExecution, _Mapping]] = ...) -> None: ...

class TrailingStopPolicy(_message.Message):
    __slots__ = ("trailing_distance_ticks", "trailing_distance_bps", "max_slippage_ticks", "max_slippage_bps", "activation_price_ticks")
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    trailing_distance_ticks: int
    trailing_distance_bps: int
    max_slippage_ticks: int
    max_slippage_bps: int
    activation_price_ticks: int
    def __init__(self, trailing_distance_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ...) -> None: ...

class RiskPolicy(_message.Message):
    __slots__ = ("take_profit", "stop_loss", "trailing_stop", "oco")
    TAKE_PROFIT_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_FIELD_NUMBER: _ClassVar[int]
    OCO_FIELD_NUMBER: _ClassVar[int]
    take_profit: TakeProfitPolicy
    stop_loss: StopLossPolicy
    trailing_stop: TrailingStopPolicy
    oco: bool
    def __init__(self, take_profit: _Optional[_Union[TakeProfitPolicy, _Mapping]] = ..., stop_loss: _Optional[_Union[StopLossPolicy, _Mapping]] = ..., trailing_stop: _Optional[_Union[TrailingStopPolicy, _Mapping]] = ..., oco: _Optional[bool] = ...) -> None: ...

class CancelAllOrdersRequest(_message.Message):
    __slots__ = ("subaccount_id", "symbol", "side", "dry_run", "request_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    DRY_RUN_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol: str
    side: Side
    dry_run: bool
    request_id: str
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., dry_run: _Optional[bool] = ..., request_id: _Optional[str] = ...) -> None: ...

class CancelAllOrdersResponse(_message.Message):
    __slots__ = ("status", "matched_orders", "submitted_cancels", "failed_cancels", "ts", "ts_ns")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MATCHED_ORDERS_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_CANCELS_FIELD_NUMBER: _ClassVar[int]
    FAILED_CANCELS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    status: str
    matched_orders: int
    submitted_cancels: int
    failed_cancels: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, status: _Optional[str] = ..., matched_orders: _Optional[int] = ..., submitted_cancels: _Optional[int] = ..., failed_cancels: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class CancelAllAfterRequest(_message.Message):
    __slots__ = ("subaccount_id", "timeout_sec", "symbol", "side", "request_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_SEC_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    timeout_sec: int
    symbol: str
    side: Side
    request_id: str
    def __init__(self, subaccount_id: _Optional[int] = ..., timeout_sec: _Optional[int] = ..., symbol: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., request_id: _Optional[str] = ...) -> None: ...

class CancelAllAfterResponse(_message.Message):
    __slots__ = ("status", "effective_timeout_sec", "expires_at_ts_ns", "ts", "ts_ns")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_TIMEOUT_SEC_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_TS_NS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    status: str
    effective_timeout_sec: int
    expires_at_ts_ns: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, status: _Optional[str] = ..., effective_timeout_sec: _Optional[int] = ..., expires_at_ts_ns: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class BatchCreateAccepted(_message.Message):
    __slots__ = ("order_id", "take_profit_trigger_id", "stop_loss_trigger_id", "trailing_stop_trigger_id", "resolved_base_qty_scaled", "submitted_max_quote_debit_scaled")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    RESOLVED_BASE_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    SUBMITTED_MAX_QUOTE_DEBIT_SCALED_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    take_profit_trigger_id: int
    stop_loss_trigger_id: int
    trailing_stop_trigger_id: int
    resolved_base_qty_scaled: int
    submitted_max_quote_debit_scaled: int
    def __init__(self, order_id: _Optional[int] = ..., take_profit_trigger_id: _Optional[int] = ..., stop_loss_trigger_id: _Optional[int] = ..., trailing_stop_trigger_id: _Optional[int] = ..., resolved_base_qty_scaled: _Optional[int] = ..., submitted_max_quote_debit_scaled: _Optional[int] = ...) -> None: ...

class BatchCreateRejected(_message.Message):
    __slots__ = ("error",)
    ERROR_FIELD_NUMBER: _ClassVar[int]
    error: ErrorDetail
    def __init__(self, error: _Optional[_Union[ErrorDetail, _Mapping]] = ...) -> None: ...

class BatchCreateResultItem(_message.Message):
    __slots__ = ("client_order_id", "accepted", "rejected")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    REJECTED_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    accepted: BatchCreateAccepted
    rejected: BatchCreateRejected
    def __init__(self, client_order_id: _Optional[str] = ..., accepted: _Optional[_Union[BatchCreateAccepted, _Mapping]] = ..., rejected: _Optional[_Union[BatchCreateRejected, _Mapping]] = ...) -> None: ...

class BatchCreateOrdersRequest(_message.Message):
    __slots__ = ("subaccount_id", "request_id", "items")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    request_id: str
    items: _containers.RepeatedCompositeFieldContainer[OrderIntent]
    def __init__(self, subaccount_id: _Optional[int] = ..., request_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[OrderIntent, _Mapping]]] = ...) -> None: ...

class BatchCreateOrdersResponse(_message.Message):
    __slots__ = ("results", "accepted_count", "rejected_count", "ts", "ts_ns")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    REJECTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[BatchCreateResultItem]
    accepted_count: int
    rejected_count: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, results: _Optional[_Iterable[_Union[BatchCreateResultItem, _Mapping]]] = ..., accepted_count: _Optional[int] = ..., rejected_count: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class ModifyOrderRequest(_message.Message):
    __slots__ = ("subaccount_id", "order_id", "client_order_id", "request_id", "new_price_ticks", "new_qty_scaled", "new_attached_risk", "behavior", "new_client_order_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    NEW_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    NEW_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    NEW_ATTACHED_RISK_FIELD_NUMBER: _ClassVar[int]
    BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
    NEW_CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    order_id: int
    client_order_id: str
    request_id: str
    new_price_ticks: int
    new_qty_scaled: int
    new_attached_risk: RiskPolicy
    behavior: ModifyBehavior
    new_client_order_id: str
    def __init__(self, subaccount_id: _Optional[int] = ..., order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., request_id: _Optional[str] = ..., new_price_ticks: _Optional[int] = ..., new_qty_scaled: _Optional[int] = ..., new_attached_risk: _Optional[_Union[RiskPolicy, _Mapping]] = ..., behavior: _Optional[_Union[ModifyBehavior, str]] = ..., new_client_order_id: _Optional[str] = ...) -> None: ...

class ModifyOrderResponse(_message.Message):
    __slots__ = ("action_taken", "old_order_id", "final_order_id", "code", "take_profit_trigger_id", "stop_loss_trigger_id", "trailing_stop_trigger_id", "ts", "ts_ns")
    ACTION_TAKEN_FIELD_NUMBER: _ClassVar[int]
    OLD_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FINAL_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    action_taken: ModifyActionTaken
    old_order_id: int
    final_order_id: int
    code: str
    take_profit_trigger_id: int
    stop_loss_trigger_id: int
    trailing_stop_trigger_id: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, action_taken: _Optional[_Union[ModifyActionTaken, str]] = ..., old_order_id: _Optional[int] = ..., final_order_id: _Optional[int] = ..., code: _Optional[str] = ..., take_profit_trigger_id: _Optional[int] = ..., stop_loss_trigger_id: _Optional[int] = ..., trailing_stop_trigger_id: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class BatchReplaceOrderItem(_message.Message):
    __slots__ = ("order_id", "client_order_id", "new_price_ticks", "new_qty_scaled", "new_attached_risk", "new_client_order_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    NEW_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    NEW_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    NEW_ATTACHED_RISK_FIELD_NUMBER: _ClassVar[int]
    NEW_CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    client_order_id: str
    new_price_ticks: int
    new_qty_scaled: int
    new_attached_risk: RiskPolicy
    new_client_order_id: str
    def __init__(self, order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., new_price_ticks: _Optional[int] = ..., new_qty_scaled: _Optional[int] = ..., new_attached_risk: _Optional[_Union[RiskPolicy, _Mapping]] = ..., new_client_order_id: _Optional[str] = ...) -> None: ...

class BatchReplaceAdmissionItem(_message.Message):
    __slots__ = ("item_index", "status", "old_order_id", "replacement_order_id", "client_order_id", "code", "error")
    ITEM_INDEX_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    OLD_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REPLACEMENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    item_index: int
    status: BatchReplaceItemAdmissionStatus
    old_order_id: int
    replacement_order_id: int
    client_order_id: str
    code: str
    error: ErrorDetail
    def __init__(self, item_index: _Optional[int] = ..., status: _Optional[_Union[BatchReplaceItemAdmissionStatus, str]] = ..., old_order_id: _Optional[int] = ..., replacement_order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., code: _Optional[str] = ..., error: _Optional[_Union[ErrorDetail, _Mapping]] = ...) -> None: ...

class BatchReplaceOrdersRequest(_message.Message):
    __slots__ = ("subaccount_id", "symbol_id", "request_id", "items")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol_id: int
    request_id: str
    items: _containers.RepeatedCompositeFieldContainer[BatchReplaceOrderItem]
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., request_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[BatchReplaceOrderItem, _Mapping]]] = ...) -> None: ...

class BatchReplaceOrdersResponse(_message.Message):
    __slots__ = ("batch_request_id", "status", "results", "accepted_count", "rejected_count", "accepted_ts", "accepted_ts_ns")
    BATCH_REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    REJECTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_TS_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_TS_NS_FIELD_NUMBER: _ClassVar[int]
    batch_request_id: int
    status: BatchReplaceAdmissionStatus
    results: _containers.RepeatedCompositeFieldContainer[BatchReplaceAdmissionItem]
    accepted_count: int
    rejected_count: int
    accepted_ts: _timestamp_pb2.Timestamp
    accepted_ts_ns: int
    def __init__(self, batch_request_id: _Optional[int] = ..., status: _Optional[_Union[BatchReplaceAdmissionStatus, str]] = ..., results: _Optional[_Iterable[_Union[BatchReplaceAdmissionItem, _Mapping]]] = ..., accepted_count: _Optional[int] = ..., rejected_count: _Optional[int] = ..., accepted_ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., accepted_ts_ns: _Optional[int] = ...) -> None: ...

class BatchCancelItem(_message.Message):
    __slots__ = ("order_id", "client_order_id", "symbol_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    client_order_id: str
    symbol_id: int
    def __init__(self, order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., symbol_id: _Optional[int] = ...) -> None: ...

class BatchCancelResultItem(_message.Message):
    __slots__ = ("status", "order_id", "client_order_id", "code", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: str
    order_id: int
    client_order_id: str
    code: str
    error: ErrorDetail
    def __init__(self, status: _Optional[str] = ..., order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., code: _Optional[str] = ..., error: _Optional[_Union[ErrorDetail, _Mapping]] = ...) -> None: ...

class BatchCancelOrdersRequest(_message.Message):
    __slots__ = ("subaccount_id", "request_id", "items")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    request_id: str
    items: _containers.RepeatedCompositeFieldContainer[BatchCancelItem]
    def __init__(self, subaccount_id: _Optional[int] = ..., request_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[BatchCancelItem, _Mapping]]] = ...) -> None: ...

class BatchCancelOrdersResponse(_message.Message):
    __slots__ = ("results", "accepted_count", "rejected_count", "ts", "ts_ns")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    REJECTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[BatchCancelResultItem]
    accepted_count: int
    rejected_count: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, results: _Optional[_Iterable[_Union[BatchCancelResultItem, _Mapping]]] = ..., accepted_count: _Optional[int] = ..., rejected_count: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...
