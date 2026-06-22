import pytest

from polyester.models import TransfersList


@pytest.mark.integration
async def test_transfers_list(live_client):
    result = await live_client.transfers.list(limit=5)
    assert isinstance(result, TransfersList)
