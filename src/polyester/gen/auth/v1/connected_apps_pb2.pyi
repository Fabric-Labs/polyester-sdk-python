import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ConnectedAppClient(_message.Message):
    __slots__ = ("client_id", "name")
    CLIENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    client_id: str
    name: str
    def __init__(self, client_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class AppConnectionRequest(_message.Message):
    __slots__ = ("client", "scopes", "resource", "redirect_host", "expires_at")
    CLIENT_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    REDIRECT_HOST_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    client: ConnectedAppClient
    scopes: _containers.RepeatedScalarFieldContainer[str]
    resource: str
    redirect_host: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, client: _Optional[_Union[ConnectedAppClient, _Mapping]] = ..., scopes: _Optional[_Iterable[str]] = ..., resource: _Optional[str] = ..., redirect_host: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ConnectedApp(_message.Message):
    __slots__ = ("connected_app_id", "client", "scopes", "resource", "connected_at", "last_used_at", "expires_at")
    CONNECTED_APP_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_FIELD_NUMBER: _ClassVar[int]
    SCOPES_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    CONNECTED_AT_FIELD_NUMBER: _ClassVar[int]
    LAST_USED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    connected_app_id: int
    client: ConnectedAppClient
    scopes: _containers.RepeatedScalarFieldContainer[str]
    resource: str
    connected_at: _timestamp_pb2.Timestamp
    last_used_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, connected_app_id: _Optional[int] = ..., client: _Optional[_Union[ConnectedAppClient, _Mapping]] = ..., scopes: _Optional[_Iterable[str]] = ..., resource: _Optional[str] = ..., connected_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., last_used_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetAppConnectionRequestRequest(_message.Message):
    __slots__ = ("request_id",)
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    def __init__(self, request_id: _Optional[str] = ...) -> None: ...

class GetAppConnectionRequestResponse(_message.Message):
    __slots__ = ("connection_request",)
    CONNECTION_REQUEST_FIELD_NUMBER: _ClassVar[int]
    connection_request: AppConnectionRequest
    def __init__(self, connection_request: _Optional[_Union[AppConnectionRequest, _Mapping]] = ...) -> None: ...

class ApproveAppConnectionRequestRequest(_message.Message):
    __slots__ = ("request_id",)
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    def __init__(self, request_id: _Optional[str] = ...) -> None: ...

class ApproveAppConnectionRequestResponse(_message.Message):
    __slots__ = ("redirect_url",)
    REDIRECT_URL_FIELD_NUMBER: _ClassVar[int]
    redirect_url: str
    def __init__(self, redirect_url: _Optional[str] = ...) -> None: ...

class DenyAppConnectionRequestRequest(_message.Message):
    __slots__ = ("request_id",)
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    def __init__(self, request_id: _Optional[str] = ...) -> None: ...

class DenyAppConnectionRequestResponse(_message.Message):
    __slots__ = ("redirect_url",)
    REDIRECT_URL_FIELD_NUMBER: _ClassVar[int]
    redirect_url: str
    def __init__(self, redirect_url: _Optional[str] = ...) -> None: ...

class ListConnectedAppsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListConnectedAppsResponse(_message.Message):
    __slots__ = ("apps",)
    APPS_FIELD_NUMBER: _ClassVar[int]
    apps: _containers.RepeatedCompositeFieldContainer[ConnectedApp]
    def __init__(self, apps: _Optional[_Iterable[_Union[ConnectedApp, _Mapping]]] = ...) -> None: ...

class RevokeConnectedAppRequest(_message.Message):
    __slots__ = ("connected_app_id",)
    CONNECTED_APP_ID_FIELD_NUMBER: _ClassVar[int]
    connected_app_id: int
    def __init__(self, connected_app_id: _Optional[int] = ...) -> None: ...

class RevokeConnectedAppResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
