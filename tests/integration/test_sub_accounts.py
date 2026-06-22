import pytest

from polyester.models import (
    SubAccountActivityList,
    SubAccountInvitesList,
    SubAccountsList,
)


@pytest.mark.integration
async def test_sub_accounts_list(live_client):
    result = await live_client.sub_accounts.list()
    assert isinstance(result, SubAccountsList)
    assert isinstance(result.subaccounts, list)


@pytest.mark.integration
async def test_sub_accounts_list_invites(live_client):
    result = await live_client.sub_accounts.list_invites()
    assert isinstance(result, SubAccountInvitesList)
    assert isinstance(result.invites, list)


@pytest.mark.integration
async def test_sub_accounts_get(live_client):
    listed = await live_client.sub_accounts.list()
    if not listed.subaccounts:
        pytest.skip("no subaccounts on devnet")
    result = await live_client.sub_accounts.get(
        sub_account_id=listed.subaccounts[0].id,
        include_members=True,
    )
    assert result.subaccount is not None
    assert result.subaccount.id == listed.subaccounts[0].id


@pytest.mark.integration
async def test_sub_accounts_list_members(live_client):
    listed = await live_client.sub_accounts.list()
    if not listed.subaccounts:
        pytest.skip("no subaccounts on devnet")
    result = await live_client.sub_accounts.list_members(
        sub_account_id=listed.subaccounts[0].id
    )
    assert isinstance(result.members, list)


@pytest.mark.integration
async def test_sub_accounts_list_activity(live_client):
    listed = await live_client.sub_accounts.list()
    if not listed.subaccounts:
        pytest.skip("no subaccounts on devnet")
    result = await live_client.sub_accounts.list_activity(
        sub_account_id=listed.subaccounts[0].id,
        limit=5,
    )
    assert isinstance(result, SubAccountActivityList)
    assert isinstance(result.events, list)
