from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.scalars import format_id
from polyester.gen.layout.v1 import layout_pb2
from polyester.gen.polychart.v1 import polychart_pb2 as pc_pb2
from polyester.services.layout import AsyncLayoutService
from polyester.services.polychart import AsyncPolychartService
from tests.unit.support import CaptureUnary

_LAYER = {"ownerId": 1, "layerId": 42}
_DRAWING = {"drawingId": 9}
_LAYOUT = {"layoutId": 7, "name": "main"}


@pytest.mark.asyncio
async def test_polychart_get_market_layers_sets_symbol_id() -> None:
    capture = CaptureUnary(pc_pb2.GetMarketLayersResponse())
    with patch("polyester.services.polychart.unary_auth_decoded", capture):
        service = AsyncPolychartService(transport=MagicMock())
        await service.get_market_layers(engine_symbol_id=123)
    assert capture.request.engine_symbol_id == 123


@pytest.mark.asyncio
async def test_polychart_list_inbox_passes_pagination() -> None:
    capture = CaptureUnary(pc_pb2.ListInboxMarketLayersResponse())
    with patch("polyester.services.polychart.unary_auth_decoded", capture):
        service = AsyncPolychartService(transport=MagicMock())
        await service.list_inbox_market_layers(engine_symbol_id=1, limit=50, page_token="tok")
    assert capture.request.limit == 50
    assert capture.request.page_token == "tok"


@pytest.mark.asyncio
async def test_polychart_publish_layer_extends_tags() -> None:
    capture = CaptureUnary(pc_pb2.PublishLayerResponse())
    with patch("polyester.services.polychart.unary_auth_decoded", capture):
        service = AsyncPolychartService(transport=MagicMock())
        await service.publish_layer(
            layer=_LAYER,
            title="TA",
            description="notes",
            tags=["eth", "btc"],
        )
    assert capture.request.title == "TA"
    assert list(capture.request.tags) == ["eth", "btc"]
    assert capture.request.layer.layer_id == 42


@pytest.mark.asyncio
async def test_polychart_upsert_layer_sets_expected_revision() -> None:
    capture = CaptureUnary(pc_pb2.UpsertLayerResponse())
    with patch("polyester.services.polychart.unary_auth_decoded", capture):
        service = AsyncPolychartService(transport=MagicMock())
        await service.upsert_layer(
            layer={"layerId": 5, "ownerId": 1, "name": "layer"},
            expected_revision=3,
        )
    assert capture.request.expected_revision == 3
    assert capture.request.layer.layer_id == 5


@pytest.mark.asyncio
async def test_polychart_delete_drawing_wraps_refs() -> None:
    capture = CaptureUnary(pc_pb2.DeleteDrawingResponse())
    with patch("polyester.services.polychart.unary_auth_decoded", capture):
        service = AsyncPolychartService(transport=MagicMock())
        await service.delete_drawing(
            drawing=_DRAWING,
            layer=_LAYER,
            expected_layer_revision=2,
        )
    assert capture.request.expected_layer_revision == 2
    assert capture.request.layer.layer_id == 42
    assert capture.request.drawing.drawing_id == 9


@pytest.mark.asyncio
async def test_polychart_set_layer_subscriptions_builds_entries() -> None:
    capture = CaptureUnary(pc_pb2.SetLayerSubscriptionsResponse())
    with patch("polyester.services.polychart.unary_auth_decoded", capture):
        service = AsyncPolychartService(transport=MagicMock())
        await service.set_layer_subscriptions(
            engine_symbol_id=99,
            subscriptions=[{"layer": {"ownerId": 1, "layerId": 2}}],
        )
    assert capture.request.engine_symbol_id == 99
    assert len(capture.request.subscriptions) == 1
    assert capture.request.subscriptions[0].layer.layer_id == 2


@pytest.mark.asyncio
async def test_layout_get_layout_converts_id() -> None:
    capture = CaptureUnary(layout_pb2.GetLayoutResponse())
    with patch("polyester.services.layout.unary_auth_decoded", capture):
        service = AsyncLayoutService(transport=MagicMock())
        await service.get_layout(layout_id=format_id(15))
    assert capture.request.layout_id == 15


@pytest.mark.asyncio
async def test_layout_upsert_layout_wraps_message() -> None:
    capture = CaptureUnary(layout_pb2.UpsertLayoutResponse())
    with patch("polyester.services.layout.unary_auth_decoded", capture):
        service = AsyncLayoutService(transport=MagicMock())
        await service.upsert_layout(layout=_LAYOUT)
    assert capture.request.layout.layout_id == 7
    assert capture.request.layout.name == "main"


@pytest.mark.asyncio
async def test_layout_publish_layout_sets_listing_fields() -> None:
    capture = CaptureUnary(layout_pb2.PublishLayoutResponse())
    with patch("polyester.services.layout.unary_auth_decoded", capture):
        service = AsyncLayoutService(transport=MagicMock())
        await service.publish_layout(
            layout_id=8,
            title="grid",
            is_listed=True,
            changelog="v2",
            tags=["spot"],
        )
    assert capture.request.layout_id == 8
    assert capture.request.is_listed is True
    assert capture.request.changelog == "v2"
    assert list(capture.request.tags) == ["spot"]


@pytest.mark.asyncio
async def test_layout_set_template_subscription_pins_version() -> None:
    capture = CaptureUnary(layout_pb2.SetLayoutTemplateSubscriptionResponse())
    with patch("polyester.services.layout.unary_auth_decoded", capture):
        service = AsyncLayoutService(transport=MagicMock())
        await service.set_layout_template_subscription(
            owner_id=1,
            template_id=2,
            track_latest=False,
            pinned_version=4,
        )
    assert capture.request.template_id == 2
    assert capture.request.pinned_version == 4
    assert capture.request.track_latest is False
