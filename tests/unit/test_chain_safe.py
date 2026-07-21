"""CREATE2 Safe prediction parity with TypeScript / permissionless."""

from __future__ import annotations

from polyester.chain.safe import (  # noqa: E402
    predict_safe_address,
    predict_safe_address_with_data,
)

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
