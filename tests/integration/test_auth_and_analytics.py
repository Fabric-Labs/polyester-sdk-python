import pytest

from polyester.models.auth import MeResult
from tests.integration.support import call_required


@pytest.mark.integration
async def test_auth_me_returns_identity_fields(live_client) -> None:
    result = await call_required(live_client.auth.me(), label="auth.me")
    assert isinstance(result, MeResult)
    assert result.account_id or result.api_key_id, "me() should identify the caller"
