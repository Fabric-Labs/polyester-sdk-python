from polyester.gen.polychart.v1 import polychart_pb2 as _polychart_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PolychartEventEnvelope(_message.Message):
    __slots__ = ("server_ts_ms", "drawing_committed", "drawing_deleted", "layer_updated", "layer_deleted", "layer_access_granted", "layer_access_revoked")
    SERVER_TS_MS_FIELD_NUMBER: _ClassVar[int]
    DRAWING_COMMITTED_FIELD_NUMBER: _ClassVar[int]
    DRAWING_DELETED_FIELD_NUMBER: _ClassVar[int]
    LAYER_UPDATED_FIELD_NUMBER: _ClassVar[int]
    LAYER_DELETED_FIELD_NUMBER: _ClassVar[int]
    LAYER_ACCESS_GRANTED_FIELD_NUMBER: _ClassVar[int]
    LAYER_ACCESS_REVOKED_FIELD_NUMBER: _ClassVar[int]
    server_ts_ms: int
    drawing_committed: DrawingCommitted
    drawing_deleted: DrawingDeleted
    layer_updated: LayerUpdated
    layer_deleted: LayerDeleted
    layer_access_granted: LayerAccessGranted
    layer_access_revoked: LayerAccessRevoked
    def __init__(self, server_ts_ms: _Optional[int] = ..., drawing_committed: _Optional[_Union[DrawingCommitted, _Mapping]] = ..., drawing_deleted: _Optional[_Union[DrawingDeleted, _Mapping]] = ..., layer_updated: _Optional[_Union[LayerUpdated, _Mapping]] = ..., layer_deleted: _Optional[_Union[LayerDeleted, _Mapping]] = ..., layer_access_granted: _Optional[_Union[LayerAccessGranted, _Mapping]] = ..., layer_access_revoked: _Optional[_Union[LayerAccessRevoked, _Mapping]] = ...) -> None: ...

class DrawingCommitted(_message.Message):
    __slots__ = ("drawing", "layer_revision")
    DRAWING_FIELD_NUMBER: _ClassVar[int]
    LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    drawing: _polychart_pb2.Drawing
    layer_revision: int
    def __init__(self, drawing: _Optional[_Union[_polychart_pb2.Drawing, _Mapping]] = ..., layer_revision: _Optional[int] = ...) -> None: ...

class DrawingDeleted(_message.Message):
    __slots__ = ("drawing", "layer", "layer_revision")
    DRAWING_FIELD_NUMBER: _ClassVar[int]
    LAYER_FIELD_NUMBER: _ClassVar[int]
    LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    drawing: _polychart_pb2.DrawingRef
    layer: _polychart_pb2.LayerRef
    layer_revision: int
    def __init__(self, drawing: _Optional[_Union[_polychart_pb2.DrawingRef, _Mapping]] = ..., layer: _Optional[_Union[_polychart_pb2.LayerRef, _Mapping]] = ..., layer_revision: _Optional[int] = ...) -> None: ...

class LayerUpdated(_message.Message):
    __slots__ = ("layer",)
    LAYER_FIELD_NUMBER: _ClassVar[int]
    layer: _polychart_pb2.Layer
    def __init__(self, layer: _Optional[_Union[_polychart_pb2.Layer, _Mapping]] = ...) -> None: ...

class LayerDeleted(_message.Message):
    __slots__ = ("layer", "layer_revision")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    layer: _polychart_pb2.LayerRef
    layer_revision: int
    def __init__(self, layer: _Optional[_Union[_polychart_pb2.LayerRef, _Mapping]] = ..., layer_revision: _Optional[int] = ...) -> None: ...

class LayerAccessGranted(_message.Message):
    __slots__ = ("layer",)
    LAYER_FIELD_NUMBER: _ClassVar[int]
    layer: _polychart_pb2.Layer
    def __init__(self, layer: _Optional[_Union[_polychart_pb2.Layer, _Mapping]] = ...) -> None: ...

class LayerAccessRevoked(_message.Message):
    __slots__ = ("layer", "engine_symbol_id")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    layer: _polychart_pb2.LayerRef
    engine_symbol_id: int
    def __init__(self, layer: _Optional[_Union[_polychart_pb2.LayerRef, _Mapping]] = ..., engine_symbol_id: _Optional[int] = ...) -> None: ...
