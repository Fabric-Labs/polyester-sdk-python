"""Live on-chain Funding UserOps (POLY-3569).

Gated by ``POLYESTER_TEST_CHAIN_USEROP=1`` plus ``POLYESTER_OWNER_PRIVATE_KEY``.
"""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal

import pytest

from polyester.chain import (
    POLYESTER_TESTNET_ENVIRONMENT,
    PolyesterSmartAccount,
    encode_funding_withdraw_to_chain,
    encode_trading_gateway_deposit,
    encode_withdraw_destination,
    quote_zipper_fee,
)
from tests.helpers import trading_balance_decimal


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").lower() in ("1", "true", "yes")


def _require_chain_userop() -> str:
    if not _env_truthy("POLYESTER_TEST_CHAIN_USEROP"):
        pytest.skip("Set POLYESTER_TEST_CHAIN_USEROP=1 to run on-chain Funding UserOp tests")
    owner = (os.getenv("POLYESTER_OWNER_PRIVATE_KEY") or "").strip()
    if not owner:
        pytest.skip("Set POLYESTER_OWNER_PRIVATE_KEY for on-chain Funding UserOp tests")
    return owner


async def _usdt_asset(live_client):
    zipper = await live_client.zipper.get_deposit_withdraw_config()
    live_client.catalogs.hydrate_zipper_config(zipper)
    override = (os.getenv("POLYESTER_TEST_U_ASSET_ID") or "").strip()
    for asset in zipper.assets or []:
        if override and asset.u_asset_id.lower() == override.lower():
            return asset, zipper
        if asset.ledger_id == 1 or (asset.asset or "").upper() == "USDT":
            return asset, zipper
    pytest.skip("USDT / ledger_id=1 not found in zipper deposit-withdraw config")


def _funding_balance_decimal(balances, asset_id: int) -> Decimal:
    for row in balances.balances:
        if row.asset_id == asset_id:
            return Decimal(row.funding or "0") / Decimal(10**18)
    return Decimal(0)


def _scaled_from_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    return int(raw)


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_funding_to_trading_userop(live_client, funded_enabled, mutation_enabled):
    owner = _require_chain_userop()
    asset, _ = await _usdt_asset(live_client)
    quantity = _scaled_from_env("POLYESTER_TEST_DEPOSIT_QTY_SCALED", 10**18)

    before = await live_client.balances.list()
    funding_before = _funding_balance_decimal(before, asset.ledger_id)
    trading_before = trading_balance_decimal(before, asset.ledger_id)
    if funding_before * Decimal(10**18) < quantity:
        pytest.skip(
            f"Funding {funding_before} below deposit qty {quantity} for asset {asset.ledger_id}"
        )

    account = PolyesterSmartAccount(owner_private_key=owner)
    call = encode_trading_gateway_deposit(
        trading_gateway=POLYESTER_TESTNET_ENVIRONMENT.contracts.trading_gateway_address,
        u_asset_id=asset.u_asset_id,
        quantity_scaled=quantity,
    )
    receipt = account.send_calls([call], wait=True, receipt_timeout_s=120)
    assert getattr(receipt, "success", False) is True
    assert getattr(receipt, "user_operation_hash", "")

    expected_trading = trading_before + (Decimal(quantity) / Decimal(10**18))
    trading_after = trading_before
    for _ in range(30):
        await asyncio.sleep(1)
        after = await live_client.balances.list()
        trading_after = trading_balance_decimal(after, asset.ledger_id)
        if trading_after >= expected_trading:
            break
    assert trading_after >= expected_trading


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_funding_withdraw_to_chain_userop(live_client, funded_enabled, mutation_enabled):
    owner = _require_chain_userop()
    dest = (os.getenv("POLYESTER_TEST_WITHDRAW_DESTINATION") or "").strip()
    if not dest:
        pytest.skip("Set POLYESTER_TEST_WITHDRAW_DESTINATION for Funding→external UserOp")
    chain_id = int((os.getenv("POLYESTER_TEST_WITHDRAW_CHAIN_ID") or "6").strip() or "6")
    human_amount = Decimal((os.getenv("POLYESTER_TEST_WITHDRAW_AMOUNT") or "1").strip() or "1")
    z_amount = int(human_amount * Decimal(10**18))

    asset, zipper = await _usdt_asset(live_client)
    variant = next((v for v in asset.variants or [] if v.chain_id == chain_id), None)
    if variant is None or not (variant.z_token and variant.z_token.address):
        pytest.skip(f"No USDT z_token variant for withdraw chain_id={chain_id}")

    chain_meta = next((c for c in (zipper.chains or []) if c.chain_id == chain_id), None)
    case_sensitive = bool(chain_meta and chain_meta.is_case_sensitive)

    before = await live_client.balances.list()
    funding_before = _funding_balance_decimal(before, asset.ledger_id)
    if funding_before < human_amount:
        pytest.skip(
            f"Funding {funding_before} below withdraw amount {human_amount} "
            f"for asset {asset.ledger_id}"
        )

    fee = quote_zipper_fee(
        chain_id=chain_id,
        z_token=variant.z_token.address,
        zipper_endpoint=POLYESTER_TESTNET_ENVIRONMENT.contracts.zipper_endpoint_address,
    )
    max_fee = fee.fee + fee.fee // 10
    if z_amount <= max_fee:
        pytest.skip(
            f"withdraw amount {z_amount} must be greater than max_fee {max_fee}; "
            "raise POLYESTER_TEST_WITHDRAW_AMOUNT"
        )

    account = PolyesterSmartAccount(owner_private_key=owner)
    call = encode_funding_withdraw_to_chain(
        funding_account=POLYESTER_TESTNET_ENVIRONMENT.contracts.funding_account_address,
        chain_id=chain_id,
        z_token=variant.z_token.address,
        withdraw_destination=encode_withdraw_destination(
            address=dest,
            is_case_sensitive=case_sensitive,
        ),
        z_amount=z_amount,
        max_fee=max_fee,
    )
    receipt = account.send_calls([call], wait=True, receipt_timeout_s=120)
    assert getattr(receipt, "success", False) is True
    assert getattr(receipt, "user_operation_hash", "")

    funding_after = funding_before
    for _ in range(30):
        await asyncio.sleep(1)
        after = await live_client.balances.list()
        funding_after = _funding_balance_decimal(after, asset.ledger_id)
        if funding_after < funding_before:
            break
    assert funding_after < funding_before
