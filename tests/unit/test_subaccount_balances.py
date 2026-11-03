"""``sub_accounts.get(include_balances=True)`` returns the sub-account's balances."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester import AUTH_TEMPORARILY_UNAVAILABLE, is_retryable_error
from polyester.errors import PolyesterApiError
from polyester.gen.auth.v1 import subaccounts_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.models import AssetBalance, BalancesList
from polyester.services.sub_accounts import AsyncSubAccountsService
from tests.unit.support import CaptureUnary

SUB = 42


def _response(*, with_balances: bool) -> subaccounts_pb2.GetSubaccountResponse:
    response = subaccounts_pb2.GetSubaccountResponse(
        subaccount=subaccounts_pb2.Subaccount(id=SUB, label="bot")
    )
    if with_balances:
        response.balances.CopyFrom(
            ledger_read_pb2.GetBalancesResponse(
                balances=[
                    ledger_read_pb2.AssetBalance(
                        asset_id=1,
                        trading=u128_pb2.U128(lo=1_500_000_000_000_000_000),
                        available=u128_pb2.U128(lo=1_500_000_000_000_000_000),
                        trading_revision=3,
                    )
                ]
            )
        )
    return response


async def _get(capture: CaptureUnary, **kwargs: object):
    service = AsyncSubAccountsService(MagicMock(), None)
    with patch("polyester.services.sub_accounts.unary_auth_decoded", capture):
        return await service.get(sub_account_id=str(SUB), **kwargs)


@pytest.mark.asyncio
async def test_get_requests_and_parses_balances_when_asked() -> None:
    capture = CaptureUnary(_response(with_balances=True))
    result = await _get(capture, include_balances=True)
    assert isinstance(capture.request, subaccounts_pb2.GetSubaccountRequest)
    assert capture.request.include_balances is True
    assert result.balances == BalancesList(
        balances=[
            AssetBalance(
                asset_id=1,
                trading="1500000000000000000",
                funding="0",
                reserved="0",
                available="1500000000000000000",
                trading_revision=3,
                funding_revision=0,
            )
        ]
    )


@pytest.mark.asyncio
async def test_get_with_balances_asked_but_none_held_reads_an_empty_list() -> None:
    response = _response(with_balances=False)
    response.balances.SetInParent()
    result = await _get(CaptureUnary(response), include_balances=True)
    assert result.balances == BalancesList(balances=[])


@pytest.mark.asyncio
async def test_get_without_include_balances_returns_no_balances() -> None:
    capture = CaptureUnary(_response(with_balances=False))
    result = await _get(capture)
    assert isinstance(capture.request, subaccounts_pb2.GetSubaccountRequest)
    assert capture.request.include_balances is False
    assert result.balances is None


def test_balances_temporarily_unavailable_is_retryable() -> None:
    err = PolyesterApiError("balances unavailable", code=AUTH_TEMPORARILY_UNAVAILABLE)
    assert is_retryable_error(err)
