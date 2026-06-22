from __future__ import annotations

from typing import Any

from polyester.codecs.decode.common import api_data_from_proto
from polyester.codecs.proto_build import message_from_mapping
from polyester.codecs.scalars import id_to_int
from polyester.gen.layout.v1 import layout_pb2
from polyester.gen.layout.v1.layout_connect import LayoutServiceClient
from polyester.models import ApiData
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded


class AsyncLayoutService(BaseService):
    async def get_layouts(self, *, limit: int = 0, page_token: str = "") -> ApiData:
        return await self._call(
            layout_pb2.GetLayoutsRequest(limit=limit, page_token=page_token),
            LayoutServiceClient.get_layouts,
        )

    async def get_layout(self, *, layout_id: str | int) -> ApiData:
        return await self._call(
            layout_pb2.GetLayoutRequest(layout_id=id_to_int(layout_id, "layout_id")),
            LayoutServiceClient.get_layout,
        )

    async def upsert_layout(self, *, layout: dict[str, Any]) -> ApiData:
        return await self._call(
            layout_pb2.UpsertLayoutRequest(
                layout=message_from_mapping(layout_pb2.Layout, layout),
            ),
            LayoutServiceClient.upsert_layout,
        )

    async def delete_layout(self, *, layout_id: str | int) -> ApiData:
        return await self._call(
            layout_pb2.DeleteLayoutRequest(layout_id=id_to_int(layout_id, "layout_id")),
            LayoutServiceClient.delete_layout,
        )

    async def resolve_layout_share_token(self, *, token: str) -> ApiData:
        return await self._call(
            layout_pb2.ResolveLayoutShareTokenRequest(token=token),
            LayoutServiceClient.resolve_layout_share_token,
        )

    async def create_layout_share_link(
        self,
        *,
        layout_id: str | int,
        expires_at_ms: int = 0,
    ) -> ApiData:
        return await self._call(
            layout_pb2.CreateLayoutShareLinkRequest(
                layout_id=id_to_int(layout_id, "layout_id"),
                expires_at_ms=expires_at_ms,
            ),
            LayoutServiceClient.create_layout_share_link,
        )

    async def revoke_layout_share_link(self, *, token: str) -> ApiData:
        return await self._call(
            layout_pb2.RevokeLayoutShareLinkRequest(token=token),
            LayoutServiceClient.revoke_layout_share_link,
        )

    async def list_owner_published_layouts(
        self,
        *,
        owner_id: str | int,
        limit: int = 0,
        page_token: str = "",
    ) -> ApiData:
        return await self._call(
            layout_pb2.ListOwnerPublishedLayoutsRequest(
                owner_id=id_to_int(owner_id, "owner_id"),
                limit=limit,
                page_token=page_token,
            ),
            LayoutServiceClient.list_owner_published_layouts,
        )

    async def publish_layout(
        self,
        *,
        layout_id: str | int,
        title: str = "",
        description: str = "",
        tags: list[str] | None = None,
        is_listed: bool = False,
        changelog: str = "",
    ) -> ApiData:
        request = layout_pb2.PublishLayoutRequest(
            layout_id=id_to_int(layout_id, "layout_id"),
            title=title,
            description=description,
            is_listed=is_listed,
            changelog=changelog,
        )
        if tags:
            request.tags.extend(tags)
        return await self._call(request, LayoutServiceClient.publish_layout)

    async def unpublish_layout(self, *, template_id: str | int) -> ApiData:
        return await self._call(
            layout_pb2.UnpublishLayoutRequest(
                template_id=id_to_int(template_id, "template_id"),
            ),
            LayoutServiceClient.unpublish_layout,
        )

    async def list_layout_template_versions(
        self,
        *,
        owner_id: str | int,
        template_id: str | int,
        limit: int = 0,
        page_token: str = "",
    ) -> ApiData:
        return await self._call(
            layout_pb2.ListLayoutTemplateVersionsRequest(
                owner_id=id_to_int(owner_id, "owner_id"),
                template_id=id_to_int(template_id, "template_id"),
                limit=limit,
                page_token=page_token,
            ),
            LayoutServiceClient.list_layout_template_versions,
        )

    async def get_layout_template_version(
        self,
        *,
        owner_id: str | int,
        template_id: str | int,
        version: int,
    ) -> ApiData:
        return await self._call(
            layout_pb2.GetLayoutTemplateVersionRequest(
                owner_id=id_to_int(owner_id, "owner_id"),
                template_id=id_to_int(template_id, "template_id"),
                version=version,
            ),
            LayoutServiceClient.get_layout_template_version,
        )

    async def set_layout_template_subscription(
        self,
        *,
        owner_id: str | int,
        template_id: str | int,
        track_latest: bool = False,
        pinned_version: int = 0,
    ) -> ApiData:
        return await self._call(
            layout_pb2.SetLayoutTemplateSubscriptionRequest(
                owner_id=id_to_int(owner_id, "owner_id"),
                template_id=id_to_int(template_id, "template_id"),
                track_latest=track_latest,
                pinned_version=pinned_version,
            ),
            LayoutServiceClient.set_layout_template_subscription,
        )

    async def delete_layout_template_subscription(
        self,
        *,
        owner_id: str | int,
        template_id: str | int,
    ) -> ApiData:
        return await self._call(
            layout_pb2.DeleteLayoutTemplateSubscriptionRequest(
                owner_id=id_to_int(owner_id, "owner_id"),
                template_id=id_to_int(template_id, "template_id"),
            ),
            LayoutServiceClient.delete_layout_template_subscription,
        )

    async def list_my_layout_template_subscriptions(
        self,
        *,
        limit: int = 0,
        page_token: str = "",
    ) -> ApiData:
        return await self._call(
            layout_pb2.ListMyLayoutTemplateSubscriptionsRequest(
                limit=limit,
                page_token=page_token,
            ),
            LayoutServiceClient.list_my_layout_template_subscriptions,
        )

    async def _call(self, request, call):
        return await unary_auth_decoded(
            self._transport,
            LayoutServiceClient,
            call,
            request,
            api_data_from_proto,
        )
