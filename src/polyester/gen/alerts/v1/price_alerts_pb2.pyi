import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import field_mask_pb2 as _field_mask_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_UNSPECIFIED: _ClassVar[ErrorCode]
    ALERT_NOT_FOUND: _ClassVar[ErrorCode]
    UNKNOWN_SYMBOL: _ClassVar[ErrorCode]
    PRICE_UNAVAILABLE: _ClassVar[ErrorCode]
    PRICE_SOURCE_UNSUPPORTED: _ClassVar[ErrorCode]
    ALERT_LIMIT_REACHED: _ClassVar[ErrorCode]
    REVISION_CONFLICT: _ClassVar[ErrorCode]
    ALERT_CANCELLED: _ClassVar[ErrorCode]
    ALERT_TRIGGERED: _ClassVar[ErrorCode]
    IDEMPOTENCY_CONFLICT: _ClassVar[ErrorCode]
    SERVICE_UNAVAILABLE: _ClassVar[ErrorCode]
    SUBACCOUNT_KEY_REFUSED: _ClassVar[ErrorCode]
    ALERT_UPDATE_LIMIT_REACHED: _ClassVar[ErrorCode]

class AlertDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DIRECTION_UNSPECIFIED: _ClassVar[AlertDirection]
    ABOVE: _ClassVar[AlertDirection]
    BELOW: _ClassVar[AlertDirection]

class AlertPriceSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRICE_SOURCE_UNSPECIFIED: _ClassVar[AlertPriceSource]
    LAST_PRICE: _ClassVar[AlertPriceSource]
    INDEX_PRICE: _ClassVar[AlertPriceSource]

class AlertStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATUS_UNSPECIFIED: _ClassVar[AlertStatus]
    ACTIVE: _ClassVar[AlertStatus]
    TRIGGERED: _ClassVar[AlertStatus]
    CANCELLED: _ClassVar[AlertStatus]

