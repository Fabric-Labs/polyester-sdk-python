from __future__ import annotations

import asyncio
import contextlib
import math
import os
import threading
import time
from typing import Any, Literal, NoReturn

from google.protobuf.message import Message

from polyester._catalog_startup import CatalogSource, load_catalog
from polyester._redact import register_url_secrets
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
from polyester._wire import protobuf_to_public_dict
from polyester.auth import (
    ACCOUNT_ID_ENV,
    API_KEY_ID_ENV,
    API_PRIVATE_KEY_ENV,
    load_api_key_credentials,
)
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.zipper import deposit_withdraw_config_from_proto
from polyester.codecs.spot_config import spot_config_from_dict
from polyester.environment import (
    ENV_NAME_ENV,
    ENV_NAME_ENV_ALIAS,
    POLYESTER_DEVNET_ENVIRONMENT,
    PolyesterEnvironment,
    environment_from_name,
    parse_polyester_environment,
)
from polyester.errors import (
    PolyesterCatalogHydrationError,
    PolyesterError,
    PolyesterValidationError,
)
from polyester.gen.chain.zipper.v1.zipper_connect import ZipperServiceClient
from polyester.gen.chain.zipper.v1.zipper_pb2 import GetDepositWithdrawConfigRequest
from polyester.gen.marketdata.v1.marketdata_connect import MarketDataServiceClient
from polyester.gen.marketdata.v1.marketdata_pb2 import GetSpotConfigRequest
from polyester.models.system import ServerVersion
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
from polyester.services.system import AsyncSystemService
from polyester.sync_subscribe import SyncSubscription
from polyester.transport import TransportConfig, TransportFactory

