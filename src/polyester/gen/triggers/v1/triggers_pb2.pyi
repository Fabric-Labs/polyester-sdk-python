import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from polyester.gen.google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.orders.v1 import orders_pb2 as _orders_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TriggerType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRIGGER_TYPE_UNSPECIFIED: _ClassVar[TriggerType]
    STOP_LOSS: _ClassVar[TriggerType]
    TAKE_PROFIT: _ClassVar[TriggerType]
    TRAILING_STOP: _ClassVar[TriggerType]
    TWAP: _ClassVar[TriggerType]
    LADDER: _ClassVar[TriggerType]

class TriggerStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUS_UNSPECIFIED: _ClassVar[TriggerStatus]
    STATUS_CREATED: _ClassVar[TriggerStatus]
    STATUS_ARMED: _ClassVar[TriggerStatus]
    STATUS_RUNNING: _ClassVar[TriggerStatus]
    STATUS_COMPLETED: _ClassVar[TriggerStatus]
    STATUS_CANCELED: _ClassVar[TriggerStatus]
    STATUS_FAILED: _ClassVar[TriggerStatus]
    STATUS_PAUSED: _ClassVar[TriggerStatus]

class TriggerEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVENT_UNSPECIFIED: _ClassVar[TriggerEventType]
    EVENT_FIRED: _ClassVar[TriggerEventType]
    EVENT_CANCELED: _ClassVar[TriggerEventType]
    EVENT_UPDATED: _ClassVar[TriggerEventType]
    EVENT_FAILED: _ClassVar[TriggerEventType]

