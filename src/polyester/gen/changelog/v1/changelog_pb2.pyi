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

class ChangeCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CATEGORY_UNSPECIFIED: _ClassVar[ChangeCategory]
    BREAKING_CHANGE: _ClassVar[ChangeCategory]
    NEW_FEATURE: _ClassVar[ChangeCategory]
    IMPROVEMENT: _ClassVar[ChangeCategory]
    BUG_FIX: _ClassVar[ChangeCategory]

class Audience(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AUDIENCE_UNSPECIFIED: _ClassVar[Audience]
    ALL_USERS: _ClassVar[Audience]
    TRADERS: _ClassVar[Audience]
    MARKET_MAKERS: _ClassVar[Audience]
    DEVELOPERS: _ClassVar[Audience]

class Surface(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SURFACE_UNSPECIFIED: _ClassVar[Surface]
    TRADING: _ClassVar[Surface]
    FUNDING: _ClassVar[Surface]
    ACCOUNTS: _ClassVar[Surface]
    API: _ClassVar[Surface]
    EXPLORER: _ClassVar[Surface]
    DOCUMENTATION: _ClassVar[Surface]
    PLATFORM: _ClassVar[Surface]

class SortDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SORT_DIRECTION_UNSPECIFIED: _ClassVar[SortDirection]
    SORT_ASC: _ClassVar[SortDirection]
    SORT_DESC: _ClassVar[SortDirection]
CATEGORY_UNSPECIFIED: ChangeCategory
BREAKING_CHANGE: ChangeCategory
NEW_FEATURE: ChangeCategory
IMPROVEMENT: ChangeCategory
BUG_FIX: ChangeCategory
AUDIENCE_UNSPECIFIED: Audience
ALL_USERS: Audience
TRADERS: Audience
MARKET_MAKERS: Audience
DEVELOPERS: Audience
SURFACE_UNSPECIFIED: Surface
TRADING: Surface
FUNDING: Surface
ACCOUNTS: Surface
API: Surface
EXPLORER: Surface
DOCUMENTATION: Surface
PLATFORM: Surface
SORT_DIRECTION_UNSPECIFIED: SortDirection
SORT_ASC: SortDirection
SORT_DESC: SortDirection

class Change(_message.Message):
    __slots__ = ("id", "title", "summary", "details", "category", "action_required", "migration_guidance", "audiences", "surfaces")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    ACTION_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    MIGRATION_GUIDANCE_FIELD_NUMBER: _ClassVar[int]
    AUDIENCES_FIELD_NUMBER: _ClassVar[int]
    SURFACES_FIELD_NUMBER: _ClassVar[int]
    id: int
    title: str
    summary: str
    details: str
    category: ChangeCategory
    action_required: bool
    migration_guidance: str
    audiences: _containers.RepeatedScalarFieldContainer[Audience]
    surfaces: _containers.RepeatedScalarFieldContainer[Surface]
    def __init__(self, id: _Optional[int] = ..., title: _Optional[str] = ..., summary: _Optional[str] = ..., details: _Optional[str] = ..., category: _Optional[_Union[ChangeCategory, str]] = ..., action_required: _Optional[bool] = ..., migration_guidance: _Optional[str] = ..., audiences: _Optional[_Iterable[_Union[Audience, str]]] = ..., surfaces: _Optional[_Iterable[_Union[Surface, str]]] = ...) -> None: ...

class Section(_message.Message):
    __slots__ = ("heading", "summary", "changes")
    HEADING_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    CHANGES_FIELD_NUMBER: _ClassVar[int]
    heading: str
    summary: str
    changes: _containers.RepeatedCompositeFieldContainer[Change]
    def __init__(self, heading: _Optional[str] = ..., summary: _Optional[str] = ..., changes: _Optional[_Iterable[_Union[Change, _Mapping]]] = ...) -> None: ...

class PostSummary(_message.Message):
    __slots__ = ("slug", "title", "introduction", "published_at", "coverage_cutoff", "change_count", "breaking_change_count", "action_required_count", "new_feature_count", "improvement_count", "bug_fix_count")
    SLUG_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    INTRODUCTION_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_FIELD_NUMBER: _ClassVar[int]
    COVERAGE_CUTOFF_FIELD_NUMBER: _ClassVar[int]
    CHANGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    BREAKING_CHANGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    ACTION_REQUIRED_COUNT_FIELD_NUMBER: _ClassVar[int]
    NEW_FEATURE_COUNT_FIELD_NUMBER: _ClassVar[int]
    IMPROVEMENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    BUG_FIX_COUNT_FIELD_NUMBER: _ClassVar[int]
    slug: str
    title: str
    introduction: str
    published_at: _timestamp_pb2.Timestamp
    coverage_cutoff: _timestamp_pb2.Timestamp
    change_count: int
    breaking_change_count: int
    action_required_count: int
    new_feature_count: int
    improvement_count: int
    bug_fix_count: int
    def __init__(self, slug: _Optional[str] = ..., title: _Optional[str] = ..., introduction: _Optional[str] = ..., published_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., coverage_cutoff: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., change_count: _Optional[int] = ..., breaking_change_count: _Optional[int] = ..., action_required_count: _Optional[int] = ..., new_feature_count: _Optional[int] = ..., improvement_count: _Optional[int] = ..., bug_fix_count: _Optional[int] = ...) -> None: ...

class Post(_message.Message):
    __slots__ = ("summary", "sections")
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    SECTIONS_FIELD_NUMBER: _ClassVar[int]
    summary: PostSummary
    sections: _containers.RepeatedCompositeFieldContainer[Section]
    def __init__(self, summary: _Optional[_Union[PostSummary, _Mapping]] = ..., sections: _Optional[_Iterable[_Union[Section, _Mapping]]] = ...) -> None: ...

class ListPostsRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListPostsResponse(_message.Message):
    __slots__ = ("posts", "next_page_token")
    POSTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    posts: _containers.RepeatedCompositeFieldContainer[PostSummary]
    next_page_token: str
    def __init__(self, posts: _Optional[_Iterable[_Union[PostSummary, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetPostRequest(_message.Message):
    __slots__ = ("slug",)
    SLUG_FIELD_NUMBER: _ClassVar[int]
    slug: str
    def __init__(self, slug: _Optional[str] = ...) -> None: ...

class GetPostResponse(_message.Message):
    __slots__ = ("post",)
    POST_FIELD_NUMBER: _ClassVar[int]
    post: Post
    def __init__(self, post: _Optional[_Union[Post, _Mapping]] = ...) -> None: ...

class ListChangesRequest(_message.Message):
    __slots__ = ("categories", "action_required", "surfaces", "audiences", "start_time", "end_time", "post_slug", "sort", "limit", "page_token")
    CATEGORIES_FIELD_NUMBER: _ClassVar[int]
    ACTION_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    SURFACES_FIELD_NUMBER: _ClassVar[int]
    AUDIENCES_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    POST_SLUG_FIELD_NUMBER: _ClassVar[int]
    SORT_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    categories: _containers.RepeatedScalarFieldContainer[ChangeCategory]
    action_required: bool
    surfaces: _containers.RepeatedScalarFieldContainer[Surface]
    audiences: _containers.RepeatedScalarFieldContainer[Audience]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    post_slug: str
    sort: SortDirection
    limit: int
    page_token: str
    def __init__(self, categories: _Optional[_Iterable[_Union[ChangeCategory, str]]] = ..., action_required: _Optional[bool] = ..., surfaces: _Optional[_Iterable[_Union[Surface, str]]] = ..., audiences: _Optional[_Iterable[_Union[Audience, str]]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., post_slug: _Optional[str] = ..., sort: _Optional[_Union[SortDirection, str]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ChangeEntry(_message.Message):
    __slots__ = ("change", "post_slug", "published_at", "section_heading")
    CHANGE_FIELD_NUMBER: _ClassVar[int]
    POST_SLUG_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_FIELD_NUMBER: _ClassVar[int]
    SECTION_HEADING_FIELD_NUMBER: _ClassVar[int]
    change: Change
    post_slug: str
    published_at: _timestamp_pb2.Timestamp
    section_heading: str
    def __init__(self, change: _Optional[_Union[Change, _Mapping]] = ..., post_slug: _Optional[str] = ..., published_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., section_heading: _Optional[str] = ...) -> None: ...

class ListChangesResponse(_message.Message):
    __slots__ = ("changes", "next_page_token")
    CHANGES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    changes: _containers.RepeatedCompositeFieldContainer[ChangeEntry]
    next_page_token: str
    def __init__(self, changes: _Optional[_Iterable[_Union[ChangeEntry, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
