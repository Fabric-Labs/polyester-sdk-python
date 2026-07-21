"""Unit tests for UserOp calldata packing (no network)."""

from __future__ import annotations

import pytest

eth_abi = pytest.importorskip("eth_abi")
pytest.importorskip("eth_account")

from eth_utils import function_signature_to_4byte_selector  # noqa: E402

from polyester.chain.calldata import ChainCall  # noqa: E402
from polyester.chain.userop import (  # noqa: E402
    add_user_operation_gas_buffer,
    encode_execute_user_op_call_data,
    pack_paymaster_and_data,
)


def test_execute_user_op_selector() -> None:
    call = ChainCall(
        to="0xD3fecf5D39131e23b6B0f872cA0a21c8A5a30932",
        data=b"\x12\x34",
        value=0,
    )
    encoded = encode_execute_user_op_call_data(call)
    expected = function_signature_to_4byte_selector(
        "executeUserOpWithErrorString(address,uint256,bytes,uint8)"
    )
    assert encoded[:4] == expected


def test_gas_buffer_applies_minimum() -> None:
    assert add_user_operation_gas_buffer(100) == 50_100
    assert add_user_operation_gas_buffer(1_000_000) == 1_200_000


def test_pack_paymaster_and_data_empty_without_paymaster() -> None:
    assert pack_paymaster_and_data(paymaster=None) == b""
