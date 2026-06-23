from __future__ import annotations

from polyester.codecs.address_book import (
    address_book_entry_kind_from_label,
    address_book_tag_input_to_proto,
    create_entry_external_to_proto,
    create_entry_internal_to_proto,
    transfer_counterparty_direction_from_label,
)
from polyester.codecs.decode.address_book import (
    address_book_view_from_proto,
    entry_from_copy_proto,
    entry_from_create_proto,
    entry_from_update_proto,
    list_books_from_proto,
    list_counterparties_from_proto,
    list_destinations_from_proto,
    list_entries_from_proto,
    list_internal_whitelist_from_proto,
    tag_from_create_proto,
    tag_from_update_proto,
    withdraw_whitelist_view_from_get_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_address_book_invalidation_bytes
from polyester.codecs.scalars import id_to_int
from polyester.gen.auth.v1.address_book_connect import AddressBookServiceClient
from polyester.gen.auth.v1.address_book_pb2 import (
    CopyAddressBookEntryRequest,
    CreateAddressBookEntryRequest,
    CreateAddressBookTagRequest,
    DeleteAddressBookEntryRequest,
    DeleteAddressBookTagRequest,
    GetAddressBookViewRequest,
    GetWithdrawWhitelistViewRequest,
    ListAddressBookEntriesRequest,
    ListAddressBooksRequest,
    ListInternalTransferWhitelistEntriesRequest,
    ListTransferCounterpartiesRequest,
    ListTransferDestinationsRequest,
    UpdateAddressBookEntryRequest,
    UpdateAddressBookTagRequest,
)
from polyester.models.address_book import (
    AddressBookEntriesList,
    AddressBookEntry,
    AddressBooksList,
    AddressBookTag,
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
from polyester.services._scope import resolve_sub_account_id


class AsyncAddressBookService(BaseService):
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
        sub_account_id: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> AddressBookEntriesList:
        request = ListAddressBookEntriesRequest(limit=limit)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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

    async def create_entry(
        self,
        *,
        label: str,
        sub_account_id: str | None = None,
        note: str = "",
        kind: str,
        polychain_chain_id: int | None = None,
        address: str | None = None,
        smart_account_address: str | None = None,
        tag_ids: list[str] | None = None,
        new_tags: list[dict[str, str]] | None = None,
    ) -> AddressBookEntry:
        request = CreateAddressBookEntryRequest(label=label, note=note)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        entry_kind = kind.lower()
        if entry_kind in ("external", "external_chain"):
            if polychain_chain_id is None or not address:
                from polyester.errors import PolyesterValidationError

                raise PolyesterValidationError(
                    "external entries require polychain_chain_id and address"
                )
            request.external.CopyFrom(
                create_entry_external_to_proto(
                    polychain_chain_id=polychain_chain_id,
                    address=address,
                )
            )
        elif entry_kind in ("internal", "internal_account"):
            if not smart_account_address:
                from polyester.errors import PolyesterValidationError

                raise PolyesterValidationError("internal entries require smart_account_address")
            request.internal.CopyFrom(
                create_entry_internal_to_proto(smart_account_address=smart_account_address)
            )
        else:
            from polyester.errors import PolyesterValidationError

            raise PolyesterValidationError("kind must be 'external' or 'internal'")
        if tag_ids:
            request.tag_ids.extend(id_to_int(item, "tag_id") for item in tag_ids)
        if new_tags:
            for tag in new_tags:
                request.new_tags.append(
                    address_book_tag_input_to_proto(
                        name=tag["name"],
                        color=tag.get("color", ""),
                    )
                )
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.create_address_book_entry(req),
            request,
            entry_from_create_proto,
        )

    async def update_entry(
        self,
        *,
        address_book_entry_id: str,
        label: str,
        note: str = "",
        tag_ids: list[str] | None = None,
        new_tags: list[dict[str, str]] | None = None,
    ) -> AddressBookEntry:
        request = UpdateAddressBookEntryRequest(
            address_book_entry_id=id_to_int(address_book_entry_id, "address_book_entry_id"),
            label=label,
            note=note,
        )
        if tag_ids:
            request.tag_ids.extend(id_to_int(item, "tag_id") for item in tag_ids)
        if new_tags:
            for tag in new_tags:
                request.new_tags.append(
                    address_book_tag_input_to_proto(
                        name=tag["name"],
                        color=tag.get("color", ""),
                    )
                )
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.update_address_book_entry(req),
            request,
            entry_from_update_proto,
        )

    async def delete_entry(self, *, address_book_entry_id: str) -> None:
        await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.delete_address_book_entry(req),
            DeleteAddressBookEntryRequest(
                address_book_entry_id=id_to_int(address_book_entry_id, "address_book_entry_id")
            ),
            lambda _msg: None,
        )

    async def copy_entry(
        self,
        *,
        address_book_entry_id: str,
        target_sub_account_id: str | None = None,
    ) -> AddressBookEntry:
        request = CopyAddressBookEntryRequest(
            address_book_entry_id=id_to_int(address_book_entry_id, "address_book_entry_id")
        )
        parsed_target = parse_optional_subaccount_id(target_sub_account_id)
        if parsed_target is not None:
            request.target_subaccount_id = parsed_target
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.copy_address_book_entry(req),
            request,
            entry_from_copy_proto,
        )

    async def create_tag(
        self,
        *,
        name: str,
        sub_account_id: str | None = None,
        color: str = "",
    ) -> AddressBookTag:
        request = CreateAddressBookTagRequest(name=name, color=color)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.create_address_book_tag(req),
            request,
            tag_from_create_proto,
        )

    async def update_tag(
        self,
        *,
        tag_id: str,
        name: str,
        color: str = "",
    ) -> AddressBookTag:
        return await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.update_address_book_tag(req),
            UpdateAddressBookTagRequest(
                tag_id=id_to_int(tag_id, "tag_id"),
                name=name,
                color=color,
            ),
            tag_from_update_proto,
        )

    async def delete_tag(self, *, tag_id: str) -> None:
        await unary_auth_decoded(
            self._transport,
            AddressBookServiceClient,
            lambda client, req: client.delete_address_book_tag(req),
            DeleteAddressBookTagRequest(tag_id=id_to_int(tag_id, "tag_id")),
            lambda _msg: None,
        )

    async def list_transfer_counterparties(
        self,
        *,
        sub_account_id: str | None = None,
        direction: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> TransferCounterpartiesList:
        request = ListTransferCounterpartiesRequest(limit=limit)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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
        sub_account_id: str | None = None,
        kind: str = "internal_account",
        limit: int = 50,
        page_token: str | None = None,
    ) -> AddressBookTransferDestinationsList:
        request = ListTransferDestinationsRequest(
            kind=address_book_entry_kind_from_label(kind),
            limit=limit,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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
        sub_account_id: str | None = None,
        limit: int = 50,
        page_token: str | None = None,
    ) -> InternalTransferWhitelistEntriesList:
        request = ListInternalTransferWhitelistEntriesRequest(limit=limit)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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
        sub_account_id: str | None = None,
    ) -> WithdrawWhitelistView | None:
        request = GetWithdrawWhitelistViewRequest()
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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
        sub_account_id: str | None = None,
        limit: int = 50,
    ) -> AddressBookView:
        request = GetAddressBookViewRequest(limit=limit)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
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

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
