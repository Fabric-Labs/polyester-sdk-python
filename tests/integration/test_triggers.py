import pytest

from polyester.models import TriggersList


@pytest.mark.integration
@pytest.mark.smoke
async def test_triggers_list(live_client):
    result = await live_client.triggers.list(limit=10)
    assert isinstance(result, TriggersList)
