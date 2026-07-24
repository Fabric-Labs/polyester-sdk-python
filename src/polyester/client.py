from __future__ import annotations

import asyncio
import contextlib
import os
import threading
from typing import Literal

from polyester.auth import (
    ACCOUNT_ID_ENV,
    API_KEY_ID_ENV,
    API_PRIVATE_KEY_ENV,
    load_api_key_credentials,
)
from polyester.catalogs import CatalogManager
from polyester.realtime.client import AsyncRealtimeClient
from polyester.services import (
    AsyncAddressBookService,
    AsyncApiKeysService,
    AsyncAuthService,
    AsyncBalancesService,
    AsyncChainAnalyticsService,
    AsyncDepositService,
    AsyncGuardSignerService,
    AsyncHeatmapService,
    AsyncInternalTransfersService,
    AsyncLayoutService,
    AsyncLifecycleService,
    AsyncMarketDataService,
    AsyncMarketOverviewService,
    AsyncOrderbookService,
    AsyncOrdersService,
    AsyncPoliciesService,
    AsyncPolychartService,
    AsyncResolveService,
    AsyncSocialVerificationService,
    AsyncSubAccountsService,
    AsyncTradesService,
    AsyncTransfersService,
    AsyncTriggersService,
    AsyncWhiteboardService,
    AsyncWithdrawService,
    AsyncZipperService,
)
from polyester.sync_subscribe import (
    SyncSubscription,
)
from polyester.sync_subscribe import (
    subscribe_sync as _subscribe_sync_impl,
)
from polyester.transport import TransportConfig, TransportFactory

DEFAULT_API_URL = "https://api-devnet.polyester.ai"
DEFAULT_WS_URL = "wss://api-devnet.polyester.ai"


class AsyncPolyester:
    def __init__(
        self,
        *,
        api_key_id: str | None = None,
        api_private_key: str | bytes | None = None,
        api_url: str = DEFAULT_API_URL,
        ws_url: str = DEFAULT_WS_URL,
        default_sub_account_id: str | None = None,
        default_account_id: str | int | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        wire_format: Literal["binary", "json"] = "binary",
        hydrate_catalogs: bool = True,
    ) -> None:
        self.api_url = api_url
        self.ws_url = ws_url
        self.default_sub_account_id = default_sub_account_id
        self.default_account_id = default_account_id
        self.catalogs = CatalogManager()
        credentials = load_api_key_credentials(
            api_key_id=api_key_id,
            api_private_key=api_private_key,
            from_env=False,
        )
        self._transport = TransportFactory(
            TransportConfig(
                api_url=api_url,
                timeout=timeout,
                max_retries=max_retries,
                wire_format=wire_format,
            ),
            credentials=credentials,
        )
        self.realtime = AsyncRealtimeClient(
            ws_url,
            api_url=api_url,
            credentials=credentials,
            http=self._transport.public_http,
        )
        self.auth = AsyncAuthService(self._transport, realtime=self.realtime)
        self.chain_analytics = AsyncChainAnalyticsService(self._transport)
        self.market_data = AsyncMarketDataService(
            self._transport,
            self.catalogs,
            realtime=self.realtime,
        )
        self.candles = self.market_data
        self.market_overview = AsyncMarketOverviewService(
            self._transport,
            realtime=self.realtime,
        )
        self.zipper = AsyncZipperService(
            self._transport,
            catalogs=self.catalogs,
            realtime=self.realtime,
        )
        self.heatmap = AsyncHeatmapService(
            self._transport,
            self.catalogs,
            realtime=self.realtime,
        )
        self.lifecycle = AsyncLifecycleService(self._transport, realtime=self.realtime)
        self.balances = AsyncBalancesService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id,
            realtime=self.realtime,
        )
        self.orderbook = AsyncOrderbookService(
            self._transport,
            catalogs=self.catalogs,
            realtime=self.realtime,
        )
        self.orders = AsyncOrdersService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.trades = AsyncTradesService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.triggers = AsyncTriggersService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.transfers = AsyncTransfersService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.internal_transfers = AsyncInternalTransfersService(
            self._transport, self.catalogs, default_sub_account_id
        )
        self.deposit = AsyncDepositService(self._transport, default_sub_account_id)
        self.api_keys = AsyncApiKeysService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.policies = AsyncPoliciesService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.sub_accounts = AsyncSubAccountsService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.resolve = AsyncResolveService(self._transport)
        self.accounts = self.resolve
        self.address_book = AsyncAddressBookService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.social_verification = AsyncSocialVerificationService(self._transport)
        self.whiteboard = AsyncWhiteboardService(self._transport)
        self.polychart = AsyncPolychartService(self._transport)
        self.layout = AsyncLayoutService(self._transport)
        self.guard_signer = AsyncGuardSignerService(self._transport, default_sub_account_id)
        self.withdraw = AsyncWithdrawService(self._transport, default_sub_account_id)
        self.trading_withdraws = self.withdraw
        if hydrate_catalogs:
            self._catalog_task = asyncio.create_task(self._hydrate_catalogs_best_effort())
        else:
            self._catalog_task = None

    @classmethod
    def from_env(cls, **overrides) -> AsyncPolyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
        if "api_key_id" not in overrides:
            api_key_id = os.getenv(API_KEY_ID_ENV)
            if api_key_id:
                overrides["api_key_id"] = api_key_id.strip()
        if "api_private_key" not in overrides:
            api_private_key = os.getenv(API_PRIVATE_KEY_ENV)
            if api_private_key:
                overrides["api_private_key"] = api_private_key.strip()
        if "default_account_id" not in overrides:
            account_id = os.getenv(ACCOUNT_ID_ENV)
            if account_id:
                overrides["default_account_id"] = account_id.strip()
        return cls(**overrides)

    async def _hydrate_catalogs_best_effort(self) -> None:
        try:
            spot_config = await self.market_data.get_spot_config()
            self.catalogs.hydrate_spot_config(spot_config.raw)
        except Exception:
            pass
        try:
            zipper_config = await self.zipper.get_deposit_withdraw_config()
            self.catalogs.hydrate_zipper_config(zipper_config)
        except Exception:
            pass

    async def wait_for_catalogs(self) -> None:
        if self._catalog_task is None:
            return
        with contextlib.suppress(asyncio.CancelledError):
            await self._catalog_task

    async def __aenter__(self) -> AsyncPolyester:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._catalog_task is not None and not self._catalog_task.done():
            self._catalog_task.cancel()
        await self._transport.aclose()


