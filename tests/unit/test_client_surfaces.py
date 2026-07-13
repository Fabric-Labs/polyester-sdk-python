import pytest

from polyester import AsyncPolyester
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV

EXPECTED_ASYNC_SERVICES = (
    "auth",
    "accounts",
    "chain_analytics",
    "market_data",
    "candles",
    "market_overview",
    "zipper",
    "heatmap",
    "lifecycle",
    "balances",
    "orderbook",
    "orders",
    "trades",
    "triggers",
    "transfers",
    "internal_transfers",
    "deposit",
    "api_keys",
    "policies",
    "sub_accounts",
    "resolve",
    "address_book",
    "social_verification",
    "whiteboard",
    "polychart",
    "layout",
    "guard_signer",
    "withdraw",
    "trading_withdraws",
    "realtime",
)


@pytest.mark.asyncio
async def test_async_client_exposes_all_documented_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    client = AsyncPolyester(hydrate_catalogs=False)
    try:
        for name in EXPECTED_ASYNC_SERVICES:
            assert hasattr(client, name), f"missing client.{name}"
        assert client.accounts is client.resolve
        assert client.candles is client.market_data
        assert client.trading_withdraws is client.withdraw
        assert hasattr(client.auth, "profile")
    finally:
        await client.aclose()
