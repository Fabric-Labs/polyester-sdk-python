"""CREATE2 Safe prediction parity with TypeScript / permissionless."""

from __future__ import annotations

import pytest

from polyester.chain.safe import (  # noqa: E402
    predict_polyester_smart_account_address,
    predict_safe_address,
    predict_safe_address_with_data,
)
from polyester.errors import PolyesterValidationError

# Golden vectors from polyester-sdk-typescript predict-safe-address (key = 0x01).
OWNER = "0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf"
SALT0 = "0xA244Ed1dc6B46C75F37E0119054fFa45E76c9B6f"
SALT7 = "0x4AEdcc90537f9fb3828E6b431E5A16Cdc473D6f0"


def test_predict_safe_address_salt_zero_matches_typescript() -> None:
    assert predict_safe_address(owner_address=OWNER, salt_nonce=0) == SALT0


def test_predict_safe_address_salt_seven_matches_typescript() -> None:
    assert predict_safe_address(owner_address=OWNER, salt_nonce=7) == SALT7


def test_predict_safe_address_with_data_includes_factory_calldata() -> None:
    predicted = predict_safe_address_with_data(owners=[OWNER], salt_nonce=0)
    assert predicted.address == SALT0
    assert predicted.initializer.hex().startswith("b63e800d")
    assert predicted.factory_calldata.hex().startswith("1688f0b9")


# Owners that are not an address someone controls: not 20 bytes of hex, or the
# zero address, which the Safe contract refuses as an owner.
INVALID_OWNERS = [
    "",
    "   ",
    "nothex",
    "0x",
    "0x1234",
    "0x" + "a" * 39,
    "0x" + "a" * 41,
    "0x" + "a" * 38 + "zz",
    "0x\u00e9" + "a" * 38,
    "0x" + "0" * 40,
    "0" * 40,
    "0X" + "0" * 40,
]


@pytest.mark.parametrize("owner", INVALID_OWNERS)
def test_predict_safe_address_refuses_an_owner_that_is_not_an_address(owner: str) -> None:
    with pytest.raises(PolyesterValidationError, match="owner_address"):
        predict_safe_address(owner_address=owner)
    with pytest.raises(PolyesterValidationError, match="owner_address"):
        predict_polyester_smart_account_address(owner_address=owner)
    with pytest.raises(PolyesterValidationError, match=r"owners\[1\]"):
        predict_safe_address_with_data(owners=[OWNER, owner])


@pytest.mark.parametrize(
    "owner",
    [OWNER, OWNER.lower(), "0x" + OWNER[2:].upper(), "0X" + OWNER[2:], OWNER[2:]],
)
def test_predict_safe_address_accepts_every_address_spelling(owner: str) -> None:
    assert predict_safe_address(owner_address=owner) == SALT0