class UpdateOutcome(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UPDATE_OUTCOME_UNSPECIFIED: _ClassVar[UpdateOutcome]
    APPLIED: _ClassVar[UpdateOutcome]
    UNCHANGED: _ClassVar[UpdateOutcome]
    REPLAYED: _ClassVar[UpdateOutcome]

class AlertChannel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHANNEL_UNSPECIFIED: _ClassVar[AlertChannel]
    IN_APP: _ClassVar[AlertChannel]
    TELEGRAM: _ClassVar[AlertChannel]
ERROR_UNSPECIFIED: ErrorCode
ALERT_NOT_FOUND: ErrorCode
UNKNOWN_SYMBOL: ErrorCode
PRICE_UNAVAILABLE: ErrorCode
PRICE_SOURCE_UNSUPPORTED: ErrorCode
ALERT_LIMIT_REACHED: ErrorCode
REVISION_CONFLICT: ErrorCode
ALERT_CANCELLED: ErrorCode
ALERT_TRIGGERED: ErrorCode
IDEMPOTENCY_CONFLICT: ErrorCode
SERVICE_UNAVAILABLE: ErrorCode
SUBACCOUNT_KEY_REFUSED: ErrorCode
ALERT_UPDATE_LIMIT_REACHED: ErrorCode
DIRECTION_UNSPECIFIED: AlertDirection
ABOVE: AlertDirection
BELOW: AlertDirection
PRICE_SOURCE_UNSPECIFIED: AlertPriceSource
LAST_PRICE: AlertPriceSource
INDEX_PRICE: AlertPriceSource
STATUS_UNSPECIFIED: AlertStatus
ACTIVE: AlertStatus
TRIGGERED: AlertStatus
CANCELLED: AlertStatus
UPDATE_OUTCOME_UNSPECIFIED: UpdateOutcome
APPLIED: UpdateOutcome
UNCHANGED: UpdateOutcome
REPLAYED: UpdateOutcome
CHANNEL_UNSPECIFIED: AlertChannel
IN_APP: AlertChannel
TELEGRAM: AlertChannel

class ErrorDetail(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ...) -> None: ...

class PriceAlert(_message.Message):
    __slots__ = ("alert_id", "symbol_id", "direction", "price_source", "price_ticks", "reference_price_ticks", "armed", "status", "channels", "revision", "created_at", "updated_at", "triggered_at", "triggered_price_ticks")
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    ARMED_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    TRIGGERED_AT_FIELD_NUMBER: _ClassVar[int]
    TRIGGERED_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    alert_id: int
    symbol_id: int
    direction: AlertDirection
    price_source: AlertPriceSource
    price_ticks: int
    reference_price_ticks: int
    armed: bool
    status: AlertStatus
    channels: _containers.RepeatedScalarFieldContainer[AlertChannel]
    revision: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    triggered_at: _timestamp_pb2.Timestamp
    triggered_price_ticks: int
    def __init__(self, alert_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., direction: _Optional[_Union[AlertDirection, str]] = ..., price_source: _Optional[_Union[AlertPriceSource, str]] = ..., price_ticks: _Optional[int] = ..., reference_price_ticks: _Optional[int] = ..., armed: _Optional[bool] = ..., status: _Optional[_Union[AlertStatus, str]] = ..., channels: _Optional[_Iterable[_Union[AlertChannel, str]]] = ..., revision: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., triggered_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., triggered_price_ticks: _Optional[int] = ...) -> None: ...

class CreateAlertRequest(_message.Message):
    __slots__ = ("symbol_id", "direction", "price_source", "price_ticks", "channels", "idempotency_key")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    direction: AlertDirection
    price_source: AlertPriceSource
    price_ticks: int
    channels: _containers.RepeatedScalarFieldContainer[AlertChannel]
    idempotency_key: str
    def __init__(self, symbol_id: _Optional[int] = ..., direction: _Optional[_Union[AlertDirection, str]] = ..., price_source: _Optional[_Union[AlertPriceSource, str]] = ..., price_ticks: _Optional[int] = ..., channels: _Optional[_Iterable[_Union[AlertChannel, str]]] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class CreateAlertResponse(_message.Message):
    __slots__ = ("alert",)
    ALERT_FIELD_NUMBER: _ClassVar[int]
    alert: PriceAlert
    def __init__(self, alert: _Optional[_Union[PriceAlert, _Mapping]] = ...) -> None: ...

class ListAlertsRequest(_message.Message):
    __slots__ = ("statuses", "symbol_id", "limit", "page_token")
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    statuses: _containers.RepeatedScalarFieldContainer[AlertStatus]
    symbol_id: int
    limit: int
    page_token: str
    def __init__(self, statuses: _Optional[_Iterable[_Union[AlertStatus, str]]] = ..., symbol_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListAlertsResponse(_message.Message):
    __slots__ = ("alerts", "next_page_token")
    ALERTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    alerts: _containers.RepeatedCompositeFieldContainer[PriceAlert]
    next_page_token: str
    def __init__(self, alerts: _Optional[_Iterable[_Union[PriceAlert, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class AlertUpdate(_message.Message):
    __slots__ = ("direction", "price_ticks", "channels")
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    direction: AlertDirection
    price_ticks: int
    channels: _containers.RepeatedScalarFieldContainer[AlertChannel]
    def __init__(self, direction: _Optional[_Union[AlertDirection, str]] = ..., price_ticks: _Optional[int] = ..., channels: _Optional[_Iterable[_Union[AlertChannel, str]]] = ...) -> None: ...

class UpdateAlertRequest(_message.Message):
    __slots__ = ("alert_id", "update", "update_mask", "expected_revision", "idempotency_key")
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    UPDATE_FIELD_NUMBER: _ClassVar[int]
    UPDATE_MASK_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    alert_id: int
    update: AlertUpdate
    update_mask: _field_mask_pb2.FieldMask
    expected_revision: int
    idempotency_key: str
    def __init__(self, alert_id: _Optional[int] = ..., update: _Optional[_Union[AlertUpdate, _Mapping]] = ..., update_mask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., expected_revision: _Optional[int] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class UpdateAlertResponse(_message.Message):
    __slots__ = ("alert", "outcome")
    ALERT_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    alert: PriceAlert
    outcome: UpdateOutcome
    def __init__(self, alert: _Optional[_Union[PriceAlert, _Mapping]] = ..., outcome: _Optional[_Union[UpdateOutcome, str]] = ...) -> None: ...

class CancelAlertRequest(_message.Message):
    __slots__ = ("alert_id",)
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    alert_id: int
    def __init__(self, alert_id: _Optional[int] = ...) -> None: ...

class CancelAlertResponse(_message.Message):
    __slots__ = ("alert",)
    ALERT_FIELD_NUMBER: _ClassVar[int]
    alert: PriceAlert
    def __init__(self, alert: _Optional[_Union[PriceAlert, _Mapping]] = ...) -> None: ...
