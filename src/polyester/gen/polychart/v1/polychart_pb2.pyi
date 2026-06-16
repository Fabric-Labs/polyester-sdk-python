from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LayerRef(_message.Message):
    __slots__ = ("owner_id", "layer_id")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    LAYER_ID_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    layer_id: int
    def __init__(self, owner_id: _Optional[int] = ..., layer_id: _Optional[int] = ...) -> None: ...

class DrawingRef(_message.Message):
    __slots__ = ("owner_id", "drawing_id")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    DRAWING_ID_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    drawing_id: int
    def __init__(self, owner_id: _Optional[int] = ..., drawing_id: _Optional[int] = ...) -> None: ...

class Layer(_message.Message):
    __slots__ = ("owner_id", "layer_id", "engine_symbol_id", "name", "sort_hint", "color_rgba", "use_layer_color", "is_locked", "is_visible", "revision", "updated_at_ms")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    LAYER_ID_FIELD_NUMBER: _ClassVar[int]
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SORT_HINT_FIELD_NUMBER: _ClassVar[int]
    COLOR_RGBA_FIELD_NUMBER: _ClassVar[int]
    USE_LAYER_COLOR_FIELD_NUMBER: _ClassVar[int]
    IS_LOCKED_FIELD_NUMBER: _ClassVar[int]
    IS_VISIBLE_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    layer_id: int
    engine_symbol_id: int
    name: str
    sort_hint: int
    color_rgba: int
    use_layer_color: bool
    is_locked: bool
    is_visible: bool
    revision: int
    updated_at_ms: int
    def __init__(self, owner_id: _Optional[int] = ..., layer_id: _Optional[int] = ..., engine_symbol_id: _Optional[int] = ..., name: _Optional[str] = ..., sort_hint: _Optional[int] = ..., color_rgba: _Optional[int] = ..., use_layer_color: _Optional[bool] = ..., is_locked: _Optional[bool] = ..., is_visible: _Optional[bool] = ..., revision: _Optional[int] = ..., updated_at_ms: _Optional[int] = ...) -> None: ...

class Drawing(_message.Message):
    __slots__ = ("owner_id", "drawing_id", "layer", "engine_symbol_id", "type", "version", "payload", "bbox_time_min_ms", "bbox_time_max_ms", "bbox_price_min", "bbox_price_max", "updated_at_ms", "deleted_at_ms", "client_updated_at_ms")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    DRAWING_ID_FIELD_NUMBER: _ClassVar[int]
    LAYER_FIELD_NUMBER: _ClassVar[int]
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    BBOX_TIME_MIN_MS_FIELD_NUMBER: _ClassVar[int]
    BBOX_TIME_MAX_MS_FIELD_NUMBER: _ClassVar[int]
    BBOX_PRICE_MIN_FIELD_NUMBER: _ClassVar[int]
    BBOX_PRICE_MAX_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    CLIENT_UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    drawing_id: int
    layer: LayerRef
    engine_symbol_id: int
    type: int
    version: int
    payload: bytes
    bbox_time_min_ms: int
    bbox_time_max_ms: int
    bbox_price_min: float
    bbox_price_max: float
    updated_at_ms: int
    deleted_at_ms: int
    client_updated_at_ms: int
    def __init__(self, owner_id: _Optional[int] = ..., drawing_id: _Optional[int] = ..., layer: _Optional[_Union[LayerRef, _Mapping]] = ..., engine_symbol_id: _Optional[int] = ..., type: _Optional[int] = ..., version: _Optional[int] = ..., payload: _Optional[bytes] = ..., bbox_time_min_ms: _Optional[int] = ..., bbox_time_max_ms: _Optional[int] = ..., bbox_price_min: _Optional[float] = ..., bbox_price_max: _Optional[float] = ..., updated_at_ms: _Optional[int] = ..., deleted_at_ms: _Optional[int] = ..., client_updated_at_ms: _Optional[int] = ...) -> None: ...

class LayerSubscription(_message.Message):
    __slots__ = ("viewer_id", "engine_symbol_id", "layer", "alias_name", "sort_order", "is_enabled", "is_pinned", "is_visible_override", "is_locked_override")
    VIEWER_ID_FIELD_NUMBER: _ClassVar[int]
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    LAYER_FIELD_NUMBER: _ClassVar[int]
    ALIAS_NAME_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    IS_ENABLED_FIELD_NUMBER: _ClassVar[int]
    IS_PINNED_FIELD_NUMBER: _ClassVar[int]
    IS_VISIBLE_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    IS_LOCKED_OVERRIDE_FIELD_NUMBER: _ClassVar[int]
    viewer_id: int
    engine_symbol_id: int
    layer: LayerRef
    alias_name: str
    sort_order: int
    is_enabled: bool
    is_pinned: bool
    is_visible_override: bool
    is_locked_override: bool
    def __init__(self, viewer_id: _Optional[int] = ..., engine_symbol_id: _Optional[int] = ..., layer: _Optional[_Union[LayerRef, _Mapping]] = ..., alias_name: _Optional[str] = ..., sort_order: _Optional[int] = ..., is_enabled: _Optional[bool] = ..., is_pinned: _Optional[bool] = ..., is_visible_override: _Optional[bool] = ..., is_locked_override: _Optional[bool] = ...) -> None: ...

