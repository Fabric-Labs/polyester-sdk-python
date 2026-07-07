import pytest

from polyester.models import BalancesList, LedgerHealth
from tests.integration.support import call_optional


@pytest.mark.integration
async def test_balances_list(live_client):
    result = await live_client.balances.list()
    assert isinstance(result, BalancesList)
    for row in result.balances:
        assert row.asset_id > 0
        assert int(row.trading) >= 0
        assert int(row.funding) >= 0
        assert int(row.reserved) >= 0
        assert int(row.available) >= 0


@pytest.mark.integration
@pytest.mark.optional
async def test_balances_get_health(live_client):
    result = await call_optional(
        live_client.balances.get_health(),
        label="balances.get_health",
    )
    assert isinstance(result, LedgerHealth)
    assert result.ok is True


@pytest.mark.integration
async def test_balances_get_balance_history(live_client):
    result = await live_client.balances.get_balance_history(range="7d")
    assert result.range == "7d"
    assert result.start_ts_sec <= result.end_ts_sec
    assert result.points >= 0
    for series in result.series:
        assert series.asset_id >= 0
        assert series.account_code >= 0
        assert len(series.balance_q) <= result.points


@pytest.mark.integration
@pytest.mark.optional
async def test_balances_list_holds(live_client, capabilities):
    if not capabilities["list_holds"]:
        pytest.skip("list_holds unavailable on devnet")
    result = await live_client.balances.list_holds(limit=5)
    assert isinstance(result.holds, list)
