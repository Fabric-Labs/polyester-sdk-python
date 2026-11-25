"""Public contract a3e3784: flow IDs, memo rules, account permissions, transfer codes."""

from __future__ import annotations

import base64
from typing import Any

import msgspec
import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.catalogs.zipper import build_zipper_catalog_data
from polyester.catalogs.zipper_supply import patch_zipper_catalog_supply
from polyester.codecs.decode.internal_transfers import internal_transfer_from_proto
from polyester.codecs.decode.policies import api_policy_from_proto, subaccount_policy_from_proto
from polyester.codecs.decode.transfers import ledger_transfer_from_proto
from polyester.codecs.decode.zipper import deposit_withdraw_config_from_proto
from polyester.codecs.realtime_decode import decode_ledger_transfer_batch_bytes
from polyester.codecs.wire_decode import decode_internal_transfer_result, decode_ledger_transfer
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    auth_error_code,
    is_session_required,
)
from polyester.gen.auth.v1 import auth_pb2, policies_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.chain.zipper.v1 import zipper_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.v1 import catalog_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2
from polyester.models.zipper import ZippedAssetSupplyUpdate
from tests.unit.test_auth_error_codes import _rest_error

# --- CreateInternalTransferResponse.flow_id -------------------------------------------------


def test_internal_transfer_receipt_keeps_flow_id() -> None:
    result = internal_transfer_from_proto(
        internal_transfer_pb2.CreateInternalTransferResponse(
            request_id="r-1",
            transfer_id="254811058965469215576143367742519946794",
            asset_id=2,
            amount_e18=u128_pb2.U128(lo=10**18),
            status=internal_transfer_pb2.INTERNAL_TRANSFER_STATUS_ACCEPTED,
            flow_id="flow-7",
        )
    )
    assert result.flow_id == "flow-7"
    assert msgspec.to_builtins(result)["flow_id"] == "flow-7"


def test_internal_transfer_receipt_without_flow_id_reads_empty() -> None:
    result = internal_transfer_from_proto(
        internal_transfer_pb2.CreateInternalTransferResponse(request_id="r-1", transfer_id="9")
    )
    assert result.flow_id == ""
    assert "flow_id" not in msgspec.to_builtins(result)


def test_internal_transfer_json_receipt_keeps_flow_id() -> None:
    result = decode_internal_transfer_result(
        {"requestId": "r-1", "transferId": "9", "flowId": "flow-7"}
    )
    assert result.flow_id == "flow-7"


# --- ChainConfig memo rule --------------------------------------------------------------------

_HINT = "Numeric, 1 to 10 digits; e.g. 12345 (not 0x...)"


def _zipper_config(**chain: Any) -> zipper_pb2.GetDepositWithdrawConfigResponse:
    return zipper_pb2.GetDepositWithdrawConfigResponse(
        chains=[zipper_pb2.ChainConfig(chain_id=7, code="XRP", **chain)],
        assets=[
            zipper_pb2.AssetConfig(
                asset="XRP",
                quantity_scale=6,
                variants=[zipper_pb2.AssetChainVariant(zipped_asset_id=70, chain_id=7)],
            )
        ],
    )


@pytest.mark.parametrize(
    ("requirement", "label"),
    [
        (zipper_pb2.REQUIRED, "required"),
        (zipper_pb2.OPTIONAL, "optional"),
        (zipper_pb2.NOT_SUPPORTED, "not_supported"),
        (zipper_pb2.MEMO_UNSPECIFIED, ""),
        (9, "9"),
    ],
)
def test_chain_config_memo_requirement_label(requirement: int, label: str) -> None:
    cfg = deposit_withdraw_config_from_proto(_zipper_config(memo_requirement=requirement))
    assert cfg.chains[0].memo_requirement == label


def test_chain_config_memo_label_and_hint_are_kept_verbatim() -> None:
    cfg = deposit_withdraw_config_from_proto(
        _zipper_config(
            memo_requirement=zipper_pb2.OPTIONAL,
            memo_label="Destination tag",
            memo_format_hint=_HINT,
        )
    )
    chain = cfg.chains[0]
    assert (chain.memo_requirement, chain.memo_label, chain.memo_format_hint) == (
        "optional",
        "Destination tag",
        _HINT,
    )
    encoded = msgspec.to_builtins(chain)
    assert encoded["memo_requirement"] == "optional"
    assert encoded["memo_format_hint"] == _HINT


