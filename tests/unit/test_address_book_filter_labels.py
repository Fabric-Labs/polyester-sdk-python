"""Address-book filter labels: only the documented labels are accepted."""

from __future__ import annotations

import pytest

from polyester.codecs.address_book import (
    address_book_entry_kind_from_label,
    transfer_counterparty_direction_from_label,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import address_book_pb2
from polyester.services.address_book import AsyncAddressBookService


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("external", address_book_pb2.EXTERNAL_CHAIN),
        ("external_chain", address_book_pb2.EXTERNAL_CHAIN),
        ("EXTERNAL_CHAIN", address_book_pb2.EXTERNAL_CHAIN),
        ("internal", address_book_pb2.INTERNAL_ACCOUNT),
        ("internal-account", address_book_pb2.INTERNAL_ACCOUNT),
        ("INTERNAL_ACCOUNT", address_book_pb2.INTERNAL_ACCOUNT),
    ],
)
def test_entry_kind_accepts_documented_labels(label: str, expected: int) -> None:
    assert address_book_entry_kind_from_label(label) == expected


@pytest.mark.parametrize(
    "label",
    [
        "totally_invalid_kind",
        "unspecified",
        "entry_kind_unspecified",
        "ENTRY_KIND_UNSPECIFIED",
        "entry_kind_external_chain",
        "scope_root",
        "deposit_from",
        "descriptor",
    ],
)
def test_entry_kind_refuses_other_labels(label: str) -> None:
    with pytest.raises(PolyesterValidationError) as excinfo:
        address_book_entry_kind_from_label(label)
    message = str(excinfo.value)
    for accepted in ("external", "external_chain", "internal", "internal_account"):
        assert accepted in message


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("deposit_from", address_book_pb2.DEPOSIT_FROM),
        ("WITHDRAW_TO", address_book_pb2.WITHDRAW_TO),
        ("internal-transfer-from", address_book_pb2.INTERNAL_TRANSFER_FROM),
        ("internal_transfer_to", address_book_pb2.INTERNAL_TRANSFER_TO),
    ],
)
def test_direction_accepts_documented_labels(label: str, expected: int) -> None:
    assert transfer_counterparty_direction_from_label(label) == expected


@pytest.mark.parametrize(
    "label",
    [
        "totally_invalid_direction",
        "scope_root",
        "descriptor",
        "transfer_counterparty_direction_unspecified",
        "external_chain",
    ],
)
def test_direction_refuses_other_labels(label: str) -> None:
    with pytest.raises(PolyesterValidationError) as excinfo:
        transfer_counterparty_direction_from_label(label)
    message = str(excinfo.value)
    for accepted in (
        "deposit_from",
        "withdraw_to",
        "internal_transfer_from",
        "internal_transfer_to",
    ):
        assert accepted in message


class _RefusingTransport:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"transport used: {name}")


async def test_filters_refuse_unknown_labels_before_sending() -> None:
    service = AsyncAddressBookService(_RefusingTransport(), None)
    with pytest.raises(PolyesterValidationError):
        await service.list_entries(kind="unspecified")
    with pytest.raises(PolyesterValidationError):
        await service.list_transfer_counterparties(direction="scope_root")
    with pytest.raises(PolyesterValidationError):
        await service.list_transfer_counterparties(kind="entry_kind_unspecified")
