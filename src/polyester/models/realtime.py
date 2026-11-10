from __future__ import annotations

import msgspec

from polyester.models.address_book import AccountScope


class AddressBookViewInvalidation(msgspec.Struct, kw_only=True, omit_defaults=True):
    scope: AccountScope | None = None
    """The address book that changed: its scope type (``"root"`` or
    ``"subaccount"``), its root account and, for a sub-account's book, the
    sub-account, as public IDs. A root scope's ``sub_account_id`` is empty.
    ``None`` when the event names no scope."""
    invalidated_at: str = ""
    view_revision: int = 0


class OrderBookDeltaUpdate(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int = 0
    book_seq_start: str = ""
    book_seq_end: str = ""
    reset: bool = False
    bids: list[tuple[str, str]] = msgspec.field(default_factory=list)
    asks: list[tuple[str, str]] = msgspec.field(default_factory=list)
