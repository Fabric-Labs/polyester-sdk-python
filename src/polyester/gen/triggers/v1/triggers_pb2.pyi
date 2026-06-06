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
    TRIGGER_STATUS_UNSPECIFIED: _ClassVar[TriggerStatus]
    CREATED: _ClassVar[TriggerStatus]
    ARMED: _ClassVar[TriggerStatus]
    RUNNING: _ClassVar[TriggerStatus]
    COMPLETED: _ClassVar[TriggerStatus]
    CANCELLED: _ClassVar[TriggerStatus]
    FAILED: _ClassVar[TriggerStatus]
    PAUSED: _ClassVar[TriggerStatus]

class TriggerEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRIGGER_EVENT_TYPE_UNSPECIFIED: _ClassVar[TriggerEventType]
    FIRED: _ClassVar[TriggerEventType]
    CANCELED: _ClassVar[TriggerEventType]
    UPDATED: _ClassVar[TriggerEventType]

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
TRIGGER_STATUS_UNSPECIFIED: TriggerStatus
CREATED: TriggerStatus
ARMED: TriggerStatus
RUNNING: TriggerStatus
COMPLETED: TriggerStatus
CANCELLED: TriggerStatus
FAILED: TriggerStatus
PAUSED: TriggerStatus
TRIGGER_EVENT_TYPE_UNSPECIFIED: TriggerEventType
FIRED: TriggerEventType
CANCELED: TriggerEventType
UPDATED: TriggerEventType
LADDER_DISTRIBUTION_UNSPECIFIED: LadderDistribution
LINEAR: LadderDistribution
GEOMETRIC: LadderDistribution
WEIGHTED_FAVORABLE: LadderDistribution

class CreateTriggerRequest(_message.Message):
    __slots__ = ("subaccount_id", "symbol", "trigger_type", "trigger_price_ticks", "trigger_price_source", "side", "order_type", "tif", "qty_scaled", "limit_price_ticks", "fee_source", "stp_mode", "post_only", "trailing_distance_ticks", "trailing_distance_bps", "activation_price_ticks", "max_slippage_ticks", "max_slippage_bps", "twap_duration_ms", "twap_slice_interval_ms", "ladder_price_min_ticks", "ladder_price_max_ticks", "ladder_levels", "ladder_distribution", "client_trigger_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_TYPE_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIF_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    FEE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    STP_MODE_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    TWAP_DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    TWAP_SLICE_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    LADDER_PRICE_MIN_TICKS_FIELD_NUMBER: _ClassVar[int]
    LADDER_PRICE_MAX_TICKS_FIELD_NUMBER: _ClassVar[int]
    LADDER_LEVELS_FIELD_NUMBER: _ClassVar[int]
    LADDER_DISTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol: str
    trigger_type: TriggerType
    trigger_price_ticks: int
    trigger_price_source: _orders_pb2.TriggerPriceSource
    side: _orders_pb2.Side
    order_type: _orders_pb2.OrderType
    tif: _orders_pb2.TIF
    qty_scaled: int
    limit_price_ticks: int
    fee_source: _orders_pb2.FeeSource
    stp_mode: _orders_pb2.STPMode
    post_only: bool
    trailing_distance_ticks: int
    trailing_distance_bps: int
    activation_price_ticks: int
    max_slippage_ticks: int
    max_slippage_bps: int
    twap_duration_ms: int
    twap_slice_interval_ms: int
    ladder_price_min_ticks: int
    ladder_price_max_ticks: int
    ladder_levels: int
    ladder_distribution: LadderDistribution
    client_trigger_id: str
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol: _Optional[str] = ..., trigger_type: _Optional[_Union[TriggerType, str]] = ..., trigger_price_ticks: _Optional[int] = ..., trigger_price_source: _Optional[_Union[_orders_pb2.TriggerPriceSource, str]] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., order_type: _Optional[_Union[_orders_pb2.OrderType, str]] = ..., tif: _Optional[_Union[_orders_pb2.TIF, str]] = ..., qty_scaled: _Optional[int] = ..., limit_price_ticks: _Optional[int] = ..., fee_source: _Optional[_Union[_orders_pb2.FeeSource, str]] = ..., stp_mode: _Optional[_Union[_orders_pb2.STPMode, str]] = ..., post_only: _Optional[bool] = ..., trailing_distance_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ..., twap_duration_ms: _Optional[int] = ..., twap_slice_interval_ms: _Optional[int] = ..., ladder_price_min_ticks: _Optional[int] = ..., ladder_price_max_ticks: _Optional[int] = ..., ladder_levels: _Optional[int] = ..., ladder_distribution: _Optional[_Union[LadderDistribution, str]] = ..., client_trigger_id: _Optional[str] = ...) -> None: ...

class CreateTriggerResponse(_message.Message):
    __slots__ = ("trigger_id", "status", "client_trigger_id", "ts", "ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    TS_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    status: TriggerStatus
    client_trigger_id: str
    ts: _timestamp_pb2.Timestamp
    ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., client_trigger_id: _Optional[str] = ..., ts: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ts_ns: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("subaccount_id", "symbol", "status", "trigger_type", "parent_order_id", "limit", "offset")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_TYPE_FIELD_NUMBER: _ClassVar[int]
    PARENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    symbol: str
    status: _containers.RepeatedScalarFieldContainer[TriggerStatus]
    trigger_type: TriggerType
    parent_order_id: int
    limit: int
    offset: int
    def __init__(self, subaccount_id: _Optional[int] = ..., symbol: _Optional[str] = ..., status: _Optional[_Iterable[_Union[TriggerStatus, str]]] = ..., trigger_type: _Optional[_Union[TriggerType, str]] = ..., parent_order_id: _Optional[int] = ..., limit: _Optional[int] = ..., offset: _Optional[int] = ...) -> None: ...

class ListTriggersResponse(_message.Message):
    __slots__ = ("triggers", "total")
    TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    triggers: _containers.RepeatedCompositeFieldContainer[Trigger]
    total: int
    def __init__(self, triggers: _Optional[_Iterable[_Union[Trigger, _Mapping]]] = ..., total: _Optional[int] = ...) -> None: ...

class ListTriggerEventsRequest(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "limit", "before_ts_ns")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    BEFORE_TS_NS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    limit: int
    before_ts_ns: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., limit: _Optional[int] = ..., before_ts_ns: _Optional[int] = ...) -> None: ...

