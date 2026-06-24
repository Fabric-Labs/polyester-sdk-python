import pytest

from polyester import AsyncPolyester, Polyester
from polyester.auth import API_KEY_ID_ENV, API_PRIVATE_KEY_ENV


def test_sync_client_exposes_catalogs_and_nested_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    client = Polyester(hydrate_catalogs=False)
    try:
        assert client.catalogs is client.catalog
        assert hasattr(client.auth, "profile")
        assert callable(client.auth.profile.get)
        assert hasattr(client.auth.profile, "subscribe_sync")
        subscribe_surfaces = {
            "orders": ("subscribe_sync",),
            "trades": ("subscribe_sync",),
            "balances": ("subscribe_sync",),
            "orderbook": ("subscribe_sync",),
            "market_overview": ("subscribe_sync",),
            "zipper": ("subscribe_sync",),
            "transfers": ("subscribe_sync",),
            "triggers": ("subscribe_sync", "subscribe_events_sync"),
            "market_data": ("subscribe_trades_sync", "subscribe_candles_sync"),
            "heatmap": ("subscribe_sync",),
            "lifecycle": ("subscribe_open_flows_sync", "subscribe_flow_detail_sync"),
            "api_keys": ("subscribe_sync",),
            "policies": ("subscribe_sync",),
            "sub_accounts": ("subscribe_sync", "subscribe_api_keys_sync"),
            "address_book": ("subscribe_sync",),
        }
        for service, methods in subscribe_surfaces.items():
            assert hasattr(client, service)
            svc = getattr(client, service)
            for method in methods:
                assert hasattr(svc, method), f"{service}.{method}"
    finally:
        client.close()


def test_async_and_sync_clients_share_service_tree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_KEY_ID_ENV, raising=False)
    monkeypatch.delenv(API_PRIVATE_KEY_ENV, raising=False)
    async_client = AsyncPolyester(hydrate_catalogs=False)
    sync_client = Polyester(hydrate_catalogs=False)
    try:
        for name in ("orders", "zipper", "orderbook", "market_overview"):
            assert hasattr(sync_client, name)
            assert hasattr(async_client, name)
    finally:
        sync_client.close()
        import asyncio

        asyncio.run(async_client.aclose())
