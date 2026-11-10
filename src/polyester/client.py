from __future__ import annotations

import asyncio
import contextlib
import os
import threading
from typing import Any, Literal

from polyester._sync_bridge import refuse_on_client_loop, run_on_loop
from polyester._sync_services import (
    SyncAddressBookService,
    SyncApiKeysService,
    SyncAuthService,
    SyncBalancesService,
    SyncChainAnalyticsService,
    SyncChangelogService,
    SyncDepositService,
    SyncFeeService,
    SyncGuardSignerService,
    SyncHeatmapService,
    SyncInternalTransfersService,
    SyncLifecycleService,
    SyncMarketDataService,
    SyncMarketOverviewService,
    SyncOrderbookService,
    SyncOrdersService,
    SyncPoliciesService,
    SyncProfileService,
    SyncRateLimitService,
    SyncRealtimeClient,
    SyncSocialVerificationService,
    SyncSubAccountsService,
    SyncTradesService,
    SyncTransfersService,
    SyncTriggersService,
    SyncVIPService,
    SyncWithdrawService,
    SyncZipperService,
)
from polyester.auth import (
    ACCOUNT_ID_ENV,
    API_KEY_ID_ENV,
    API_PRIVATE_KEY_ENV,
    load_api_key_credentials,
)
from polyester.catalogs import CatalogManager
from polyester.environment import (
    ENV_NAME_ENV,
    ENV_NAME_ENV_ALIAS,
    POLYESTER_DEVNET_ENVIRONMENT,
    PolyesterEnvironment,
    environment_from_name,
    parse_polyester_environment,
)
from polyester.errors import PolyesterError, PolyesterTransportError, PolyesterValidationError
from polyester.realtime.client import AsyncRealtimeClient
from polyester.services import (
    AsyncAddressBookService,
    AsyncApiKeysService,
    AsyncAuthService,
    AsyncBalancesService,
    AsyncChainAnalyticsService,
    AsyncChangelogService,
    AsyncDepositService,
    AsyncFeeService,
    AsyncGuardSignerService,
    AsyncHeatmapService,
    AsyncInternalTransfersService,
    AsyncLifecycleService,
    AsyncMarketDataService,
    AsyncMarketOverviewService,
    AsyncOrderbookService,
    AsyncOrdersService,
    AsyncPoliciesService,
    AsyncRateLimitService,
    AsyncSocialVerificationService,
    AsyncSubAccountsService,
    AsyncTradesService,
    AsyncTransfersService,
    AsyncTriggersService,
    AsyncVIPService,
    AsyncWithdrawService,
    AsyncZipperService,
)
from polyester.services._scope import default_sub_account_scope
from polyester.sync_subscribe import SyncSubscription
from polyester.transport import TransportConfig, TransportFactory

DEFAULT_API_URL = POLYESTER_DEVNET_ENVIRONMENT.api_url
DEFAULT_WS_URL = POLYESTER_DEVNET_ENVIRONMENT.websocket_url
API_URL_ENV = "POLYESTER_API_URL"
WS_URL_ENV = "POLYESTER_WS_URL"


def _apply_from_env(overrides: dict[str, Any]) -> dict[str, Any]:
    """Fill missing constructor kwargs from ``POLYESTER_*`` process env."""
    if "environment" not in overrides:
        env_name = os.getenv(ENV_NAME_ENV) or os.getenv(ENV_NAME_ENV_ALIAS)
        if env_name:
            overrides["environment"] = environment_from_name(env_name)
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
    if "api_url" not in overrides:
        api_url = os.getenv(API_URL_ENV)
        if api_url:
            overrides["api_url"] = api_url.strip()
    if "ws_url" not in overrides:
        ws_url = os.getenv(WS_URL_ENV)
        if ws_url:
            overrides["ws_url"] = ws_url.strip()
    return overrides


