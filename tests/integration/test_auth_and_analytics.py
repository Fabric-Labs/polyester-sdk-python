import pytest

from polyester.models.auth import MeResult, UsernameHistoryList, UserProfile
from tests.integration.support import call_optional, call_required


@pytest.mark.integration
async def test_auth_me_returns_identity_fields(live_client) -> None:
    result = await call_required(live_client.auth.me(), label="auth.me")
    assert isinstance(result, MeResult)
    assert result.account_id or result.api_key_id, "me() should identify the caller"


@pytest.mark.integration
@pytest.mark.optional
@pytest.mark.jwt_session
async def test_profile_get_matches_me_username_when_present(live_client) -> None:
    me = await call_required(live_client.auth.me(), label="auth.me")
    profile = await call_optional(live_client.auth.profile.get(), label="profile.get")
    assert isinstance(profile, UserProfile)
    if me.username:
        assert profile.username == me.username


@pytest.mark.integration
@pytest.mark.optional
@pytest.mark.jwt_session
async def test_profile_username_history_is_list(live_client) -> None:
    result = await call_optional(
        live_client.auth.profile.get_username_history(),
        label="profile.get_username_history",
    )
    assert isinstance(result, UsernameHistoryList)
    assert isinstance(result.history, list)
    for entry in result.history:
        assert entry.username
