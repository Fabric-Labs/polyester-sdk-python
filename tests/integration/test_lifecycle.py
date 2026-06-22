import pytest

from polyester.errors import PolyesterServerError


@pytest.mark.integration
@pytest.mark.optional
async def test_lifecycle_list_flows(live_client):
    try:
        result = await live_client.lifecycle.list_flows(limit=5)
    except PolyesterServerError:
        pytest.skip("lifecycle flows response incompatible with current proto on devnet")
    assert isinstance(result.flows, list)
