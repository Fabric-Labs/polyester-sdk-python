import datetime

from polyester.gen.auth.v1 import subaccounts_pb2 as _subaccounts_pb2
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

class ListAccountActivityRequest(_message.Message):
    __slots__ = ("limit", "page_token", "subaccount_ids", "include_main_account", "entity_kinds", "event_actions", "sources", "api_key_id", "start_time", "end_time")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_IDS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_MAIN_ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    ENTITY_KINDS_FIELD_NUMBER: _ClassVar[int]
    EVENT_ACTIONS_FIELD_NUMBER: _ClassVar[int]
    SOURCES_FIELD_NUMBER: _ClassVar[int]
    API_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    subaccount_ids: _containers.RepeatedScalarFieldContainer[int]
    include_main_account: bool
    entity_kinds: _containers.RepeatedScalarFieldContainer[_subaccounts_pb2.ActivityEntityKind]
    event_actions: _containers.RepeatedScalarFieldContainer[_subaccounts_pb2.ActivityEventAction]
    sources: _containers.RepeatedScalarFieldContainer[_subaccounts_pb2.ActivityEventSource]
    api_key_id: str
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ..., subaccount_ids: _Optional[_Iterable[int]] = ..., include_main_account: _Optional[bool] = ..., entity_kinds: _Optional[_Iterable[_Union[_subaccounts_pb2.ActivityEntityKind, str]]] = ..., event_actions: _Optional[_Iterable[_Union[_subaccounts_pb2.ActivityEventAction, str]]] = ..., sources: _Optional[_Iterable[_Union[_subaccounts_pb2.ActivityEventSource, str]]] = ..., api_key_id: _Optional[str] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListAccountActivityResponse(_message.Message):
    __slots__ = ("events", "next_page_token")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[_subaccounts_pb2.ActivityEvent]
    next_page_token: str
    def __init__(self, events: _Optional[_Iterable[_Union[_subaccounts_pb2.ActivityEvent, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
