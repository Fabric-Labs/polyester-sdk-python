import datetime

from polyester.gen.alerts.v1 import price_alerts_pb2 as _price_alerts_pb2
from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
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
    NOTIFICATION_NOT_FOUND: _ClassVar[ErrorCode]
    SERVICE_UNAVAILABLE: _ClassVar[ErrorCode]

class NotificationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TYPE_UNSPECIFIED: _ClassVar[NotificationType]
    PRICE_ALERT: _ClassVar[NotificationType]
    TELEGRAM_APPROVAL: _ClassVar[NotificationType]
    BROKER_ALLOWLIST_CHANGE: _ClassVar[NotificationType]

class NotificationCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CATEGORY_UNSPECIFIED: _ClassVar[NotificationCategory]
    ALERTS: _ClassVar[NotificationCategory]
    SECURITY: _ClassVar[NotificationCategory]

class ReadState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    READ_STATE_UNSPECIFIED: _ClassVar[ReadState]
    UNREAD: _ClassVar[ReadState]
    READ: _ClassVar[ReadState]

class TelegramApprovalAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACTION_UNSPECIFIED: _ClassVar[TelegramApprovalAction]
    PLACE_ORDER: _ClassVar[TelegramApprovalAction]
    PLACE_ORDERS: _ClassVar[TelegramApprovalAction]
    MODIFY_ORDERS: _ClassVar[TelegramApprovalAction]
    CANCEL_ORDER: _ClassVar[TelegramApprovalAction]
    CANCEL_ALL_ORDERS: _ClassVar[TelegramApprovalAction]
    MODIFY_TRIGGER: _ClassVar[TelegramApprovalAction]
    PAUSE_TRIGGER: _ClassVar[TelegramApprovalAction]
    RESUME_TRIGGER: _ClassVar[TelegramApprovalAction]
    SWAP: _ClassVar[TelegramApprovalAction]

