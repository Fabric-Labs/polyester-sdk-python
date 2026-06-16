import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from polyester.gen.google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BoardAudience(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    AUDIENCE_UNSPECIFIED: _ClassVar[BoardAudience]
    PRIVATE: _ClassVar[BoardAudience]
    PUBLIC: _ClassVar[BoardAudience]
    FOLLOWERS: _ClassVar[BoardAudience]

class BoardRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ROLE_UNSPECIFIED: _ClassVar[BoardRole]
    VIEWER: _ClassVar[BoardRole]
    EDITOR: _ClassVar[BoardRole]
    OWNER: _ClassVar[BoardRole]

class BoardAclSubjectType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SUBJECT_TYPE_UNSPECIFIED: _ClassVar[BoardAclSubjectType]
    USER_SUBJECT: _ClassVar[BoardAclSubjectType]
    GROUP_SUBJECT: _ClassVar[BoardAclSubjectType]
AUDIENCE_UNSPECIFIED: BoardAudience
PRIVATE: BoardAudience
PUBLIC: BoardAudience
FOLLOWERS: BoardAudience
ROLE_UNSPECIFIED: BoardRole
VIEWER: BoardRole
EDITOR: BoardRole
OWNER: BoardRole
SUBJECT_TYPE_UNSPECIFIED: BoardAclSubjectType
USER_SUBJECT: BoardAclSubjectType
GROUP_SUBJECT: BoardAclSubjectType

class BoardAclEntry(_message.Message):
    __slots__ = ("subject_type", "subject_id", "role")
    SUBJECT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    subject_type: BoardAclSubjectType
    subject_id: int
    role: BoardRole
    def __init__(self, subject_type: _Optional[_Union[BoardAclSubjectType, str]] = ..., subject_id: _Optional[int] = ..., role: _Optional[_Union[BoardRole, str]] = ...) -> None: ...

class BoardPermissions(_message.Message):
    __slots__ = ("can_view", "can_edit", "can_manage")
    CAN_VIEW_FIELD_NUMBER: _ClassVar[int]
    CAN_EDIT_FIELD_NUMBER: _ClassVar[int]
    CAN_MANAGE_FIELD_NUMBER: _ClassVar[int]
    can_view: bool
    can_edit: bool
    can_manage: bool
    def __init__(self, can_view: _Optional[bool] = ..., can_edit: _Optional[bool] = ..., can_manage: _Optional[bool] = ...) -> None: ...

class BoardAccess(_message.Message):
    __slots__ = ("role", "permissions")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    role: BoardRole
    permissions: BoardPermissions
    def __init__(self, role: _Optional[_Union[BoardRole, str]] = ..., permissions: _Optional[_Union[BoardPermissions, _Mapping]] = ...) -> None: ...

class Board(_message.Message):
    __slots__ = ("board_id", "owner_account_id", "title", "audience", "default_role", "access_version", "initial_snapshot", "created_at", "updated_at", "archived_at")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    OWNER_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_ROLE_FIELD_NUMBER: _ClassVar[int]
    ACCESS_VERSION_FIELD_NUMBER: _ClassVar[int]
    INITIAL_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    ARCHIVED_AT_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    owner_account_id: int
    title: str
    audience: BoardAudience
    default_role: BoardRole
    access_version: int
    initial_snapshot: _struct_pb2.Struct
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    archived_at: _timestamp_pb2.Timestamp
    def __init__(self, board_id: _Optional[str] = ..., owner_account_id: _Optional[int] = ..., title: _Optional[str] = ..., audience: _Optional[_Union[BoardAudience, str]] = ..., default_role: _Optional[_Union[BoardRole, str]] = ..., access_version: _Optional[int] = ..., initial_snapshot: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., archived_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class BoardListItem(_message.Message):
    __slots__ = ("board", "access")
    BOARD_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    board: Board
    access: BoardAccess
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ...) -> None: ...

class PresencePayload(_message.Message):
    __slots__ = ("account_id", "role")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    account_id: int
    role: BoardRole
    def __init__(self, account_id: _Optional[int] = ..., role: _Optional[_Union[BoardRole, str]] = ...) -> None: ...

class CreateBoardRequest(_message.Message):
    __slots__ = ("title", "audience", "default_role", "acl_entries", "initial_snapshot")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_ROLE_FIELD_NUMBER: _ClassVar[int]
    ACL_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    INITIAL_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    title: str
    audience: BoardAudience
    default_role: BoardRole
    acl_entries: _containers.RepeatedCompositeFieldContainer[BoardAclEntry]
    initial_snapshot: _struct_pb2.Struct
    def __init__(self, title: _Optional[str] = ..., audience: _Optional[_Union[BoardAudience, str]] = ..., default_role: _Optional[_Union[BoardRole, str]] = ..., acl_entries: _Optional[_Iterable[_Union[BoardAclEntry, _Mapping]]] = ..., initial_snapshot: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class CreateBoardResponse(_message.Message):
    __slots__ = ("board", "acl_entries", "access")
    BOARD_FIELD_NUMBER: _ClassVar[int]
    ACL_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    board: Board
    acl_entries: _containers.RepeatedCompositeFieldContainer[BoardAclEntry]
    access: BoardAccess
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ..., acl_entries: _Optional[_Iterable[_Union[BoardAclEntry, _Mapping]]] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ...) -> None: ...

class GetBoardRequest(_message.Message):
    __slots__ = ("board_id",)
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    def __init__(self, board_id: _Optional[str] = ...) -> None: ...

class GetBoardResponse(_message.Message):
    __slots__ = ("board", "acl_entries", "access")
    BOARD_FIELD_NUMBER: _ClassVar[int]
    ACL_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    board: Board
    acl_entries: _containers.RepeatedCompositeFieldContainer[BoardAclEntry]
    access: BoardAccess
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ..., acl_entries: _Optional[_Iterable[_Union[BoardAclEntry, _Mapping]]] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ...) -> None: ...

