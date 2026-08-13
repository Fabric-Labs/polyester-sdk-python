import pytest

from polyester.models.fees import SpotFeeRatesList
from polyester.models.trading_rate_limits import RateLimitConfig, TradingRateLimits
from polyester.models.vip import VIPStatus, VIPTiersList
from tests.integration.support import call_optional


@pytest.mark.integration
@pytest.mark.optional
async def test_list_vip_tiers(live_client):
    result = await call_optional(
        live_client.vip.list_vip_tiers(),
        label="vip.list_vip_tiers",
    )
    assert isinstance(result, VIPTiersList)
    assert result.policy_version >= 0
    assert len(result.tiers) <= 11


@pytest.mark.integration
@pytest.mark.optional
async def test_get_vip_status(live_client):
    result = await call_optional(
        live_client.vip.get_vip_status(),
        label="vip.get_vip_status",
    )
    assert isinstance(result, VIPStatus)
    assert 0 <= result.tier <= 10


@pytest.mark.integration
@pytest.mark.optional
async def test_get_spot_fee_rates(live_client):
    result = await call_optional(
        live_client.fees.get_spot_fee_rates(),
        label="fees.get_spot_fee_rates",
    )
    assert isinstance(result, SpotFeeRatesList)


@pytest.mark.integration
@pytest.mark.optional
async def test_get_rate_limit_config(live_client):
    result = await call_optional(
        live_client.rate_limits.get_rate_limit_config(),
        label="rate_limits.get_rate_limit_config",
    )
    assert isinstance(result, RateLimitConfig)


@pytest.mark.integration
@pytest.mark.optional
async def test_get_trading_rate_limits(live_client):
    result = await call_optional(
        live_client.rate_limits.get_trading_rate_limits(),
        label="rate_limits.get_trading_rate_limits",
    )
    assert isinstance(result, TradingRateLimits)
