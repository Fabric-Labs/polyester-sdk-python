"""Every integer a user operation encodes or signs (call value, gas fields,
fees, nonce, validity window, Safe salt) is used exactly as given, or refused
with PolyesterValidationError before anything is encoded or signed."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from eth_account import Account

from polyester import AsyncPolyester
from polyester.chain.calldata import ChainCall
from polyester.chain.environment import POLYESTER_DEVNET_ENVIRONMENT
from polyester.chain.safe import predict_safe_address
from polyester.chain.userop import (
    PolyesterSmartAccount,
    encode_execute_user_op_call_data,
    pack_paymaster_and_data,
    sign_safe_user_operation,
)
from polyester.codecs.scalars import market_id
from polyester.errors import PolyesterValidationError
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

ADDRESS = "0x" + "11" * 20
OWNER = Account.from_key("0x" + "07" * 32)


class FloatIndex(float):
    def __index__(self) -> int:
        return int(self)


# Each would be encoded as 1, or parsed, by int(); none is an exact integer.
NOT_INTEGERS: list[Any] = [1.5, 1.9, True, Decimal("1.9"), Decimal("1"), "42.0", FloatIndex(1.5)]


@pytest.mark.parametrize("value", [*NOT_INTEGERS, "1", None, -1, 2**256])
def test_call_value_refuses_non_exact_values(value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="value"):
        encode_execute_user_op_call_data(ChainCall(to=ADDRESS, data=b"", value=value))


@pytest.mark.parametrize("value", [0, 1, 10**18, 2**256 - 1])
def test_call_value_is_encoded_exactly(value: int) -> None:
    data = encode_execute_user_op_call_data(ChainCall(to=ADDRESS, data=b"", value=value))
    # selector, address word, then the value word.
    assert int.from_bytes(data[4 + 32 : 4 + 64], "big") == value


@pytest.mark.parametrize(
    "field", ["paymaster_verification_gas_limit", "paymaster_post_op_gas_limit"]
)
@pytest.mark.parametrize("value", [*NOT_INTEGERS, -1, 2**128])
def test_paymaster_gas_limits_refuse_non_exact_values(field: str, value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        pack_paymaster_and_data(paymaster=ADDRESS, **{field: value})


def test_paymaster_gas_limits_are_packed_exactly() -> None:
    packed = pack_paymaster_and_data(
        paymaster=ADDRESS,
        paymaster_verification_gas_limit=2**128 - 1,
        paymaster_post_op_gas_limit=7,
    )
    assert int.from_bytes(packed[20:36], "big") == 2**128 - 1
    assert int.from_bytes(packed[36:52], "big") == 7


_SIGNED_FIELDS: dict[str, int] = {
    "nonce": 0,
    "call_gas_limit": 1,
    "verification_gas_limit": 1,
    "pre_verification_gas": 1,
    "max_fee_per_gas": 1,
    "max_priority_fee_per_gas": 1,
    "valid_after": 0,
    "valid_until": 0,
}


def _sign(**overrides: Any) -> bytes:
    return sign_safe_user_operation(
        owner=OWNER,
        environment=POLYESTER_DEVNET_ENVIRONMENT,
        sender=ADDRESS,
        init_code=b"",
        call_data=b"",
        paymaster_and_data=b"",
        **{**_SIGNED_FIELDS, **overrides},
    )


@pytest.mark.parametrize("field", list(_SIGNED_FIELDS))
@pytest.mark.parametrize("value", [*NOT_INTEGERS, -1])
def test_signed_user_operation_fields_refuse_non_exact_values(field: str, value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        _sign(**{field: value})


@pytest.mark.parametrize("field", ["valid_after", "valid_until"])
def test_validity_window_refuses_values_beyond_uint48(field: str) -> None:
    with pytest.raises(PolyesterValidationError, match=field):
        _sign(**{field: 2**48})


def test_validity_window_is_packed_exactly() -> None:
    signature = _sign(valid_after=5, valid_until=2**48 - 1)
    assert int.from_bytes(signature[:6], "big") == 5
    assert int.from_bytes(signature[6:12], "big") == 2**48 - 1


@pytest.mark.parametrize("salt", [*NOT_INTEGERS, -1, 2**256])
def test_safe_salt_nonce_refuses_non_exact_values(salt: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="salt_nonce"):
        predict_safe_address(owner_address=ADDRESS, salt_nonce=salt)
    with pytest.raises(PolyesterValidationError, match="salt_nonce"):
        PolyesterSmartAccount(owner_private_key="07" * 32, salt_nonce=salt)


def test_safe_salt_nonce_predicts_the_same_address_for_the_same_integer() -> None:
    assert predict_safe_address(owner_address=ADDRESS, salt_nonce=7) == predict_safe_address(
        owner_address=ADDRESS, salt_nonce=7
    )
    assert predict_safe_address(owner_address=ADDRESS, salt_nonce=7) != predict_safe_address(
        owner_address=ADDRESS, salt_nonce=8
    )


@pytest.mark.parametrize("value", [FloatIndex(8.9), FloatIndex(8.0)])
def test_market_id_refuses_float_index_objects(value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="market"):
        market_id(value, "market")


@pytest.mark.asyncio
@pytest.mark.parametrize("asset_id", [FloatIndex(2.5), 2.0, True, Decimal("2"), "2", 0, 2**32])
async def test_internal_transfer_asset_id_refuses_non_exact_values(asset_id: Any) -> None:
    seen: list[str] = []

    async def handler(req: ParsedRequest):
        seen.append(req.path)
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(PolyesterValidationError, match="asset_id"):
            await client.internal_transfers.create(
                asset_id=asset_id,
                quantity="1",
                idempotency_key="k",
                destination_account_id=5,
            )
    finally:
        await client.aclose()
        await http.aclose()
    assert seen == []