class GetMarketLayersRequest(_message.Message):
    __slots__ = ("engine_symbol_id",)
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    engine_symbol_id: int
    def __init__(self, engine_symbol_id: _Optional[int] = ...) -> None: ...

class GetMarketLayersResponse(_message.Message):
    __slots__ = ("engine_symbol_id", "subscriptions", "layers", "drawings")
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    LAYERS_FIELD_NUMBER: _ClassVar[int]
    DRAWINGS_FIELD_NUMBER: _ClassVar[int]
    engine_symbol_id: int
    subscriptions: _containers.RepeatedCompositeFieldContainer[LayerSubscription]
    layers: _containers.RepeatedCompositeFieldContainer[Layer]
    drawings: _containers.RepeatedCompositeFieldContainer[Drawing]
    def __init__(self, engine_symbol_id: _Optional[int] = ..., subscriptions: _Optional[_Iterable[_Union[LayerSubscription, _Mapping]]] = ..., layers: _Optional[_Iterable[_Union[Layer, _Mapping]]] = ..., drawings: _Optional[_Iterable[_Union[Drawing, _Mapping]]] = ...) -> None: ...

class ListInboxMarketLayersRequest(_message.Message):
    __slots__ = ("engine_symbol_id", "limit", "page_token")
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    engine_symbol_id: int
    limit: int
    page_token: str
    def __init__(self, engine_symbol_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListInboxMarketLayersResponse(_message.Message):
    __slots__ = ("engine_symbol_id", "layers", "next_page_token")
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    LAYERS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    engine_symbol_id: int
    layers: _containers.RepeatedCompositeFieldContainer[Layer]
    next_page_token: str
    def __init__(self, engine_symbol_id: _Optional[int] = ..., layers: _Optional[_Iterable[_Union[Layer, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetLayerSnapshotRequest(_message.Message):
    __slots__ = ("layer",)
    LAYER_FIELD_NUMBER: _ClassVar[int]
    layer: LayerRef
    def __init__(self, layer: _Optional[_Union[LayerRef, _Mapping]] = ...) -> None: ...

class GetLayerSnapshotResponse(_message.Message):
    __slots__ = ("layer", "drawings")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    DRAWINGS_FIELD_NUMBER: _ClassVar[int]
    layer: Layer
    drawings: _containers.RepeatedCompositeFieldContainer[Drawing]
    def __init__(self, layer: _Optional[_Union[Layer, _Mapping]] = ..., drawings: _Optional[_Iterable[_Union[Drawing, _Mapping]]] = ...) -> None: ...

class ResolveLayerShareTokenRequest(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class ResolveLayerShareTokenResponse(_message.Message):
    __slots__ = ("layer", "drawings", "centrifugo_sub_token")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    DRAWINGS_FIELD_NUMBER: _ClassVar[int]
    CENTRIFUGO_SUB_TOKEN_FIELD_NUMBER: _ClassVar[int]
    layer: Layer
    drawings: _containers.RepeatedCompositeFieldContainer[Drawing]
    centrifugo_sub_token: str
    def __init__(self, layer: _Optional[_Union[Layer, _Mapping]] = ..., drawings: _Optional[_Iterable[_Union[Drawing, _Mapping]]] = ..., centrifugo_sub_token: _Optional[str] = ...) -> None: ...

class GetLayerSubscribeTokensRequest(_message.Message):
    __slots__ = ("layers",)
    LAYERS_FIELD_NUMBER: _ClassVar[int]
    layers: _containers.RepeatedCompositeFieldContainer[LayerRef]
    def __init__(self, layers: _Optional[_Iterable[_Union[LayerRef, _Mapping]]] = ...) -> None: ...

class LayerSubscribeToken(_message.Message):
    __slots__ = ("layer", "centrifugo_sub_token")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    CENTRIFUGO_SUB_TOKEN_FIELD_NUMBER: _ClassVar[int]
    layer: LayerRef
    centrifugo_sub_token: str
    def __init__(self, layer: _Optional[_Union[LayerRef, _Mapping]] = ..., centrifugo_sub_token: _Optional[str] = ...) -> None: ...

class GetLayerSubscribeTokensResponse(_message.Message):
    __slots__ = ("tokens",)
    TOKENS_FIELD_NUMBER: _ClassVar[int]
    tokens: _containers.RepeatedCompositeFieldContainer[LayerSubscribeToken]
    def __init__(self, tokens: _Optional[_Iterable[_Union[LayerSubscribeToken, _Mapping]]] = ...) -> None: ...

class CreateLayerShareLinkRequest(_message.Message):
    __slots__ = ("layer", "perms", "expires_at_ms")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    PERMS_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_MS_FIELD_NUMBER: _ClassVar[int]
    layer: LayerRef
    perms: int
    expires_at_ms: int
    def __init__(self, layer: _Optional[_Union[LayerRef, _Mapping]] = ..., perms: _Optional[int] = ..., expires_at_ms: _Optional[int] = ...) -> None: ...

class CreateLayerShareLinkResponse(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class RevokeLayerShareLinkRequest(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class RevokeLayerShareLinkResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PublishedLayer(_message.Message):
    __slots__ = ("layer", "title", "description", "tags", "published_at_ms")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    layer: Layer
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    published_at_ms: int
    def __init__(self, layer: _Optional[_Union[Layer, _Mapping]] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., published_at_ms: _Optional[int] = ...) -> None: ...

class ListOwnerPublishedLayersRequest(_message.Message):
    __slots__ = ("owner_id", "engine_symbol_id", "limit", "page_token")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    engine_symbol_id: int
    limit: int
    page_token: str
    def __init__(self, owner_id: _Optional[int] = ..., engine_symbol_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListOwnerPublishedLayersResponse(_message.Message):
    __slots__ = ("layers", "next_page_token")
    LAYERS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    layers: _containers.RepeatedCompositeFieldContainer[PublishedLayer]
    next_page_token: str
    def __init__(self, layers: _Optional[_Iterable[_Union[PublishedLayer, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class PublishLayerRequest(_message.Message):
    __slots__ = ("layer", "title", "description", "tags")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    layer: LayerRef
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, layer: _Optional[_Union[LayerRef, _Mapping]] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ...) -> None: ...

class PublishLayerResponse(_message.Message):
    __slots__ = ("layer",)
    LAYER_FIELD_NUMBER: _ClassVar[int]
    layer: PublishedLayer
    def __init__(self, layer: _Optional[_Union[PublishedLayer, _Mapping]] = ...) -> None: ...

class UnpublishLayerRequest(_message.Message):
    __slots__ = ("layer",)
    LAYER_FIELD_NUMBER: _ClassVar[int]
    layer: LayerRef
    def __init__(self, layer: _Optional[_Union[LayerRef, _Mapping]] = ...) -> None: ...

class UnpublishLayerResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class UpsertLayerRequest(_message.Message):
    __slots__ = ("layer", "expected_revision")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    layer: Layer
    expected_revision: int
    def __init__(self, layer: _Optional[_Union[Layer, _Mapping]] = ..., expected_revision: _Optional[int] = ...) -> None: ...

class UpsertLayerResponse(_message.Message):
    __slots__ = ("layer",)
    LAYER_FIELD_NUMBER: _ClassVar[int]
    layer: Layer
    def __init__(self, layer: _Optional[_Union[Layer, _Mapping]] = ...) -> None: ...

class DeleteLayerRequest(_message.Message):
    __slots__ = ("layer", "expected_revision")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    layer: LayerRef
    expected_revision: int
    def __init__(self, layer: _Optional[_Union[LayerRef, _Mapping]] = ..., expected_revision: _Optional[int] = ...) -> None: ...

class DeleteLayerResponse(_message.Message):
    __slots__ = ("layer_revision",)
    LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    layer_revision: int
    def __init__(self, layer_revision: _Optional[int] = ...) -> None: ...

class UpsertDrawingRequest(_message.Message):
    __slots__ = ("drawing", "expected_layer_revision")
    DRAWING_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    drawing: Drawing
    expected_layer_revision: int
    def __init__(self, drawing: _Optional[_Union[Drawing, _Mapping]] = ..., expected_layer_revision: _Optional[int] = ...) -> None: ...

class UpsertDrawingResponse(_message.Message):
    __slots__ = ("drawing", "layer_revision")
    DRAWING_FIELD_NUMBER: _ClassVar[int]
    LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    drawing: Drawing
    layer_revision: int
    def __init__(self, drawing: _Optional[_Union[Drawing, _Mapping]] = ..., layer_revision: _Optional[int] = ...) -> None: ...

class DeleteDrawingRequest(_message.Message):
    __slots__ = ("drawing", "layer", "expected_layer_revision")
    DRAWING_FIELD_NUMBER: _ClassVar[int]
    LAYER_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    drawing: DrawingRef
    layer: LayerRef
    expected_layer_revision: int
    def __init__(self, drawing: _Optional[_Union[DrawingRef, _Mapping]] = ..., layer: _Optional[_Union[LayerRef, _Mapping]] = ..., expected_layer_revision: _Optional[int] = ...) -> None: ...

class DeleteDrawingResponse(_message.Message):
    __slots__ = ("layer_revision",)
    LAYER_REVISION_FIELD_NUMBER: _ClassVar[int]
    layer_revision: int
    def __init__(self, layer_revision: _Optional[int] = ...) -> None: ...

class SetLayerSubscriptionsRequest(_message.Message):
    __slots__ = ("engine_symbol_id", "subscriptions")
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    engine_symbol_id: int
    subscriptions: _containers.RepeatedCompositeFieldContainer[LayerSubscription]
    def __init__(self, engine_symbol_id: _Optional[int] = ..., subscriptions: _Optional[_Iterable[_Union[LayerSubscription, _Mapping]]] = ...) -> None: ...

class SetLayerSubscriptionsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
