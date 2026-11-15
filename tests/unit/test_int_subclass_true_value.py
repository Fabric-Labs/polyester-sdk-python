"""An int subclass is used for its true integer value, never for what its
__int__ claims: an override returning 1 must not sign nonce 42 as nonce 1,
or turn a negative call value into an accepted positive one."""

from __future__ import annotations

from typing import Any

import pytest

from polyester.chain.calldata import ChainCall
from polyester.chain.userop import encode_execute_user_op_call_data
from polyester.codecs.bps import validate_bps
from polyester.codecs.scalars import (
    exact_integer,
    id_to_int,
    market_id,
    tick_count,
    validate_protocol_scale,
)
from polyester.codecs.withdraw import trading_withdraw_payload_to_proto
from polyester.errors import PolyesterValidationError
from polyester.types.money import AssetAmount, QuantityDomain

ADDRESS = "0x" + "11" * 20


class LyingInt(int):
    """An int whose __int__ (and __float__) lies; its true value is int.__index__."""

    def __int__(self) -> int:
        return 1

    def __float__(self) -> float:
        return 1.0


def _u128(value: Any) -> int:
    return (int(value.hi) << 64) | int(value.lo)


def test_withdraw_nonce_signs_the_true_value_of_an_int_subclass() -> None:
    payload = trading_withdraw_payload_to_proto(
        action="to_funding",
        asset_id=LyingInt(2),
        amount="1",
        idempotency_key="k",
        deadline_ts_sec=LyingInt(1_800_000_000),
        nonce=LyingInt(42),
    )
    assert _u128(payload.nonce) == 42
    assert payload.deadline_ts_sec == 1_800_000_000
    assert payload.asset_id == 2


def test_negative_int_subclass_call_value_is_refused() -> None:
    with pytest.raises(PolyesterValidationError, match="value"):
        encode_execute_user_op_call_data(ChainCall(to=ADDRESS, data=b"", value=LyingInt(-1)))


def test_int_subclass_call_value_encodes_its_true_value() -> None:
    data = encode_execute_user_op_call_data(ChainCall(to=ADDRESS, data=b"", value=LyingInt(42)))
    assert int.from_bytes(data[4 + 32 : 4 + 64], "big") == 42


def test_exact_integer_returns_the_true_value_as_a_plain_int() -> None:
    value = exact_integer(LyingInt(42), "field", min_value=0, max_value=100)
    assert value == 42 and type(value) is int
    with pytest.raises(PolyesterValidationError, match="outside"):
        exact_integer(LyingInt(-1), "field", min_value=0, max_value=100)


def test_market_id_uses_the_true_value() -> None:
    value = market_id(LyingInt(8), "market")
    assert value == 8 and type(value) is int


def test_tick_count_and_bps_use_the_true_value() -> None:
    assert tick_count(LyingInt(42), "ticks") == 42
    with pytest.raises(PolyesterValidationError):
        tick_count(LyingInt(-5), "ticks")
    assert validate_bps(LyingInt(42), "bps") == 42
    with pytest.raises(PolyesterValidationError):
        validate_bps(LyingInt(20_000), "bps")


def test_ids_scales_and_scaled_amounts_return_plain_ints() -> None:
    for value in (
        id_to_int(LyingInt(42)),
        validate_protocol_scale(LyingInt(8)),
    ):
        assert value in (42, 8) and type(value) is int
    amount = AssetAmount.from_scaled(LyingInt(5), scale=18, domain=QuantityDomain.ASSET, asset_id=2)
    assert int(amount.scaled) == 5 and type(amount.scaled) is int


def _prepare(nonce: Any):
    from polyester import AsyncPolyester
    from tests.hardening_support import make_test_credentials

    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url="http://127.0.0.1:9",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    prepared = client.trading_withdraws.prepare_api_key_to_funding(
        asset_id=LyingInt(2),
        quantity="1",
        idempotency_key="k",
        deadline_ts_sec=LyingInt(1_800_000_000),
        nonce=nonce,
    )
    return creds, prepared


def test_prepared_signed_withdraw_signs_the_true_value_of_an_int_subclass() -> None:
    from polyester.gen.chain.withdraw.v1 import withdraw_pb2

    creds, prepared = _prepare(LyingInt(42))
    request = withdraw_pb2.CreateTradingWithdrawRequest.FromString(prepared.request_bytes)
    assert _u128(request.payload.nonce) == 42
    assert request.payload.deadline_ts_sec == 1_800_000_000
    assert request.payload.asset_id == 2
    # The signature covers the payload that carries nonce 42.
    payload_bytes = request.payload.SerializeToString(deterministic=True)
    assert request.payload_signature == creds.sign_payload(payload_bytes)


@pytest.mark.parametrize("nonce", [LyingInt(-1), LyingInt(0)])
def test_prepared_signed_withdraw_refuses_a_non_positive_int_subclass_nonce(nonce: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="nonce"):
        _prepare(nonce)


def test_market_id_refuses_a_negative_int_subclass() -> None:
    with pytest.raises(PolyesterValidationError, match="outside"):
        market_id(LyingInt(-1), "market")
