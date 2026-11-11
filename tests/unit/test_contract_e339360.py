"""Public contract e339360: version endpoint, wallet balances, account permissions,
assistant keys, Telegram links, withdrawal refusals, transfer codes and equity flags."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from google.protobuf.timestamp_pb2 import Timestamp
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

import polyester.errors as polyester_errors
from polyester import AsyncPolyester, Polyester
from polyester._wire import map_connect_error, protobuf_to_public_dict
from polyester.codecs.decode.api_keys import api_key_from_proto
from polyester.codecs.decode.lifecycle import lifecycle_reason_from_code
from polyester.codecs.decode.policies import api_policy_from_proto
from polyester.codecs.decode.ratelimit import rate_limit_detail_from_proto
from polyester.codecs.scalars import format_id
from polyester.codecs.spot_config import spot_config_from_dict
from polyester.codecs.wire_decode import decode_api_key, decode_ledger_transfer
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    auth_error_code,
    is_retryable_error,
)
from polyester.gen.auth.v1 import api_keys_pb2, auth_pb2, policies_pb2
from polyester.gen.auth.v1 import social_verification_pb2 as sv_pb2
from polyester.gen.chain.lifecycle.v1 import types_pb2 as lifecycle_types_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.v1 import catalog_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.gen.system.v1 import system_pb2
from polyester.services.social_verification import AsyncSocialVerificationService
from polyester.services.withdraw import AsyncWithdrawService
from tests.unit.support import CaptureUnary

AUTH_HEADERS = ("authorization", "x-api-key-id", "x-api-signature")
VERSION_PATH = "/system.v1.SystemService/GetVersion"
TEST_KEY_ID = "ak_e339360"
TEST_PRIVATE_KEY = "11" * 32


def _ok(message: system_pb2.GetVersionResponse) -> Response:
    return Response(message.SerializeToString(), status=200, content_type="application/proto")


class _VersionServer:
    def __init__(self, response: system_pb2.GetVersionResponse) -> None:
        self.response = response
        self.auth_header_seen = False
        self.calls = 0

    def handle(self, request: Request) -> Response:
        self.calls += 1
        if any(request.headers.get(name) for name in AUTH_HEADERS):
            self.auth_header_seen = True
        system_pb2.GetVersionRequest.FromString(request.get_data())
        return _ok(self.response)


def _serve_version(httpserver: HTTPServer, response: system_pb2.GetVersionResponse) -> tuple:
    server = _VersionServer(response)
    httpserver.expect_request(VERSION_PATH, method="POST").respond_with_handler(server.handle)
    return server, httpserver.url_for("").rstrip("/")


# --- system.v1.SystemService/GetVersion ------------------------------------------------------

_DEVNET_BUILD = system_pb2.GetVersionResponse(
    version="0.10.0-12-g4e21a2f09670",
    commit="4e21a2f0967068fc944f5229eead01985df301b9",
    environment="devnet",
)


async def test_get_version_reads_the_build_unsigned_even_with_credentials(
    httpserver: HTTPServer,
) -> None:
    server, url = _serve_version(httpserver, _DEVNET_BUILD)
    async with AsyncPolyester(
        api_url=url,
        api_key_id=TEST_KEY_ID,
        api_private_key=TEST_PRIVATE_KEY,
        hydrate_catalogs=False,
    ) as client:
        version = await client.get_version()
    assert server.calls == 1
    assert server.auth_header_seen is False
    # A build after a release keeps its suffix: it is not a semantic version.
    assert version.version == "0.10.0-12-g4e21a2f09670"
    assert version.commit == "4e21a2f0967068fc944f5229eead01985df301b9"
    assert version.environment == "devnet"
    assert version.release == "0.10.0"


async def test_get_version_keeps_an_environment_this_sdk_does_not_know(
    httpserver: HTTPServer,
) -> None:
    _, url = _serve_version(
        httpserver,
        system_pb2.GetVersionResponse(version="1.2.3", commit="a" * 40, environment="staging-eu"),
    )
    async with AsyncPolyester(api_url=url, hydrate_catalogs=False) as client:
        version = await client.get_version()
    assert version.environment == "staging-eu"
    assert version.release == "1.2.3"


def test_sync_client_get_version(httpserver: HTTPServer) -> None:
    _, url = _serve_version(httpserver, _DEVNET_BUILD)
    with Polyester(api_url=url, hydrate_catalogs=False) as client:
        version = client.get_version()
    assert version.environment == "devnet"
    assert version.version == "0.10.0-12-g4e21a2f09670"


# --- chain.withdraw.v1.WithdrawService/GetWalletBalances --------------------------------------

_WALLET = withdraw_pb2.GetWalletBalancesResponse(
    smart_account_address="0x1111111111111111111111111111111111111111",
    balances=[
        withdraw_pb2.WalletBalance(
            zipped_asset_id=12,
            unified_asset_id=7,
            chain_id=8453,
            ztoken_address="0x2222222222222222222222222222222222222222",
            amount_e18=u128_pb2.U128(hi=1, lo=5),
        ),
        withdraw_pb2.WalletBalance(
            zipped_asset_id=13,
            unified_asset_id=3,
            chain_id=1,
            ztoken_address="0x3333333333333333333333333333333333333333",
            amount_e18=u128_pb2.U128(lo=1_250_000_000_000_000_000),
        ),
    ],
)


async def test_get_wallet_balances_decodes_every_balance() -> None:
    capture = CaptureUnary(_WALLET)
    with patch("polyester.services.withdraw.unary_auth_decoded", capture):
        service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
        result = await service.get_wallet_balances()
    assert isinstance(capture.request, withdraw_pb2.GetWalletBalancesRequest)
    assert capture.request.subaccount_id == 0
    assert result.smart_account_address == "0x1111111111111111111111111111111111111111"
    first, second = result.balances
    assert (first.zipped_asset_id, first.unified_asset_id, first.chain_id) == (12, 7, 8453)
    assert first.ztoken_address == "0x2222222222222222222222222222222222222222"
    # U128 across both halves, kept exact.
    assert first.amount_e18 == str((1 << 64) + 5)
    assert second.amount_e18 == "1250000000000000000"
    assert second.amount == Decimal("1.25")


async def test_get_wallet_balances_sends_the_sub_account_or_the_default() -> None:
    capture = CaptureUnary(withdraw_pb2.GetWalletBalancesResponse())
    with patch("polyester.services.withdraw.unary_auth_decoded", capture):
        service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=format_id(42))
        empty = await service.get_wallet_balances()
        assert capture.request.subaccount_id == 42
        await service.get_wallet_balances(sub_account_id=77)
        assert capture.request.subaccount_id == 77
    assert empty.balances == []


def test_sync_withdraw_view_declares_get_wallet_balances() -> None:
    from polyester._sync_services import SyncWithdrawService

    assert "get_wallet_balances" in vars(SyncWithdrawService)


# --- PolicyAction account permissions ---------------------------------------------------------

_ACCOUNT_PERMISSIONS = {
    "CREATE_DEPOSIT_ADDRESS": 10,
    "READ_DEPOSIT_ADDRESSES": None,
    "READ_SUBACCOUNTS": None,
    "READ_SUBACCOUNT_ACTIVITY": None,
    "READ_SUBACCOUNT_MEMBERS": None,
    "READ_SUBACCOUNT_INVITES": None,
    "READ_GUARD_SIGNER_STATUS": None,
}


def test_account_permissions_decode_by_name_and_round_trip() -> None:
    names = list(_ACCOUNT_PERMISSIONS)
    values = [policies_pb2.PolicyAction.Value(name) for name in names]
    assert policies_pb2.PolicyAction.Value("CREATE_DEPOSIT_ADDRESS") == 10
    policy = api_policy_from_proto(policies_pb2.ApiPolicyView(id=1, actions=values))
    assert policy.actions == [name.lower() for name in names]
    assert [policies_pb2.PolicyAction.Value(a.upper()) for a in policy.actions] == values


def test_missing_account_permission_is_an_api_key_access_refusal() -> None:
    message = "api key policy does not allow READ_SUBACCOUNTS"
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
    assert "READ_SUBACCOUNTS" in str(err)
    assert not is_retryable_error(err)


# --- auth.v1 error codes and API key purpose --------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "AUTH_REPLAY_DETECTED",
        "AUTH_ASSISTANT_KEY_ACTION_NOT_ALLOWED",
        "AUTH_ASSISTANT_KEY_DEADLINE_TOO_FAR",
        "AUTH_ASSISTANT_KEY_PROOF_INVALID",
        "AUTH_ASSISTANT_KEY_REGISTRATION_EXPIRED",
    ],
)
def test_new_auth_codes_keep_their_names(name: str) -> None:
    code = auth_pb2.AuthErrorCode.Value(name)
    err = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "refused",
            details=[auth_pb2.AuthErrorDetail(code=code, message="refused")],
        )
    )
    assert auth_error_code(err) == name


def test_replay_detected_is_auth_code_63() -> None:
    assert auth_pb2.AuthErrorCode.Value("AUTH_REPLAY_DETECTED") == 63


@pytest.mark.parametrize(
    ("purpose", "label"),
    [
        (api_keys_pb2.STANDARD, "standard"),
        (api_keys_pb2.ASSISTANT, "assistant"),
        (api_keys_pb2.PURPOSE_UNSPECIFIED, ""),
    ],
)
def test_api_key_reads_its_purpose(purpose: int, label: str) -> None:
    key = api_key_from_proto(api_keys_pb2.ApiKey(key_id="k1", purpose=purpose))
    assert key.purpose == label


@pytest.mark.parametrize(
    ("wire", "label"),
    [("STANDARD", "standard"), ("ASSISTANT", "assistant"), ("PURPOSE_UNSPECIFIED", ""), (None, "")],
)
def test_api_key_json_reads_its_purpose(wire: str | None, label: str) -> None:
    data = {"keyId": "k1"}
    if wire is not None:
        data["purpose"] = wire
    assert decode_api_key(data).purpose == label


# --- Telegram social verification -------------------------------------------------------------


async def test_social_verification_reads_telegram() -> None:
    capture = CaptureUnary(
        sv_pb2.GetSocialVerificationResponse(
            verification=sv_pb2.SocialVerification(
                provider=sv_pb2.TELEGRAM,
                status=sv_pb2.STATUS_AWAITING_CONFIRMATION,
                handle="alice",
                display_name="Alice",
                provider_user_id="7654321098",
            )
        )
    )
    with patch("polyester.services.social_verification.unary_auth_decoded", capture):
        result = await AsyncSocialVerificationService(MagicMock()).get(provider="telegram")
    assert capture.request.provider == sv_pb2.TELEGRAM
    verification = result.raw["verification"]
    assert verification["status"] == "STATUS_AWAITING_CONFIRMATION"
    assert verification["displayName"] == "Alice"
    # A 64-bit Telegram user ID stays a string.
    assert verification["providerUserId"] == "7654321098"


# --- chain.lifecycle.v1 -----------------------------------------------------------------------


def test_compliance_transfer_reason_has_its_label() -> None:
    code = int(lifecycle_types_pb2.ZIPPER_COMPLIANCE_TRANSFERRED)
    assert lifecycle_reason_from_code(code) == "zipper_compliance_transferred"


# --- chain.withdraw.v1 refusals ---------------------------------------------------------------


def _withdraw_error(code: int, **fields: object) -> BaseException:
    return map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "refused",
            details=[withdraw_pb2.ErrorDetail(code=code, **fields)],
        )
    )


def test_cooling_down_destination_says_when_it_can_be_paid() -> None:
    payable_from = Timestamp()
    payable_from.FromDatetime(datetime(2026, 11, 11, 14, tzinfo=UTC))
    err = _withdraw_error(
        withdraw_pb2.ERROR_CODE_EXTERNAL_DESTINATION_COOLING_DOWN,
        field_path="destination_address",
        payable_from=payable_from,
    )
    assert isinstance(err, polyester_errors.PolyesterWithdrawError)
    assert isinstance(err, PolyesterApiError)
    assert not isinstance(err, PolyesterAuthError)
    assert err.code == "ERROR_CODE_EXTERNAL_DESTINATION_COOLING_DOWN"
    assert err.payable_from == datetime(2026, 11, 11, 14, tzinfo=UTC)
    assert err.field_path == "destination_address"
    assert err.min_floor_e18 is None
    # Not before payable_from: an immediate retry is refused the same way.
    assert not is_retryable_error(err)


def test_min_amount_below_floor_carries_the_floor_and_field() -> None:
    err = _withdraw_error(
        withdraw_pb2.ERROR_CODE_MIN_AMOUNT_BELOW_FLOOR,
        field_path="destinations[0].min_amount_e18",
        min_floor_e18=u128_pb2.U128(lo=400_000_000_000_000_000),
    )
    assert isinstance(err, polyester_errors.PolyesterWithdrawError)
    assert err.code == "ERROR_CODE_MIN_AMOUNT_BELOW_FLOOR"
    assert err.field_path == "destinations[0].min_amount_e18"
    assert err.min_floor_e18 == "400000000000000000"
    assert err.min_floor == Decimal("0.4")
    assert err.payable_from is None


@pytest.mark.parametrize(
    "name",
    [
        "ERROR_CODE_DESTINATION_INVALID",
        "ERROR_CODE_ROUTE_UNSUPPORTED",
        "ERROR_CODE_VERSION_CONFLICT",
    ],
)
def test_new_withdraw_codes_keep_their_names(name: str) -> None:
    err = _withdraw_error(withdraw_pb2.ErrorCode.Value(name))
    assert isinstance(err, polyester_errors.PolyesterWithdrawError)
    assert err.code == name
    assert err.field_path is None


# --- ledger.v1.TransferCode.WITHDRAW_FAILED ---------------------------------------------------


def test_withdraw_failed_transfer_code() -> None:
    assert catalog_pb2.TransferCode.Value("WITHDRAW_FAILED") == 1075
    for spelling in ("withdraw_failed", "WITHDRAW_FAILED", 1075):
        transfer = decode_ledger_transfer({"transferCode": spelling, "isDebit": True})
        assert transfer.transfer_type == 1075
        assert transfer.is_debit is True


# --- marketdata.v1.AssetConfig.included_in_equity ---------------------------------------------


def test_spot_config_assets_keep_included_in_equity_presence() -> None:
    response = marketdata_pb2.GetSpotConfigResponse(
        assets=[
            marketdata_pb2.AssetConfig(
                asset="BTC", ledger_id=3, quantity_scale=8, included_in_equity=True
            ),
            marketdata_pb2.AssetConfig(
                asset="ZTKN", ledger_id=9, quantity_scale=18, included_in_equity=False
            ),
            marketdata_pb2.AssetConfig(asset="OLD", ledger_id=4, quantity_scale=6),
        ]
    )
    config = spot_config_from_dict(protobuf_to_public_dict(response))
    by_asset = {asset.asset: asset for asset in config.assets}
    assert by_asset["BTC"].included_in_equity is True
    assert by_asset["ZTKN"].included_in_equity is False
    # Absent means unknown, never "outside equity".
    assert by_asset["OLD"].included_in_equity is None
    assert (by_asset["BTC"].ledger_id, by_asset["BTC"].quantity_scale) == (3, 8)


def test_spot_config_rest_spelling_reads_included_in_equity() -> None:
    config = spot_config_from_dict(
        {"assets": [{"asset": "BTC", "ledgerId": 3, "includedInEquity": False}]}
    )
    assert config.assets[0].included_in_equity is False


# --- polyester.ratelimit.v1.PolicyClass -------------------------------------------------------


@pytest.mark.parametrize("name", ["ASSISTANT_MESSAGE", "ASSISTANT_CONTROL", "ASSISTANT_READ"])
def test_assistant_policy_classes_read_by_name(name: str) -> None:
    detail = rate_limit_detail_from_proto(
        ratelimit_pb2.RateLimitDetail(policy_class=ratelimit_pb2.PolicyClass.Value(name))
    )
    assert detail.policy_class == name


# --- AUTH_REPLAY_DETECTED is a final API-key refusal ------------------------------------------


def test_connect_replay_detected_is_a_final_auth_error() -> None:
    err = map_connect_error(
        ConnectError(
            Code.UNAUTHENTICATED,
            "replayed",
            details=[
                auth_pb2.AuthErrorDetail(code=auth_pb2.AUTH_REPLAY_DETECTED, message="replayed")
            ],
        )
    )
    assert isinstance(err, PolyesterAuthError)
    assert auth_error_code(err) == polyester_errors.AUTH_REPLAY_DETECTED == "AUTH_REPLAY_DETECTED"
    assert err.status_code == 401
    # The server already saw that exact signed request: never retry it as is.
    assert not is_retryable_error(err)


async def test_rest_replay_detected_is_the_same_auth_error(httpserver: HTTPServer) -> None:
    from tests.unit.test_auth_error_codes import _rest_error

    err = await _rest_error(
        httpserver, 401, {"status": 401, "code": "REPLAY_DETECTED", "title": "Unauthorized"}
    )
    assert isinstance(err, PolyesterAuthError)
    assert auth_error_code(err) == "AUTH_REPLAY_DETECTED"
    assert err.status_code == 401
    assert not is_retryable_error(err)
