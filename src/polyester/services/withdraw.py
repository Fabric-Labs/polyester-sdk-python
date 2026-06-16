from __future__ import annotations

from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.scalars import parse_qty_scaled
from polyester.codecs.wire_decode import decode_withdraw_intent
from polyester.gen.chain.withdraw.v1.withdraw_connect import WithdrawServiceClient
from polyester.gen.chain.withdraw.v1.withdraw_pb2 import CreateTradingWithdrawRequest
from polyester.models import WithdrawIntentResult
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth
from polyester.services._scope import resolve_sub_account_id


class AsyncWithdrawService(BaseService):
    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def create_trading_withdraw(
        self,
        *,
        ledger_id: int,
        quantity: str,
        idempotency_key: str,
        sub_account_id: str | None = None,
        quantity_scale: int = 8,
    ) -> WithdrawIntentResult:
        request = CreateTradingWithdrawRequest(
            ledger_id=ledger_id,
            quantity_scaled=parse_qty_scaled(quantity, quantity_scale, "quantity"),
            idempotency_key=idempotency_key,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        data = await unary_auth(
            self._transport,
            WithdrawServiceClient,
            lambda client, req: client.create_trading_withdraw(req),
            request,
        )
        return decode_withdraw_intent(data)

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
