from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.auth.v1 import social_verification_pb2 as sv_pb2
from polyester.gen.auth.v1.auth_pb2 import MeRequest
from polyester.gen.chain.analytics.v1 import analytics_read_pb2
from polyester.gen.collab.v1 import whiteboard_pb2 as wb_pb2
from polyester.gen.layout.v1 import layout_pb2
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import ApiData
from polyester.services.auth import AsyncAuthService
from polyester.services.chain_analytics import AsyncChainAnalyticsService
from polyester.services.layout import AsyncLayoutService
from polyester.services.orders import AsyncOrdersService
from polyester.services.social_verification import AsyncSocialVerificationService
from polyester.services.triggers import AsyncTriggersService
from polyester.services.whiteboard import AsyncWhiteboardService
from tests.unit.support import CaptureUnary


@pytest.mark.asyncio
async def test_auth_me_sends_empty_me_request() -> None:
    capture = CaptureUnary(auth_pb2.MeResponse(account_id=42, username="alice"))
    with patch("polyester.services.auth.unary_auth_decoded", capture):
        service = AsyncAuthService(transport=MagicMock())
        result = await service.me()
    assert isinstance(capture.request, MeRequest)
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_chain_analytics_rejects_non_positive_asset_id() -> None:
    service = AsyncChainAnalyticsService(transport=MagicMock())
    with pytest.raises(PolyesterValidationError, match="asset_id must be positive"):
        await service.get_unified_asset_balances(asset_id=0, range="7d")


@pytest.mark.asyncio
async def test_chain_analytics_public_unary_sets_range() -> None:
    capture = CaptureUnary(
        analytics_read_pb2.GetUnifiedAssetBalancesResponse(
            asset_id=7,
            range=analytics_read_pb2.DAY_7,
            points=0,
        )
    )

    async def public_decoded(transport, client_cls, call, request, decoder):
        capture.request = request
        return decoder(capture.response)

    with patch("polyester.services.chain_analytics.unary_public_decoded", public_decoded):
        service = AsyncChainAnalyticsService(transport=MagicMock())
        result = await service.get_unified_asset_balances(asset_id=7, range="7d")
    assert capture.request.asset_id == 7
    assert capture.request.range == analytics_read_pb2.DAY_7
    assert isinstance(result, ApiData)


@pytest.mark.asyncio
async def test_social_verification_start_sets_provider_and_method() -> None:
    capture = CaptureUnary(sv_pb2.StartSocialVerificationResponse(challenge_code="abc"))
    with patch("polyester.services.social_verification.unary_auth_decoded", capture):
        service = AsyncSocialVerificationService(transport=MagicMock())
        result = await service.start(provider="twitter", method="profile", handle="@alice")
    assert capture.request.provider == sv_pb2.TWITTER
    assert capture.request.method == sv_pb2.METHOD_PROFILE
    assert capture.request.handle == "@alice"
    assert result.raw["challengeCode"] == "abc"


@pytest.mark.asyncio
async def test_whiteboard_create_sets_title_and_audience() -> None:
    capture = CaptureUnary(wb_pb2.CreateBoardResponse())
    with patch("polyester.services.whiteboard.unary_auth_decoded", capture):
        service = AsyncWhiteboardService(transport=MagicMock())
        await service.create(title="standup", audience="private", default_role="viewer")
    assert isinstance(capture.request, wb_pb2.CreateBoardRequest)
    assert capture.request.title == "standup"
    assert capture.request.audience == wb_pb2.PRIVATE
    assert capture.request.default_role == wb_pb2.VIEWER


@pytest.mark.asyncio
async def test_layout_get_layouts_passes_pagination() -> None:
    capture = CaptureUnary(layout_pb2.GetLayoutsResponse())
    with patch("polyester.services.layout.unary_auth_decoded", capture):
        service = AsyncLayoutService(transport=MagicMock())
        await service.get_layouts(limit=25, page_token="tok")
    assert capture.request.limit == 25
    assert capture.request.page_token == "tok"


@pytest.mark.asyncio
async def test_triggers_list_and_list_events_pass_page_token() -> None:
    list_capture = CaptureUnary(triggers_pb2.ListTriggersResponse(next_page_token="trig-page-2"))
    with patch("polyester.services.triggers.unary_auth_decoded", list_capture):
        service = AsyncTriggersService(MagicMock(), MagicMock(), None)
        listed = await service.list(limit=10, page_token="trig-page-1")
    assert list_capture.request.page_token == "trig-page-1"
    assert listed.next_page_token == "trig-page-2"

    events_capture = CaptureUnary(
        triggers_pb2.ListTriggerEventsResponse(next_page_token="evt-page-2")
    )
    with patch("polyester.services.triggers.unary_auth_decoded", events_capture):
        service = AsyncTriggersService(MagicMock(), MagicMock(), None)
        events = await service.list_events(
            trigger_id=7,
            limit=20,
            event_type="fired",
            page_token="evt-page-1",
        )
    assert events_capture.request.trigger_id == 7
    assert events_capture.request.event_type == triggers_pb2.EVENT_FIRED
    assert events_capture.request.page_token == "evt-page-1"
    assert events.next_page_token == "evt-page-2"


@pytest.mark.asyncio
async def test_orders_list_open_and_history_pass_trigger_id() -> None:
    open_capture = CaptureUnary(orders_read_pb2.GetOpenOrdersResponse())
    with patch("polyester.services.orders.unary_auth_decoded", open_capture):
        service = AsyncOrdersService(MagicMock(), MagicMock(), None)
        await service.list_open(trigger_id=42, limit=5)
    assert open_capture.request.trigger_id == 42
    assert open_capture.request.limit == 5

    history_capture = CaptureUnary(orders_read_pb2.GetOrderHistoryResponse())
    with patch("polyester.services.orders.unary_auth_decoded", history_capture):
        service = AsyncOrdersService(MagicMock(), MagicMock(), None)
        await service.list_history(trigger_id=42, limit=5)
    assert history_capture.request.trigger_id == 42
    assert history_capture.request.limit == 5