def test_enriched_zipper_catalog_chains_carry_the_memo_rule() -> None:
    cfg = deposit_withdraw_config_from_proto(
        _zipper_config(
            memo_requirement=zipper_pb2.REQUIRED, memo_label="Memo", memo_format_hint=_HINT
        )
    )
    catalog = build_zipper_catalog_data(cfg)
    chain = catalog.assets[0].chains[0]
    assert (chain.memo_requirement, chain.memo_label, chain.memo_format_hint) == (
        "required",
        "Memo",
        _HINT,
    )
    patched = patch_zipper_catalog_supply(
        catalog, [ZippedAssetSupplyUpdate(zipped_asset_id=70, supply="5")]
    )
    chain = patched.assets[0].chains[0]
    assert chain.supply == "5"
    assert (chain.memo_requirement, chain.memo_label, chain.memo_format_hint) == (
        "required",
        "Memo",
        _HINT,
    )


# --- PolicyAction account permissions ---------------------------------------------------------

_NEW_ACTIONS = [
    "READ_API_KEYS",
    "READ_API_POLICIES",
    "READ_SUBACCOUNT_POLICIES",
    "READ_SUBACCOUNT_PERMISSIONS",
    "READ_VIP_STATUS",
    "READ_SOCIAL_VERIFICATION",
    "READ_PROFILE",
    "READ_ACCOUNT_DIRECTORY",
    "READ_WITHDRAW_VALIDATION",
    "READ_DAILY_CLAIMS",
    "CLAIM_DAILY_REWARD",
    "READ_CHECKPOINTS",
    "READ_REWARDS",
]


def test_new_policy_actions_decode_by_name_and_round_trip() -> None:
    values = [policies_pb2.PolicyAction.Value(name) for name in _NEW_ACTIONS]
    api = api_policy_from_proto(policies_pb2.ApiPolicyView(id=1, actions=values))
    sub = subaccount_policy_from_proto(policies_pb2.SubaccountPolicyView(id=1, actions=values))
    expected = [name.lower() for name in _NEW_ACTIONS]
    assert api.actions == expected
    assert sub.actions == expected
    assert [policies_pb2.PolicyAction.Value(name.upper()) for name in api.actions] == values


# --- ledger.v1.TransferCode -------------------------------------------------------------------

_NEW_TRANSFER_CODES = {
    "trading_withdraw_fee_leg": 1066,
    "quickswap_polyester_fee": 1067,
    "quickswap_broker_fee": 1068,
    "quickswap_affiliate_fee": 1069,
    "fee_sweep": 1072,
    "fee_refill": 1073,
    "system_adjustment": 1074,
}


def test_generated_transfer_codes_match_the_contract() -> None:
    for label, number in _NEW_TRANSFER_CODES.items():
        assert catalog_pb2.TransferCode.Value(label.upper()) == number


def _system_row(*, is_debit: bool) -> ledger_read_pb2.TransferRow:
    return ledger_read_pb2.TransferRow(
        asset_id=2,
        amount_e18=u128_pb2.U128(lo=5 * 10**18),
        transfer_code=catalog_pb2.SYSTEM_ADJUSTMENT,
        account_code=catalog_pb2.TRADING,
        is_debit=is_debit,
        transfer_id="11",
        source=ledger_read_pb2.TransferSide(kind=ledger_read_pb2.SYSTEM_ACCOUNT),
    )


def test_system_account_seeding_credit_reads_as_a_credit() -> None:
    row = _system_row(is_debit=False)
    for transfer in (
        ledger_transfer_from_proto(row),
        decode_ledger_transfer_batch_bytes(
            ledger_read_pb2.TransferRowBatch(events=[row]).SerializeToString()
        )[0],
    ):
        assert transfer.transfer_type == 1074
        assert transfer.is_debit is False
        assert transfer.source is not None and transfer.source.kind == "system_account"


