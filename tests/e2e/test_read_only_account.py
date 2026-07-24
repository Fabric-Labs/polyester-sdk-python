import pytest


@pytest.mark.integration
@pytest.mark.smoke
async def test_account_read_snapshot(live_client, smoke_symbol):
    spot = await live_client.market_data.get_spot_config()
    assert spot.raw
    symbols = {pair.get("symbol") for pair in spot.raw.get("pairs") or []}
    assert smoke_symbol in symbols

    balances = await live_client.balances.list()
    assert isinstance(balances.balances, list)
    for row in balances.balances:
        assert row.asset_id > 0
        assert int(row.trading) >= 0
        assert int(row.funding) >= 0

    orders = await live_client.orders.list_open(limit=5)
    assert isinstance(orders.orders, list)

    triggers = await live_client.triggers.list(limit=5)
    assert isinstance(triggers.triggers, list)

    transfers = await live_client.transfers.list(limit=5)
    assert isinstance(transfers.transfers, list)
    for transfer in transfers.transfers:
        assert transfer.asset_id >= 0
        assert int(transfer.amount) >= 0

    subaccounts = await live_client.sub_accounts.list()
    assert isinstance(subaccounts.subaccounts, list)
