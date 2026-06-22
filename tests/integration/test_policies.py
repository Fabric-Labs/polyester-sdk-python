import pytest

from polyester.models import ApiPoliciesList, SubaccountPoliciesList


@pytest.mark.integration
async def test_policies_list_subaccount_policies(live_client):
    result = await live_client.policies.list_subaccount_policies()
    assert isinstance(result, SubaccountPoliciesList)
    assert isinstance(result.policies, list)


@pytest.mark.integration
async def test_policies_list_api_policies(live_client):
    result = await live_client.policies.list_api_policies()
    assert isinstance(result, ApiPoliciesList)
    assert isinstance(result.policies, list)


@pytest.mark.integration
async def test_policies_get_subaccount_policy_when_present(live_client):
    listed = await live_client.policies.list_subaccount_policies()
    if not listed.policies:
        pytest.skip("no subaccount policies on devnet")
    policy = await live_client.policies.get_subaccount_policy(
        policy_id=listed.policies[0].id
    )
    assert policy is not None
    assert policy.id == listed.policies[0].id


@pytest.mark.integration
async def test_policies_get_api_policy_when_present(live_client):
    listed = await live_client.policies.list_api_policies()
    if not listed.policies:
        pytest.skip("no api policies on devnet")
    policy = await live_client.policies.get_api_policy(policy_id=listed.policies[0].id)
    assert policy is not None
    assert policy.id == listed.policies[0].id
