import pytest

from polyester.models import ApiData, MarketOverviewList
from tests.integration.support import assert_api_data_shape, call_optional, call_required


@pytest.mark.integration
@pytest.mark.smoke
async def test_market_overview_list_has_markets(live_client) -> None:
    result = await call_required(
        live_client.market_overview.list(limit=10),
        label="market_overview.list",
    )
    assert isinstance(result, MarketOverviewList)
    assert isinstance(result.markets, list)
    for market in result.markets:
        assert market.symbol


@pytest.mark.integration
@pytest.mark.optional
async def test_heatmap_get(live_client, smoke_symbol) -> None:
    result = await call_optional(
        live_client.heatmap.get(symbol=smoke_symbol),
        label="heatmap.get",
    )
    assert isinstance(result, ApiData)
    assert result.raw


@pytest.mark.integration
@pytest.mark.optional
async def test_zipper_get_deposit_withdraw_config(live_client) -> None:
    result = await call_optional(
        live_client.zipper.get_deposit_withdraw_config(),
        label="zipper.get_deposit_withdraw_config",
    )
    assert isinstance(result, ApiData)
    assert_api_data_shape(result.raw, "assets", "chains")


@pytest.mark.integration
@pytest.mark.optional
async def test_chain_analytics_unified_balances_series_shape(live_client) -> None:
    zipper = await call_optional(
        live_client.zipper.get_deposit_withdraw_config(),
        label="zipper.get_deposit_withdraw_config",
    )
    assets = zipper.raw.get("assets") or []
    if not assets:
        pytest.skip("zipper config missing assets")
    asset_id = int(assets[0].get("ledgerId") or assets[0].get("ledger_id") or 0)
    if asset_id <= 0:
        pytest.skip("cannot resolve asset id for chain analytics")
    result = await call_optional(
        live_client.chain_analytics.get_unified_asset_balances(
            asset_id=asset_id,
            range="7d",
        ),
        label="chain_analytics.get_unified_asset_balances",
    )
    assert isinstance(result, ApiData)
    assert_api_data_shape(result.raw, "range", "points", "startTsSec", "endTsSec")
    assert int(result.raw["points"]) >= 0
