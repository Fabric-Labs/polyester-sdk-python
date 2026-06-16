from __future__ import annotations

from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.wire_decode import decode_transfer_destinations
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1.address_book_connect import AddressBookServiceClient
from polyester.gen.auth.v1.address_book_pb2 import ListTransferDestinationsRequest
from polyester.models import TransferDestinationsList
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth
from polyester.services._scope import resolve_sub_account_id


class AsyncAddressBookService(BaseService):
    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def list_transfer_destinations(
        self,
        *,
        sub_account_id: str | None = None,
        kind: str = "internal_account",
    ) -> TransferDestinationsList:
        from polyester.gen.auth.v1 import address_book_pb2

        kind_aliases = {
            "internal": "INTERNAL_ACCOUNT",
            "internal_account": "INTERNAL_ACCOUNT",
            "external": "EXTERNAL_CHAIN",
            "external_chain": "EXTERNAL_CHAIN",
        }
        kind_name = kind_aliases.get(kind.lower(), kind.upper())
        kind_enum = getattr(address_book_pb2, kind_name, None)
        if kind_enum is None:
            raise PolyesterValidationError(
                "kind must be 'internal_account' or 'external_chain'"
            )
        request = ListTransferDestinationsRequest(kind=kind_enum)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        data = await unary_auth(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.list_transfer_destinations(req),
            request,
        )
        return decode_transfer_destinations(data)

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
