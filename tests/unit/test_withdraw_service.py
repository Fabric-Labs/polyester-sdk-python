from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.services.withdraw import AsyncWithdrawService
from tests.unit.support import CaptureUnary

_WITHDRAW_RESPONSE = withdraw_pb2.CreateTradingWithdrawResponse(intent_id="intent-99")


@pytest.mark.asyncio
async def test_create_to_funding_builds_signed_request() -> None:
    capture = CaptureUnary(_WITHDRAW_RESPONSE)
    with patch("polyester.services.withdraw.unary_auth_decoded", capture):
        service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
        result = await service.create_to_funding(
            asset_id=3,
            quantity="10",
            payload_signature=b"\x01\x02",
            idempotency_key="idem-1",
            nonce=42,
            deadline_ts_sec=1_800_000_000,
        )
    assert isinstance(capture.request, withdraw_pb2.CreateTradingWithdrawRequest)
    assert capture.request.payload.action == withdraw_pb2.TO_FUNDING
    assert capture.request.payload.asset_id == 3
    assert capture.request.payload.idempotency_key == "idem-1"
    assert capture.request.payload_signature == b"\x01\x02"
    assert result.intent_id == "intent-99"


@pytest.mark.asyncio
async def test_create_to_funding_rejects_missing_signature() -> None:
    service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="payload_signature is required"):
        await service.create_to_funding(
            asset_id=1,
            quantity="1",
            payload_signature=b"",
            idempotency_key="missing-signature",
            nonce=42,
        )


@pytest.mark.asyncio
async def test_create_to_external_chain_requires_destination() -> None:
    service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="destination_address is required"):
        await service.create_to_external_chain(
            asset_id=1,
            quantity="1",
            payload_signature=b"\xaa",
            destination_chain_id=1,
            destination_address="",
            idempotency_key="missing-destination",
            nonce=42,
            deadline_ts_sec=1_800_000_000,
        )


@pytest.mark.asyncio
async def test_create_to_external_chain_builds_payload() -> None:
    capture = CaptureUnary(_WITHDRAW_RESPONSE)
    with patch("polyester.services.withdraw.unary_auth_decoded", capture):
        service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
        await service.create_to_external_chain(
            asset_id=5,
            quantity="0.1",
            payload_signature=b"\xbb",
            destination_chain_id=42161,
            destination_address="0xabc",
            idempotency_key="ext-1",
            nonce=42,
            deadline_ts_sec=1_800_000_000,
        )
    assert capture.request.payload.action == withdraw_pb2.TO_EXTERNAL_CHAIN
    assert capture.request.payload.destination_chain_id == 42161
    assert capture.request.payload.destination_address == "0xabc"


@pytest.mark.asyncio
async def test_create_wallet_trading_withdraw_sets_subaccount_id() -> None:
    capture = CaptureUnary(_WITHDRAW_RESPONSE)
    with patch("polyester.services.withdraw.unary_auth_decoded", capture):
        service = AsyncWithdrawService(
            transport=MagicMock(),
            default_sub_account_id=format_id(12),
        )
        await service.create_wallet_trading_withdraw(
            action="to_funding",
            asset_id=1,
            amount="1",
            idempotency_key="wallet-1",
            payload_signature=b"\xcc",
            signer_wallet="0xsigner",
            nonce=42,
            deadline_ts_sec=1_800_000_000,
        )
    assert isinstance(capture.request, withdraw_pb2.CreateWalletTradingWithdrawRequest)
    assert capture.request.signer_wallet == "0xsigner"
    assert capture.request.subaccount_id == 12


@pytest.mark.asyncio
async def test_create_to_funding_rejects_empty_idempotency_key() -> None:
    service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="idempotency_key"):
        await service.create_to_funding(
            asset_id=1,
            quantity="1",
            payload_signature=b"\x01",
            idempotency_key="",
            nonce=42,
            deadline_ts_sec=1_800_000_000,
        )


@pytest.mark.asyncio
async def test_create_to_funding_rejects_zero_nonce() -> None:
    service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="nonce"):
        await service.create_to_funding(
            asset_id=1,
            quantity="1",
            payload_signature=b"\x01",
            idempotency_key="stable-withdraw",
            nonce=0,
            deadline_ts_sec=1_800_000_000,
        )


@pytest.mark.asyncio
async def test_validate_destination_builds_request() -> None:
    capture = CaptureUnary(
        withdraw_pb2.ValidateWithdrawDestinationResponse(
            valid=True,
            code=withdraw_pb2.VALID,
            message="ok",
            canonical_destination_address="0xabc",
        )
    )
    with patch("polyester.services.withdraw.unary_auth_decoded", capture):
        service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
        result = await service.validate_destination(
            destination_chain_id=6,
            destination_address="0xAbC",
        )
    assert isinstance(capture.request, withdraw_pb2.ValidateWithdrawDestinationRequest)
    assert capture.request.destination_chain_id == 6
    assert capture.request.destination_address == "0xAbC"
    assert result.valid is True
    assert result.code == "valid"
    assert result.canonical_destination_address == "0xabc"


@pytest.mark.asyncio
async def test_validate_destination_rejects_missing_inputs() -> None:
    service = AsyncWithdrawService(transport=MagicMock(), default_sub_account_id=None)
    with pytest.raises(PolyesterValidationError, match="destination_chain_id"):
        await service.validate_destination(
            destination_chain_id=0,
            destination_address="0xabc",
        )
    with pytest.raises(PolyesterValidationError, match="destination_address"):
        await service.validate_destination(
            destination_chain_id=6,
            destination_address="",
        )
