import pytest

from tests.integration.support import call_optional, call_required


@pytest.mark.integration
async def test_account_identity_snapshot(live_client, smoke_symbol) -> None:
    """API-key identity snapshot across auth, balances, api keys, and spot config."""
    me = await call_required(live_client.auth.me(), label="auth.me")
    balances = await call_required(live_client.balances.list(), label="balances.list")
    keys = await call_required(live_client.api_keys.list(), label="api_keys.list")

    assert me.account_id or me.api_key_id, "auth.me should identify the API-key caller"
    for key in keys.api_keys:
        assert key.key_id
        assert key.status

    assert isinstance(balances.balances, list)
    spot = await live_client.market_data.get_spot_config()
    symbols = {pair.get("symbol") for pair in spot.raw.get("pairs") or []}
    assert smoke_symbol in symbols


@pytest.mark.integration
@pytest.mark.optional
@pytest.mark.jwt_session
async def test_profile_identity_snapshot(live_client) -> None:
    """Session-profile compatibility check; skipped under API-key-only devnet auth."""
    me = await call_required(live_client.auth.me(), label="auth.me")
    profile = await call_optional(live_client.auth.profile.get(), label="profile.get")
    if me.username:
        assert profile.username == me.username
