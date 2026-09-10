"""Live coverage for currency-conversion config and rates."""

from __future__ import annotations

import pytest

from polyester.models import CurrencyConversionConfig, CurrencyConversionRates
from tests.integration.support import call_optional

_USD_E8 = 100_000_000


def _assert_metadata(entries, *, label: str) -> None:
    for item in entries:
        assert item.code, f"{label} missing code"
        assert item.fraction_digits >= 0, f"{label} {item.code} fraction_digits"


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_currency_conversion_config(live_client) -> None:
    result = await call_optional(
        live_client.market_overview.get_currency_conversion_config(),
        label="market_overview.get_currency_conversion_config",
    )
    assert isinstance(result, CurrencyConversionConfig)
    assert isinstance(result.fiat, list)
    assert isinstance(result.stablecoins, list)
    _assert_metadata(result.fiat, label="fiat")
    _assert_metadata(result.stablecoins, label="stablecoin")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_currency_conversion_rates(live_client) -> None:
    result = await call_optional(
        live_client.market_overview.get_currency_conversion_rates(),
        label="market_overview.get_currency_conversion_rates",
    )
    assert isinstance(result, CurrencyConversionRates)
    assert result.snapshot_ts_sec >= 0
    if result.fiat is not None:
        assert result.fiat.source_ts_sec >= 0
        assert isinstance(result.fiat.stale, bool)
        usd = next((rate for rate in result.fiat.rates if rate.code == "USD"), None)
        if usd is not None:
            assert usd.units_per_usd_e8 == _USD_E8
        for rate in result.fiat.rates:
            assert rate.code
            assert rate.units_per_usd_e8 != 0
    for rate in result.stablecoins:
        assert rate.code
        assert rate.usd_per_unit_e8 != 0
        assert rate.source_ts_sec >= 0
        assert isinstance(rate.stale, bool)