class Polyester:
    def __init__(self, **config) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            name="polyester-sync-loop",
            daemon=True,
        )
        self._loop_thread.start()
        hydrate = config.get("hydrate_catalogs", True)
        self._active_sync_subscriptions: list[SyncSubscription] = []

        async def _bootstrap() -> AsyncPolyester:
            client = AsyncPolyester(**config)
            if hydrate:
                await client.wait_for_catalogs()
            return client

        self._client = asyncio.run_coroutine_threadsafe(_bootstrap(), self._loop).result(
            timeout=60
        )
        self.catalogs = self._client.catalogs
        self.catalog = self.catalogs
        self.realtime = _SyncService(self._loop, self._client.realtime)
        self.auth = _SyncService(self._loop, self._client.auth)
        self.auth.profile = _SyncSubscribeService(
            self._loop,
            self._client.auth.profile,
            self._active_sync_subscriptions,
            subscribe_methods={"subscribe_sync": "subscribe_identity"},
        )
        self.chain_analytics = _SyncService(self._loop, self._client.chain_analytics)
        self.market_data = _SyncSubscribeService(
            self._loop,
            self._client.market_data,
            self._active_sync_subscriptions,
            subscribe_methods={
                "subscribe_trades_sync": "subscribe_trades",
                "subscribe_candles_sync": "subscribe_candles",
            },
        )
        self.candles = self.market_data
        self.market_overview = _SyncSubscribeService(
            self._loop,
            self._client.market_overview,
            self._active_sync_subscriptions,
            subscribe_methods={"subscribe_sync": "create_subscription"},
        )
        self.zipper = _SyncSubscribeService(
            self._loop,
            self._client.zipper,
            self._active_sync_subscriptions,
            subscribe_methods={"subscribe_sync": "subscribe_zipped_asset_supply"},
        )
        self.heatmap = _SyncSubscribeService(
            self._loop,
            self._client.heatmap,
            self._active_sync_subscriptions,
            subscribe_methods={"subscribe_sync": "subscribe_live"},
        )
        self.lifecycle = _SyncSubscribeService(
            self._loop,
            self._client.lifecycle,
            self._active_sync_subscriptions,
            subscribe_methods={
                "subscribe_open_flows_sync": "subscribe_open_flows",
                "subscribe_flow_detail_sync": "subscribe_flow_detail",
            },
        )
        self.balances = _SyncSubscribeService(
            self._loop, self._client.balances, self._active_sync_subscriptions
        )
        self.orderbook = _SyncSubscribeService(
            self._loop,
            self._client.orderbook,
            self._active_sync_subscriptions,
            subscribe_methods={"subscribe_sync": "create_subscription"},
        )
        self.orders = _SyncSubscribeService(
            self._loop, self._client.orders, self._active_sync_subscriptions
        )
        self.trades = _SyncSubscribeService(
            self._loop, self._client.trades, self._active_sync_subscriptions
        )
        self.triggers = _SyncSubscribeService(
            self._loop,
            self._client.triggers,
            self._active_sync_subscriptions,
            subscribe_methods={
                "subscribe_sync": "subscribe",
                "subscribe_events_sync": "subscribe_events",
            },
        )
        self.transfers = _SyncSubscribeService(
            self._loop, self._client.transfers, self._active_sync_subscriptions
        )
        self.internal_transfers = _SyncService(self._loop, self._client.internal_transfers)
        self.deposit = _SyncService(self._loop, self._client.deposit)
        self.api_keys = _SyncSubscribeService(
            self._loop, self._client.api_keys, self._active_sync_subscriptions
        )
        self.policies = _SyncSubscribeService(
            self._loop,
            self._client.policies,
            self._active_sync_subscriptions,
            subscribe_methods={
                "subscribe_sync": "subscribe_subaccount_policies",
                "subscribe_api_policies_sync": "subscribe_api_policies",
            },
        )
        self.sub_accounts = _SyncSubscribeService(
            self._loop,
            self._client.sub_accounts,
            self._active_sync_subscriptions,
            subscribe_methods={
                "subscribe_sync": "subscribe",
                "subscribe_api_keys_sync": "subscribe_api_keys",
            },
        )
        self.resolve = _SyncService(self._loop, self._client.resolve)
        self.accounts = self.resolve
        self.address_book = _SyncSubscribeService(
            self._loop,
            self._client.address_book,
            self._active_sync_subscriptions,
            subscribe_methods={"subscribe_sync": "subscribe_view_invalidations"},
        )
        self.social_verification = _SyncService(self._loop, self._client.social_verification)
        self.whiteboard = _SyncService(self._loop, self._client.whiteboard)
        self.polychart = _SyncService(self._loop, self._client.polychart)
        self.layout = _SyncService(self._loop, self._client.layout)
        self.guard_signer = _SyncService(self._loop, self._client.guard_signer)
        self.withdraw = _SyncService(self._loop, self._client.withdraw)
        self.trading_withdraws = self.withdraw

    @classmethod
    def from_env(cls, **overrides) -> Polyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
        if "api_key_id" not in overrides:
            api_key_id = os.getenv(API_KEY_ID_ENV)
            if api_key_id:
                overrides["api_key_id"] = api_key_id.strip()
        if "api_private_key" not in overrides:
            api_private_key = os.getenv(API_PRIVATE_KEY_ENV)
            if api_private_key:
                overrides["api_private_key"] = api_private_key.strip()
        if "default_account_id" not in overrides:
            account_id = os.getenv(ACCOUNT_ID_ENV)
            if account_id:
                overrides["default_account_id"] = account_id.strip()
        return cls(**overrides)

    def close(self) -> None:
        for subscription in list(self._active_sync_subscriptions):
            subscription.close()
        self._active_sync_subscriptions.clear()

        async def _shutdown() -> None:
            await self._client.aclose()

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        with contextlib.suppress(Exception):
            future.result(timeout=10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=5)

    def __enter__(self) -> Polyester:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class _SyncService:
    def __init__(self, loop: asyncio.AbstractEventLoop, service: object) -> None:
        self._loop = loop
        self._service = service

    def __getattr__(self, name: str):
        attr = getattr(self._service, name)
        if isinstance(attr, _SyncService):
            return attr
        if not callable(attr) and type(attr).__name__.endswith("Service"):
            return _SyncService(self._loop, attr)
        if asyncio.iscoroutinefunction(attr):
            def async_call(*args, **kwargs):
                future = asyncio.run_coroutine_threadsafe(attr(*args, **kwargs), self._loop)
                return future.result(timeout=60)

            return async_call

        if callable(attr):
            def call(*args, **kwargs):
                result = attr(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    future = asyncio.run_coroutine_threadsafe(result, self._loop)
                    return future.result(timeout=60)
                return result

            return call
        return attr


class _SyncSubscribeService(_SyncService):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        service: object,
        active_subscriptions: list[SyncSubscription],
        *,
        subscribe_methods: dict[str, str] | None = None,
    ) -> None:
        super().__init__(loop, service)
        self._active_subscriptions = active_subscriptions
        for sync_name, async_attr in (subscribe_methods or {"subscribe_sync": "subscribe"}).items():
            setattr(self, sync_name, self._make_subscribe_sync(async_attr))

    def _make_subscribe_sync(self, async_attr: str):
        def subscribe_sync(
            *,
            on_event,
            on_error=None,
            **kwargs,
        ) -> SyncSubscription:
            subscribe_fn = getattr(self._service, async_attr)
            handle = _subscribe_sync_impl(
                self._loop,
                lambda: subscribe_fn(**kwargs),
                on_event=on_event,
                on_error=on_error,
            )
            self._active_subscriptions.append(handle)
            return handle

        return subscribe_sync
