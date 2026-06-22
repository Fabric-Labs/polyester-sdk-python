from __future__ import annotations

from typing import Any

from polyester.codecs.decode.common import api_data_from_proto
from polyester.codecs.proto_build import message_from_mapping, repeated_messages_from_mappings
from polyester.codecs.scalars import id_to_int
from polyester.gen.polychart.v1 import polychart_pb2 as pc_pb2
from polyester.gen.polychart.v1.polychart_connect import PolychartServiceClient
from polyester.models import ApiData
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded


class AsyncPolychartService(BaseService):
    async def get_market_layers(self, *, engine_symbol_id: int) -> ApiData:
        return await self._call(
            pc_pb2.GetMarketLayersRequest(engine_symbol_id=engine_symbol_id),
            PolychartServiceClient.get_market_layers,
        )

    async def list_inbox_market_layers(
        self,
        *,
        engine_symbol_id: int,
        limit: int = 0,
        page_token: str = "",
    ) -> ApiData:
        return await self._call(
            pc_pb2.ListInboxMarketLayersRequest(
                engine_symbol_id=engine_symbol_id,
                limit=limit,
                page_token=page_token,
            ),
            PolychartServiceClient.list_inbox_market_layers,
        )

    async def get_layer_snapshot(self, *, layer: dict[str, Any]) -> ApiData:
        return await self._call(
            pc_pb2.GetLayerSnapshotRequest(
                layer=message_from_mapping(pc_pb2.LayerRef, layer),
            ),
            PolychartServiceClient.get_layer_snapshot,
        )

    async def get_layer_subscribe_tokens(
        self,
        *,
        layers: list[dict[str, Any]],
    ) -> ApiData:
        return await self._call(
            pc_pb2.GetLayerSubscribeTokensRequest(
                layers=repeated_messages_from_mappings(pc_pb2.LayerRef, layers),
            ),
            PolychartServiceClient.get_layer_subscribe_tokens,
        )

    async def resolve_layer_share_token(self, *, token: str) -> ApiData:
        return await self._call(
            pc_pb2.ResolveLayerShareTokenRequest(token=token),
            PolychartServiceClient.resolve_layer_share_token,
        )

    async def create_layer_share_link(
        self,
        *,
        layer: dict[str, Any],
        perms: int = 0,
        expires_at_ms: int = 0,
    ) -> ApiData:
        return await self._call(
            pc_pb2.CreateLayerShareLinkRequest(
                layer=message_from_mapping(pc_pb2.LayerRef, layer),
                perms=perms,
                expires_at_ms=expires_at_ms,
            ),
            PolychartServiceClient.create_layer_share_link,
        )

    async def revoke_layer_share_link(self, *, token: str) -> ApiData:
        return await self._call(
            pc_pb2.RevokeLayerShareLinkRequest(token=token),
            PolychartServiceClient.revoke_layer_share_link,
        )

    async def list_owner_published_layers(
        self,
        *,
        owner_id: str | int,
        engine_symbol_id: int = 0,
        limit: int = 0,
        page_token: str = "",
    ) -> ApiData:
        return await self._call(
            pc_pb2.ListOwnerPublishedLayersRequest(
                owner_id=id_to_int(owner_id, "owner_id"),
                engine_symbol_id=engine_symbol_id,
                limit=limit,
                page_token=page_token,
            ),
            PolychartServiceClient.list_owner_published_layers,
        )

    async def publish_layer(
        self,
        *,
        layer: dict[str, Any],
        title: str = "",
        description: str = "",
        tags: list[str] | None = None,
    ) -> ApiData:
        request = pc_pb2.PublishLayerRequest(
            layer=message_from_mapping(pc_pb2.LayerRef, layer),
            title=title,
            description=description,
        )
        if tags:
            request.tags.extend(tags)
        return await self._call(request, PolychartServiceClient.publish_layer)

    async def unpublish_layer(self, *, layer: dict[str, Any]) -> ApiData:
        return await self._call(
            pc_pb2.UnpublishLayerRequest(layer=message_from_mapping(pc_pb2.LayerRef, layer)),
            PolychartServiceClient.unpublish_layer,
        )

    async def upsert_layer(
        self,
        *,
        layer: dict[str, Any],
        expected_revision: int = 0,
    ) -> ApiData:
        return await self._call(
            pc_pb2.UpsertLayerRequest(
                layer=message_from_mapping(pc_pb2.Layer, layer),
                expected_revision=expected_revision,
            ),
            PolychartServiceClient.upsert_layer,
        )

    async def delete_layer(
        self,
        *,
        layer: dict[str, Any],
        expected_revision: int = 0,
    ) -> ApiData:
        return await self._call(
            pc_pb2.DeleteLayerRequest(
                layer=message_from_mapping(pc_pb2.LayerRef, layer),
                expected_revision=expected_revision,
            ),
            PolychartServiceClient.delete_layer,
        )

    async def upsert_drawing(
        self,
        *,
        drawing: dict[str, Any],
        expected_layer_revision: int = 0,
    ) -> ApiData:
        return await self._call(
            pc_pb2.UpsertDrawingRequest(
                drawing=message_from_mapping(pc_pb2.Drawing, drawing),
                expected_layer_revision=expected_layer_revision,
            ),
            PolychartServiceClient.upsert_drawing,
        )

    async def delete_drawing(
        self,
        *,
        drawing: dict[str, Any],
        layer: dict[str, Any],
        expected_layer_revision: int = 0,
    ) -> ApiData:
        return await self._call(
            pc_pb2.DeleteDrawingRequest(
                drawing=message_from_mapping(pc_pb2.DrawingRef, drawing),
                layer=message_from_mapping(pc_pb2.LayerRef, layer),
                expected_layer_revision=expected_layer_revision,
            ),
            PolychartServiceClient.delete_drawing,
        )

    async def set_layer_subscriptions(
        self,
        *,
        engine_symbol_id: int,
        subscriptions: list[dict[str, Any]],
    ) -> ApiData:
        return await self._call(
            pc_pb2.SetLayerSubscriptionsRequest(
                engine_symbol_id=engine_symbol_id,
                subscriptions=repeated_messages_from_mappings(
                    pc_pb2.LayerSubscription, subscriptions
                ),
            ),
            PolychartServiceClient.set_layer_subscriptions,
        )

    async def _call(self, request, call):
        return await unary_auth_decoded(
            self._transport,
            PolychartServiceClient,
            call,
            request,
            api_data_from_proto,
        )
