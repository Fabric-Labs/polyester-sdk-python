from __future__ import annotations

import pytest

from polyester import (
    POLYESTER_DEVNET_ENVIRONMENT,
    POLYESTER_TESTNET_ENVIRONMENT,
    AsyncPolyester,
    create_polyester_environment,
    environment_from_name,
)
from polyester.client import DEFAULT_API_URL, DEFAULT_WS_URL, ENV_NAME_ENV
from polyester.environment import ENV_NAME_ENV as CLIENT_ENV_NAME_ENV
from polyester.errors import PolyesterValidationError


def test_devnet_preset_matches_typescript_and_zipper_extras() -> None:
    env = POLYESTER_DEVNET_ENVIRONMENT
    assert env.name == "polyester-devnet"
    assert env.api_url == "https://api-devnet.polyester.ai"
    assert env.websocket_url == "wss://api-devnet.polyester.ai"
    assert env.rpc_url == "https://rpc.polyester.tech"
    assert env.chain_id == 888168
    assert env.account_abstraction.entry_point.version == "0.7"
    assert env.account_abstraction.entry_point.address == "0x59a4B77766509c4507D79eFF8089474eC3daC174"
    assert env.contracts.trading_gateway_address == "0xD3fecf5D39131e23b6B0f872cA0a21c8A5a30932"
    assert env.contracts.funding_account_address == "0xBfF4F6224BC10f233dDB1E61E770d9832aabC7c4"
    assert env.contracts.guard_registry_address == "0xd71F60FD6f784Cc0aD8c25441568C48705D95f64"
    assert env.contracts.zipper_endpoint_address == "0xae6B981BE9B73421eB1ba5372d1A4A937d63ffFB"


def test_testnet_preset_matches_typescript_and_zipper_extras() -> None:
    env = POLYESTER_TESTNET_ENVIRONMENT
    assert env.name == "polyester-testnet"
    assert env.api_url == "https://api-testnet.polyester.com"
    assert env.websocket_url == "wss://api-testnet.polyester.com"
    assert env.rpc_url == "https://rpc.polyester.live"
    assert env.chain_id == 888169
    assert env.account_abstraction.bundler_url == "https://bundler.polyester.live"
    assert env.contracts.trading_gateway_address == "0x20ef1BCeE69D73Ce1649E688dAA9A7AcF441f0EE"
    assert env.contracts.funding_account_address == "0x57D15F393772041b4107943CAFa8A70b620212D1"
    assert env.contracts.guard_registry_address == "0xB0E23DDa102c5d37AcBA583cf84E5aC214e7521C"
    assert env.contracts.zipper_endpoint_address == "0xD439270f881b56727EaaB878CE4e80eB08A25BEB"


def test_presets_are_distinct() -> None:
    assert POLYESTER_DEVNET_ENVIRONMENT.chain_id != POLYESTER_TESTNET_ENVIRONMENT.chain_id
    assert POLYESTER_DEVNET_ENVIRONMENT.api_url != POLYESTER_TESTNET_ENVIRONMENT.api_url
    assert (
        POLYESTER_DEVNET_ENVIRONMENT.contracts.trading_gateway_address
        != POLYESTER_TESTNET_ENVIRONMENT.contracts.trading_gateway_address
    )


def test_default_client_urls_match_devnet() -> None:
    assert DEFAULT_API_URL == POLYESTER_DEVNET_ENVIRONMENT.api_url
    assert DEFAULT_WS_URL == POLYESTER_DEVNET_ENVIRONMENT.websocket_url


def test_environment_from_name() -> None:
    assert environment_from_name("devnet") is POLYESTER_DEVNET_ENVIRONMENT
    assert environment_from_name("polyester-testnet") is POLYESTER_TESTNET_ENVIRONMENT
    with pytest.raises(PolyesterValidationError, match="unknown environment"):
        environment_from_name("mainnet")


