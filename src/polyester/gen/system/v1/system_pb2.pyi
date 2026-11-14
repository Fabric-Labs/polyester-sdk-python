import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StatusEventKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KIND_UNSPECIFIED: _ClassVar[StatusEventKind]
    MAINTENANCE: _ClassVar[StatusEventKind]
    INCIDENT: _ClassVar[StatusEventKind]

class StatusEventState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATE_UNSPECIFIED: _ClassVar[StatusEventState]
    SCHEDULED: _ClassVar[StatusEventState]
    IN_PROGRESS: _ClassVar[StatusEventState]
    COMPLETED: _ClassVar[StatusEventState]
    CANCELLED: _ClassVar[StatusEventState]

class StatusEventImpact(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    IMPACT_UNSPECIFIED: _ClassVar[StatusEventImpact]
    DEGRADED: _ClassVar[StatusEventImpact]
    PARTIAL_OUTAGE: _ClassVar[StatusEventImpact]
    MAJOR_OUTAGE: _ClassVar[StatusEventImpact]

class AffectedService(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SERVICE_UNSPECIFIED: _ClassVar[AffectedService]
    TRADING: _ClassVar[AffectedService]
    MARKET_DATA: _ClassVar[AffectedService]
    DEPOSITS: _ClassVar[AffectedService]
    WITHDRAWALS: _ClassVar[AffectedService]
    TRANSFERS: _ClassVar[AffectedService]
    ACCOUNTS: _ClassVar[AffectedService]
    API: _ClassVar[AffectedService]
    QUICKSWAP: _ClassVar[AffectedService]
    APP: _ClassVar[AffectedService]
KIND_UNSPECIFIED: StatusEventKind
MAINTENANCE: StatusEventKind
INCIDENT: StatusEventKind
STATE_UNSPECIFIED: StatusEventState
SCHEDULED: StatusEventState
IN_PROGRESS: StatusEventState
COMPLETED: StatusEventState
CANCELLED: StatusEventState
IMPACT_UNSPECIFIED: StatusEventImpact
DEGRADED: StatusEventImpact
PARTIAL_OUTAGE: StatusEventImpact
MAJOR_OUTAGE: StatusEventImpact
SERVICE_UNSPECIFIED: AffectedService
TRADING: AffectedService
MARKET_DATA: AffectedService
DEPOSITS: AffectedService
WITHDRAWALS: AffectedService
TRANSFERS: AffectedService
ACCOUNTS: AffectedService
API: AffectedService
QUICKSWAP: AffectedService
APP: AffectedService

class GetVersionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetVersionResponse(_message.Message):
    __slots__ = ("version", "commit", "environment")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    COMMIT_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    version: str
    commit: str
    environment: str
    def __init__(self, version: _Optional[str] = ..., commit: _Optional[str] = ..., environment: _Optional[str] = ...) -> None: ...

class StatusEventUpdate(_message.Message):
    __slots__ = ("id", "message", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    message: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., message: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StatusEvent(_message.Message):
    __slots__ = ("id", "kind", "state", "title", "message", "start_time", "end_time", "services", "markets", "updated_at", "impact", "assets", "cancelled_at", "updates", "details_url")
    ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    IMPACT_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    CANCELLED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATES_FIELD_NUMBER: _ClassVar[int]
    DETAILS_URL_FIELD_NUMBER: _ClassVar[int]
    id: int
    kind: StatusEventKind
    state: StatusEventState
    title: str
    message: str
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    services: _containers.RepeatedScalarFieldContainer[AffectedService]
    markets: _containers.RepeatedScalarFieldContainer[str]
    updated_at: _timestamp_pb2.Timestamp
    impact: StatusEventImpact
    assets: _containers.RepeatedScalarFieldContainer[str]
    cancelled_at: _timestamp_pb2.Timestamp
    updates: _containers.RepeatedCompositeFieldContainer[StatusEventUpdate]
    details_url: str
    def __init__(self, id: _Optional[int] = ..., kind: _Optional[_Union[StatusEventKind, str]] = ..., state: _Optional[_Union[StatusEventState, str]] = ..., title: _Optional[str] = ..., message: _Optional[str] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., services: _Optional[_Iterable[_Union[AffectedService, str]]] = ..., markets: _Optional[_Iterable[str]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., impact: _Optional[_Union[StatusEventImpact, str]] = ..., assets: _Optional[_Iterable[str]] = ..., cancelled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updates: _Optional[_Iterable[_Union[StatusEventUpdate, _Mapping]]] = ..., details_url: _Optional[str] = ...) -> None: ...

class ListStatusEventsRequest(_message.Message):
    __slots__ = ("states", "kinds", "limit", "page_token")
    STATES_FIELD_NUMBER: _ClassVar[int]
    KINDS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    states: _containers.RepeatedScalarFieldContainer[StatusEventState]
    kinds: _containers.RepeatedScalarFieldContainer[StatusEventKind]
    limit: int
    page_token: str
    def __init__(self, states: _Optional[_Iterable[_Union[StatusEventState, str]]] = ..., kinds: _Optional[_Iterable[_Union[StatusEventKind, str]]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListStatusEventsResponse(_message.Message):
    __slots__ = ("events", "next_page_token")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[StatusEvent]
    next_page_token: str
    def __init__(self, events: _Optional[_Iterable[_Union[StatusEvent, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
