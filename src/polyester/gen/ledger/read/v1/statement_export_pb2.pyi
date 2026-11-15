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

class StatementExportStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATEMENT_EXPORT_STATUS_UNSPECIFIED: _ClassVar[StatementExportStatus]
    STATEMENT_EXPORT_STATUS_QUEUED: _ClassVar[StatementExportStatus]
    STATEMENT_EXPORT_STATUS_PROCESSING: _ClassVar[StatementExportStatus]
    STATEMENT_EXPORT_STATUS_READY: _ClassVar[StatementExportStatus]
    STATEMENT_EXPORT_STATUS_FAILED: _ClassVar[StatementExportStatus]
    STATEMENT_EXPORT_STATUS_EXPIRED: _ClassVar[StatementExportStatus]

class StatementExportFailureReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATEMENT_EXPORT_FAILURE_REASON_UNSPECIFIED: _ClassVar[StatementExportFailureReason]
    STATEMENT_EXPORT_FAILURE_REASON_TOO_LARGE: _ClassVar[StatementExportFailureReason]
    STATEMENT_EXPORT_FAILURE_REASON_UNAVAILABLE: _ClassVar[StatementExportFailureReason]
STATEMENT_EXPORT_STATUS_UNSPECIFIED: StatementExportStatus
STATEMENT_EXPORT_STATUS_QUEUED: StatementExportStatus
STATEMENT_EXPORT_STATUS_PROCESSING: StatementExportStatus
STATEMENT_EXPORT_STATUS_READY: StatementExportStatus
STATEMENT_EXPORT_STATUS_FAILED: StatementExportStatus
STATEMENT_EXPORT_STATUS_EXPIRED: StatementExportStatus
STATEMENT_EXPORT_FAILURE_REASON_UNSPECIFIED: StatementExportFailureReason
STATEMENT_EXPORT_FAILURE_REASON_TOO_LARGE: StatementExportFailureReason
STATEMENT_EXPORT_FAILURE_REASON_UNAVAILABLE: StatementExportFailureReason

class StatementExport(_message.Message):
    __slots__ = ("export_id", "subaccount_id", "start_time", "end_time", "asset_id", "idempotency_key", "status", "complete_through", "movements", "bytes", "created_at", "ready_at", "expires_at", "failure_reason")
    EXPORT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_THROUGH_FIELD_NUMBER: _ClassVar[int]
    MOVEMENTS_FIELD_NUMBER: _ClassVar[int]
    BYTES_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    READY_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    FAILURE_REASON_FIELD_NUMBER: _ClassVar[int]
    export_id: int
    subaccount_id: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    asset_id: int
    idempotency_key: str
    status: StatementExportStatus
    complete_through: _timestamp_pb2.Timestamp
    movements: int
    bytes: int
    created_at: _timestamp_pb2.Timestamp
    ready_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    failure_reason: StatementExportFailureReason
    def __init__(self, export_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., asset_id: _Optional[int] = ..., idempotency_key: _Optional[str] = ..., status: _Optional[_Union[StatementExportStatus, str]] = ..., complete_through: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., movements: _Optional[int] = ..., bytes: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ready_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., failure_reason: _Optional[_Union[StatementExportFailureReason, str]] = ...) -> None: ...

class CreateStatementExportRequest(_message.Message):
    __slots__ = ("subaccount_id", "start_time", "end_time", "asset_id", "idempotency_key")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    asset_id: int
    idempotency_key: str
    def __init__(self, subaccount_id: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., asset_id: _Optional[int] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class CreateStatementExportResponse(_message.Message):
    __slots__ = ("export",)
    EXPORT_FIELD_NUMBER: _ClassVar[int]
    export: StatementExport
    def __init__(self, export: _Optional[_Union[StatementExport, _Mapping]] = ...) -> None: ...

class GetStatementExportRequest(_message.Message):
    __slots__ = ("export_id",)
    EXPORT_ID_FIELD_NUMBER: _ClassVar[int]
    export_id: int
    def __init__(self, export_id: _Optional[int] = ...) -> None: ...

class GetStatementExportResponse(_message.Message):
    __slots__ = ("export",)
    EXPORT_FIELD_NUMBER: _ClassVar[int]
    export: StatementExport
    def __init__(self, export: _Optional[_Union[StatementExport, _Mapping]] = ...) -> None: ...

class ListStatementExportsRequest(_message.Message):
    __slots__ = ("subaccount_id", "limit", "page_token")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    limit: int
    page_token: str
    def __init__(self, subaccount_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListStatementExportsResponse(_message.Message):
    __slots__ = ("exports", "next_page_token")
    EXPORTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    exports: _containers.RepeatedCompositeFieldContainer[StatementExport]
    next_page_token: str
    def __init__(self, exports: _Optional[_Iterable[_Union[StatementExport, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
