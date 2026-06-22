import pytest

from polyester.models.address_book import AddressBooksList, AddressBookView


@pytest.mark.integration
async def test_address_book_list_books(live_client):
    result = await live_client.address_book.list_books()
    assert isinstance(result, AddressBooksList)
    assert isinstance(result.books, list)


@pytest.mark.integration
async def test_address_book_get_view(live_client):
    result = await live_client.address_book.get_view()
    assert isinstance(result, AddressBookView)
