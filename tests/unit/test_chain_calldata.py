"""Calldata encoders for on-chain Funding ops (POLY-3569).

Selectors and shapes must stay aligned with TypeScript
``TRADING_GATEWAY_DEPOSIT_ABI`` / ``FUNDING_ACCOUNT_WITHDRAW_TO_CHAIN_ABI``.
"""

from __future__ import annotations

import pytest

eth_abi = pytest.importorskip("eth_abi")
from eth_utils import function_signature_to_4byte_selector  # noqa: E402

from polyester.chain import (  # noqa: E402
    GuardApproval,
    encode_add_allowed_external_destinations,
    encode_add_allowed_internal_accounts,
    encode_funding_withdraw_to_chain,
    encode_initialize_guard_signer,
    encode_remove_allowed_external_destinations,
    encode_remove_allowed_internal_accounts,
    encode_rotate_guard_signer,
    encode_set_external_destination_allowlist_required,
    encode_set_internal_account_allowlist_required,
    encode_trading_gateway_deposit,
    encode_trading_gateway_deposit_to,
    encode_withdraw_destination,
)
from polyester.errors import PolyesterValidationError  # noqa: E402
TRADING_GATEWAY = "0x4444444444444444444444444444444444444444"
FUNDING_ACCOUNT = "0x1111111111111111111111111111111111111111"
INTERNAL_ACCOUNT = "0x3333333333333333333333333333333333333333"
U_ASSET_ID = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
Z_TOKEN = "0x5555555555555555555555555555555555555555"


def test_encode_trading_gateway_deposit_selector_and_args() -> None:
    call = encode_trading_gateway_deposit(
        trading_gateway=TRADING_GATEWAY,
        u_asset_id=U_ASSET_ID,
        quantity_scaled=1_000_000,
    )
    assert call.to == TRADING_GATEWAY.lower()
    assert call.value == 0
    selector = function_signature_to_4byte_selector("deposit(bytes32,uint256)")
    assert call.data[:4] == selector
    decoded = eth_abi.decode(["bytes32", "uint256"], call.data[4:])
    assert decoded[0] == bytes.fromhex(U_ASSET_ID[2:])
    assert decoded[1] == 1_000_000


def test_encode_trading_gateway_deposit_to_selector_and_args() -> None:
    call = encode_trading_gateway_deposit_to(
        trading_gateway=TRADING_GATEWAY,
        to_account=INTERNAL_ACCOUNT,
        u_asset_id=U_ASSET_ID,
        quantity_scaled=1_000_000,
    )
    selector = function_signature_to_4byte_selector("depositTo(address,bytes32,uint256)")
    assert call.data[:4] == selector
    decoded = eth_abi.decode(["address", "bytes32", "uint256"], call.data[4:])
    assert decoded[0].lower() == INTERNAL_ACCOUNT.lower()
    assert decoded[2] == 1_000_000


def test_encode_funding_withdraw_to_chain_selector_and_tuple() -> None:
    destination = bytes.fromhex("1234")
    call = encode_funding_withdraw_to_chain(
        funding_account=FUNDING_ACCOUNT,
        chain_id=56,
        z_token=Z_TOKEN,
        withdraw_destination=destination,
        z_amount=2_000_000,
        max_fee=1000,
    )
    selector = function_signature_to_4byte_selector(
        "withdrawToChain((uint16,address,bytes,uint256,uint256))"
    )
    assert call.to == FUNDING_ACCOUNT.lower()
    assert call.data[:4] == selector
    decoded = eth_abi.decode(["(uint16,address,bytes,uint256,uint256)"], call.data[4:])
    chain_id, z_token, dest, z_amount, max_fee = decoded[0]
    assert chain_id == 56
    assert z_token.lower() == Z_TOKEN.lower()
    assert dest == destination
    assert z_amount == 2_000_000
    assert max_fee == 1000


def test_encode_withdraw_destination_case_sensitive() -> None:
    address = "Tb1QCaseSensitiveAddress"
    assert encode_withdraw_destination(address=address, is_case_sensitive=True) == address.encode(
        "utf-8"
    )


def test_encode_withdraw_destination_lowercases_when_insensitive() -> None:
    address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"
    assert encode_withdraw_destination(
        address=address, is_case_sensitive=False
    ) == address.lower().encode("utf-8")


