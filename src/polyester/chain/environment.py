"""Pinned Polyester chain / account-abstraction environments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntryPointConfig:
    address: str
    version: str = "0.7"


@dataclass(frozen=True, slots=True)
class SafeDeploymentConfig:
    version: str
    safe_module_setup_address: str
    safe_4337_module_address: str
    safe_proxy_factory_address: str
    safe_singleton_address: str
    multi_send_address: str
    multi_send_call_only_address: str | None = None


@dataclass(frozen=True, slots=True)
class AccountAbstractionEnvironment:
    bundler_url: str
    paymaster_url: str
    entry_point: EntryPointConfig
    safe: SafeDeploymentConfig


@dataclass(frozen=True, slots=True)
class ContractsEnvironment:
    trading_gateway_address: str
    funding_account_address: str = "0xBfF4F6224BC10f233dDB1E61E770d9832aabC7c4"
    guard_registry_address: str = "0xd71F60FD6f784Cc0aD8c25441568C48705D95f64"
    zipper_endpoint_address: str = "0xae6B981BE9B73421eB1ba5372d1A4A937d63ffFB"


@dataclass(frozen=True, slots=True)
class PolyesterChainEnvironment:
    """On-chain / AA settings for Funding UserOps (not API-key Connect)."""

    name: str
    api_url: str
    websocket_url: str
    rpc_url: str
    chain_id: int
    account_abstraction: AccountAbstractionEnvironment
    contracts: ContractsEnvironment


POLYESTER_TESTNET_ENVIRONMENT = PolyesterChainEnvironment(
    name="polyester-testnet",
    api_url="https://api-devnet.polyester.ai",
    websocket_url="wss://api-devnet.polyester.ai",
    rpc_url="https://rpc.polyester.tech",
    chain_id=888168,
    account_abstraction=AccountAbstractionEnvironment(
        bundler_url="https://bundler.polyester.tech",
        paymaster_url="https://paymaster.polyester.tech",
        entry_point=EntryPointConfig(
            address="0x59a4B77766509c4507D79eFF8089474eC3daC174",
            version="0.7",
        ),
        safe=SafeDeploymentConfig(
            version="1.4.1",
            safe_module_setup_address="0x80791683D9C079A37Debc67EaDdbFcBC6f0FF2bB",
            safe_4337_module_address="0x0713FF3d4c1b4f177833a372b1e3cb977540EA11",
            safe_proxy_factory_address="0xF8F0F649Dd3bFa9095206691E9fb2356c26216dE",
            safe_singleton_address="0x92abEa238FEA8908c397cE65366ea9278f0AeC7A",
            multi_send_address="0x70C8a8CcB45a8E2589B0f019374fc923dA34E4c7",
            multi_send_call_only_address="0x375C86a08DA98d1944D7B3c736307A72186CcAf1",
        ),
    ),
    contracts=ContractsEnvironment(
        trading_gateway_address="0xD3fecf5D39131e23b6B0f872cA0a21c8A5a30932",
        funding_account_address="0xBfF4F6224BC10f233dDB1E61E770d9832aabC7c4",
        guard_registry_address="0xd71F60FD6f784Cc0aD8c25441568C48705D95f64",
        zipper_endpoint_address="0xae6B981BE9B73421eB1ba5372d1A4A937d63ffFB",
    ),
)
