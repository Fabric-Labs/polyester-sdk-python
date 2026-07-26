from __future__ import annotations

from polyester.codecs.decode.withdraw import withdraw_intent_from_proto
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.withdraw import trading_withdraw_payload_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.chain.withdraw.v1.withdraw_connect import WithdrawServiceClient
from polyester.models import WithdrawIntentResult
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.types.money import AssetAmount


class AsyncWithdrawService(ScopedSubAccountMixin, BaseService):
    """Trading withdraw intents (trading → funding or external chain)."""

    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def create_to_funding(
        self,
        *,
        asset_id: int,
        quantity: str | AssetAmount,
        payload_signature: bytes,
        idempotency_key: str,
        nonce: str | int,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        destination_address: str = "",
        amount_scale: int = 18,
        deadline_ts_sec: int | None = None,
    ) -> WithdrawIntentResult:
        """Move trading balance to funding via a signed withdraw intent."""
        if not payload_signature:
            raise PolyesterValidationError("payload_signature is required for trading withdraw")
        payload = trading_withdraw_payload_to_proto(
            action="to_funding",
            asset_id=asset_id,
            amount=quantity,
            idempotency_key=idempotency_key,
            deadline_ts_sec=deadline_ts_sec,
            nonce=nonce,
            destination_address=destination_address,
            amount_scale=amount_scale,
        )
        request = withdraw_pb2.CreateTradingWithdrawRequest(
            payload=payload,
            payload_signature=payload_signature,
        )
        return await self._create_trading_withdraw(request)

    async def create_to_external_chain(
        self,
        *,
        asset_id: int,
        quantity: str | AssetAmount,
        payload_signature: bytes,
        destination_chain_id: int,
        destination_address: str,
        idempotency_key: str,
        nonce: str | int,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        amount_scale: int = 18,
        deadline_ts_sec: int | None = None,
    ) -> WithdrawIntentResult:
        if not payload_signature:
            raise PolyesterValidationError("payload_signature is required for trading withdraw")
        if not destination_address:
            raise PolyesterValidationError(
                "destination_address is required for external-chain withdraw"
            )
        payload = trading_withdraw_payload_to_proto(
            action="to_external_chain",
            asset_id=asset_id,
            amount=quantity,
            idempotency_key=idempotency_key,
            destination_chain_id=destination_chain_id,
            deadline_ts_sec=deadline_ts_sec,
            nonce=nonce,
            destination_address=destination_address,
            amount_scale=amount_scale,
        )
        request = withdraw_pb2.CreateTradingWithdrawRequest(
            payload=payload,
            payload_signature=payload_signature,
        )
        return await self._create_trading_withdraw(request)

    async def create_wallet_trading_withdraw(
        self,
        *,
        action: str,
        asset_id: int,
        amount: str | AssetAmount,
        idempotency_key: str,
        payload_signature: bytes,
        signer_wallet: str,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        destination_chain_id: int = 0,
        deadline_ts_sec: int | None = None,
        nonce: str | int,
        destination_address: str = "",
        amount_scale: int = 18,
    ) -> WithdrawIntentResult:
        if not payload_signature:
            raise PolyesterValidationError("payload_signature is required for trading withdraw")
        payload = trading_withdraw_payload_to_proto(
            action=action,
            asset_id=asset_id,
            amount=amount,
            idempotency_key=idempotency_key,
            destination_chain_id=destination_chain_id,
            deadline_ts_sec=deadline_ts_sec,
            nonce=nonce,
            destination_address=destination_address,
            amount_scale=amount_scale,
        )
        request = withdraw_pb2.CreateWalletTradingWithdrawRequest(
            payload=payload,
            signer_wallet=signer_wallet,
            payload_signature=payload_signature,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            WithdrawServiceClient,
            lambda client, req: client.create_wallet_trading_withdraw(req),
            request,
            withdraw_intent_from_proto,
        )

    async def _create_trading_withdraw(
        self,
        request: withdraw_pb2.CreateTradingWithdrawRequest,
    ) -> WithdrawIntentResult:
        return await unary_auth_decoded(
            self._transport,
            WithdrawServiceClient,
            lambda client, req: client.create_trading_withdraw(req),
            request,
            withdraw_intent_from_proto,
        )