class AsyncPolyester:
    def __init__(
        self,
        *,
        environment: PolyesterEnvironment | None = None,
        api_key_id: str | None = None,
        api_private_key: str | bytes | None = None,
        api_url: str | None = None,
        ws_url: str | None = None,
        default_sub_account_id: str | int | None = None,
        default_account_id: str | int | None = None,
        timeout: float = 10.0,
        wire_format: Literal["binary", "json"] = "binary",
        hydrate_catalogs: bool = True,
        recv_window_ms: int | None = None,
    ) -> None:
        """``default_sub_account_id`` scopes every call that takes a sub-account
        and names none: a public ID string, or the numeric ID as an ``int``. An
        empty string or ``None`` means the main account. 0, ``False`` and any
        other type raise :class:`PolyesterValidationError` here.

        ``recv_window_ms`` is the receive window of every signed API request,
        sent as the signed ``X-API-RECV-WINDOW`` header: the server processes a
        request only until its signing timestamp plus that many milliseconds,
        and refuses it after that, having changed nothing, as the retryable
        :class:`PolyesterTimestampSkewError`, or ``REQUEST_DEADLINE_EXCEEDED``
        once authenticated. It must be an ``int`` from 1 to 60000; any other
        value raises :class:`PolyesterValidationError` here. ``None``, the
        default, sends no header, and the server applies 10000. Realtime token
        requests always use the default.
        """
        default_sub_account_id = default_sub_account_scope(default_sub_account_id)
        resolved = parse_polyester_environment(environment or POLYESTER_DEVNET_ENVIRONMENT)
        self.environment = resolved
        self.api_url = api_url if api_url is not None else resolved.api_url
        self.ws_url = ws_url if ws_url is not None else resolved.websocket_url
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
                api_url=self.api_url,
                timeout=timeout,
                wire_format=wire_format,
                recv_window_ms=recv_window_ms,
            ),
            credentials=credentials,
        )
        self.realtime = AsyncRealtimeClient(
            self.ws_url,
            api_url=self.api_url,
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
            catalogs=self.catalogs,
            realtime=self.realtime,
            wait_for_catalogs=self.wait_for_catalogs,
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
        self.triggers = AsyncTriggersService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
            wait_for_catalogs=self.wait_for_catalogs,
        )
        self.orders = AsyncOrdersService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
            wait_for_catalogs=self.wait_for_catalogs,
            triggers=self.triggers,
        )
        self.trades = AsyncTradesService(
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
        self.fees = AsyncFeeService(self._transport, default_sub_account_id, catalogs=self.catalogs)
        self.api_keys = AsyncApiKeysService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.policies = AsyncPoliciesService(
            self._transport,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.sub_accounts = AsyncSubAccountsService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.address_book = AsyncAddressBookService(
            self._transport,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
        )
        self.social_verification = AsyncSocialVerificationService(self._transport)
        self.guard_signer = AsyncGuardSignerService(self._transport, default_sub_account_id)
        self.rate_limits = AsyncRateLimitService(self._transport, default_sub_account_id)
        self.vip = AsyncVIPService(self._transport)
        self.changelog = AsyncChangelogService(self._transport)
        self.withdraw = AsyncWithdrawService(self._transport, default_sub_account_id)
        self.trading_withdraws = self.withdraw
        self._catalog_last_error: BaseException | None = None
        self._catalog_task: asyncio.Task[None] | None
        if hydrate_catalogs:
            self._catalog_task = asyncio.create_task(self._hydrate_catalogs())
        else:
            self._catalog_task = None

    @classmethod
    def from_env(cls, **overrides) -> AsyncPolyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
        return cls(**_apply_from_env(overrides))

    @property
    def catalogs_last_error(self) -> BaseException | None:
        """Last catalog hydration failure, if any (also raised by ``wait_for_catalogs``)."""
        return self._catalog_last_error

    async def _hydrate_catalogs(self) -> None:
        """Hydrate spot + zipper catalogs. Records failure on ``catalogs_last_error``."""
        try:
            spot_config = await self.market_data.get_spot_config()
            raw = spot_config.raw if hasattr(spot_config, "raw") else spot_config
            if not isinstance(raw, dict):
                raise PolyesterValidationError("spot catalog response is not an object")
            self.catalogs.hydrate_spot_config(raw)
            zipper_config = await self.zipper.get_deposit_withdraw_config()
            self.catalogs.hydrate_zipper_config(zipper_config)
            self._catalog_last_error = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self.catalogs.is_unusable:
                self.catalogs.mark_unusable(f"catalog hydration failed: {exc}")
            if isinstance(exc, PolyesterError):
                self._catalog_last_error = exc
            else:
                wrapped = PolyesterTransportError(f"catalog hydration failed: {exc}")
                wrapped.__cause__ = exc
                self._catalog_last_error = wrapped

    async def wait_for_catalogs(self) -> None:
        """Await construction-time catalog hydration.

        Raises when hydration failed (HTTP errors, empty/malformed catalogs, bad
        scales/ids). Previously returned successfully after a failed best-effort
        attempt — that behavior is removed (POLY-3746).
        """
        if self._catalog_task is None:
            return
        try:
            await self._catalog_task
        except asyncio.CancelledError:
            if self._catalog_last_error is not None:
                raise self._catalog_last_error from None
            raise
        if self._catalog_last_error is not None:
            raise self._catalog_last_error

    async def __aenter__(self) -> AsyncPolyester:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._catalog_task is not None and not self._catalog_task.done():
            self._catalog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._catalog_task
        await self.realtime.aclose()
        await self._transport.aclose()


class Polyester:
    """The client for synchronous code: each call runs the :class:`AsyncPolyester`
    call of the same name on a private event loop and returns its result.
    It takes the parameters of :class:`AsyncPolyester`."""

    def __init__(
        self,
        *,
        environment: PolyesterEnvironment | None = None,
        api_key_id: str | None = None,
        api_private_key: str | bytes | None = None,
        api_url: str | None = None,
        ws_url: str | None = None,
        default_sub_account_id: str | int | None = None,
        default_account_id: str | int | None = None,
        timeout: float = 10.0,
        wire_format: Literal["binary", "json"] = "binary",
        hydrate_catalogs: bool = True,
        recv_window_ms: int | None = None,
    ) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever,
            name="polyester-sync-loop",
            daemon=True,
        )
        # The loop runs this first, so once it is set the loop is running.
        loop_started = threading.Event()
        self._loop.call_soon(loop_started.set)
        self._loop_thread.start()
        while not loop_started.wait(0.05):
            if not self._loop_thread.is_alive():
                self._loop.close()
                raise PolyesterError("the client's event loop did not start")
        self._active_sync_subscriptions: list[SyncSubscription] = []

        async def _bootstrap() -> AsyncPolyester:
            client = AsyncPolyester(
                environment=environment,
                api_key_id=api_key_id,
                api_private_key=api_private_key,
                api_url=api_url,
                ws_url=ws_url,
                default_sub_account_id=default_sub_account_id,
                default_account_id=default_account_id,
                timeout=timeout,
                wire_format=wire_format,
                hydrate_catalogs=hydrate_catalogs,
                recv_window_ms=recv_window_ms,
            )
            if hydrate_catalogs:
                await client.wait_for_catalogs()
            return client

        try:
            self._client = run_on_loop(self._loop, _bootstrap)
        except BaseException:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop_thread.join(timeout=5)
            raise
        loop = self._loop
        client = self._client
        subscriptions = self._active_sync_subscriptions
        self.catalogs = client.catalogs
        self.catalog = self.catalogs
        self.realtime = SyncRealtimeClient(loop, client.realtime)
        self.auth = SyncAuthService(loop, client.auth)
        self.auth.profile = SyncProfileService(loop, client.auth.profile, subscriptions)
        self.chain_analytics = SyncChainAnalyticsService(loop, client.chain_analytics)
        self.market_data = SyncMarketDataService(loop, client.market_data, subscriptions)
        self.candles = self.market_data
        self.market_overview = SyncMarketOverviewService(
            loop, client.market_overview, subscriptions
        )
        self.zipper = SyncZipperService(loop, client.zipper, subscriptions)
        self.heatmap = SyncHeatmapService(loop, client.heatmap, subscriptions)
        self.lifecycle = SyncLifecycleService(loop, client.lifecycle, subscriptions)
        self.balances = SyncBalancesService(loop, client.balances, subscriptions)
        self.orderbook = SyncOrderbookService(loop, client.orderbook, subscriptions)
        self.orders = SyncOrdersService(loop, client.orders, subscriptions)
        self.trades = SyncTradesService(loop, client.trades, subscriptions)
        self.triggers = SyncTriggersService(loop, client.triggers, subscriptions)
        self.transfers = SyncTransfersService(loop, client.transfers, subscriptions)
        self.internal_transfers = SyncInternalTransfersService(loop, client.internal_transfers)
        self.deposit = SyncDepositService(loop, client.deposit)
        self.fees = SyncFeeService(loop, client.fees)
        self.api_keys = SyncApiKeysService(loop, client.api_keys, subscriptions)
        self.policies = SyncPoliciesService(loop, client.policies, subscriptions)
        self.sub_accounts = SyncSubAccountsService(loop, client.sub_accounts, subscriptions)
        self.address_book = SyncAddressBookService(loop, client.address_book, subscriptions)
        self.social_verification = SyncSocialVerificationService(loop, client.social_verification)
        self.guard_signer = SyncGuardSignerService(loop, client.guard_signer)
        self.rate_limits = SyncRateLimitService(loop, client.rate_limits)
        self.vip = SyncVIPService(loop, client.vip)
        self.changelog = SyncChangelogService(loop, client.changelog)
        self.withdraw = SyncWithdrawService(loop, client.withdraw)
        self.trading_withdraws = self.withdraw

    @classmethod
    def from_env(cls, **overrides) -> Polyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
        return cls(**_apply_from_env(overrides))

    def close(self) -> None:
        """Close every sync subscription and the client.

        A subscription that failed with no ``on_error`` raises its failure here, once
        everything has shut down, as does a close a callback scheduled that failed.

        Calling it from a client callback raises
        :class:`~polyester.errors.PolyesterError` at once and leaves the client
        open: the callback runs on the client loop, which can't be stopped from
        inside. Close a subscription from its callback instead, or close the
        client from another thread.
        """
        refuse_on_client_loop(self._loop, "Polyester.close()")
        first_failure: Exception | None = None
        for subscription in list(self._active_sync_subscriptions):
            try:
                subscription.close()
            except Exception as exc:
                first_failure = first_failure or exc
        self._active_sync_subscriptions.clear()

        async def _shutdown() -> None:
            await self._client.aclose()

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        with contextlib.suppress(Exception):
            future.result(timeout=10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=5)
        if first_failure is not None:
            raise first_failure

    def __enter__(self) -> Polyester:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
