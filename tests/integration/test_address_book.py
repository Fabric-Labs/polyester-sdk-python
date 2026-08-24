import time
import uuid

import pytest

from polyester.models.address_book import AddressBooksList, AddressBookView
from tests.integration.support import call_optional, call_required


@pytest.mark.integration
async def test_address_book_list_books(live_client):
    result = await call_required(
        live_client.address_book.list_books(),
        label="address_book.list_books",
    )
    assert isinstance(result, AddressBooksList)
    assert isinstance(result.books, list)


@pytest.mark.integration
async def test_address_book_get_view(live_client):
    result = await call_required(live_client.address_book.get_view(), label="address_book.get_view")
    assert isinstance(result, AddressBookView)


@pytest.mark.integration
async def test_address_book_create_update_new_tags_round_trip(live_client) -> None:
    suffix = uuid.uuid4().hex[:10]
    address = f"0x{uuid.uuid4().hex[:40]:0<40}"
    created = await call_optional(
        live_client.address_book.create_entry(
            label=f"sdk-new-tags-{suffix}",
            address=address,
            polychain_chain_id=1,
            new_tags=[{"name": f"hot-{suffix}", "color": "#f00"}],
        ),
        label="address_book.create_entry",
    )
    created_names = {tag.name for tag in (created.tags or [])}
    assert f"hot-{suffix}" in created_names
    updated = None
    try:
        updated = await call_optional(
            live_client.address_book.update_entry(
                address_book_entry_id=created.address_book_entry_id,
                expected_revision=created.revision,
                new_tags=[{"name": f"vip-{suffix}"}],
            ),
            label="address_book.update_entry",
        )
        names = {tag.name for tag in (updated.tags or [])}
        assert f"hot-{suffix}" in names
        assert f"vip-{suffix}" in names
    finally:
        entry_id = (updated or created).address_book_entry_id
        await call_optional(
            live_client.address_book.delete_entry(address_book_entry_id=entry_id),
            label="address_book.delete_entry",
        )
        leftover = {
            tag.tag_id
            for tag in (*(created.tags or []), *((updated.tags if updated else None) or []))
        }
        for tag_id in leftover:
            await call_optional(
                live_client.address_book.delete_tag(tag_id=tag_id),
                label="address_book.delete_tag",
            )


@pytest.mark.integration
async def test_social_verification_start_accepts_at_handle(live_client) -> None:
    handle = f"@sdk{int(time.time()) % 100000:05d}"
    result = await call_optional(
        live_client.social_verification.start(
            provider="twitter",
            method="profile",
            handle=handle,
        ),
        label="social_verification.start",
    )
    assert result is not None
