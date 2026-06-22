import pytest

from tests.integration.support import call_optional, call_required


@pytest.mark.integration
@pytest.mark.optional
async def test_account_identity_snapshot(live_client, smoke_symbol) -> None:
    """Cross-service read snapshot: identity + balances + api keys stay consistent."""
    me = await call_required(live_client.auth.me(), label="auth.me")
    profile = await call_optional(live_client.auth.profile.get(), label="profile.get")
    balances = await call_required(live_client.balances.list(), label="balances.list")
    keys = await call_required(live_client.api_keys.list(), label="api_keys.list")

    if profile is not None and me.username:
        assert profile.username == me.username

    if me.api_key_id and keys.api_keys:
        assert any(key.key_id == me.api_key_id for key in keys.api_keys)

    assert isinstance(balances.balances, list)
    spot = await live_client.market_data.get_spot_config()
    symbols = {pair.get("symbol") for pair in spot.raw.get("pairs") or []}
    assert smoke_symbol in symbols