class LadderDistribution(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LADDER_DISTRIBUTION_UNSPECIFIED: _ClassVar[LadderDistribution]
    LINEAR: _ClassVar[LadderDistribution]
    GEOMETRIC: _ClassVar[LadderDistribution]
    WEIGHTED_FAVORABLE: _ClassVar[LadderDistribution]
TRIGGER_TYPE_UNSPECIFIED: TriggerType
STOP_LOSS: TriggerType
TAKE_PROFIT: TriggerType
TRAILING_STOP: TriggerType
TWAP: TriggerType
LADDER: TriggerType
STATUS_UNSPECIFIED: TriggerStatus
STATUS_CREATED: TriggerStatus
STATUS_ARMED: TriggerStatus
STATUS_RUNNING: TriggerStatus
STATUS_COMPLETED: TriggerStatus
STATUS_CANCELED: TriggerStatus
STATUS_FAILED: TriggerStatus
STATUS_PAUSED: TriggerStatus
EVENT_UNSPECIFIED: TriggerEventType
EVENT_FIRED: TriggerEventType
EVENT_CANCELED: TriggerEventType
EVENT_UPDATED: TriggerEventType
EVENT_FAILED: TriggerEventType
LADDER_DISTRIBUTION_UNSPECIFIED: LadderDistribution
LINEAR: LadderDistribution
GEOMETRIC: LadderDistribution
WEIGHTED_FAVORABLE: LadderDistribution

class TriggerMarketIoc(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TriggerLimitGtc(_message.Message):
    __slots__ = ("price_ticks", "post_only")
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    post_only: bool
    def __init__(self, price_ticks: _Optional[int] = ..., post_only: _Optional[bool] = ...) -> None: ...

class TriggerLimitIoc(_message.Message):
    __slots__ = ("price_ticks",)
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    def __init__(self, price_ticks: _Optional[int] = ...) -> None: ...

class TriggerLimitFok(_message.Message):
    __slots__ = ("price_ticks",)
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    def __init__(self, price_ticks: _Optional[int] = ...) -> None: ...

class ConditionalChildExecution(_message.Message):
    __slots__ = ("market_ioc", "limit_gtc", "limit_ioc", "limit_fok")
    MARKET_IOC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_GTC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_IOC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FOK_FIELD_NUMBER: _ClassVar[int]
    market_ioc: TriggerMarketIoc
    limit_gtc: TriggerLimitGtc
    limit_ioc: TriggerLimitIoc
    limit_fok: TriggerLimitFok
    def __init__(self, market_ioc: _Optional[_Union[TriggerMarketIoc, _Mapping]] = ..., limit_gtc: _Optional[_Union[TriggerLimitGtc, _Mapping]] = ..., limit_ioc: _Optional[_Union[TriggerLimitIoc, _Mapping]] = ..., limit_fok: _Optional[_Union[TriggerLimitFok, _Mapping]] = ...) -> None: ...

class ConditionalTrigger(_message.Message):
    __slots__ = ("trigger_price_ticks", "side", "child")
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    CHILD_FIELD_NUMBER: _ClassVar[int]
    trigger_price_ticks: int
    side: _orders_pb2.Side
    child: ConditionalChildExecution
    def __init__(self, trigger_price_ticks: _Optional[int] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., child: _Optional[_Union[ConditionalChildExecution, _Mapping]] = ...) -> None: ...

class TrailingStopTrigger(_message.Message):
    __slots__ = ("trailing_distance_ticks", "trailing_distance_bps", "activation_price_ticks", "max_slippage_ticks", "max_slippage_bps", "side")
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    trailing_distance_ticks: int
    trailing_distance_bps: int
    activation_price_ticks: int
    max_slippage_ticks: int
    max_slippage_bps: int
    side: _orders_pb2.Side
    def __init__(self, trailing_distance_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ...) -> None: ...

class TwapMarketIoc(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TwapLimitGtc(_message.Message):
    __slots__ = ("price_ticks",)
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    price_ticks: int
    def __init__(self, price_ticks: _Optional[int] = ...) -> None: ...

class TwapTrigger(_message.Message):
    __slots__ = ("side", "duration_ms", "slice_interval_ms", "market_ioc", "limit_gtc")
    SIDE_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    SLICE_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    MARKET_IOC_FIELD_NUMBER: _ClassVar[int]
    LIMIT_GTC_FIELD_NUMBER: _ClassVar[int]
    side: _orders_pb2.Side
    duration_ms: int
    slice_interval_ms: int
    market_ioc: TwapMarketIoc
    limit_gtc: TwapLimitGtc
    def __init__(self, side: _Optional[_Union[_orders_pb2.Side, str]] = ..., duration_ms: _Optional[int] = ..., slice_interval_ms: _Optional[int] = ..., market_ioc: _Optional[_Union[TwapMarketIoc, _Mapping]] = ..., limit_gtc: _Optional[_Union[TwapLimitGtc, _Mapping]] = ...) -> None: ...

class LadderTrigger(_message.Message):
    __slots__ = ("side", "price_min_ticks", "price_max_ticks", "levels", "post_only")
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_MIN_TICKS_FIELD_NUMBER: _ClassVar[int]
    PRICE_MAX_TICKS_FIELD_NUMBER: _ClassVar[int]
    LEVELS_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    side: _orders_pb2.Side
    price_min_ticks: int
    price_max_ticks: int
    levels: int
    post_only: bool
    def __init__(self, side: _Optional[_Union[_orders_pb2.Side, str]] = ..., price_min_ticks: _Optional[int] = ..., price_max_ticks: _Optional[int] = ..., levels: _Optional[int] = ..., post_only: _Optional[bool] = ...) -> None: ...

class TriggerIntent(_message.Message):
    __slots__ = ("symbol_id", "qty_scaled", "fee_asset", "self_trade_prevention_mode", "client_trigger_id", "stop_loss", "take_profit", "trailing_stop", "twap", "ladder")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_PREVENTION_MODE_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_FIELD_NUMBER: _ClassVar[int]
    TWAP_FIELD_NUMBER: _ClassVar[int]
    LADDER_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    qty_scaled: int
    fee_asset: _orders_pb2.FeeAsset
    self_trade_prevention_mode: _orders_pb2.SelfTradePreventionMode
    client_trigger_id: str
    stop_loss: ConditionalTrigger
    take_profit: ConditionalTrigger
    trailing_stop: TrailingStopTrigger
    twap: TwapTrigger
    ladder: LadderTrigger
    def __init__(self, symbol_id: _Optional[int] = ..., qty_scaled: _Optional[int] = ..., fee_asset: _Optional[_Union[_orders_pb2.FeeAsset, str]] = ..., self_trade_prevention_mode: _Optional[_Union[_orders_pb2.SelfTradePreventionMode, str]] = ..., client_trigger_id: _Optional[str] = ..., stop_loss: _Optional[_Union[ConditionalTrigger, _Mapping]] = ..., take_profit: _Optional[_Union[ConditionalTrigger, _Mapping]] = ..., trailing_stop: _Optional[_Union[TrailingStopTrigger, _Mapping]] = ..., twap: _Optional[_Union[TwapTrigger, _Mapping]] = ..., ladder: _Optional[_Union[LadderTrigger, _Mapping]] = ...) -> None: ...

class CreateTriggerRequest(_message.Message):
    __slots__ = ("subaccount_id", "trigger")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    trigger: TriggerIntent
    def __init__(self, subaccount_id: _Optional[int] = ..., trigger: _Optional[_Union[TriggerIntent, _Mapping]] = ...) -> None: ...

class CreateTriggerResponse(_message.Message):
    __slots__ = ("trigger_id", "client_trigger_id", "accepted_at", "accepted_at_ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_AT_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_AT_TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    client_trigger_id: str
    accepted_at: _timestamp_pb2.Timestamp
    accepted_at_ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., client_trigger_id: _Optional[str] = ..., accepted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., accepted_at_ts_ns: _Optional[int] = ...) -> None: ...

class GetTriggerRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class GetTriggerResponse(_message.Message):
    __slots__ = ("trigger",)
    TRIGGER_FIELD_NUMBER: _ClassVar[int]
    trigger: Trigger
    def __init__(self, trigger: _Optional[_Union[Trigger, _Mapping]] = ...) -> None: ...

class ListTriggersRequest(_message.Message):
    __slots__ = ("subaccount_id", "symbol_id", "status", "trigger_type", "parent_order_id", "limit", "page_token")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_TYPE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol_id: int
    status: _containers.RepeatedScalarFieldContainer[TriggerStatus]
    trigger_type: TriggerType
    parent_order_id: int
    limit: int
    page_token: str
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., status: _Optional[_Iterable[_Union[TriggerStatus, str]]] = ..., trigger_type: _Optional[_Union[TriggerType, str]] = ..., parent_order_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListTriggersResponse(_message.Message):
    __slots__ = ("triggers", "next_page_token")
    TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    triggers: _containers.RepeatedCompositeFieldContainer[Trigger]
    next_page_token: str
    def __init__(self, triggers: _Optional[_Iterable[_Union[Trigger, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListTriggerEventsRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "limit", "event_type", "page_token")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    limit: int
    event_type: TriggerEventType
    page_token: str
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., limit: _Optional[int] = ..., event_type: _Optional[_Union[TriggerEventType, str]] = ..., page_token: _Optional[str] = ...) -> None: ...

class TriggerEvent(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "symbol_id", "trigger_type", "event_type", "ts_ns", "child_seq", "child_order_id", "fire_price_ticks", "reason")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_TYPE_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    CHILD_SEQ_FIELD_NUMBER: _ClassVar[int]
    CHILD_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FIRE_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    symbol_id: int
    trigger_type: TriggerType
    event_type: TriggerEventType
    ts_ns: int
    child_seq: int
    child_order_id: int
    fire_price_ticks: int
    reason: str
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., trigger_type: _Optional[_Union[TriggerType, str]] = ..., event_type: _Optional[_Union[TriggerEventType, str]] = ..., ts_ns: _Optional[int] = ..., child_seq: _Optional[int] = ..., child_order_id: _Optional[int] = ..., fire_price_ticks: _Optional[int] = ..., reason: _Optional[str] = ...) -> None: ...

class ListTriggerEventsResponse(_message.Message):
    __slots__ = ("events", "next_page_token")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[TriggerEvent]
    next_page_token: str
    def __init__(self, events: _Optional[_Iterable[_Union[TriggerEvent, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CancelTriggerRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class CancelTriggerResponse(_message.Message):
    __slots__ = ("trigger_id", "status", "ts", "ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    status: TriggerStatus
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class ModifyTriggerRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "symbol_id", "trigger_price_ticks", "limit_price_ticks", "trailing_distance_ticks", "trailing_distance_bps", "activation_price_ticks", "max_slippage_ticks", "max_slippage_bps")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    symbol_id: int
    trigger_price_ticks: int
    limit_price_ticks: int
    trailing_distance_ticks: int
    trailing_distance_bps: int
    activation_price_ticks: int
    max_slippage_ticks: int
    max_slippage_bps: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., trigger_price_ticks: _Optional[int] = ..., limit_price_ticks: _Optional[int] = ..., trailing_distance_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ...) -> None: ...

class ModifyTriggerResponse(_message.Message):
    __slots__ = ("trigger_id", "status", "ts", "ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    status: TriggerStatus
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class PauseTriggerRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class PauseTriggerResponse(_message.Message):
    __slots__ = ("trigger_id", "status", "ts", "ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    status: TriggerStatus
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class ResumeTriggerRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "symbol_id")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    symbol_id: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ...) -> None: ...

class ResumeTriggerResponse(_message.Message):
    __slots__ = ("trigger_id", "status", "ts", "ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    status: TriggerStatus
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

class StopDetails(_message.Message):
    __slots__ = ("trigger_price_ticks", "trigger_price_source", "trigger_direction")
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    trigger_price_ticks: int
    trigger_price_source: _orders_pb2.TriggerPriceSource
    trigger_direction: _orders_pb2.TriggerDirection
    def __init__(self, trigger_price_ticks: _Optional[int] = ..., trigger_price_source: _Optional[_Union[_orders_pb2.TriggerPriceSource, str]] = ..., trigger_direction: _Optional[_Union[_orders_pb2.TriggerDirection, str]] = ...) -> None: ...

class TrailingDetails(_message.Message):
    __slots__ = ("trailing_distance_ticks", "activation_price_ticks", "peak_price_ticks", "trough_price_ticks", "trailing_distance_bps", "max_slippage_ticks", "max_slippage_bps", "trigger_price_source", "trigger_direction")
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    PEAK_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TROUGH_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_DIRECTION_FIELD_NUMBER: _ClassVar[int]
    trailing_distance_ticks: int
    activation_price_ticks: int
    peak_price_ticks: int
    trough_price_ticks: int
    trailing_distance_bps: int
    max_slippage_ticks: int
    max_slippage_bps: int
    trigger_price_source: _orders_pb2.TriggerPriceSource
    trigger_direction: _orders_pb2.TriggerDirection
    def __init__(self, trailing_distance_ticks: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ..., peak_price_ticks: _Optional[int] = ..., trough_price_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ..., trigger_price_source: _Optional[_Union[_orders_pb2.TriggerPriceSource, str]] = ..., trigger_direction: _Optional[_Union[_orders_pb2.TriggerDirection, str]] = ...) -> None: ...

class TwapDetails(_message.Message):
    __slots__ = ("twap_duration_ms", "twap_slice_interval_ms", "slice_idx", "slice_count", "executed_qty_scaled")
    TWAP_DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    TWAP_SLICE_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    SLICE_IDX_FIELD_NUMBER: _ClassVar[int]
    SLICE_COUNT_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    twap_duration_ms: int
    twap_slice_interval_ms: int
    slice_idx: int
    slice_count: int
    executed_qty_scaled: int
    def __init__(self, twap_duration_ms: _Optional[int] = ..., twap_slice_interval_ms: _Optional[int] = ..., slice_idx: _Optional[int] = ..., slice_count: _Optional[int] = ..., executed_qty_scaled: _Optional[int] = ...) -> None: ...

class LadderDetails(_message.Message):
    __slots__ = ("ladder_price_min_ticks", "ladder_price_max_ticks", "ladder_levels", "ladder_distribution")
    LADDER_PRICE_MIN_TICKS_FIELD_NUMBER: _ClassVar[int]
    LADDER_PRICE_MAX_TICKS_FIELD_NUMBER: _ClassVar[int]
    LADDER_LEVELS_FIELD_NUMBER: _ClassVar[int]
    LADDER_DISTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    ladder_price_min_ticks: int
    ladder_price_max_ticks: int
    ladder_levels: int
    ladder_distribution: LadderDistribution
    def __init__(self, ladder_price_min_ticks: _Optional[int] = ..., ladder_price_max_ticks: _Optional[int] = ..., ladder_levels: _Optional[int] = ..., ladder_distribution: _Optional[_Union[LadderDistribution, str]] = ...) -> None: ...

class Trigger(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "symbol_id", "status", "parent_order_id", "qty_scaled", "fee_asset", "self_trade_prevention_mode", "stop_loss", "take_profit", "trailing_stop", "twap", "ladder", "stop", "trailing", "twap_state", "ladder_state", "client_trigger_id", "created_at", "updated_at", "armed_at", "completed_at")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PARENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_PREVENTION_MODE_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_FIELD_NUMBER: _ClassVar[int]
    TWAP_FIELD_NUMBER: _ClassVar[int]
    LADDER_FIELD_NUMBER: _ClassVar[int]
    STOP_FIELD_NUMBER: _ClassVar[int]
    TRAILING_FIELD_NUMBER: _ClassVar[int]
    TWAP_STATE_FIELD_NUMBER: _ClassVar[int]
    LADDER_STATE_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    ARMED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    symbol_id: int
    status: TriggerStatus
    parent_order_id: int
    qty_scaled: int
    fee_asset: _orders_pb2.FeeAsset
    self_trade_prevention_mode: _orders_pb2.SelfTradePreventionMode
    stop_loss: ConditionalTrigger
    take_profit: ConditionalTrigger
    trailing_stop: TrailingStopTrigger
    twap: TwapTrigger
    ladder: LadderTrigger
    stop: StopDetails
    trailing: TrailingDetails
    twap_state: TwapDetails
    ladder_state: LadderDetails
    client_trigger_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    armed_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., parent_order_id: _Optional[int] = ..., qty_scaled: _Optional[int] = ..., fee_asset: _Optional[_Union[_orders_pb2.FeeAsset, str]] = ..., self_trade_prevention_mode: _Optional[_Union[_orders_pb2.SelfTradePreventionMode, str]] = ..., stop_loss: _Optional[_Union[ConditionalTrigger, _Mapping]] = ..., take_profit: _Optional[_Union[ConditionalTrigger, _Mapping]] = ..., trailing_stop: _Optional[_Union[TrailingStopTrigger, _Mapping]] = ..., twap: _Optional[_Union[TwapTrigger, _Mapping]] = ..., ladder: _Optional[_Union[LadderTrigger, _Mapping]] = ..., stop: _Optional[_Union[StopDetails, _Mapping]] = ..., trailing: _Optional[_Union[TrailingDetails, _Mapping]] = ..., twap_state: _Optional[_Union[TwapDetails, _Mapping]] = ..., ladder_state: _Optional[_Union[LadderDetails, _Mapping]] = ..., client_trigger_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., armed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