def test_encode_set_external_destination_allowlist_required() -> None:
    call = encode_set_external_destination_allowlist_required(
        funding_account=FUNDING_ACCOUNT,
        required=True,
    )
    selector = function_signature_to_4byte_selector(
        "setExternalDestinationAllowlistRequired(bool,(uint192,uint256,bytes))"
    )
    assert call.data[:4] == selector
    decoded = eth_abi.decode(["bool", "(uint192,uint256,bytes)"], call.data[4:])
    assert decoded[0] is True
    assert decoded[1] == (0, 0, b"")

    call_false = encode_set_external_destination_allowlist_required(
        funding_account=FUNDING_ACCOUNT,
        required=False,
        approval=GuardApproval(nonce_space=7, deadline=123, signature=b"\xab\xcd"),
    )
    decoded_false = eth_abi.decode(["bool", "(uint192,uint256,bytes)"], call_false.data[4:])
    assert decoded_false[0] is False
    assert decoded_false[1] == (7, 123, b"\xab\xcd")


def test_deposit_rejects_non_positive_amount() -> None:
    with pytest.raises(PolyesterValidationError, match="quantity_scaled"):
        encode_trading_gateway_deposit(
            trading_gateway=TRADING_GATEWAY,
            u_asset_id=U_ASSET_ID,
            quantity_scaled=0,
        )


def test_withdraw_rejects_amount_not_greater_than_fee() -> None:
    with pytest.raises(PolyesterValidationError, match="greater than max_fee"):
        encode_funding_withdraw_to_chain(
            funding_account=FUNDING_ACCOUNT,
            chain_id=1,
            z_token=Z_TOKEN,
            withdraw_destination=b"\x12\x34",
            z_amount=100,
            max_fee=100,
        )


def test_encode_set_internal_account_allowlist_required() -> None:
    call = encode_set_internal_account_allowlist_required(
        funding_account=FUNDING_ACCOUNT,
        required=True,
    )
    selector = function_signature_to_4byte_selector(
        "setInternalAccountAllowlistRequired(bool,(uint192,uint256,bytes))"
    )
    assert call.data[:4] == selector


def test_encode_add_remove_external_destinations() -> None:
    dest = [b"\x01\x02", encode_withdraw_destination(address="0xABCD", is_case_sensitive=False)]
    add = encode_add_allowed_external_destinations(
        funding_account=FUNDING_ACCOUNT,
        chain_id=6,
        destinations=dest,
    )
    rem = encode_remove_allowed_external_destinations(
        funding_account=FUNDING_ACCOUNT,
        chain_id=6,
        destinations=dest,
    )
    assert add.data[:4] == function_signature_to_4byte_selector(
        "addAllowedExternalDestinations(uint16,bytes[],(uint192,uint256,bytes))"
    )
    assert rem.data[:4] == function_signature_to_4byte_selector(
        "removeAllowedExternalDestinations(uint16,bytes[],(uint192,uint256,bytes))"
    )
    decoded = eth_abi.decode(["uint16", "bytes[]", "(uint192,uint256,bytes)"], add.data[4:])
    assert decoded[0] == 6
    assert list(decoded[1]) == dest


def test_encode_add_remove_internal_accounts() -> None:
    add = encode_add_allowed_internal_accounts(
        funding_account=FUNDING_ACCOUNT,
        accounts=[INTERNAL_ACCOUNT],
    )
    rem = encode_remove_allowed_internal_accounts(
        funding_account=FUNDING_ACCOUNT,
        accounts=[INTERNAL_ACCOUNT],
    )
    assert add.data[:4] == function_signature_to_4byte_selector(
        "addAllowedInternalAccounts(address[],(uint192,uint256,bytes))"
    )
    assert rem.data[:4] == function_signature_to_4byte_selector(
        "removeAllowedInternalAccounts(address[],(uint192,uint256,bytes))"
    )


def test_encode_guard_registry_initialize_and_rotate() -> None:
    registry = "0x6666666666666666666666666666666666666666"
    init = encode_initialize_guard_signer(guard_registry=registry, signer=INTERNAL_ACCOUNT)
    rot = encode_rotate_guard_signer(
        guard_registry=registry,
        new_signer=INTERNAL_ACCOUNT,
        approval=GuardApproval(nonce_space=1, deadline=2, signature=b"\xff"),
    )
    assert init.data[:4] == function_signature_to_4byte_selector("initializeSigner(address)")
    assert rot.data[:4] == function_signature_to_4byte_selector(
        "rotateSigner(address,(uint192,uint256,bytes))"
    )