def test_system_adjustment_debit_correction_reads_as_a_debit() -> None:
    row = _system_row(is_debit=True)
    for transfer in (
        ledger_transfer_from_proto(row),
        decode_ledger_transfer_batch_bytes(
            ledger_read_pb2.TransferRowBatch(events=[row]).SerializeToString()
        )[0],
    ):
        assert transfer.transfer_type == 1074
        assert transfer.is_debit is True


@pytest.mark.parametrize(("label", "number"), sorted(_NEW_TRANSFER_CODES.items()))
def test_json_transfer_labels_decode_to_their_codes(label: str, number: int) -> None:
    for key in ("transferCode", "transfer_code", "type"):
        for spelling in (label, label.upper(), number):
            transfer = decode_ledger_transfer({key: spelling, "isDebit": False})
            assert transfer.transfer_type == number, (key, spelling)


def test_json_system_adjustment_keeps_its_direction() -> None:
    credit = decode_ledger_transfer({"transferCode": "system_adjustment", "isDebit": False})
    debit = decode_ledger_transfer({"transferCode": "system_adjustment", "isDebit": True})
    assert (credit.transfer_type, credit.is_debit) == (1074, False)
    assert (debit.transfer_type, debit.is_debit) == (1074, True)


def test_json_unknown_transfer_label_reads_unspecified() -> None:
    assert decode_ledger_transfer({"transferCode": "future_reason"}).transfer_type == 0


# --- path and body ID mismatch ----------------------------------------------------------------


async def test_rest_path_body_id_mismatch_stays_specific(httpserver: Any) -> None:
    # Orders and auth both define it; REST reads it as the order code, as it
    # reads every code the orders service names, never as a generic refusal.
    err = await _rest_error(
        httpserver, 400, {"code": "PATH_BODY_ID_MISMATCH", "detail": "path and body IDs differ"}
    )
    assert isinstance(err, PolyesterApiError)
    assert err.code == "ERROR_CODE_PATH_BODY_ID_MISMATCH"
    assert str(err) == "path and body IDs differ"


async def _connect_error(httpserver: Any, detail_type: str, detail: Any) -> BaseException:
    body = {
        "code": "invalid_argument",
        "message": "path and body IDs differ",
        "details": [
            {"type": detail_type, "value": base64.b64encode(detail.SerializeToString()).decode()}
        ],
    }
    return await _rest_error(httpserver, 400, body, content_type="application/json")


async def test_connect_orders_path_body_id_mismatch_keeps_its_code(httpserver: Any) -> None:
    err = await _connect_error(
        httpserver,
        "orders.v1.ErrorDetail",
        orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_PATH_BODY_ID_MISMATCH),
    )
    assert isinstance(err, PolyesterApiError)
    assert err.code == "ERROR_CODE_PATH_BODY_ID_MISMATCH"


async def test_connect_auth_path_body_id_mismatch_keeps_its_code(httpserver: Any) -> None:
    err = await _connect_error(
        httpserver,
        "auth.v1.AuthErrorDetail",
        auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_PATH_BODY_ID_MISMATCH),
    )
    assert auth_error_code(err) == "AUTH_PATH_BODY_ID_MISMATCH"


# --- missing account permission ---------------------------------------------------------------


def test_missing_account_permission_names_it_and_is_not_session_required() -> None:
    message = "api key policy does not allow READ_VIP_STATUS"
    err = map_connect_error(
        ConnectError(
            Code.PERMISSION_DENIED,
            message,
            details=[
                auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_API_KEY_ACCESS_DENIED, message=message)
            ],
        )
    )
    assert isinstance(err, PolyesterApiError)
    assert auth_error_code(err) == "AUTH_API_KEY_ACCESS_DENIED"
    assert "READ_VIP_STATUS" in str(err)
    assert not is_session_required(err)


def test_destination_check_without_its_permission_is_a_withdraw_refusal() -> None:
    message = "api key policy does not allow READ_WITHDRAW_VALIDATION"
    err = map_connect_error(
        ConnectError(
            Code.PERMISSION_DENIED,
            message,
            details=[withdraw_pb2.ErrorDetail(code=withdraw_pb2.ERROR_CODE_PERMISSION_DENIED)],
        )
    )
    assert isinstance(err, PolyesterAuthError)
    assert err.code == "ERROR_CODE_PERMISSION_DENIED"
    assert "READ_WITHDRAW_VALIDATION" in str(err)
