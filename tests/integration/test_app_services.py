import pytest

from polyester.models import ApiData
from tests.integration.support import call_optional


@pytest.mark.integration
@pytest.mark.optional
@pytest.mark.jwt_session
async def test_social_verification_get_twitter(live_client) -> None:
    result = await call_optional(
        live_client.social_verification.get(provider="twitter"),
        label="social_verification.get",
    )
    assert isinstance(result, ApiData)
    assert "verification" in result.raw