SPOT_CONFIG = CatalogSource(
    catalog="spot",
    name="spot config",
    operation="marketdata.v1.MarketDataService/GetSpotConfig",
    client_cls=MarketDataServiceClient,
    read=lambda client, timeout_ms: client.get_spot_config(
        GetSpotConfigRequest(), timeout_ms=timeout_ms
    ),
)
FUNDING_CONFIG = CatalogSource(
    catalog="funding",
    name="funding config",
    operation="chain.zipper.v1.ZipperService/GetDepositWithdrawConfig",
    client_cls=ZipperServiceClient,
    read=lambda client, timeout_ms: client.get_deposit_withdraw_config(
        GetDepositWithdrawConfigRequest(), timeout_ms=timeout_ms
    ),
)

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
        catalog_timeout: float | None = None,
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
        default, sends no header, and the server applies 5000. Realtime token
        requests always use the default.

        ``timeout`` is the deadline of each request, in seconds. With
        ``hydrate_catalogs`` the client loads the spot config and the funding
        (deposit/withdraw) config when it is created, each on its own, and
        reads one again when a connection drops or a read times out: at most
        3 reads each, with backoff, every retry on a new connection, all
        within ``catalog_timeout`` seconds of creating the client (by default
        twice ``timeout``). See :meth:`wait_for_catalogs` and
        :meth:`wait_for_funding_catalog`.
        """
        startup_timeout = _catalog_timeout(catalog_timeout, timeout)
        default_sub_account_id = default_sub_account_scope(default_sub_account_id)
        resolved = parse_polyester_environment(environment or POLYESTER_DEVNET_ENVIRONMENT)
        self.environment = resolved
        self.api_url = api_url if api_url is not None else resolved.api_url
        self.ws_url = ws_url if ws_url is not None else resolved.websocket_url
        register_url_secrets(self.ws_url)
        self.default_sub_account_id = default_sub_account_id
        self.default_account_id = default_account_id
        self.catalogs = CatalogManager()
        # Services that read the catalogs wait for construction-time hydration:
        # every one of them for the spot config, the zipper supply stream for
        # the funding config.
        catalog_wait = self._await_catalog_hydration if hydrate_catalogs else None
        funding_wait = self._await_funding_hydration if hydrate_catalogs else None
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
            wait_for_catalogs=catalog_wait,
        )
        self.candles = self.market_data
        self.market_overview = AsyncMarketOverviewService(
            self._transport,
            catalogs=self.catalogs,
            realtime=self.realtime,
            wait_for_catalogs=catalog_wait,
        )
        self.zipper = AsyncZipperService(
            self._transport,
            catalogs=self.catalogs,
            realtime=self.realtime,
            wait_for_catalogs=funding_wait,
        )
        self.heatmap = AsyncHeatmapService(
            self._transport,
            self.catalogs,
            realtime=self.realtime,
            wait_for_catalogs=catalog_wait,
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
            wait_for_catalogs=catalog_wait,
        )
        self.triggers = AsyncTriggersService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
            wait_for_catalogs=catalog_wait,
        )
        self.orders = AsyncOrdersService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
            wait_for_catalogs=catalog_wait,
            triggers=self.triggers,
        )
        self.trades = AsyncTradesService(
            self._transport,
            self.catalogs,
            default_sub_account_id,
            default_account_id=default_account_id,
            realtime=self.realtime,
            wait_for_catalogs=catalog_wait,
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
        self.fees = AsyncFeeService(
            self._transport,
            default_sub_account_id,
            catalogs=self.catalogs,
            wait_for_catalogs=catalog_wait,
        )
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
        self._system = AsyncSystemService(self._transport)
        self.withdraw = AsyncWithdrawService(self._transport, default_sub_account_id)
        self.trading_withdraws = self.withdraw
        self._timeout = timeout
        self._spot_failure: PolyesterCatalogHydrationError | None = None
        self._funding_failure: PolyesterCatalogHydrationError | None = None
        self._catalog_task: asyncio.Task[None] | None = None
        self._funding_task: asyncio.Task[None] | None = None
        if hydrate_catalogs:
            deadline = time.monotonic() + startup_timeout
            self._catalog_task = asyncio.create_task(self._hydrate_spot(deadline))
            self._funding_task = asyncio.create_task(self._hydrate_funding(deadline))

    @classmethod
    def from_env(cls, **overrides) -> AsyncPolyester:
        """Create a client using ``POLYESTER_*`` variables from the process environment."""
        return cls(**_apply_from_env(overrides))

    @property
    def catalogs_last_error(self) -> BaseException | None:
        """Why the spot config failed to load, if it did: the ``__cause__`` of the
        :class:`PolyesterCatalogHydrationError` that :meth:`wait_for_catalogs` raises."""
        failure = self._spot_failure
        if failure is None:
            return None
        return failure.__cause__ or failure

    async def _hydrate_spot(self, deadline: float) -> None:
        """Load the spot config; on failure every spot lookup fails closed."""

        def install(response: Message) -> None:
            spot_config = spot_config_from_dict(protobuf_to_public_dict(response))
            raw = spot_config.raw if hasattr(spot_config, "raw") else spot_config
            if not isinstance(raw, dict):
                raise PolyesterValidationError("spot catalog response is not an object")
            self.catalogs.hydrate_spot_config(raw)

        try:
            await load_catalog(
                self._transport,
                SPOT_CONFIG,
                install,
                request_timeout=self._timeout,
                deadline=deadline,
            )
        except PolyesterCatalogHydrationError as exc:
            self.catalogs.mark_spot_unusable(str(exc))
            self._spot_failure = exc

    async def _hydrate_funding(self, deadline: float) -> None:
        """Load the funding config; on failure only funding lookups fail closed."""

        def install(response: Message) -> None:
            self.catalogs.hydrate_zipper_config(
                deposit_withdraw_config_from_proto(response)  # type: ignore[arg-type]
            )

        try:
            await load_catalog(
                self._transport,
                FUNDING_CONFIG,
                install,
                request_timeout=self._timeout,
                deadline=deadline,
            )
        except PolyesterCatalogHydrationError as exc:
            self.catalogs.mark_funding_unusable(str(exc))
            self._funding_failure = exc

    async def get_version(self) -> ServerVersion:
        """The build the API serves: its ``version``, source ``commit`` and
        ``environment``. Needs no API key and sends none."""
        return await self._system.get_version()

    async def wait_for_catalogs(self) -> None:
        """Wait until the spot config, which every spot trading call needs, is ready.

        Returns once it has loaded and validated, so spot calls can go on even
        while the funding config is still loading or failed to: that one has
        :meth:`wait_for_funding_catalog`. Raises
        :class:`PolyesterCatalogHydrationError` when the spot config could not be
        loaded (a read that kept timing out or losing its connection, an error
        answer, an empty or malformed catalog), naming the operation, the kind
        of failure and the response reference; its ``__cause__`` is the failure.
        Calls that name a market then raise it too: they fail closed.

        Calls that name a market by symbol or need a pair's scales already wait
        for the spot config themselves; call this to learn early whether it
        failed. Cancelling this call leaves the load running.
        """
        await self._await_catalog_hydration()

    async def wait_for_funding_catalog(self) -> None:
        """Wait until the funding (deposit/withdraw) config is ready.

        Raises :class:`PolyesterCatalogHydrationError` naming the funding config
        when it could not be loaded. Read ``client.catalogs.zipper`` (and the
        asset lookups that use it) after this returns. Cancelling this call
        leaves the load running.
        """
        await self._await_funding_hydration()

    async def _await_catalog_hydration(self) -> None:
        """Wait for the spot config before a service reads the catalogs.

        A failed load raises :class:`PolyesterCatalogHydrationError`, so a call
        that needs the catalogs names why they are missing rather than refusing
        the symbol as unknown.
        """
        await _settled_or_raise(self._catalog_task, lambda: self._spot_failure, "spot config")

    async def _await_funding_hydration(self) -> None:
        await _settled_or_raise(self._funding_task, lambda: self._funding_failure, "funding config")

    async def __aenter__(self) -> AsyncPolyester:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        for task in (self._catalog_task, self._funding_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        await self.realtime.aclose()
        await self._transport.aclose()


def _catalog_timeout(catalog_timeout: object, timeout: float) -> float:
    if catalog_timeout is None:
        return 2 * timeout
    if (
        isinstance(catalog_timeout, bool)
        or not isinstance(catalog_timeout, int | float)
        or not math.isfinite(catalog_timeout)
        or catalog_timeout <= 0
    ):
        raise PolyesterValidationError(
            "catalog_timeout must be a positive, finite number of seconds"
        )
    return float(catalog_timeout)


async def _catalog_task_settled(task: asyncio.Task[None]) -> None:
    """Return once ``task`` has ended.

    Unlike awaiting the task, a caller cancelled while it waits leaves the
    shared hydration running for every other call.
    """
    if not task.done():
        await asyncio.wait((task,))


async def _settled_or_raise(
    task: asyncio.Task[None] | None,
    failure: Any,
    name: str,
) -> None:
    """Wait for a catalog load and raise a fresh copy of its failure, if any.

    A copy, so each caller gets a traceback of its own, with the same cause.
    """
    if task is None:
        return
    await _catalog_task_settled(task)
    error: PolyesterCatalogHydrationError | None = failure()
    if error is not None:
        _raise_copy(error)
    if task.cancelled():
        raise PolyesterCatalogHydrationError(
            f"catalog hydration failed: the client was closed before the {name} loaded"
        )


def _raise_copy(error: PolyesterCatalogHydrationError) -> NoReturn:
    raise PolyesterCatalogHydrationError(
        str(error),
        catalog=error.catalog,
        operation=error.operation,
        failure=error.failure,
        attempts=error.attempts,
        response_ref=error.response_ref,
    ) from error.__cause__


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
        catalog_timeout: float | None = None,
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
                catalog_timeout=catalog_timeout,
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

    def get_version(self) -> ServerVersion:
        """The build the API serves: its ``version``, source ``commit`` and
        ``environment``. Needs no API key and sends none."""
        return run_on_loop(
            self._loop, self._client.get_version, what="Polyester.get_version()"
        )

    def wait_for_funding_catalog(self) -> None:
        """Wait until the funding (deposit/withdraw) config is ready.

        The client returns from its constructor once the spot config is ready;
        the funding config may still be loading. Raises
        :class:`PolyesterCatalogHydrationError` naming the funding config when
        it could not be loaded.
        """
        run_on_loop(
            self._loop,
            self._client.wait_for_funding_catalog,
            what="Polyester.wait_for_funding_catalog()",
        )

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
