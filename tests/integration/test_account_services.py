import pytest

from polyester.models import ApiKeysList, DepositAddressesList
from tests.integration.support import call_optional, call_required


@pytest.mark.integration
async def test_api_keys_list_returns_key_summaries(live_client) -> None:
    result = await call_required(live_client.api_keys.list(), label="api_keys.list")
    assert isinstance(result, ApiKeysList)
    for key in result.api_keys:
        assert key.key_id
        assert key.status


@pytest.mark.integration
async def test_api_keys_get_round_trips_listed_key(live_client) -> None:
    listed = await call_required(live_client.api_keys.list(), label="api_keys.list")
    if not listed.api_keys:
        pytest.skip("no API keys on devnet account")
    key_id = listed.api_keys[0].key_id
    fetched = await call_required(
        live_client.api_keys.get(key_id=key_id),
        label="api_keys.get",
    )
    assert fetched is not None
    assert fetched.key_id == key_id
    assert fetched.label == listed.api_keys[0].label


@pytest.mark.integration
@pytest.mark.optional
async def test_deposit_list_addresses(live_client) -> None:
    result = await call_optional(
        live_client.deposit.list_addresses(chain_id=1),
        label="deposit.list_addresses",
    )
    assert isinstance(result, DepositAddressesList)
    for row in result.addresses:
        assert row.chain_id > 0
        assert row.deposit_address
        assert len(row.deposit_address.strip()) >= 8
