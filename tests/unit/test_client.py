import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester import AsyncPolyester, PolyesterAuthError
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV
from polyester.client import API_URL_ENV, DEFAULT_API_URL, DEFAULT_WS_URL, WS_URL_ENV


def _private_key_hex() -> str:
    return Ed25519PrivateKey.generate().private_bytes_raw().hex()


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


@pytest.mark.asyncio
async def test_constructor_does_not_implicitly_read_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_env")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, _private_key_hex())
    client = AsyncPolyester(hydrate_catalogs=False)
    try:
        assert client._transport.credentials is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_from_env_reads_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = _private_key_hex()
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_env")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, private_key)
    client = AsyncPolyester.from_env(hydrate_catalogs=False)
    try:
        assert client._transport.credentials is not None
        assert client._transport.credentials.key_id == "ak_env"
        assert client.api_url == DEFAULT_API_URL
        assert client.ws_url == DEFAULT_WS_URL
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_from_env_reads_api_and_ws_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_KEY_ID_ENV, "ak_env")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, _private_key_hex())
    monkeypatch.setenv(API_URL_ENV, "https://api.example.test")
    monkeypatch.setenv(WS_URL_ENV, "wss://ws.example.test")
    client = AsyncPolyester.from_env(hydrate_catalogs=False)
    try:
        assert client.api_url == "https://api.example.test"
        assert client.ws_url == "wss://ws.example.test"
    finally:
        await client.aclose()


def test_is_batch_replace_settled_is_exported() -> None:
    from polyester import is_batch_replace_settled

    assert callable(is_batch_replace_settled)
