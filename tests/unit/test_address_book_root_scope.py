"""A root address book names no sub-account on every path.

The contract sends sub-account 0 for a root scope, which is not an ID. The
reads (``list_books``, ``get_view``, ``list_entries`` and every
other read that carries a scope) and the change event decode it the same
way, as ``""``, so the scope of a book read equals the scope of its change
event and a cache keyed by scope can refresh the root book. A sub-account
book keeps its public ID on both paths.
"""

from __future__ import annotations

from typing import Any

import pytest
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.codecs.decode.address_book import account_scope_from_proto
from polyester.codecs.realtime_decode import decode_address_book_invalidation_bytes
from polyester.gen.auth.v1 import account_scope_pb2, address_book_pb2
from polyester.models.address_book import AccountScope
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

WIRES = pytest.mark.parametrize("json_wire", [False, True], ids=["binary", "json"])

ROOT_ID = 13235591962976289070
SUB_ID = 771156649032427868
ROOT = AccountScope(scope_type="root", root_account_id="Xiw8QFupu6d", sub_account_id="")
SUB = AccountScope(
    scope_type="subaccount", root_account_id="Xiw8QFupu6d", sub_account_id="2nphEX67UQT"
)


def _root_ref() -> address_book_pb2.AccountScopeRef:
    return address_book_pb2.AccountScopeRef(
        scope_type=account_scope_pb2.SCOPE_ROOT, root_account_id=ROOT_ID
    )


def _sub_ref() -> address_book_pb2.AccountScopeRef:
    return address_book_pb2.AccountScopeRef(
        scope_type=account_scope_pb2.SCOPE_SUBACCOUNT,
        root_account_id=ROOT_ID,
        subaccount_id=SUB_ID,
    )


def _event_scope(ref: address_book_pb2.AccountScopeRef) -> AccountScope | None:
    payload = address_book_pb2.AddressBookViewInvalidated(
        scope=ref, view_revision=1
    ).SerializeToString()
    return decode_address_book_invalidation_bytes(payload).scope


def _books() -> list[address_book_pb2.AddressBook]:
    return [
        address_book_pb2.AddressBook(scope=_root_ref(), label="main"),
        address_book_pb2.AddressBook(scope=_sub_ref(), label="desk"),
    ]


_RESPONSES: dict[str, Message] = {
    "ListAddressBooks": address_book_pb2.ListAddressBooksResponse(books=_books()),
    "GetAddressBookView": address_book_pb2.GetAddressBookViewResponse(
        books=_books(),
        view_revision=3,
    ),
    "ListAddressBookEntries": address_book_pb2.ListAddressBookEntriesResponse(
        entries=[
            address_book_pb2.AddressBookEntry(address_book_entry_id=11, scope=_root_ref()),
            address_book_pb2.AddressBookEntry(address_book_entry_id=12, scope=_sub_ref()),
        ]
    ),
}


async def _client(json_wire: bool) -> tuple[AsyncPolyester, Any]:
    async def handler(req: ParsedRequest) -> HttpScript:
        response = _RESPONSES[req.path.rsplit("/", 1)[-1]]
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
    )
    return client, http


def test_the_scope_decoder_names_no_sub_account_for_a_root_scope() -> None:
    assert account_scope_from_proto(_root_ref()) == ROOT
    assert account_scope_from_proto(_sub_ref()) == SUB


def test_a_root_scope_decodes_equal_on_the_read_and_the_event_path() -> None:
    assert account_scope_from_proto(_root_ref()) == _event_scope(_root_ref())
    assert account_scope_from_proto(_sub_ref()) == _event_scope(_sub_ref())
    assert account_scope_from_proto(_root_ref()) != _event_scope(_sub_ref())


@pytest.mark.asyncio
@WIRES
async def test_read_scopes_match_their_change_events(json_wire: bool) -> None:
    client, http = await _client(json_wire)
    try:
        listed = await client.address_book.list_books()
        view = await client.address_book.get_view()
        entries = await client.address_book.list_entries()
    finally:
        await client.aclose()
        await http.aclose()

    root_event = _event_scope(_root_ref())
    sub_event = _event_scope(_sub_ref())
    assert root_event == ROOT
    assert sub_event == SUB

    for books in (listed.books, view.books or []):
        assert [book.scope for book in books] == [ROOT, SUB]
        # A cache keyed by scope finds the book each event invalidates.
        by_scope = {_scope_key(book.scope): book.label for book in books}
        assert by_scope[_scope_key(root_event)] == "main"
        assert by_scope[_scope_key(sub_event)] == "desk"

    assert [entry.scope for entry in entries.entries] == [ROOT, SUB]


def _scope_key(scope: AccountScope | None) -> tuple[str, str, str]:
    assert scope is not None
    return (scope.scope_type, scope.root_account_id, scope.sub_account_id)
