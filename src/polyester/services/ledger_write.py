from __future__ import annotations

from polyester.codecs.decode.ledger_write import ledger_write_transfer_result_from_proto
from polyester.codecs.ledger_amounts import LEDGER_SCALE
from polyester.codecs.ledger_write import (
    create_funding_user_transfer_to_proto,
    release_trading_withdraw_reserve_to_proto,
    reserve_trading_withdraw_to_proto,
    transfer_trading_to_trading_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.write.v1.ledger_write_connect import LedgerWriteServiceClient
from polyester.models import LedgerWriteTransferResult
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import resolve_sub_account_id


class AsyncLedgerWriteService(BaseService):
    def __init__(
        self,
        transport,
        default_sub_account_id: str | None = None,
        default_account_id: str | int | None = None,
    ) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id

    async def transfer_trading_to_trading(
        self,
        *,
        to_account_id: str | int,
        ledger_id: int,
        quantity: str,
        from_account_id: str | int | None = None,
        request_id: str | None = None,
        quantity_scale: int = LEDGER_SCALE,
    ) -> LedgerWriteTransferResult:
        source = self._resolve_account_id(from_account_id)
        request = transfer_trading_to_trading_to_proto(
            from_account_id=source,
            to_account_id=to_account_id,
            ledger_id=ledger_id,
            quantity=quantity,
            request_id=request_id,
            quantity_scale=quantity_scale,
        )
        return await self._call(request, LedgerWriteServiceClient.transfer_trading_to_trading)

    async def create_funding_user_transfer(
        self,
        *,
        to_account_id: str | int,
        ledger_id: int,
        quantity: str,
        from_account_id: str | int | None = None,
        intent_id: str | None = None,
        quantity_scale: int = LEDGER_SCALE,
    ) -> LedgerWriteTransferResult:
        source = self._resolve_account_id(from_account_id)
        request = create_funding_user_transfer_to_proto(
            from_account_id=source,
            to_account_id=to_account_id,
            ledger_id=ledger_id,
            quantity=quantity,
            intent_id=intent_id,
            quantity_scale=quantity_scale,
        )
        return await self._call(request, LedgerWriteServiceClient.create_funding_user_transfer)

    async def reserve_trading_withdraw(
        self,
        *,
        ledger_id: int,
        quantity: str,
        account_id: str | int | None = None,
        intent_id: str | None = None,
        quantity_scale: int = LEDGER_SCALE,
    ) -> LedgerWriteTransferResult:
        request = reserve_trading_withdraw_to_proto(
            account_id=self._resolve_account_id(account_id),
            ledger_id=ledger_id,
            quantity=quantity,
            intent_id=intent_id,
            quantity_scale=quantity_scale,
        )
        return await self._call(request, LedgerWriteServiceClient.reserve_trading_withdraw)

    async def release_trading_withdraw_reserve(
        self,
        *,
        ledger_id: int,
        intent_id: str,
        account_id: str | int | None = None,
        close_scope: str = "",
    ) -> LedgerWriteTransferResult:
        request = release_trading_withdraw_reserve_to_proto(
            account_id=self._resolve_account_id(account_id),
            ledger_id=ledger_id,
            intent_id=intent_id,
            close_scope=close_scope,
        )
        return await self._call(
            request,
            LedgerWriteServiceClient.release_trading_withdraw_reserve,
        )

    async def _call(self, request, call):
        return await unary_auth_decoded(
            self._transport,
            LedgerWriteServiceClient,
            call,
            request,
            ledger_write_transfer_result_from_proto,
        )

    def _resolve_account_id(self, value: str | int | None) -> str | int:
        if value is not None:
            return value
        if self._default_account_id is not None:
            return self._default_account_id
        resolved_sub = resolve_sub_account_id(None, self._default_sub_account_id)
        if resolved_sub is not None:
            return resolved_sub
        raise PolyesterValidationError(
            "account_id is required; set POLYESTER_ACCOUNT_ID or pass account_id explicitly"
        )
