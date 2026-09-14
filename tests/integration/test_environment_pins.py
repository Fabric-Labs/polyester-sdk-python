"""Public live check: SDK pins match the Zipper catalog for that API host."""

from __future__ import annotations

import os

import pytest

from polyester import (
    POLYESTER_DEVNET_ENVIRONMENT,
    POLYESTER_TESTNET_ENVIRONMENT,
    AsyncPolyester,
    PolyesterEnvironment,
    PolyesterTransportError,
)


def _contract_map(config) -> dict[str, str]:
    return {item.name: item.address for item in config.contracts}


async def _assert_pins_match_catalog(environment: PolyesterEnvironment) -> None:
    async with AsyncPolyester(environment=environment, hydrate_catalogs=False) as client:
        config = await client.zipper.get_deposit_withdraw_config()
    by_name = _contract_map(config)
    expected = {
        "tradingGateway": environment.contracts.trading_gateway_address,
        "fundingAccount": environment.contracts.funding_account_address,
        "guardRegistry": environment.contracts.guard_registry_address,
        "zipperEndpoint": environment.contracts.zipper_endpoint_address,
        "EntryPoint": environment.account_abstraction.entry_point.address,
    }
    for name, address in expected.items():
        assert name in by_name, f"{environment.name} catalog missing {name}"
        assert by_name[name].lower() == address.lower(), (
            f"{environment.name} {name}: catalog {by_name[name]} != pin {address}"
        )


async def _run_pin_check(environment: PolyesterEnvironment) -> None:
    try:
        await _assert_pins_match_catalog(environment)
    except PolyesterTransportError as exc:
        if os.getenv("POLYESTER_TEST_STRICT_LIVE", "").lower() in {"1", "true", "yes"}:
            raise
        pytest.skip(f"live zipper catalog unavailable: {exc}")


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.public_smoke
async def test_devnet_pins_match_live_zipper_catalog() -> None:
    await _run_pin_check(POLYESTER_DEVNET_ENVIRONMENT)


@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.public_smoke
async def test_testnet_pins_match_live_zipper_catalog() -> None:
    await _run_pin_check(POLYESTER_TESTNET_ENVIRONMENT)