class TriggerEvent(_message.Message):
    __slots__ = ("trigger_id", "subaccount_id", "symbol_id", "trigger_type", "event_type", "ts_ns", "child_seq", "child_order_id", "fire_px_ticks", "reason")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_TYPE_FIELD_NUMBER: _ClassVar[int]
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    TS_NS_FIELD_NUMBER: _ClassVar[int]
    CHILD_SEQ_FIELD_NUMBER: _ClassVar[int]
    CHILD_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FIRE_PX_TICKS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    symbol_id: int
    trigger_type: TriggerType
    event_type: TriggerEventType
    ts_ns: int
    child_seq: int
    child_order_id: int
    fire_px_ticks: int
    reason: str
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., trigger_type: _Optional[_Union[TriggerType, str]] = ..., event_type: _Optional[_Union[TriggerEventType, str]] = ..., ts_ns: _Optional[int] = ..., child_seq: _Optional[int] = ..., child_order_id: _Optional[int] = ..., fire_px_ticks: _Optional[int] = ..., reason: _Optional[str] = ...) -> None: ...

class ListTriggerEventsResponse(_message.Message):
    __slots__ = ("events", "next_before_ts_ns")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_BEFORE_TS_NS_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[TriggerEvent]
    next_before_ts_ns: int
    def __init__(self, events: _Optional[_Iterable[_Union[TriggerEvent, _Mapping]]] = ..., next_before_ts_ns: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("trigger_id", "subaccount_id", "trigger_price_ticks", "limit_price_ticks", "trailing_distance_ticks", "trailing_distance_bps", "activation_price_ticks", "max_slippage_ticks", "max_slippage_bps")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_TICKS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    trigger_price_ticks: int
    limit_price_ticks: int
    trailing_distance_ticks: int
    trailing_distance_bps: int
    activation_price_ticks: int
    max_slippage_ticks: int
    max_slippage_bps: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., trigger_price_ticks: _Optional[int] = ..., limit_price_ticks: _Optional[int] = ..., trailing_distance_ticks: _Optional[int] = ..., trailing_distance_bps: _Optional[int] = ..., activation_price_ticks: _Optional[int] = ..., max_slippage_ticks: _Optional[int] = ..., max_slippage_bps: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("trigger_id", "subaccount_id")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("trigger_id", "subaccount_id", "symbol_id", "symbol", "trigger_type", "status", "parent_order_id", "side", "order_type", "tif", "qty_scaled", "limit_price_ticks", "fee_source", "stp_mode", "post_only", "stop", "trailing", "twap", "ladder", "client_trigger_id", "created_at", "updated_at", "armed_at", "completed_at", "child_order_ids")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PARENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    TIF_FIELD_NUMBER: _ClassVar[int]
    QTY_SCALED_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    FEE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    STP_MODE_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    STOP_FIELD_NUMBER: _ClassVar[int]
    TRAILING_FIELD_NUMBER: _ClassVar[int]
    TWAP_FIELD_NUMBER: _ClassVar[int]
    LADDER_FIELD_NUMBER: _ClassVar[int]
    CLIENT_TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    ARMED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    CHILD_ORDER_IDS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    subaccount_id: int
    symbol_id: int
    symbol: str
    trigger_type: TriggerType
    status: TriggerStatus
    parent_order_id: int
    side: _orders_pb2.Side
    order_type: _orders_pb2.OrderType
    tif: _orders_pb2.TIF
    qty_scaled: int
    limit_price_ticks: int
    fee_source: _orders_pb2.FeeSource
    stp_mode: _orders_pb2.STPMode
    post_only: bool
    stop: StopDetails
    trailing: TrailingDetails
    twap: TwapDetails
    ladder: LadderDetails
    client_trigger_id: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    armed_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    child_order_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, trigger_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., symbol: _Optional[str] = ..., trigger_type: _Optional[_Union[TriggerType, str]] = ..., status: _Optional[_Union[TriggerStatus, str]] = ..., parent_order_id: _Optional[int] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., order_type: _Optional[_Union[_orders_pb2.OrderType, str]] = ..., tif: _Optional[_Union[_orders_pb2.TIF, str]] = ..., qty_scaled: _Optional[int] = ..., limit_price_ticks: _Optional[int] = ..., fee_source: _Optional[_Union[_orders_pb2.FeeSource, str]] = ..., stp_mode: _Optional[_Union[_orders_pb2.STPMode, str]] = ..., post_only: _Optional[bool] = ..., stop: _Optional[_Union[StopDetails, _Mapping]] = ..., trailing: _Optional[_Union[TrailingDetails, _Mapping]] = ..., twap: _Optional[_Union[TwapDetails, _Mapping]] = ..., ladder: _Optional[_Union[LadderDetails, _Mapping]] = ..., client_trigger_id: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., armed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., child_order_ids: _Optional[_Iterable[int]] = ...) -> None: ...
