"""Unit tests for Zipper fee quoting (network optional)."""

from __future__ import annotations

import pytest
from eth_utils import function_signature_to_4byte_selector

from polyester.chain.fees import quote_zipper_fee
from polyester.errors import PolyesterValidationError


def test_quote_zipper_fee_validates_inputs() -> None:
    with pytest.raises(PolyesterValidationError, match="chain_id"):
        quote_zipper_fee(chain_id=0, z_token="0x" + "11" * 20, zipper_endpoint="0x" + "22" * 20)


def test_fee_related_selectors_are_four_bytes() -> None:
    assert len(function_signature_to_4byte_selector("feeFactory()")) == 4
    assert len(function_signature_to_4byte_selector("getFee(uint16,address)")) == 4
    assert len(function_signature_to_4byte_selector("decimals()")) == 4
