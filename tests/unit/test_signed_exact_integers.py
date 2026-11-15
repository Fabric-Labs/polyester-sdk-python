"""A signed or money-moving integer is signed or sent exactly as given, or
refused with PolyesterValidationError before anything is built, signed or
sent. Nothing is converted: ``nonce=1.5`` must not sign as nonce 1."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.chain.calldata import (
    GuardApproval,
    encode_funding_withdraw_to_chain,
    encode_rotate_guard_signer,
    encode_trading_gateway_deposit,
    encode_trading_gateway_deposit_to,
)
from polyester.codecs.address_book import create_entry_to_proto
from polyester.codecs.guard_signer import protected_action_args_to_proto
from polyester.codecs.scalars import exact_integer
from polyester.codecs.withdraw import trading_withdraw_payload_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

U128_MAX = 2**128 - 1
U64_MAX = 2**64 - 1
U32_MAX = 2**32 - 1
DEADLINE = 1_800_000_000
ADDRESS = "0x" + "11" * 20

# Inputs no exact-integer field takes: they would be truncated, cast or
# mis-parsed by int(). Strings are refused unless they are decimal digits.
NOT_INTEGERS: list[Any] = [
    1.5,
    1.9,
    2.0,
    True,
    False,
    Decimal("2.5"),
    Decimal("2"),
    None,
    b"42",
    [42],
]
NOT_DECIMAL_STRINGS = ["42.0", "0x10", "", " 42", "42 ", "+42", "-1", "4_2", "1e3", "٤٢"]


def _u128(value: Any) -> int:
    return (int(value.hi) << 64) | int(value.lo)


def _payload(**overrides: Any) -> withdraw_pb2.TradingWithdrawIntentPayload:
    kwargs: dict[str, Any] = {
        "action": "to_funding",
        "asset_id": 2,
        "amount": "1",
        "idempotency_key": "exact-int",
        "deadline_ts_sec": DEADLINE,
        "nonce": 42,
    }
    kwargs.update(overrides)
    return trading_withdraw_payload_to_proto(**kwargs)


def _client() -> AsyncPolyester:
    creds = make_test_credentials()
    return AsyncPolyester(
        api_url="http://127.0.0.1:9",
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )


# --- exact_integer ---------------------------------------------------------


@pytest.mark.parametrize("value", NOT_INTEGERS + NOT_DECIMAL_STRINGS + ["42"])
def test_exact_integer_refuses_everything_but_int(value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="must be an integer"):
        exact_integer(value, "field", min_value=0, max_value=U64_MAX)


@pytest.mark.parametrize("value", NOT_INTEGERS + NOT_DECIMAL_STRINGS)
def test_exact_integer_refuses_non_decimal_strings(value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="must be an integer"):
        exact_integer(value, "field", min_value=0, max_value=U64_MAX, allow_str=True)


@pytest.mark.parametrize(
    ("value", "expected"), [(0, 0), (42, 42), ("42", 42), ("0042", 42), ("0", 0)]
)
def test_exact_integer_accepts_ints_and_decimal_strings(value: Any, expected: int) -> None:
    assert exact_integer(value, "field", min_value=0, max_value=100, allow_str=True) == expected


@pytest.mark.parametrize("value", [-1, 101, "101", "9" * 5000, 2**2000])
def test_exact_integer_refuses_out_of_range(value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match=r"outside 0\.\.100"):
        exact_integer(value, "field", min_value=0, max_value=100, allow_str=True)


class FloatIndex(float):
    """A float that also claims to be an index: int(1.5) is 1."""

    def __index__(self) -> int:
        return int(self)


class IndexOnly:
    """Not a number at all, only an __index__ method."""

    def __index__(self) -> int:
        return 7


class IntSubclass(int):
    pass


# Implement __index__ (or convert with int()) without being integers.
NOT_INTEGRAL: list[Any] = [
    FloatIndex(1.5),
    FloatIndex(1.9),
    FloatIndex(2.0),
    IndexOnly(),
    True,
    False,
    Decimal("1.9"),
    Decimal("2"),
]


@pytest.mark.parametrize("value", NOT_INTEGRAL)
def test_exact_integer_refuses_index_objects_that_are_not_integral(value: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="must be an integer"):
        exact_integer(value, "field", min_value=0, max_value=10, allow_str=True)


def test_exact_integer_accepts_integral_types() -> None:
    value = exact_integer(IntSubclass(7), "field", min_value=0, max_value=10)
    assert value == 7 and type(value) is int


def test_exact_integer_accepts_numpy_integers() -> None:
    numpy = pytest.importorskip("numpy")
    for value in (numpy.int64(7), numpy.uint8(7), numpy.int32(7)):
        assert exact_integer(value, "field", min_value=0, max_value=10) == 7
    for value in (numpy.float64(7.0), numpy.bool_(True)):
        with pytest.raises(PolyesterValidationError):
            exact_integer(value, "field", min_value=0, max_value=10)


@pytest.mark.parametrize("nonce", NOT_INTEGRAL)
def test_withdraw_nonce_refuses_index_objects(nonce: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="nonce"):
        _client().trading_withdraws.prepare_api_key_to_funding(
            asset_id=2, quantity="1", idempotency_key="k", deadline_ts_sec=DEADLINE, nonce=nonce
        )


# --- trading withdraw payload: nonce and deadline -----------------------------


@pytest.mark.parametrize("nonce", NOT_INTEGERS + NOT_DECIMAL_STRINGS)
def test_withdraw_nonce_refuses_non_integers(nonce: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="nonce"):
        _payload(nonce=nonce)


@pytest.mark.parametrize("nonce", [0, "0", -1, U128_MAX + 1, str(U128_MAX + 1)])
def test_withdraw_nonce_refuses_out_of_range(nonce: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="nonce"):
        _payload(nonce=nonce)


@pytest.mark.parametrize(
    ("nonce", "expected"),
    [(1, 1), (42, 42), ("42", 42), ("1", 1), (U128_MAX, U128_MAX), (str(U128_MAX), U128_MAX)],
)
def test_withdraw_nonce_signs_exact_value(nonce: Any, expected: int) -> None:
    assert _u128(_payload(nonce=nonce).nonce) == expected


NOT_DEADLINES = [v for v in NOT_INTEGERS if v is not None]  # None takes the default


@pytest.mark.parametrize(
    "deadline", [*NOT_DEADLINES, *NOT_DECIMAL_STRINGS, 1799999999.9, "1799999999.9"]
)
def test_withdraw_deadline_refuses_non_integers(deadline: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="deadline_ts_sec"):
        _payload(deadline_ts_sec=deadline)


@pytest.mark.parametrize("deadline", [0, "0", -1, U64_MAX + 1, str(U64_MAX + 1)])
def test_withdraw_deadline_refuses_out_of_range(deadline: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="deadline_ts_sec"):
        _payload(deadline_ts_sec=deadline)


@pytest.mark.parametrize(
    ("deadline", "expected"),
    [(1, 1), (DEADLINE, DEADLINE), (str(DEADLINE), DEADLINE), (U64_MAX, U64_MAX)],
)
def test_withdraw_deadline_signs_exact_value(deadline: Any, expected: int) -> None:
    assert _payload(deadline_ts_sec=deadline).deadline_ts_sec == expected


@pytest.mark.parametrize("asset_id", [2.0, True, "2", Decimal("2"), 0, -1, U32_MAX + 1])
def test_withdraw_asset_id_refuses_non_exact_values(asset_id: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="asset_id"):
        _payload(asset_id=asset_id)


@pytest.mark.parametrize("chain_id", [137.0, True, "137", -1, U64_MAX + 1])
def test_withdraw_destination_chain_id_refuses_non_exact_values(chain_id: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="destination_chain_id"):
        _payload(
            action="to_external_chain", destination_chain_id=chain_id, destination_address=ADDRESS
        )


def test_withdraw_payload_boundaries_sign_unchanged() -> None:
    payload = _payload(
        action="to_external_chain",
        asset_id=U32_MAX,
        destination_chain_id=U64_MAX,
        destination_address=ADDRESS,
    )
    assert (payload.asset_id, payload.destination_chain_id) == (U32_MAX, U64_MAX)


# --- every withdraw entry point -----------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nonce", 1.5),
        ("nonce", 1.9),
        ("nonce", True),
        ("nonce", "42.0"),
        ("nonce", "0x10"),
        ("deadline_ts_sec", 1799999999.9),
        ("deadline_ts_sec", "1799999999.9"),
        ("deadline_ts_sec", True),
    ],
)
def test_prepare_api_key_withdraws_refuse_before_signing(field: str, value: Any) -> None:
    client = _client()
    kwargs: dict[str, Any] = {
        "asset_id": 2,
        "quantity": "1",
        "idempotency_key": "qa-m6",
        "deadline_ts_sec": DEADLINE,
        "nonce": 42,
        field: value,
    }
    with pytest.raises(PolyesterValidationError, match=field):
        client.trading_withdraws.prepare_api_key_to_funding(**kwargs)
    with pytest.raises(PolyesterValidationError, match=field):
        client.trading_withdraws.prepare_api_key_to_external_chain(
            destination_chain_id=137, destination_address=ADDRESS, **kwargs
        )


@pytest.mark.parametrize(
    ("nonce", "deadline"), [(42, DEADLINE), ("42", DEADLINE), (42, str(DEADLINE))]
)
def test_prepare_api_key_withdraw_keeps_exact_values(nonce: Any, deadline: Any) -> None:
    prepared = _client().trading_withdraws.prepare_api_key_to_funding(
        asset_id=2,
        quantity="1",
        idempotency_key="qa-m6",
        deadline_ts_sec=deadline,
        nonce=nonce,
    )
    request = withdraw_pb2.CreateTradingWithdrawRequest.FromString(prepared.request_bytes)
    assert _u128(request.payload.nonce) == 42
    assert request.payload.deadline_ts_sec == DEADLINE


async def _sent(call) -> tuple[BaseException | None, list[str]]:
    seen: list[str] = []

    async def handler(req: ParsedRequest):
        seen.append(req.path.rsplit("/", 1)[-1])
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    error: BaseException | None = None
    try:
        await call(client)
    except Exception as exc:
        error = exc
    finally:
        await client.aclose()
        await http.aclose()
    return error, seen


_SIGNED = {"payload_signature": b"\x01" * 64, "idempotency_key": "k"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("nonce", 1.5),
        ("nonce", True),
        ("nonce", "42.0"),
        ("deadline_ts_sec", 1799999999.9),
        ("deadline_ts_sec", "1799999999.9"),
        ("deadline_ts_sec", "abc"),
    ],
)
async def test_presigned_withdraws_refuse_before_sending(field: str, value: Any) -> None:
    values: dict[str, Any] = {"nonce": 42, "deadline_ts_sec": DEADLINE, field: value}
    calls = [
        lambda c: c.trading_withdraws.create_to_funding(
            asset_id=2, quantity="1", **_SIGNED, **values
        ),
        lambda c: c.trading_withdraws.create_to_external_chain(
            asset_id=2,
            quantity="1",
            destination_chain_id=137,
            destination_address=ADDRESS,
            **_SIGNED,
            **values,
        ),
        lambda c: c.trading_withdraws.create_wallet_trading_withdraw(
            action="to_funding",
            asset_id=2,
            amount="1",
            signer_wallet=ADDRESS,
            **_SIGNED,
            **values,
        ),
    ]
    for call in calls:
        error, seen = await _sent(call)
        assert isinstance(error, PolyesterValidationError), error
        assert field in str(error)
        assert seen == []


@pytest.mark.asyncio
@pytest.mark.parametrize("chain_id", [1.9, True, "137.0", "0x89", 0, -1, U64_MAX + 1])
async def test_validate_destination_refuses_non_exact_chain_ids(chain_id: Any) -> None:
    error, seen = await _sent(
        lambda c: c.trading_withdraws.validate_destination(
            destination_chain_id=chain_id, destination_address=ADDRESS
        )
    )
    assert isinstance(error, PolyesterValidationError), error
    assert seen == []


# --- GuardSigner and address-book chain IDs -----------------------------------


@pytest.mark.parametrize("chain_id", [1.5, 137.0, "137", True, 0, -1, U32_MAX + 1])
def test_guard_signer_chain_id_refuses_non_exact_values(chain_id: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="external_polychain_chain_id"):
        protected_action_args_to_proto(
            external_polychain_chain_id=chain_id, external_addresses=[ADDRESS]
        )


@pytest.mark.parametrize("chain_id", [1, 137, U32_MAX])
def test_guard_signer_chain_id_kept_exact(chain_id: int) -> None:
    args = protected_action_args_to_proto(
        external_polychain_chain_id=chain_id, external_addresses=[ADDRESS]
    )
    assert args.external_whitelist.polychain_chain_id == chain_id


def _entry(chain_id: Any):
    return create_entry_to_proto(
        subaccount_id=None,
        label="l",
        note="",
        address=ADDRESS,
        polychain_chain_id=chain_id,
        smart_account_address=None,
        tag_ids=None,
        new_tags=None,
    )


@pytest.mark.parametrize("chain_id", [1.9, 137.0, "137.0", True, 0, -1, U32_MAX + 1])
def test_address_book_chain_id_refuses_non_exact_values(chain_id: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="polychain_chain_id"):
        _entry(chain_id)


@pytest.mark.parametrize(
    ("chain_id", "expected"), [(1, 1), (137, 137), ("137", 137), (U32_MAX, U32_MAX)]
)
def test_address_book_chain_id_kept_exact(chain_id: Any, expected: int) -> None:
    assert _entry(chain_id).external.polychain_chain_id == expected


# --- on-chain calldata --------------------------------------------------------


@pytest.mark.parametrize("value", [10.5, 10.0, True, "10", Decimal("10")])
def test_chain_calldata_refuses_non_integer_amounts(value: Any) -> None:
    base: dict[str, Any] = {
        "funding_account": ADDRESS,
        "chain_id": 1,
        "z_token": ADDRESS,
        "withdraw_destination": b"x",
        "z_amount": 10,
        "max_fee": 1,
    }
    for field in ("chain_id", "z_amount", "max_fee"):
        with pytest.raises(PolyesterValidationError, match=field):
            encode_funding_withdraw_to_chain(**{**base, field: value})
    with pytest.raises(PolyesterValidationError, match="quantity_scaled"):
        encode_trading_gateway_deposit(
            trading_gateway=ADDRESS, u_asset_id=b"\x00" * 32, quantity_scaled=value
        )
    with pytest.raises(PolyesterValidationError, match="quantity_scaled"):
        encode_trading_gateway_deposit_to(
            trading_gateway=ADDRESS,
            to_account=ADDRESS,
            u_asset_id=b"\x00" * 32,
            quantity_scaled=value,
        )
    for field in ("nonce_space", "deadline"):
        with pytest.raises(PolyesterValidationError, match=field):
            encode_rotate_guard_signer(
                guard_registry=ADDRESS,
                new_signer=ADDRESS,
                approval=GuardApproval(**{field: value}),  # type: ignore[arg-type]
            )


@pytest.mark.parametrize("value", [137.0, True, "137", 0, 2**16])
def test_guard_destination_allowlist_chain_id_refuses_non_exact_values(value: Any) -> None:
    from polyester.chain.calldata import encode_add_allowed_external_destinations

    with pytest.raises(PolyesterValidationError, match="chain_id"):
        encode_add_allowed_external_destinations(
            funding_account=ADDRESS, chain_id=value, destinations=[ADDRESS]
        )


@pytest.mark.parametrize("key", [1.5, 1.9, True, "1.5", -1, 2**192])
def test_user_operation_nonce_key_refuses_non_exact_values(key: Any) -> None:
    from polyester.chain.userop import PolyesterSmartAccount

    account = PolyesterSmartAccount(owner_private_key="07" * 32)
    calls: list[Any] = []
    account._rpc.request = lambda *args: calls.append(args)  # type: ignore[method-assign]
    with pytest.raises(PolyesterValidationError, match="nonce key"):
        account.get_nonce(key=key)
    assert calls == []


@pytest.mark.parametrize(("key", "expected"), [(0, 0), (5, 5), ("5", 5), (2**192 - 1, 2**192 - 1)])
def test_user_operation_nonce_key_kept_exact(key: Any, expected: int) -> None:
    from polyester.chain.userop import PolyesterSmartAccount

    account = PolyesterSmartAccount(owner_private_key="07" * 32)
    calls: list[Any] = []

    def request(method: str, params: list[Any]) -> str:
        calls.append(params[0]["data"])
        return "0x1"

    account._rpc.request = request  # type: ignore[method-assign]
    account.get_nonce(key=key)
    assert int(calls[0][-48:], 16) == expected


# --- idempotency key: signed exactly as given ---------------------------------


def test_withdraw_idempotency_key_rule_is_the_contracts() -> None:
    from polyester.gen.buf.validate import validate_pb2

    field = withdraw_pb2.TradingWithdrawIntentPayload.DESCRIPTOR.fields_by_name["idempotency_key"]
    rules = field.GetOptions().Extensions[validate_pb2.field]
    # Only a minimum length: the SDK refuses an empty key and nothing else.
    assert str(rules.string).strip() == "min_len: 1"


@pytest.mark.parametrize("key", [" wd-x ", "wd-x", "  ", "\t", "é"])
def test_withdraw_idempotency_key_is_signed_unchanged(key: str) -> None:
    assert _payload(idempotency_key=key).idempotency_key == key
    prepared = _client().trading_withdraws.prepare_api_key_to_funding(
        asset_id=2, quantity="1", idempotency_key=key, deadline_ts_sec=DEADLINE, nonce=42
    )
    request = withdraw_pb2.CreateTradingWithdrawRequest.FromString(prepared.request_bytes)
    assert request.payload.idempotency_key == key


@pytest.mark.parametrize("key", ["", None, 42, b"wd-x"])
def test_withdraw_idempotency_key_refuses_empty_and_non_strings(key: Any) -> None:
    with pytest.raises(PolyesterValidationError, match="idempotency_key"):
        _payload(idempotency_key=key)
