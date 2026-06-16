import pytest

from polyester import AsyncPolyester, PolyesterAuthError


@pytest.mark.asyncio
async def test_public_client_can_be_constructed_without_credentials() -> None:
    client = AsyncPolyester(hydrate_catalogs=False)
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticated_service_requires_credentials() -> None:
    client = AsyncPolyester(hydrate_catalogs=False)
    try:
        with pytest.raises(PolyesterAuthError):
            await client.orders.list_open()
    finally:
        await client.aclose()
