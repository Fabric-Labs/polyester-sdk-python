from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from polyester.gen.polychart.v1 import polychart_pb2 as _polychart_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WidgetType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WIDGET_TYPE_UNSPECIFIED: _ClassVar[WidgetType]
    CHART: _ClassVar[WidgetType]
    ORDERBOOK: _ClassVar[WidgetType]
    TRADES: _ClassVar[WidgetType]
    POSITIONS: _ClassVar[WidgetType]
    ORDERS: _ClassVar[WidgetType]
WIDGET_TYPE_UNSPECIFIED: WidgetType
CHART: WidgetType
ORDERBOOK: WidgetType
TRADES: WidgetType
POSITIONS: WidgetType
ORDERS: WidgetType

class LayoutWidget(_message.Message):
    __slots__ = ("widget_id", "widget_type", "widget_config")
    WIDGET_ID_FIELD_NUMBER: _ClassVar[int]
    WIDGET_TYPE_FIELD_NUMBER: _ClassVar[int]
    WIDGET_CONFIG_FIELD_NUMBER: _ClassVar[int]
    widget_id: str
    widget_type: WidgetType
    widget_config: bytes
    def __init__(self, widget_id: _Optional[str] = ..., widget_type: _Optional[_Union[WidgetType, str]] = ..., widget_config: _Optional[bytes] = ...) -> None: ...

class Layout(_message.Message):
    __slots__ = ("viewer_id", "layout_id", "name", "is_default", "dockview_state", "widgets", "updated_at_ms")
    VIEWER_ID_FIELD_NUMBER: _ClassVar[int]
    LAYOUT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    IS_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    DOCKVIEW_STATE_FIELD_NUMBER: _ClassVar[int]
    WIDGETS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    viewer_id: int
    layout_id: int
    name: str
    is_default: bool
    dockview_state: bytes
    widgets: _containers.RepeatedCompositeFieldContainer[LayoutWidget]
    updated_at_ms: int
    def __init__(self, viewer_id: _Optional[int] = ..., layout_id: _Optional[int] = ..., name: _Optional[str] = ..., is_default: _Optional[bool] = ..., dockview_state: _Optional[bytes] = ..., widgets: _Optional[_Iterable[_Union[LayoutWidget, _Mapping]]] = ..., updated_at_ms: _Optional[int] = ...) -> None: ...

class ChartWidgetConfig(_message.Message):
    __slots__ = ("engine_symbol_id", "timeframe", "indicators", "style", "layer_overrides", "follow_latest")
    ENGINE_SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    INDICATORS_FIELD_NUMBER: _ClassVar[int]
    STYLE_FIELD_NUMBER: _ClassVar[int]
    LAYER_OVERRIDES_FIELD_NUMBER: _ClassVar[int]
    FOLLOW_LATEST_FIELD_NUMBER: _ClassVar[int]
    engine_symbol_id: int
    timeframe: str
    indicators: _containers.RepeatedCompositeFieldContainer[ChartIndicator]
    style: ChartStyle
    layer_overrides: _containers.RepeatedCompositeFieldContainer[LayerVisibilityOverride]
    follow_latest: bool
    def __init__(self, engine_symbol_id: _Optional[int] = ..., timeframe: _Optional[str] = ..., indicators: _Optional[_Iterable[_Union[ChartIndicator, _Mapping]]] = ..., style: _Optional[_Union[ChartStyle, _Mapping]] = ..., layer_overrides: _Optional[_Iterable[_Union[LayerVisibilityOverride, _Mapping]]] = ..., follow_latest: _Optional[bool] = ...) -> None: ...

class ChartIndicator(_message.Message):
    __slots__ = ("indicator_type", "params")
    INDICATOR_TYPE_FIELD_NUMBER: _ClassVar[int]
    PARAMS_FIELD_NUMBER: _ClassVar[int]
    indicator_type: str
    params: bytes
    def __init__(self, indicator_type: _Optional[str] = ..., params: _Optional[bytes] = ...) -> None: ...

class ChartStyle(_message.Message):
    __slots__ = ("style_bytes",)
    STYLE_BYTES_FIELD_NUMBER: _ClassVar[int]
    style_bytes: bytes
    def __init__(self, style_bytes: _Optional[bytes] = ...) -> None: ...

class LayerVisibilityOverride(_message.Message):
    __slots__ = ("layer", "visible")
    LAYER_FIELD_NUMBER: _ClassVar[int]
    VISIBLE_FIELD_NUMBER: _ClassVar[int]
    layer: _polychart_pb2.LayerRef
    visible: bool
    def __init__(self, layer: _Optional[_Union[_polychart_pb2.LayerRef, _Mapping]] = ..., visible: _Optional[bool] = ...) -> None: ...

class GetLayoutsRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class GetLayoutsResponse(_message.Message):
    __slots__ = ("layouts", "next_page_token")
    LAYOUTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    layouts: _containers.RepeatedCompositeFieldContainer[Layout]
    next_page_token: str
    def __init__(self, layouts: _Optional[_Iterable[_Union[Layout, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetLayoutRequest(_message.Message):
    __slots__ = ("layout_id",)
    LAYOUT_ID_FIELD_NUMBER: _ClassVar[int]
    layout_id: int
    def __init__(self, layout_id: _Optional[int] = ...) -> None: ...

class GetLayoutResponse(_message.Message):
    __slots__ = ("layout",)
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    layout: Layout
    def __init__(self, layout: _Optional[_Union[Layout, _Mapping]] = ...) -> None: ...

class ResolveLayoutShareTokenRequest(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class ResolveLayoutShareTokenResponse(_message.Message):
    __slots__ = ("layout", "owner_id", "template_id", "version")
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    layout: Layout
    owner_id: int
    template_id: int
    version: int
    def __init__(self, layout: _Optional[_Union[Layout, _Mapping]] = ..., owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., version: _Optional[int] = ...) -> None: ...

class CreateLayoutShareLinkRequest(_message.Message):
    __slots__ = ("layout_id", "expires_at_ms")
    LAYOUT_ID_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_MS_FIELD_NUMBER: _ClassVar[int]
    layout_id: int
    expires_at_ms: int
    def __init__(self, layout_id: _Optional[int] = ..., expires_at_ms: _Optional[int] = ...) -> None: ...

class CreateLayoutShareLinkResponse(_message.Message):
    __slots__ = ("token", "owner_id", "template_id", "version")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    token: str
    owner_id: int
    template_id: int
    version: int
    def __init__(self, token: _Optional[str] = ..., owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., version: _Optional[int] = ...) -> None: ...

class RevokeLayoutShareLinkRequest(_message.Message):
    __slots__ = ("token",)
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    token: str
    def __init__(self, token: _Optional[str] = ...) -> None: ...

class RevokeLayoutShareLinkResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LayoutTemplateRef(_message.Message):
    __slots__ = ("owner_id", "template_id")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    template_id: int
    def __init__(self, owner_id: _Optional[int] = ..., template_id: _Optional[int] = ...) -> None: ...

class LayoutTemplate(_message.Message):
    __slots__ = ("template", "title", "description", "tags", "is_listed", "latest_version", "published_at_ms", "updated_at_ms")
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    IS_LISTED_FIELD_NUMBER: _ClassVar[int]
    LATEST_VERSION_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    template: LayoutTemplateRef
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    is_listed: bool
    latest_version: int
    published_at_ms: int
    updated_at_ms: int
    def __init__(self, template: _Optional[_Union[LayoutTemplateRef, _Mapping]] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., is_listed: _Optional[bool] = ..., latest_version: _Optional[int] = ..., published_at_ms: _Optional[int] = ..., updated_at_ms: _Optional[int] = ...) -> None: ...

class LayoutTemplateVersionInfo(_message.Message):
    __slots__ = ("version", "changelog", "created_at_ms")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    CHANGELOG_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    version: int
    changelog: str
    created_at_ms: int
    def __init__(self, version: _Optional[int] = ..., changelog: _Optional[str] = ..., created_at_ms: _Optional[int] = ...) -> None: ...

class ListOwnerPublishedLayoutsRequest(_message.Message):
    __slots__ = ("owner_id", "limit", "page_token")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    limit: int
    page_token: str
    def __init__(self, owner_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListOwnerPublishedLayoutsResponse(_message.Message):
    __slots__ = ("templates", "next_page_token")
    TEMPLATES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    templates: _containers.RepeatedCompositeFieldContainer[LayoutTemplate]
    next_page_token: str
    def __init__(self, templates: _Optional[_Iterable[_Union[LayoutTemplate, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListLayoutTemplateVersionsRequest(_message.Message):
    __slots__ = ("owner_id", "template_id", "limit", "page_token")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    template_id: int
    limit: int
    page_token: str
    def __init__(self, owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListLayoutTemplateVersionsResponse(_message.Message):
    __slots__ = ("versions", "next_page_token")
    VERSIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    versions: _containers.RepeatedCompositeFieldContainer[LayoutTemplateVersionInfo]
    next_page_token: str
    def __init__(self, versions: _Optional[_Iterable[_Union[LayoutTemplateVersionInfo, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetLayoutTemplateVersionRequest(_message.Message):
    __slots__ = ("owner_id", "template_id", "version")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    template_id: int
    version: int
    def __init__(self, owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., version: _Optional[int] = ...) -> None: ...

class GetLayoutTemplateVersionResponse(_message.Message):
    __slots__ = ("layout", "owner_id", "template_id", "version")
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    layout: Layout
    owner_id: int
    template_id: int
    version: int
    def __init__(self, layout: _Optional[_Union[Layout, _Mapping]] = ..., owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., version: _Optional[int] = ...) -> None: ...

class PublishLayoutRequest(_message.Message):
    __slots__ = ("layout_id", "title", "description", "tags", "is_listed", "changelog")
    LAYOUT_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    IS_LISTED_FIELD_NUMBER: _ClassVar[int]
    CHANGELOG_FIELD_NUMBER: _ClassVar[int]
    layout_id: int
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    is_listed: bool
    changelog: str
    def __init__(self, layout_id: _Optional[int] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., is_listed: _Optional[bool] = ..., changelog: _Optional[str] = ...) -> None: ...

class PublishLayoutResponse(_message.Message):
    __slots__ = ("template", "version")
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    template: LayoutTemplate
    version: int
    def __init__(self, template: _Optional[_Union[LayoutTemplate, _Mapping]] = ..., version: _Optional[int] = ...) -> None: ...

class UnpublishLayoutRequest(_message.Message):
    __slots__ = ("template_id",)
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    template_id: int
    def __init__(self, template_id: _Optional[int] = ...) -> None: ...

class UnpublishLayoutResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetLayoutTemplateSubscriptionRequest(_message.Message):
    __slots__ = ("owner_id", "template_id", "track_latest", "pinned_version")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    TRACK_LATEST_FIELD_NUMBER: _ClassVar[int]
    PINNED_VERSION_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    template_id: int
    track_latest: bool
    pinned_version: int
    def __init__(self, owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., track_latest: _Optional[bool] = ..., pinned_version: _Optional[int] = ...) -> None: ...

class SetLayoutTemplateSubscriptionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeleteLayoutTemplateSubscriptionRequest(_message.Message):
    __slots__ = ("owner_id", "template_id")
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    owner_id: int
    template_id: int
    def __init__(self, owner_id: _Optional[int] = ..., template_id: _Optional[int] = ...) -> None: ...

class DeleteLayoutTemplateSubscriptionResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LayoutTemplateSubscription(_message.Message):
    __slots__ = ("viewer_id", "owner_id", "template_id", "track_latest", "pinned_version", "updated_at_ms")
    VIEWER_ID_FIELD_NUMBER: _ClassVar[int]
    OWNER_ID_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    TRACK_LATEST_FIELD_NUMBER: _ClassVar[int]
    PINNED_VERSION_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_MS_FIELD_NUMBER: _ClassVar[int]
    viewer_id: int
    owner_id: int
    template_id: int
    track_latest: bool
    pinned_version: int
    updated_at_ms: int
    def __init__(self, viewer_id: _Optional[int] = ..., owner_id: _Optional[int] = ..., template_id: _Optional[int] = ..., track_latest: _Optional[bool] = ..., pinned_version: _Optional[int] = ..., updated_at_ms: _Optional[int] = ...) -> None: ...

class ListMyLayoutTemplateSubscriptionsRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListMyLayoutTemplateSubscriptionsResponse(_message.Message):
    __slots__ = ("subscriptions", "next_page_token")
    SUBSCRIPTIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subscriptions: _containers.RepeatedCompositeFieldContainer[LayoutTemplateSubscription]
    next_page_token: str
    def __init__(self, subscriptions: _Optional[_Iterable[_Union[LayoutTemplateSubscription, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class UpsertLayoutRequest(_message.Message):
    __slots__ = ("layout",)
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    layout: Layout
    def __init__(self, layout: _Optional[_Union[Layout, _Mapping]] = ...) -> None: ...

class UpsertLayoutResponse(_message.Message):
    __slots__ = ("layout",)
    LAYOUT_FIELD_NUMBER: _ClassVar[int]
    layout: Layout
    def __init__(self, layout: _Optional[_Union[Layout, _Mapping]] = ...) -> None: ...

class DeleteLayoutRequest(_message.Message):
    __slots__ = ("layout_id",)
    LAYOUT_ID_FIELD_NUMBER: _ClassVar[int]
    layout_id: int
    def __init__(self, layout_id: _Optional[int] = ...) -> None: ...

class DeleteLayoutResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
