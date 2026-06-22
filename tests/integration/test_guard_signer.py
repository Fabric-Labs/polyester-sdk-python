import pytest

from polyester.errors import PolyesterApiError, PolyesterServerError
from polyester.models.guard_signer import GuardSignerStatus


@pytest.mark.integration
@pytest.mark.optional
async def test_guard_signer_get_status(live_client):
    try:
        result = await live_client.guard_signer.get_status()
    except PolyesterApiError as exc:
        if "wallet not found" in str(exc).lower():
            pytest.skip("guard signer wallet not configured on this account")
        raise
    assert result is None or isinstance(result, GuardSignerStatus)