class BrokerAllowlistEvent(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BROKER_ALLOWLIST_EVENT_UNSPECIFIED: _ClassVar[BrokerAllowlistEvent]
    CHANGE_REQUESTED: _ClassVar[BrokerAllowlistEvent]
    CHANGE_APPLIED: _ClassVar[BrokerAllowlistEvent]
    CHANGE_NOT_APPLIED: _ClassVar[BrokerAllowlistEvent]

class BrokerAllowlistAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BROKER_ALLOWLIST_ACTION_UNSPECIFIED: _ClassVar[BrokerAllowlistAction]
    ADD_DESTINATION: _ClassVar[BrokerAllowlistAction]
    REMOVE_DESTINATION: _ClassVar[BrokerAllowlistAction]
ERROR_UNSPECIFIED: ErrorCode
NOTIFICATION_NOT_FOUND: ErrorCode
SERVICE_UNAVAILABLE: ErrorCode
TYPE_UNSPECIFIED: NotificationType
PRICE_ALERT: NotificationType
TELEGRAM_APPROVAL: NotificationType
BROKER_ALLOWLIST_CHANGE: NotificationType
CATEGORY_UNSPECIFIED: NotificationCategory
ALERTS: NotificationCategory
SECURITY: NotificationCategory
READ_STATE_UNSPECIFIED: ReadState
UNREAD: ReadState
READ: ReadState
ACTION_UNSPECIFIED: TelegramApprovalAction
PLACE_ORDER: TelegramApprovalAction
PLACE_ORDERS: TelegramApprovalAction
MODIFY_ORDERS: TelegramApprovalAction
CANCEL_ORDER: TelegramApprovalAction
CANCEL_ALL_ORDERS: TelegramApprovalAction
MODIFY_TRIGGER: TelegramApprovalAction
PAUSE_TRIGGER: TelegramApprovalAction
RESUME_TRIGGER: TelegramApprovalAction
SWAP: TelegramApprovalAction
BROKER_ALLOWLIST_EVENT_UNSPECIFIED: BrokerAllowlistEvent
CHANGE_REQUESTED: BrokerAllowlistEvent
CHANGE_APPLIED: BrokerAllowlistEvent
CHANGE_NOT_APPLIED: BrokerAllowlistEvent
BROKER_ALLOWLIST_ACTION_UNSPECIFIED: BrokerAllowlistAction
ADD_DESTINATION: BrokerAllowlistAction
REMOVE_DESTINATION: BrokerAllowlistAction

class ErrorDetail(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ...) -> None: ...

class Notification(_message.Message):
    __slots__ = ("notification_id", "type", "category", "title", "text", "created_at", "read_at", "price_alert", "telegram_approval", "broker_allowlist")
    NOTIFICATION_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    READ_AT_FIELD_NUMBER: _ClassVar[int]
    PRICE_ALERT_FIELD_NUMBER: _ClassVar[int]
    TELEGRAM_APPROVAL_FIELD_NUMBER: _ClassVar[int]
    BROKER_ALLOWLIST_FIELD_NUMBER: _ClassVar[int]
    notification_id: int
    type: NotificationType
    category: NotificationCategory
    title: str
    text: str
    created_at: _timestamp_pb2.Timestamp
    read_at: _timestamp_pb2.Timestamp
    price_alert: PriceAlertNotice
    telegram_approval: TelegramApprovalNotice
    broker_allowlist: BrokerAllowlistNotice
    def __init__(self, notification_id: _Optional[int] = ..., type: _Optional[_Union[NotificationType, str]] = ..., category: _Optional[_Union[NotificationCategory, str]] = ..., title: _Optional[str] = ..., text: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., read_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., price_alert: _Optional[_Union[PriceAlertNotice, _Mapping]] = ..., telegram_approval: _Optional[_Union[TelegramApprovalNotice, _Mapping]] = ..., broker_allowlist: _Optional[_Union[BrokerAllowlistNotice, _Mapping]] = ...) -> None: ...

class PriceAlertNotice(_message.Message):
    __slots__ = ("alert_id", "symbol_id", "direction", "price_source", "price_ticks", "triggered_price_ticks", "triggered_at")
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGERED_PRICE_TICKS_FIELD_NUMBER: _ClassVar[int]
    TRIGGERED_AT_FIELD_NUMBER: _ClassVar[int]
    alert_id: int
    symbol_id: int
    direction: _price_alerts_pb2.AlertDirection
    price_source: _price_alerts_pb2.AlertPriceSource
    price_ticks: int
    triggered_price_ticks: int
    triggered_at: _timestamp_pb2.Timestamp
    def __init__(self, alert_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., direction: _Optional[_Union[_price_alerts_pb2.AlertDirection, str]] = ..., price_source: _Optional[_Union[_price_alerts_pb2.AlertPriceSource, str]] = ..., price_ticks: _Optional[int] = ..., triggered_price_ticks: _Optional[int] = ..., triggered_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class NoticeField(_message.Message):
    __slots__ = ("label", "value")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    label: str
    value: str
    def __init__(self, label: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class TelegramApprovalNotice(_message.Message):
    __slots__ = ("approval_id", "action", "account_id", "summary", "parameters", "approved_at")
    APPROVAL_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    APPROVED_AT_FIELD_NUMBER: _ClassVar[int]
    approval_id: int
    action: TelegramApprovalAction
    account_id: int
    summary: str
    parameters: _containers.RepeatedCompositeFieldContainer[NoticeField]
    approved_at: _timestamp_pb2.Timestamp
    def __init__(self, approval_id: _Optional[int] = ..., action: _Optional[_Union[TelegramApprovalAction, str]] = ..., account_id: _Optional[int] = ..., summary: _Optional[str] = ..., parameters: _Optional[_Iterable[_Union[NoticeField, _Mapping]]] = ..., approved_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class BrokerAllowlistNotice(_message.Message):
    __slots__ = ("broker", "vault_account_id", "change_id", "event", "action", "destination_chain_id", "destination_address", "label", "requested_by_account_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CHANGE_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_BY_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    change_id: int
    event: BrokerAllowlistEvent
    action: BrokerAllowlistAction
    destination_chain_id: int
    destination_address: str
    label: str
    requested_by_account_id: int
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., change_id: _Optional[int] = ..., event: _Optional[_Union[BrokerAllowlistEvent, str]] = ..., action: _Optional[_Union[BrokerAllowlistAction, str]] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., label: _Optional[str] = ..., requested_by_account_id: _Optional[int] = ...) -> None: ...

class ListNotificationsRequest(_message.Message):
    __slots__ = ("categories", "read_state", "start_time", "end_time", "limit", "page_token")
    CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    READ_STATE_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    categories: _containers.RepeatedScalarFieldContainer[NotificationCategory]
    read_state: ReadState
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    limit: int
    page_token: str
    def __init__(self, categories: _Optional[_Iterable[_Union[NotificationCategory, str]]] = ..., read_state: _Optional[_Union[ReadState, str]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListNotificationsResponse(_message.Message):
    __slots__ = ("notifications", "next_page_token")
    NOTIFICATIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    notifications: _containers.RepeatedCompositeFieldContainer[Notification]
    next_page_token: str
    def __init__(self, notifications: _Optional[_Iterable[_Union[Notification, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetNotificationRequest(_message.Message):
    __slots__ = ("notification_id",)
    NOTIFICATION_ID_FIELD_NUMBER: _ClassVar[int]
    notification_id: int
    def __init__(self, notification_id: _Optional[int] = ...) -> None: ...

class GetNotificationResponse(_message.Message):
    __slots__ = ("notification",)
    NOTIFICATION_FIELD_NUMBER: _ClassVar[int]
    notification: Notification
    def __init__(self, notification: _Optional[_Union[Notification, _Mapping]] = ...) -> None: ...

class GetNotificationCountsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TypeCount(_message.Message):
    __slots__ = ("type", "category", "total", "unread")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    UNREAD_FIELD_NUMBER: _ClassVar[int]
    type: NotificationType
    category: NotificationCategory
    total: int
    unread: int
    def __init__(self, type: _Optional[_Union[NotificationType, str]] = ..., category: _Optional[_Union[NotificationCategory, str]] = ..., total: _Optional[int] = ..., unread: _Optional[int] = ...) -> None: ...

class GetNotificationCountsResponse(_message.Message):
    __slots__ = ("total", "unread", "types")
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    UNREAD_FIELD_NUMBER: _ClassVar[int]
    TYPES_FIELD_NUMBER: _ClassVar[int]
    total: int
    unread: int
    types: _containers.RepeatedCompositeFieldContainer[TypeCount]
    def __init__(self, total: _Optional[int] = ..., unread: _Optional[int] = ..., types: _Optional[_Iterable[_Union[TypeCount, _Mapping]]] = ...) -> None: ...

class MarkNotificationsReadRequest(_message.Message):
    __slots__ = ("notification_ids",)
    NOTIFICATION_IDS_FIELD_NUMBER: _ClassVar[int]
    notification_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, notification_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class MarkNotificationsReadResponse(_message.Message):
    __slots__ = ("changed",)
    CHANGED_FIELD_NUMBER: _ClassVar[int]
    changed: int
    def __init__(self, changed: _Optional[int] = ...) -> None: ...

class MarkNotificationsUnreadRequest(_message.Message):
    __slots__ = ("notification_ids",)
    NOTIFICATION_IDS_FIELD_NUMBER: _ClassVar[int]
    notification_ids: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, notification_ids: _Optional[_Iterable[int]] = ...) -> None: ...

class MarkNotificationsUnreadResponse(_message.Message):
    __slots__ = ("changed",)
    CHANGED_FIELD_NUMBER: _ClassVar[int]
    changed: int
    def __init__(self, changed: _Optional[int] = ...) -> None: ...

class MarkAllNotificationsReadRequest(_message.Message):
    __slots__ = ("categories", "through_notification_id")
    CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    THROUGH_NOTIFICATION_ID_FIELD_NUMBER: _ClassVar[int]
    categories: _containers.RepeatedScalarFieldContainer[NotificationCategory]
    through_notification_id: int
    def __init__(self, categories: _Optional[_Iterable[_Union[NotificationCategory, str]]] = ..., through_notification_id: _Optional[int] = ...) -> None: ...

class MarkAllNotificationsReadResponse(_message.Message):
    __slots__ = ("changed",)
    CHANGED_FIELD_NUMBER: _ClassVar[int]
    changed: int
    def __init__(self, changed: _Optional[int] = ...) -> None: ...
