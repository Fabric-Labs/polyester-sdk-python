from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.codecs.address_book import create_entry_to_proto, update_entry_to_proto
from polyester.codecs.decode.address_book import (
    address_book_view_from_proto,
    entry_from_create_proto,
    entry_from_update_proto,
)
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.auth.v1 import address_book_pb2
from polyester.models.address_book import AddressBookTagInput
from polyester.services.address_book import AsyncAddressBookService
from tests.unit.support import CaptureUnary


def test_create_entry_encodes_new_tags() -> None:
    req = create_entry_to_proto(
        subaccount_id=None,
        label="hot wallet",
        note="",
        address="0xabc",
        polychain_chain_id=1,
        smart_account_address=None,
        tag_ids=None,
        new_tags=[{"name": "hot", "color": "#f00"}],
    )
    assert req.external.address == "0xabc"
    assert req.external.polychain_chain_id == 1
    assert len(req.new_tags) == 1
    assert req.new_tags[0].name == "hot"
    assert req.new_tags[0].color == "#f00"


def test_create_entry_requires_exactly_one_destination() -> None:
    with pytest.raises(PolyesterValidationError, match="exactly one"):
        create_entry_to_proto(
            subaccount_id=None,
            label="",
            note="",
            address=None,
            polychain_chain_id=None,
            smart_account_address=None,
            tag_ids=None,
            new_tags=None,
        )


def test_update_entry_new_tags_only_sets_mask() -> None:
    req = update_entry_to_proto(
        address_book_entry_id=7,
        expected_revision=3,
        new_tags=[AddressBookTagInput(name="vip")],
    )
    assert list(req.update_mask.paths) == ["new_tags"]
    assert req.expected_revision == 3
    assert req.address_book_entry_id == 7
    assert len(req.entry.new_tags) == 1
    assert req.entry.new_tags[0].name == "vip"
    assert list(req.entry.tag_ids) == []


def test_update_entry_tag_ids_and_new_tags_both_selected() -> None:
    req = update_entry_to_proto(
        address_book_entry_id=7,
        expected_revision=1,
        tag_ids=[2, 3],
        new_tags=[{"name": "fresh"}],
    )
    assert list(req.update_mask.paths) == ["tag_ids", "new_tags"]
    assert list(req.entry.tag_ids) == [2, 3]
    assert req.entry.new_tags[0].name == "fresh"


def test_update_entry_rejects_empty_mask_and_non_positive_revision() -> None:
    with pytest.raises(PolyesterValidationError, match="expected_revision"):
        update_entry_to_proto(address_book_entry_id=1, expected_revision=0, label="x")
    with pytest.raises(PolyesterValidationError, match="update_mask"):
        update_entry_to_proto(address_book_entry_id=1, expected_revision=1)


def test_create_response_missing_entry_fails_closed() -> None:
    with pytest.raises(PolyesterResponseContractError, match="missing entry"):
        entry_from_create_proto(address_book_pb2.CreateAddressBookEntryResponse())


def test_update_response_maps_tags() -> None:
    resp = address_book_pb2.UpdateAddressBookEntryResponse(
        entry=address_book_pb2.AddressBookEntry(
            address_book_entry_id=9,
            label="saved",
            revision=4,
            tags=[address_book_pb2.AddressBookTag(tag_id=11, name="hot")],
        )
    )
    entry = entry_from_update_proto(resp)
    assert entry.address_book_entry_id
    assert entry.label == "saved"
    assert entry.revision == 4
    assert entry.tags is not None
    assert entry.tags[0].name == "hot"


@pytest.mark.asyncio
async def test_create_service_sends_new_tags_on_wire() -> None:
    capture = CaptureUnary(
        address_book_pb2.CreateAddressBookEntryResponse(
            entry=address_book_pb2.AddressBookEntry(
                address_book_entry_id=1,
                label="sdk",
                revision=1,
                tags=[address_book_pb2.AddressBookTag(tag_id=2, name="hot")],
            )
        )
    )
    with patch("polyester.services.address_book.unary_auth_decoded", capture):
        service = AsyncAddressBookService(
            transport=MagicMock(),
            default_sub_account_id=None,
        )
        result = await service.create_entry(
            label="sdk",
            address="0xabc",
            polychain_chain_id=1,
            new_tags=[{"name": "hot", "color": "#f00"}],
        )
    assert capture.request.new_tags[0].name == "hot"
    assert result.tags is not None
    assert result.tags[0].name == "hot"


@pytest.mark.asyncio
async def test_update_service_sends_new_tags_mask() -> None:
    capture = CaptureUnary(
        address_book_pb2.UpdateAddressBookEntryResponse(
            entry=address_book_pb2.AddressBookEntry(
                address_book_entry_id=1,
                revision=2,
            )
        )
    )
    with patch("polyester.services.address_book.unary_auth_decoded", capture):
        service = AsyncAddressBookService(
            transport=MagicMock(),
            default_sub_account_id=None,
        )
        await service.update_entry(
            address_book_entry_id=1,
            expected_revision=1,
            new_tags=[{"name": "appended"}],
        )
    assert list(capture.request.update_mask.paths) == ["new_tags"]
    assert capture.request.entry.new_tags[0].name == "appended"


@pytest.mark.asyncio
async def test_get_view_wires_minimum_view_revision() -> None:
    capture = CaptureUnary(address_book_pb2.GetAddressBookViewResponse(view_revision=9))
    with patch("polyester.services.address_book.unary_auth_decoded", capture):
        service = AsyncAddressBookService(
            transport=MagicMock(),
            default_sub_account_id=None,
        )
        view = await service.get_view(minimum_view_revision=9)
    assert capture.request.minimum_view_revision == 9
    assert view.view_revision == 9


def test_address_book_view_maps_view_revision() -> None:
    view = address_book_view_from_proto(
        address_book_pb2.GetAddressBookViewResponse(view_revision=4)
    )
    assert view.view_revision == 4
