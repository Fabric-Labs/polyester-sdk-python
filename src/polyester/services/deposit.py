from __future__ import annotations

from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.wire_decode import decode_deposit_address, decode_deposit_addresses_list
from polyester.gen.chain.deposit.v1.deposit_connect import DepositAddressServiceClient
from polyester.gen.chain.deposit.v1.deposit_pb2 import (
    CreateDepositAddressRequest,
    ListDepositAddressesRequest,
)
from polyester.models import DepositAddress, DepositAddressesList
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth
from polyester.services._scope import resolve_sub_account_id


class AsyncDepositService(BaseService):
    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def list_addresses(
        self,
        *,
        chain_id: int,
        sub_account_id: str | None = None,
    ) -> DepositAddressesList:
        request = ListDepositAddressesRequest(chain_id=chain_id)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        data = await unary_auth(
            self._transport,
            DepositAddressServiceClient,
            lambda client, req: client.list_deposit_addresses(req),
            request,
        )
        return decode_deposit_addresses_list(data)

    async def create_address(
        self,
        *,
        chain_id: int,
        sub_account_id: str | None = None,
    ) -> DepositAddress:
        request = CreateDepositAddressRequest(chain_id=chain_id)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        data = await unary_auth(
            self._transport,
            DepositAddressServiceClient,
            lambda client, req: client.create_deposit_address(req),
            request,
        )
        address_raw = data.get("depositAddress") or data.get("deposit_address")
        if isinstance(address_raw, dict):
            return decode_deposit_address(address_raw)
        return DepositAddress(chain_id=chain_id)

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