def test_with_urls_keeps_chain_pins() -> None:
    custom = POLYESTER_TESTNET_ENVIRONMENT.with_urls(
        api_url="https://mm.internal.example",
        websocket_url="wss://mm.internal.example",
    )
    assert custom.api_url == "https://mm.internal.example"
    assert custom.websocket_url == "wss://mm.internal.example"
    assert custom.chain_id == POLYESTER_TESTNET_ENVIRONMENT.chain_id
    assert custom.contracts == POLYESTER_TESTNET_ENVIRONMENT.contracts
    assert custom.rpc_url == POLYESTER_TESTNET_ENVIRONMENT.rpc_url


def test_create_rejects_remote_plaintext() -> None:
    with pytest.raises(PolyesterValidationError, match="secure protocol"):
        POLYESTER_DEVNET_ENVIRONMENT.with_urls(api_url="http://api.example.test")


def test_create_allows_loopback_http() -> None:
    custom = POLYESTER_DEVNET_ENVIRONMENT.with_urls(api_url="http://127.0.0.1:8080")
    assert custom.api_url == "http://127.0.0.1:8080"


def test_create_rejects_api_query_string() -> None:
    with pytest.raises(PolyesterValidationError, match="query"):
        POLYESTER_DEVNET_ENVIRONMENT.with_urls(api_url="https://api.example.test?x=1")


def test_create_rejects_bad_entry_point_version() -> None:
    aa = POLYESTER_DEVNET_ENVIRONMENT.account_abstraction
    with pytest.raises(PolyesterValidationError, match="0.7"):
        create_polyester_environment(
            name="bad",
            api_url=aa.bundler_url,
            websocket_url=POLYESTER_DEVNET_ENVIRONMENT.websocket_url,
            rpc_url=POLYESTER_DEVNET_ENVIRONMENT.rpc_url,
            chain_id=888168,
            account_abstraction=aa.__class__(
                bundler_url=aa.bundler_url,
                paymaster_url=aa.paymaster_url,
                entry_point=aa.entry_point.__class__(
                    address=aa.entry_point.address,
                    version="0.6",
                ),
                safe=aa.safe,
            ),
            contracts=POLYESTER_DEVNET_ENVIRONMENT.contracts,
        )


@pytest.mark.asyncio
async def test_client_uses_environment_urls() -> None:
    client = AsyncPolyester(
        environment=POLYESTER_TESTNET_ENVIRONMENT,
        hydrate_catalogs=False,
    )
    try:
        assert client.environment is POLYESTER_TESTNET_ENVIRONMENT or (
            client.environment.api_url == POLYESTER_TESTNET_ENVIRONMENT.api_url
        )
        assert client.api_url == POLYESTER_TESTNET_ENVIRONMENT.api_url
        assert client.ws_url == POLYESTER_TESTNET_ENVIRONMENT.websocket_url
        assert client._transport.config.api_url == POLYESTER_TESTNET_ENVIRONMENT.api_url
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_url_overrides_keep_environment_pins() -> None:
    client = AsyncPolyester(
        environment=POLYESTER_TESTNET_ENVIRONMENT,
        api_url="https://mm.internal.example",
        ws_url="wss://mm.internal.example",
        hydrate_catalogs=False,
    )
    try:
        assert client.api_url == "https://mm.internal.example"
        assert client.ws_url == "wss://mm.internal.example"
        assert client.environment.chain_id == 888169
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_from_env_reads_polyester_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLYESTER_API_KEY_ID", raising=False)
    monkeypatch.delenv("POLYESTER_API_PRIVATE_KEY", raising=False)
    monkeypatch.setenv(ENV_NAME_ENV, "testnet")
    assert CLIENT_ENV_NAME_ENV == ENV_NAME_ENV
    client = AsyncPolyester.from_env(hydrate_catalogs=False)
    try:
        assert client.api_url == POLYESTER_TESTNET_ENVIRONMENT.api_url
        assert client.environment.chain_id == 888169
    finally:
        await client.aclose()
