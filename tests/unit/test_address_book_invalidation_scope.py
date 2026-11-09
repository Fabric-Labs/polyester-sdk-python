"""POLY-9020: address-book invalidations keep the full account scope.

A sub-account's change names the sub-account and its scope type, so a client
can tell which address book to refresh; a root change names only the root.
"""

from __future__ import annotations

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.realtime_decode import decode_address_book_invalidation_bytes
from polyester.gen.auth.v1 import address_book_pb2
from polyester.models.address_book import AccountScope

# The Devnet account from the ticket: root Xiw8QFupu6d, sub-account 2nphEX67UQT.
ROOT_ID = 13235591962976289070
SUB_ID = 771156649032427868


def _payload(scope: address_book_pb2.AccountScopeRef, view_revision: int) -> bytes:
    invalidated_at = Timestamp()
    invalidated_at.FromJsonString("2026-11-09T15:01:23.123456789Z")
    return address_book_pb2.AddressBookViewInvalidated(
        scope=scope, invalidated_at=invalidated_at, view_revision=view_revision
    ).SerializeToString()


def test_a_sub_account_change_names_the_sub_account_and_its_scope_type() -> None:
    event = decode_address_book_invalidation_bytes(
        _payload(
            address_book_pb2.AccountScopeRef(
                scope_type=address_book_pb2.SCOPE_SUBACCOUNT,
                root_account_id=ROOT_ID,
                subaccount_id=SUB_ID,
            ),
            1004932554200,
        )
    )
    assert event.scope == AccountScope(
        scope_type="subaccount", root_account_id="Xiw8QFupu6d", sub_account_id="2nphEX67UQT"
    )
    assert event.invalidated_at == "2026-11-09T15:01:23.123456789Z"
    assert event.view_revision == 1004932554200


def test_a_root_change_names_the_root_and_no_sub_account() -> None:
    event = decode_address_book_invalidation_bytes(
        _payload(
            address_book_pb2.AccountScopeRef(
                scope_type=address_book_pb2.SCOPE_ROOT, root_account_id=ROOT_ID
            ),
            1004923642104,
        )
    )
    assert event.scope == AccountScope(scope_type="root", root_account_id="Xiw8QFupu6d")
    assert event.scope.sub_account_id == ""
    assert event.view_revision == 1004923642104


def test_an_event_without_a_scope_has_none() -> None:
    event = decode_address_book_invalidation_bytes(
        address_book_pb2.AddressBookViewInvalidated(view_revision=7).SerializeToString()
    )
    assert event.scope is None
    assert event.view_revision == 7
