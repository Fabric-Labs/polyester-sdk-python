from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import auth_pb2, profile_pb2
from polyester.gen.auth.v1 import social_verification_pb2 as sv_pb2
from polyester.gen.auth.v1.auth_pb2 import MeRequest
from polyester.gen.auth.v1.profile_pb2 import GetProfileRequest, UserProfilePatch
from polyester.gen.auth.v1.subaccounts_pb2 import UpdateSubaccountRequest
from polyester.gen.chain.analytics.v1 import analytics_read_pb2
from polyester.gen.collab.v1 import whiteboard_pb2 as wb_pb2
from polyester.gen.layout.v1 import layout_pb2
from polyester.models import ApiData
from polyester.services.auth import AsyncAuthService
from polyester.services.chain_analytics import AsyncChainAnalyticsService
from polyester.services.layout import AsyncLayoutService
from polyester.services.profile import AsyncProfileService
from polyester.services.social_verification import AsyncSocialVerificationService
from polyester.services.sub_accounts import AsyncSubAccountsService
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
async def test_profile_get_sends_get_profile_request() -> None:
    capture = CaptureUnary(profile_pb2.UserProfile(username="alice"))
    with patch("polyester.services.profile.unary_auth_decoded", capture):
        service = AsyncProfileService(transport=MagicMock())
        profile = await service.get()
    assert isinstance(capture.request, GetProfileRequest)
    assert profile.username == "alice"


@pytest.mark.asyncio
async def test_profile_update_builds_patch_fields() -> None:
    capture = CaptureUnary(profile_pb2.UserProfile(username="alice", bio="hi"))
    with patch("polyester.services.profile.unary_auth_decoded", capture):
        service = AsyncProfileService(transport=MagicMock())
        profile = await service.update(bio="hi")
    assert isinstance(capture.request, UserProfilePatch)
    assert capture.request.bio == "hi"
    assert profile.bio == "hi"


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
async def test_sub_accounts_delete_issues_soft_delete_update() -> None:
    sub_id = format_id(99)
    capture = CaptureUnary(None)

    async def fake_unary(transport, client_cls, call, request, decoder):
        capture.request = request
        return decoder(None)

    with patch("polyester.services.sub_accounts.unary_auth_decoded", fake_unary):
        service = AsyncSubAccountsService(transport=MagicMock(), default_sub_account_id=None)
        await service.delete(sub_account_id=sub_id)
    assert isinstance(capture.request, UpdateSubaccountRequest)
    assert capture.request.status == "deleted"
    assert capture.request.subaccount_id == 99
