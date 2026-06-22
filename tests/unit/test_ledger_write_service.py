from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.write.v1 import ledger_write_pb2
from polyester.services.ledger_write import AsyncLedgerWriteService
from tests.unit.support import CaptureUnary

_TRANSFER_RESPONSE = ledger_write_pb2.TransferTradingToTradingResponse(
    transfer_id="xfer-1",
    timestamp=99,
)


@pytest.mark.asyncio
async def test_transfer_trading_to_trading_uses_explicit_account_ids() -> None:
    capture = CaptureUnary(_TRANSFER_RESPONSE)
    with patch("polyester.services.ledger_write.unary_auth_decoded", capture):
        service = AsyncLedgerWriteService(transport=MagicMock())
        result = await service.transfer_trading_to_trading(
            from_account_id=10,
            to_account_id=20,
            ledger_id=3,
            quantity="1.5",
            request_id="req-1",
        )
    assert isinstance(capture.request, ledger_write_pb2.TransferTradingToTradingRequest)
    assert capture.request.from_account_id == 10
    assert capture.request.to_account_id == 20
    assert capture.request.ledger == 3
    assert capture.request.request_id == "req-1"
    assert result.transfer_id == "xfer-1"


@pytest.mark.asyncio
async def test_transfer_trading_to_trading_defaults_from_account_id() -> None:
    capture = CaptureUnary(_TRANSFER_RESPONSE)
    with patch("polyester.services.ledger_write.unary_auth_decoded", capture):
        service = AsyncLedgerWriteService(
            transport=MagicMock(),
            default_account_id=format_id(55),
        )
        await service.transfer_trading_to_trading(
            to_account_id=20,
            ledger_id=3,
            quantity="1",
        )
    assert capture.request.from_account_id == 55


@pytest.mark.asyncio
async def test_create_funding_user_transfer_builds_request() -> None:
    capture = CaptureUnary(ledger_write_pb2.CreateFundingUserTransferResponse(transfer_id="f-1"))
    with patch("polyester.services.ledger_write.unary_auth_decoded", capture):
        service = AsyncLedgerWriteService(transport=MagicMock(), default_account_id=1)
        await service.create_funding_user_transfer(
            to_account_id=2,
            ledger_id=7,
            quantity="0.5",
            intent_id="intent-abc",
        )
    assert isinstance(capture.request, ledger_write_pb2.CreateFundingUserTransferRequest)
    assert capture.request.intent_id == "intent-abc"
    assert capture.request.from_account_id == 1
    assert capture.request.to_account_id == 2
    assert capture.request.ledger == 7


@pytest.mark.asyncio
async def test_reserve_trading_withdraw_builds_request() -> None:
    capture = CaptureUnary(ledger_write_pb2.ReserveTradingWithdrawResponse(transfer_id="r-1"))
    with patch("polyester.services.ledger_write.unary_auth_decoded", capture):
        service = AsyncLedgerWriteService(transport=MagicMock(), default_account_id=88)
        await service.reserve_trading_withdraw(
            ledger_id=4,
            quantity="2",
            intent_id="reserve-1",
        )
    assert isinstance(capture.request, ledger_write_pb2.ReserveTradingWithdrawRequest)
    assert capture.request.account_id == 88
    assert capture.request.intent_id == "reserve-1"
    assert capture.request.ledger == 4


@pytest.mark.asyncio
async def test_release_trading_withdraw_reserve_builds_request() -> None:
    capture = CaptureUnary(
        ledger_write_pb2.ReleaseTradingWithdrawReserveResponse(transfer_id="rel-1")
    )
    with patch("polyester.services.ledger_write.unary_auth_decoded", capture):
        service = AsyncLedgerWriteService(transport=MagicMock(), default_account_id=88)
        await service.release_trading_withdraw_reserve(
            ledger_id=4,
            intent_id="reserve-1",
            close_scope="smoke",
        )
    assert isinstance(capture.request, ledger_write_pb2.ReleaseTradingWithdrawReserveRequest)
    assert capture.request.close_scope == "smoke"
    assert capture.request.intent_id == "reserve-1"


@pytest.mark.asyncio
async def test_ledger_write_requires_account_id_when_not_configured() -> None:
    service = AsyncLedgerWriteService(transport=MagicMock())
    with pytest.raises(PolyesterValidationError, match="account_id is required"):
        await service.reserve_trading_withdraw(ledger_id=1, quantity="1", intent_id="x")
