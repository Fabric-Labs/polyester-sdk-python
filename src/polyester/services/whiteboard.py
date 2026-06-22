from __future__ import annotations

from typing import Any

from google.protobuf import struct_pb2

from polyester.codecs.decode.common import api_data_from_proto
from polyester.codecs.enums import resolve_proto_enum
from polyester.codecs.proto_build import repeated_messages_from_mappings
from polyester.gen.collab.v1 import whiteboard_pb2 as wb_pb2
from polyester.gen.collab.v1.whiteboard_connect import WhiteboardServiceClient
from polyester.models import ApiData
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded

_AUDIENCE_ALIASES = {
    "private": wb_pb2.PRIVATE,
    "public": wb_pb2.PUBLIC,
    "followers": wb_pb2.FOLLOWERS,
}

_ROLE_ALIASES = {
    "viewer": wb_pb2.VIEWER,
    "editor": wb_pb2.EDITOR,
    "owner": wb_pb2.OWNER,
}


def _board_audience(value: str) -> int:
    return resolve_proto_enum(wb_pb2, value, aliases=_AUDIENCE_ALIASES, field_name="audience")


def _board_role(value: str) -> int:
    return resolve_proto_enum(wb_pb2, value, aliases=_ROLE_ALIASES, field_name="role")


def _struct_from_mapping(value: dict[str, Any] | struct_pb2.Struct | None) -> struct_pb2.Struct:
    if value is None:
        return struct_pb2.Struct()
    if isinstance(value, struct_pb2.Struct):
        return value
    struct = struct_pb2.Struct()
    struct.update(value)
    return struct


class AsyncWhiteboardService(BaseService):
    async def create(
        self,
        *,
        title: str,
        audience: str = "private",
        default_role: str = "viewer",
        acl_entries: list[dict[str, Any]] | None = None,
        initial_snapshot: dict[str, Any] | None = None,
    ) -> ApiData:
        request = wb_pb2.CreateBoardRequest(
            title=title,
            audience=_board_audience(audience),
            default_role=_board_role(default_role),
            acl_entries=repeated_messages_from_mappings(wb_pb2.BoardAclEntry, acl_entries),
            initial_snapshot=_struct_from_mapping(initial_snapshot),
        )
        return await self._call(request, WhiteboardServiceClient.create_board)

    async def get(self, *, board_id: str) -> ApiData:
        return await self._call(
            wb_pb2.GetBoardRequest(board_id=board_id),
            WhiteboardServiceClient.get_board,
        )

    async def list(
        self,
        *,
        include_archived: bool = False,
        limit: int = 0,
        page_token: str = "",
    ) -> ApiData:
        return await self._call(
            wb_pb2.ListBoardsRequest(
                include_archived=include_archived,
                limit=limit,
                page_token=page_token,
            ),
            WhiteboardServiceClient.list_boards,
        )

    async def update(
        self,
        *,
        board_id: str,
        title: str = "",
        audience: str = "",
        default_role: str = "",
        initial_snapshot: dict[str, Any] | None = None,
    ) -> ApiData:
        request = wb_pb2.UpdateBoardRequest(board_id=board_id, title=title)
        if audience:
            request.audience = _board_audience(audience)
        if default_role:
            request.default_role = _board_role(default_role)
        if initial_snapshot is not None:
            request.initial_snapshot.CopyFrom(_struct_from_mapping(initial_snapshot))
        return await self._call(request, WhiteboardServiceClient.update_board)

    async def update_acl(
        self,
        *,
        board_id: str,
        acl_entries: list[dict[str, Any]],
    ) -> ApiData:
        return await self._call(
            wb_pb2.UpdateBoardAclRequest(
                board_id=board_id,
                acl_entries=repeated_messages_from_mappings(wb_pb2.BoardAclEntry, acl_entries),
            ),
            WhiteboardServiceClient.update_board_acl,
        )

    async def archive(self, *, board_id: str, archived: bool = True) -> ApiData:
        return await self._call(
            wb_pb2.ArchiveBoardRequest(board_id=board_id, archived=archived),
            WhiteboardServiceClient.archive_board,
        )

    async def mint_join_token(self, *, board_id: str) -> ApiData:
        return await self._call(
            wb_pb2.MintJoinTokenRequest(board_id=board_id),
            WhiteboardServiceClient.mint_join_token,
        )

    async def _call(self, request, call):
        return await unary_auth_decoded(
            self._transport,
            WhiteboardServiceClient,
            call,
            request,
            api_data_from_proto,
        )
