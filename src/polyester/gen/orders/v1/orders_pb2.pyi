import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
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

class FeeSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FEE_SOURCE_UNSPECIFIED: _ClassVar[FeeSource]
    QUOTE: _ClassVar[FeeSource]
    RECEIVED: _ClassVar[FeeSource]

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
    ERROR_CODE_FEE_SOURCE_NOT_ALLOWED: _ClassVar[ErrorCode]
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
FEE_SOURCE_UNSPECIFIED: FeeSource
QUOTE: FeeSource
RECEIVED: FeeSource
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
ERROR_CODE_FEE_SOURCE_NOT_ALLOWED: ErrorCode
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

class CreateOrderRequest(_message.Message):
    __slots__ = ("subaccount_id", "symbol", "side", "order_type", "time_in_force", "qty_scaled", "price_ticks", "market_max_slippage_ticks", "market_max_slippage_bps", "market_client_ref_price_ticks", "post_only", "client_order_id", "fee_source", "self_trade_prevention_mode", "attached_risk")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MARKET_MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MARKET_MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    MARKET_CLIENT_REF_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FEE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_PREVENTION_MODE_FIELD_NUMBER: _ClassVar[int]
    ATTACHED_RISK_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol: str
    side: Side
    order_type: OrderType
    time_in_force: TimeInForce
    qty_scaled: int
    price_ticks: int
    market_max_slippage_ticks: int
    market_max_slippage_bps: int
    market_client_ref_price_ticks: int
    post_only: bool
    client_order_id: str
    fee_source: FeeSource
    self_trade_prevention_mode: SelfTradePreventionMode
    attached_risk: RiskPolicy
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol: _Optional[str] = ..., side: _Optional[_Union[Side, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., time_in_force: _Optional[_Union[TimeInForce, str]] = ..., qty_scaled: _Optional[int] = ..., price_ticks: _Optional[int] = ..., market_max_slippage_ticks: _Optional[int] = ..., market_max_slippage_bps: _Optional[int] = ..., market_client_ref_price_ticks: _Optional[int] = ..., post_only: _Optional[bool] = ..., client_order_id: _Optional[str] = ..., fee_source: _Optional[_Union[FeeSource, str]] = ..., self_trade_prevention_mode: _Optional[_Union[SelfTradePreventionMode, str]] = ..., attached_risk: _Optional[_Union[RiskPolicy, _Mapping]] = ...) -> None: ...

class CreateOrderResponse(_message.Message):
    __slots__ = ("status", "order_id", "client_order_id", "ts", "ts_ns", "take_profit_trigger_id", "stop_loss_trigger_id", "trailing_stop_trigger_id")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    status: str
    order_id: int
    client_order_id: str
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    take_profit_trigger_id: int
    stop_loss_trigger_id: int
    trailing_stop_trigger_id: int
    def __init__(self, status: _Optional[str] = ..., order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ..., take_profit_trigger_id: _Optional[int] = ..., stop_loss_trigger_id: _Optional[int] = ..., trailing_stop_trigger_id: _Optional[int] = ...) -> None: ...

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

class ErrorDetail(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ...) -> None: ...

class TakeProfitPolicy(_message.Message):
    __slots__ = ("trigger_price_ticks", "trigger_price_source", "order_type", "limit_price_ticks")
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    trigger_price_ticks: int
    trigger_price_source: TriggerPriceSource
    order_type: OrderType
    limit_price_ticks: int
    def __init__(self, trigger_price_ticks: _Optional[int] = ..., trigger_price_source: _Optional[_Union[TriggerPriceSource, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., limit_price_ticks: _Optional[int] = ...) -> None: ...

class StopLossPolicy(_message.Message):
    __slots__ = ("trigger_price_ticks", "trigger_price_source", "order_type", "limit_price_ticks")
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    trigger_price_ticks: int
    trigger_price_source: TriggerPriceSource
    order_type: OrderType
    limit_price_ticks: int
    def __init__(self, trigger_price_ticks: _Optional[int] = ..., trigger_price_source: _Optional[_Union[TriggerPriceSource, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., limit_price_ticks: _Optional[int] = ...) -> None: ...

class TrailingStopPolicy(_message.Message):
    __slots__ = ("trailing_distance_ticks", "trailing_distance_bps", "max_slippage_ticks", "max_slippage_bps", "activation_price_ticks", "trigger_price_source", "order_type")
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    trailing_distance_ticks: int
    trailing_distance_bps: int
    max_slippage_ticks: int
    max_slippage_bps: int
    activation_price_ticks: int
    trigger_price_source: TriggerPriceSource
    order_type: OrderType
    def __init__(self, trailing_distance_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ..., trigger_price_source: _Optional[_Union[TriggerPriceSource, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ...) -> None: ...

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

class BatchCreateResultItem(_message.Message):
    __slots__ = ("status", "order_id", "client_order_id", "code", "take_profit_trigger_id", "stop_loss_trigger_id", "trailing_stop_trigger_id")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    status: str
    order_id: int
    client_order_id: str
    code: str
    take_profit_trigger_id: int
    stop_loss_trigger_id: int
    trailing_stop_trigger_id: int
    def __init__(self, status: _Optional[str] = ..., order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., code: _Optional[str] = ..., take_profit_trigger_id: _Optional[int] = ..., stop_loss_trigger_id: _Optional[int] = ..., trailing_stop_trigger_id: _Optional[int] = ...) -> None: ...

class BatchCreateOrdersRequest(_message.Message):
    __slots__ = ("subaccount_id", "request_id", "items", "allow_partial")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    ALLOW_PARTIAL_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    request_id: str
    items: _containers.RepeatedCompositeFieldContainer[CreateOrderRequest]
    allow_partial: bool
    def __init__(self, subaccount_id: _Optional[int] = ..., request_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[CreateOrderRequest, _Mapping]]] = ..., allow_partial: _Optional[bool] = ...) -> None: ...

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

class BatchModifyItem(_message.Message):
    __slots__ = ("order_id", "client_order_id", "new_price_ticks", "new_qty_scaled", "new_attached_risk", "behavior", "new_client_order_id")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    NEW_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    NEW_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    NEW_ATTACHED_RISK_FIELD_NUMBER: _ClassVar[int]
    BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
    NEW_CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    client_order_id: str
    new_price_ticks: int
    new_qty_scaled: int
    new_attached_risk: RiskPolicy
    behavior: ModifyBehavior
    new_client_order_id: str
    def __init__(self, order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., new_price_ticks: _Optional[int] = ..., new_qty_scaled: _Optional[int] = ..., new_attached_risk: _Optional[_Union[RiskPolicy, _Mapping]] = ..., behavior: _Optional[_Union[ModifyBehavior, str]] = ..., new_client_order_id: _Optional[str] = ...) -> None: ...

class BatchModifyResultItem(_message.Message):
    __slots__ = ("status", "action_taken", "old_order_id", "final_order_id", "client_order_id", "code", "take_profit_trigger_id", "stop_loss_trigger_id", "trailing_stop_trigger_id")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ACTION_TAKEN_FIELD_NUMBER: _ClassVar[int]
    OLD_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FINAL_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    status: str
    action_taken: ModifyActionTaken
    old_order_id: int
    final_order_id: int
    client_order_id: str
    code: str
    take_profit_trigger_id: int
    stop_loss_trigger_id: int
    trailing_stop_trigger_id: int
    def __init__(self, status: _Optional[str] = ..., action_taken: _Optional[_Union[ModifyActionTaken, str]] = ..., old_order_id: _Optional[int] = ..., final_order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., code: _Optional[str] = ..., take_profit_trigger_id: _Optional[int] = ..., stop_loss_trigger_id: _Optional[int] = ..., trailing_stop_trigger_id: _Optional[int] = ...) -> None: ...

class BatchModifyOrdersRequest(_message.Message):
    __slots__ = ("subaccount_id", "request_id", "items", "behavior_default", "allow_partial")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    BEHAVIOR_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    ALLOW_PARTIAL_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    request_id: str
    items: _containers.RepeatedCompositeFieldContainer[BatchModifyItem]
    behavior_default: ModifyBehavior
    allow_partial: bool
    def __init__(self, subaccount_id: _Optional[int] = ..., request_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[BatchModifyItem, _Mapping]]] = ..., behavior_default: _Optional[_Union[ModifyBehavior, str]] = ..., allow_partial: _Optional[bool] = ...) -> None: ...

class BatchModifyOrdersResponse(_message.Message):
    __slots__ = ("results", "amended_count", "replaced_count", "rejected_count", "ts", "ts_ns")
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    AMENDED_COUNT_FIELD_NUMBER: _ClassVar[int]
    REPLACED_COUNT_FIELD_NUMBER: _ClassVar[int]
    REJECTED_COUNT_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[BatchModifyResultItem]
    amended_count: int
    replaced_count: int
    rejected_count: int
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, results: _Optional[_Iterable[_Union[BatchModifyResultItem, _Mapping]]] = ..., amended_count: _Optional[int] = ..., replaced_count: _Optional[int] = ..., rejected_count: _Optional[int] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("status", "order_id", "client_order_id", "code")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    status: str
    order_id: int
    client_order_id: str
    code: str
    def __init__(self, status: _Optional[str] = ..., order_id: _Optional[int] = ..., client_order_id: _Optional[str] = ..., code: _Optional[str] = ...) -> None: ...

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
