"""An int sub-account or account ID is the numeric ID on every account-scope path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polyester.codecs.scalars import format_id, id_to_int
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import OrderId
from polyester.services._scope import (
    ScopedSubAccountMixin,
    resolve_account_id,
    resolve_sub_account_from_scope,
)
from polyester.services.balances import AsyncBalancesService
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary

# 42 is a valid base58 string too ("42" decodes to 175); the large value is a
# valid uint64 whose decimal digits are not.
IDS = [42, 9876543219876543219, 1, 2**64 - 1]


class _Scoped(ScopedSubAccountMixin):
    def __init__(self, default: str | None = None) -> None:
        self._default_sub_account_id = default


@pytest.mark.parametrize("value", IDS)
def test_int_sub_account_id_keeps_its_value(value: int) -> None:
    resolved = _Scoped()._resolve_sub_account_id(value)
    assert resolved is not None
    assert id_to_int(resolved) == value


@pytest.mark.parametrize("value", IDS)
@pytest.mark.parametrize("key", ["subaccountId", "sub_account_id"])
def test_int_account_selector_keeps_its_value(value: int, key: str) -> None:
    resolved = _Scoped()._resolve_sub_account_id(account={key: value})  # type: ignore[dict-item]
    assert resolved is not None
    assert id_to_int(resolved) == value


@pytest.mark.parametrize("value", IDS)
def test_int_scope_overrides_a_default(value: int) -> None:
    resolved = resolve_sub_account_from_scope(sub_account_id=value, default="ignored")  # type: ignore[arg-type]
    assert resolved is not None
    assert id_to_int(resolved) == value


@pytest.mark.parametrize("value", IDS)
def test_canonical_public_string_is_unchanged(value: int) -> None:
    public = format_id(value)
    assert _Scoped()._resolve_sub_account_id(public) == public
    assert _Scoped()._resolve_sub_account_id(account={"subaccountId": public}) == public


@pytest.mark.parametrize("value", [True, False, -1, 2**64])
def test_invalid_int_scope_is_refused(value: int) -> None:
    with pytest.raises(PolyesterValidationError):
        _Scoped()._resolve_sub_account_id(value)
    with pytest.raises(PolyesterValidationError):
        _Scoped()._resolve_sub_account_id(account={"subaccountId": value})  # type: ignore[dict-item]


@pytest.mark.parametrize("value", IDS)
def test_int_account_id_keeps_its_value(value: int) -> None:
    assert id_to_int(resolve_account_id(value, None)) == value
    assert id_to_int(resolve_account_id(None, value)) == value


@pytest.mark.asyncio
@pytest.mark.parametrize("value", IDS)
async def test_balances_list_sends_the_int_sub_account(value: int) -> None:
    capture = CaptureUnary(ledger_read_pb2.GetBalancesResponse())
    service = AsyncBalancesService(MagicMock())
    with patch("polyester.services.balances.unary_auth_decoded", capture):
        await service.list(sub_account_id=value)
        assert capture.request.subaccount_id == value
        await service.list(account={"subaccountId": value})  # type: ignore[dict-item]
        assert capture.request.subaccount_id == value
        await service.list(sub_account_id=format_id(value))
        assert capture.request.subaccount_id == value


@pytest.mark.asyncio
async def test_order_write_sends_the_int_sub_account() -> None:
    capture = CaptureUnary(orders_pb2.BatchCancelOrdersResponse())
    service = AsyncOrdersService(MagicMock(), MagicMock(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.batch_cancel(sub_account_id=42, items=[{"key": OrderId(7)}])  # type: ignore[arg-type]
    assert capture.request.subaccount_id == 42


@pytest.mark.asyncio
@pytest.mark.parametrize("value", IDS)
async def test_balances_subscribe_uses_the_int_account_channel(value: int) -> None:
    realtime = MagicMock()
    realtime.subscribe_proto = AsyncMock(return_value=object())
    service = AsyncBalancesService(MagicMock(), realtime=realtime)
    await service.subscribe(account_id=value)
    channel = realtime.subscribe_proto.await_args.args[0]
    assert channel == f"private:ledger:balances:{format_id(value)}:proto"
