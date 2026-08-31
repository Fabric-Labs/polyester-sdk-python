import pytest

from polyester.models import TransfersList


@pytest.mark.integration
async def test_transfers_list(live_client):
    result = await live_client.transfers.list(limit=5)
    assert isinstance(result, TransfersList)
    for transfer in result.transfers:
        for side in (transfer.source, transfer.destination):
            if side is None:
                continue
            if side.kind == "external_address" and side.chain_id == 0:
                raise AssertionError(
                    f"external zipper chain_id must not be the zero sentinel: {side}"
                )
