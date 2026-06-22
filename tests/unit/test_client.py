import pytest

from polyester import AsyncPolyester, PolyesterAuthError
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV


@pytest.mark.asyncio
async def test_public_client_can_be_constructed_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    client = AsyncPolyester(hydrate_catalogs=False)
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticated_service_requires_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    client = AsyncPolyester(hydrate_catalogs=False)
    try:
        with pytest.raises(PolyesterAuthError):
            await client.orders.list_open()
    finally:
        await client.aclose()