class ListBoardsRequest(_message.Message):
    __slots__ = ("include_archived", "limit", "page_token")
    INCLUDE_ARCHIVED_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    include_archived: bool
    limit: int
    page_token: str
    def __init__(self, include_archived: _Optional[bool] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListBoardsResponse(_message.Message):
    __slots__ = ("boards", "next_page_token")
    BOARDS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    boards: _containers.RepeatedCompositeFieldContainer[BoardListItem]
    next_page_token: str
    def __init__(self, boards: _Optional[_Iterable[_Union[BoardListItem, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class UpdateBoardRequest(_message.Message):
    __slots__ = ("board_id", "title", "audience", "default_role", "initial_snapshot")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AUDIENCE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_ROLE_FIELD_NUMBER: _ClassVar[int]
    INITIAL_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    title: str
    audience: BoardAudience
    default_role: BoardRole
    initial_snapshot: _struct_pb2.Struct
    def __init__(self, board_id: _Optional[str] = ..., title: _Optional[str] = ..., audience: _Optional[_Union[BoardAudience, str]] = ..., default_role: _Optional[_Union[BoardRole, str]] = ..., initial_snapshot: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class UpdateBoardResponse(_message.Message):
    __slots__ = ("board", "acl_entries", "access")
    BOARD_FIELD_NUMBER: _ClassVar[int]
    ACL_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    board: Board
    acl_entries: _containers.RepeatedCompositeFieldContainer[BoardAclEntry]
    access: BoardAccess
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ..., acl_entries: _Optional[_Iterable[_Union[BoardAclEntry, _Mapping]]] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ...) -> None: ...

class UpdateBoardAclRequest(_message.Message):
    __slots__ = ("board_id", "acl_entries")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    ACL_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    acl_entries: _containers.RepeatedCompositeFieldContainer[BoardAclEntry]
    def __init__(self, board_id: _Optional[str] = ..., acl_entries: _Optional[_Iterable[_Union[BoardAclEntry, _Mapping]]] = ...) -> None: ...

class UpdateBoardAclResponse(_message.Message):
    __slots__ = ("board", "acl_entries", "access")
    BOARD_FIELD_NUMBER: _ClassVar[int]
    ACL_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    board: Board
    acl_entries: _containers.RepeatedCompositeFieldContainer[BoardAclEntry]
    access: BoardAccess
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ..., acl_entries: _Optional[_Iterable[_Union[BoardAclEntry, _Mapping]]] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ...) -> None: ...

class ArchiveBoardRequest(_message.Message):
    __slots__ = ("board_id", "archived")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    ARCHIVED_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    archived: bool
    def __init__(self, board_id: _Optional[str] = ..., archived: _Optional[bool] = ...) -> None: ...

class ArchiveBoardResponse(_message.Message):
    __slots__ = ("board", "access")
    BOARD_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    board: Board
    access: BoardAccess
    def __init__(self, board: _Optional[_Union[Board, _Mapping]] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ...) -> None: ...

class MintJoinTokenRequest(_message.Message):
    __slots__ = ("board_id",)
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    def __init__(self, board_id: _Optional[str] = ...) -> None: ...

class MintJoinTokenResponse(_message.Message):
    __slots__ = ("board_id", "access", "expires_at", "token", "room_id", "connection_id", "socket_path", "presence", "access_version")
    BOARD_ID_FIELD_NUMBER: _ClassVar[int]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_ID_FIELD_NUMBER: _ClassVar[int]
    SOCKET_PATH_FIELD_NUMBER: _ClassVar[int]
    PRESENCE_FIELD_NUMBER: _ClassVar[int]
    ACCESS_VERSION_FIELD_NUMBER: _ClassVar[int]
    board_id: str
    access: BoardAccess
    expires_at: _timestamp_pb2.Timestamp
    token: str
    room_id: str
    connection_id: str
    socket_path: str
    presence: PresencePayload
    access_version: int
    def __init__(self, board_id: _Optional[str] = ..., access: _Optional[_Union[BoardAccess, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., token: _Optional[str] = ..., room_id: _Optional[str] = ..., connection_id: _Optional[str] = ..., socket_path: _Optional[str] = ..., presence: _Optional[_Union[PresencePayload, _Mapping]] = ..., access_version: _Optional[int] = ...) -> None: ...
