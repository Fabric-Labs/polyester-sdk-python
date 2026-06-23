from __future__ import annotations

import asyncio
import os
from typing import Literal

from polyester.auth import ACCOUNT_ID_ENV, load_api_key_credentials
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
    AsyncLedgerWriteService,
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
        self.zipper = AsyncZipperService(self._transport, realtime=self.realtime)
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
        self.ledger_write = AsyncLedgerWriteService(
            self._transport,
            default_sub_account_id,
            default_account_id,
        )
        self.withdraw = AsyncWithdrawService(self._transport, default_sub_account_id)
        self.trading_withdraws = self.withdraw
        if hydrate_catalogs:
            self._catalog_task = asyncio.create_task(self._hydrate_catalogs_best_effort())
        else:
            self._catalog_task = None

    @classmethod
    def from_env(cls, **overrides) -> AsyncPolyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
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
            self.catalogs.hydrate_zipper_config(zipper_config.raw)
        except Exception:
            pass

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
        self._client = self._loop.run_until_complete(self._create_client(config))
        self.realtime = _SyncService(self._loop, self._client.realtime)
        self.auth = _SyncService(self._loop, self._client.auth)
        self.chain_analytics = _SyncService(self._loop, self._client.chain_analytics)
        self.market_data = _SyncService(self._loop, self._client.market_data)
        self.candles = self.market_data
        self.market_overview = _SyncService(self._loop, self._client.market_overview)
        self.zipper = _SyncService(self._loop, self._client.zipper)
        self.heatmap = _SyncService(self._loop, self._client.heatmap)
        self.lifecycle = _SyncService(self._loop, self._client.lifecycle)
        self.balances = _SyncService(self._loop, self._client.balances)
        self.orderbook = _SyncService(self._loop, self._client.orderbook)
        self.orders = _SyncService(self._loop, self._client.orders)
        self.trades = _SyncService(self._loop, self._client.trades)
        self.triggers = _SyncService(self._loop, self._client.triggers)
        self.transfers = _SyncService(self._loop, self._client.transfers)
        self.internal_transfers = _SyncService(self._loop, self._client.internal_transfers)
        self.deposit = _SyncService(self._loop, self._client.deposit)
        self.api_keys = _SyncService(self._loop, self._client.api_keys)
        self.policies = _SyncService(self._loop, self._client.policies)
        self.sub_accounts = _SyncService(self._loop, self._client.sub_accounts)
        self.resolve = _SyncService(self._loop, self._client.resolve)
        self.accounts = self.resolve
        self.address_book = _SyncService(self._loop, self._client.address_book)
        self.social_verification = _SyncService(self._loop, self._client.social_verification)
        self.whiteboard = _SyncService(self._loop, self._client.whiteboard)
        self.polychart = _SyncService(self._loop, self._client.polychart)
        self.layout = _SyncService(self._loop, self._client.layout)
        self.guard_signer = _SyncService(self._loop, self._client.guard_signer)
        self.ledger_write = _SyncService(self._loop, self._client.ledger_write)
        self.withdraw = _SyncService(self._loop, self._client.withdraw)
        self.trading_withdraws = self.withdraw

    @classmethod
    def from_env(cls, **overrides) -> Polyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
        return cls(**overrides)

    async def _create_client(self, config: dict) -> AsyncPolyester:
        return AsyncPolyester(**config)

    def close(self) -> None:
        self._loop.run_until_complete(self._client.aclose())
        self._loop.close()

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
        if not asyncio.iscoroutinefunction(attr):
            return attr

        def call(*args, **kwargs):
            return self._loop.run_until_complete(attr(*args, **kwargs))

        return call
