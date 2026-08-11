from __future__ import annotations

from polyester.codecs.address_book import (
    address_book_entry_kind_from_label,
    transfer_counterparty_direction_from_label,
)
from polyester.codecs.decode.address_book import (
    address_book_view_from_proto,
    list_books_from_proto,
    list_counterparties_from_proto,
    list_destinations_from_proto,
    list_entries_from_proto,
    list_internal_whitelist_from_proto,
    withdraw_whitelist_view_from_get_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_address_book_invalidation_bytes
from polyester.gen.auth.v1.address_book_connect import AddressBookServiceClient
from polyester.gen.auth.v1.address_book_pb2 import (
    GetAddressBookViewRequest,
    GetWithdrawWhitelistViewRequest,
    ListAddressBookEntriesRequest,
    ListAddressBooksRequest,
    ListInternalTransferWhitelistEntriesRequest,
    ListTransferCounterpartiesRequest,
    ListTransferDestinationsRequest,
)
from polyester.models.address_book import (
    AddressBookEntriesList,
    AddressBooksList,
    AddressBookTransferDestinationsList,
    AddressBookView,
    InternalTransferWhitelistEntriesList,
    TransferCounterpartiesList,
    WithdrawWhitelistView,
)
from polyester.models.realtime import AddressBookViewInvalidation
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._validation import validate_limit


class AsyncAddressBookService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        default_sub_account_id: str | None,
        *,
        default_account_id: str | int | None = None,
        realtime: AsyncRealtimeClient | None = None,
    ) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime

    async def list_books(self) -> AddressBooksList:
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.list_address_books(req),
            ListAddressBooksRequest(),
            list_books_from_proto,
        )

    async def list_entries(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> AddressBookEntriesList:
        request = ListAddressBookEntriesRequest(limit=validate_limit(limit))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if kind:
            request.kind = address_book_entry_kind_from_label(kind)
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.list_address_book_entries(req),
            request,
            list_entries_from_proto,
        )

    async def list_transfer_counterparties(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        direction: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> TransferCounterpartiesList:
        request = ListTransferCounterpartiesRequest(limit=validate_limit(limit))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if direction:
            request.direction = transfer_counterparty_direction_from_label(direction)
        if kind:
            request.kind = address_book_entry_kind_from_label(kind)
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.list_transfer_counterparties(req),
            request,
            list_counterparties_from_proto,
        )

    async def list_transfer_destinations(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        kind: str = "internal_account",
        limit: int = 50,
        page_token: str | None = None,
    ) -> AddressBookTransferDestinationsList:
        request = ListTransferDestinationsRequest(
            kind=address_book_entry_kind_from_label(kind),
            limit=validate_limit(limit),
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.list_transfer_destinations(req),
            request,
            list_destinations_from_proto,
        )

    async def list_internal_transfer_whitelist_entries(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> InternalTransferWhitelistEntriesList:
        request = ListInternalTransferWhitelistEntriesRequest(limit=validate_limit(limit))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.list_internal_transfer_whitelist_entries(req),
            request,
            list_internal_whitelist_from_proto,
        )

    async def get_withdraw_whitelist_view(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
    ) -> WithdrawWhitelistView | None:
        request = GetWithdrawWhitelistViewRequest()
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.get_withdraw_whitelist_view(req),
            request,
            withdraw_whitelist_view_from_get_proto,
        )

    async def get_view(
        self,
        *,
        account: AccountScope | None = None,
        sub_account_id: str | None = None,
        limit: int = 50,
    ) -> AddressBookView:
        request = GetAddressBookViewRequest(limit=validate_limit(limit))
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.get_address_book_view(req),
            request,
            address_book_view_from_proto,
        )

    async def subscribe_view_invalidations(
        self,
        *,
        root_account_public_id: str | int | None = None,
    ) -> AsyncSubscription[AddressBookViewInvalidation]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:auth:address-books:{account_id}:proto",
            account_id=root_account_public_id,
            default_account_id=self._default_account_id,
            decode=decode_address_book_invalidation_bytes,
        )
