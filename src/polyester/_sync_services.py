"""Typed views of the async services for the sync :class:`~polyester.Polyester` client.

Each ``Sync*Service`` declares every public member of its async service with
the async signature: a coroutine method returns its result, an async generator
method returns a plain iterator, and a ``subscribe*_sync`` method takes the
keywords of the async subscription it starts. At runtime a declared member
forwards to the async service on the client's event loop.
``tests/unit/test_sync_client_surface.py`` keeps the declarations in step with
the async services.
"""

from __future__ import annotations

import asyncio
import builtins
import inspect
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from typing import TYPE_CHECKING, Any, Concatenate, Generic, ParamSpec, TypeVar, Unpack, overload

from polyester._sync_bridge import run_on_loop
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
    AsyncProfileService,
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
from polyester.sync_subscribe import SyncSubscription
from polyester.sync_subscribe import subscribe_sync as _subscribe_sync_impl

if TYPE_CHECKING:
    from polyester.models import (
        ApiData,
        ApiKeySummary,
        ApiPolicy,
        AssetBalance,
        Candle,
        CreateOrderParams,
        CreateOrderRequest,
        LedgerTransfer,
        LifecycleFlowSummary,
        MarketOverviewEntry,
        OrderbookData,
        OrderMutationResult,
        PreviewOrderResult,
        PrivateOrdersEvent,
        SubAccount,
        SubaccountPolicy,
        Trigger,
        TriggerEvent,
        UserTrade,
        ZippedAssetSupplyBatch,
    )
    from polyester.models.auth import AccountIdentity
    from polyester.models.realtime import AddressBookViewInvalidation
    from polyester.services._scope import AccountScope

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")


class SyncMember(Generic[P, R]):
    """One async service member as the sync client exposes it: called with the
    async member's parameters, it returns ``R`` on the caller's thread."""

    def __init__(self, member: Callable[..., Any], kind: str) -> None:
        self.member = member
        self.kind = kind
        self.name = getattr(member, "__name__", "")

    def __set_name__(self, owner: type[Any], name: str) -> None:
        self.name = name

    @overload
    def __get__(self, obj: None, owner: type[Any]) -> SyncMember[P, R]: ...

    @overload
    def __get__(self, obj: _SyncService, owner: type[Any]) -> Callable[P, R]: ...

    def __get__(self, obj: _SyncService | None, owner: type[Any]) -> Any:
        if obj is None:
            return self
        return obj._forward(self.name)


def call(member: Callable[Concatenate[Any, P], Coroutine[Any, Any, R]]) -> SyncMember[P, R]:
    """A coroutine method, run on the client loop until it ends."""
    return SyncMember(member, "call")


def iterate(member: Callable[Concatenate[Any, P], AsyncIterator[T]]) -> SyncMember[P, Iterator[T]]:
    """An async generator method, driven on the client loop as a plain iterator."""
    return SyncMember(member, "iterate")


def plain(member: Callable[Concatenate[Any, P], R]) -> SyncMember[P, R]:
    """A plain method; a coroutine it returns is run on the client loop."""
    return SyncMember(member, "plain")


F = TypeVar("F", bound=Callable[..., SyncSubscription])


def subscribes(target: str) -> Callable[[F], F]:
    """Name the async method a ``subscribe*_sync`` method starts."""

    def mark(method: F) -> F:
        method.__sync_subscribes__ = target  # type: ignore[attr-defined]
        return method

    return mark


class _SyncService:
    def __init__(self, loop: asyncio.AbstractEventLoop, service: object) -> None:
        self._loop = loop
        self._service = service

    def _forward(self, name: str) -> Any:
        attr = getattr(self._service, name)
        if isinstance(attr, _SyncService):
            return attr
        if not callable(attr) and type(attr).__name__.endswith("Service"):
            return _SyncService(self._loop, attr)
        if inspect.isasyncgenfunction(attr):
            return self._sync_iterator(attr)
        if inspect.iscoroutinefunction(attr):

            def async_call(*args: Any, **kwargs: Any) -> Any:
                return run_on_loop(self._loop, lambda: attr(*args, **kwargs))

            return async_call

        if callable(attr):

            def call(*args: Any, **kwargs: Any) -> Any:
                result = attr(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return run_on_loop(self._loop, lambda: result)
                return result

            return call
        return attr

    if not TYPE_CHECKING:
        # Members not declared on a typed view still forward, untyped.
        def __getattr__(self, name: str) -> Any:
            return self._forward(name)

    def _sync_iterator(self, attr: Callable[..., AsyncIterator[T]]) -> Callable[..., Iterator[T]]:
        """Drive an async generator method on the client loop, one item per
        step, as a plain iterator. Leaving the loop early closes it."""

        async def step(agen: AsyncIterator[T]) -> tuple[bool, T | None]:
            try:
                return True, await agen.__anext__()
            except StopAsyncIteration:
                return False, None

        def iterate(*args: Any, **kwargs: Any) -> Iterator[T]:
            agen = attr(*args, **kwargs)
            try:
                while True:
                    has_item, item = run_on_loop(self._loop, lambda: step(agen))
                    if not has_item:
                        return
                    yield item  # type: ignore[misc]
            finally:
                if self._loop.is_running():
                    run_on_loop(self._loop, agen.aclose)  # type: ignore[attr-defined]

        return iterate


class _SyncSubscribeService(_SyncService):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        service: object,
        active_subscriptions: builtins.list[SyncSubscription],
    ) -> None:
        super().__init__(loop, service)
        self._active_subscriptions = active_subscriptions

    def _subscribe_sync(
        self,
        async_attr: str,
        on_event: Callable[[Any], object],
        on_error: Callable[[Exception], object] | None,
        **kwargs: Any,
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


class SyncAuthService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncAuthService`."""

    profile: SyncProfileService

    me = call(AsyncAuthService.me)


class SyncProfileService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncProfileService`."""

    subscribe_identity = call(AsyncProfileService.subscribe_identity)

    @subscribes("subscribe_identity")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[AccountIdentity], object],
        on_error: Callable[[Exception], object] | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe_identity", on_event, on_error)


class SyncChainAnalyticsService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncChainAnalyticsService`."""

    get_unified_asset_balances = call(AsyncChainAnalyticsService.get_unified_asset_balances)
    get_zipped_asset_supply = call(AsyncChainAnalyticsService.get_zipped_asset_supply)
    get_zipped_asset_supply_group = call(AsyncChainAnalyticsService.get_zipped_asset_supply_group)


class SyncMarketDataService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncMarketDataService`."""

    get_candles = call(AsyncMarketDataService.get_candles)
    get_candles_columns = call(AsyncMarketDataService.get_candles_columns)
    get_current_candle = call(AsyncMarketDataService.get_current_candle)
    get_spot_config = call(AsyncMarketDataService.get_spot_config)
    get_trades = call(AsyncMarketDataService.get_trades)
    subscribe_candles = call(AsyncMarketDataService.subscribe_candles)
    subscribe_trades = plain(AsyncMarketDataService.subscribe_trades)

    @subscribes("subscribe_trades")
    def subscribe_trades_sync(
        self,
        *,
        on_event: Callable[[Any], object],
        on_error: Callable[[Exception], object] | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_trades", on_event, on_error, symbol=symbol, symbol_id=symbol_id
        )

    @subscribes("subscribe_candles")
    def subscribe_candles_sync(
        self,
        *,
        on_event: Callable[[Candle], object],
        on_error: Callable[[Exception], object] | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        timeframe: str = "1m",
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_candles",
            on_event,
            on_error,
            symbol=symbol,
            symbol_id=symbol_id,
            timeframe=timeframe,
        )


class SyncMarketOverviewService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncMarketOverviewService`."""

    create_subscription = call(AsyncMarketOverviewService.create_subscription)
    get_currency_conversion_config = call(AsyncMarketOverviewService.get_currency_conversion_config)
    get_currency_conversion_rates = call(AsyncMarketOverviewService.get_currency_conversion_rates)
    get_spot_volume_history = call(AsyncMarketOverviewService.get_spot_volume_history)
    list = call(AsyncMarketOverviewService.list)
    subscribe = call(AsyncMarketOverviewService.subscribe)

    @subscribes("create_subscription")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[builtins.list[MarketOverviewEntry]], object],
        on_error: Callable[[Exception], object] | None = None,
        symbols: builtins.list[str] | None = None,
        limit: int = 50,
        include_sparklines: bool = False,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "create_subscription",
            on_event,
            on_error,
            symbols=symbols,
            limit=limit,
            include_sparklines=include_sparklines,
            on_open=on_open,
            on_close=on_close,
        )


class SyncZipperService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncZipperService`."""

    get_deposit_withdraw_config = call(AsyncZipperService.get_deposit_withdraw_config)
    subscribe_zipped_asset_supply = call(AsyncZipperService.subscribe_zipped_asset_supply)

    @subscribes("subscribe_zipped_asset_supply")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[ZippedAssetSupplyBatch], object],
        on_error: Callable[[Exception], object] | None = None,
        patch_catalog: bool = True,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_zipped_asset_supply", on_event, on_error, patch_catalog=patch_catalog
        )


class SyncHeatmapService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncHeatmapService`."""

    get = call(AsyncHeatmapService.get)
    subscribe_live = call(AsyncHeatmapService.subscribe_live)

    @subscribes("subscribe_live")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[ApiData], object],
        on_error: Callable[[Exception], object] | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        interval: str = "1s",
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_live",
            on_event,
            on_error,
            symbol=symbol,
            symbol_id=symbol_id,
            interval=interval,
        )


class SyncLifecycleService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncLifecycleService`."""

    get_flow = call(AsyncLifecycleService.get_flow)
    get_flow_by_tx = call(AsyncLifecycleService.get_flow_by_tx)
    list_flows = call(AsyncLifecycleService.list_flows)
    list_flows_by_tx = call(AsyncLifecycleService.list_flows_by_tx)
    subscribe_flow_detail = call(AsyncLifecycleService.subscribe_flow_detail)
    subscribe_open_flows = call(AsyncLifecycleService.subscribe_open_flows)

    @subscribes("subscribe_open_flows")
    def subscribe_open_flows_sync(
        self,
        *,
        on_event: Callable[[LifecycleFlowSummary], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_open_flows", on_event, on_error, account_id=account_id
        )

    @subscribes("subscribe_flow_detail")
    def subscribe_flow_detail_sync(
        self,
        *,
        on_event: Callable[[LifecycleFlowSummary], object],
        on_error: Callable[[Exception], object] | None = None,
        flow_id: str,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe_flow_detail", on_event, on_error, flow_id=flow_id)


class SyncBalancesService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncBalancesService`."""

    get_balance_history = call(AsyncBalancesService.get_balance_history)
    get_equity_history = call(AsyncBalancesService.get_equity_history)
    list = call(AsyncBalancesService.list)
    subscribe = call(AsyncBalancesService.subscribe)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[AssetBalance], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)


class SyncOrderbookService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncOrderbookService`."""

    create_subscription = call(AsyncOrderbookService.create_subscription)
    get = call(AsyncOrderbookService.get)
    subscribe = call(AsyncOrderbookService.subscribe)
    subscribe_deltas = call(AsyncOrderbookService.subscribe_deltas)

    @subscribes("create_subscription")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[OrderbookData], object],
        on_error: Callable[[Exception], object] | None = None,
        symbol: str,
        symbol_id: int | None = None,
        depth: int = 50,
        bucket: str | None = None,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_sequence_gap: Callable[[], None] | None = None,
        on_reconnect: Callable[[], None] | None = None,
        on_snapshot_refresh: Callable[[], None] | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "create_subscription",
            on_event,
            on_error,
            symbol=symbol,
            symbol_id=symbol_id,
            depth=depth,
            bucket=bucket,
            on_open=on_open,
            on_close=on_close,
            on_sequence_gap=on_sequence_gap,
            on_reconnect=on_reconnect,
            on_snapshot_refresh=on_snapshot_refresh,
        )


class SyncOrdersService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncOrdersService`."""

    batch_cancel = call(AsyncOrdersService.batch_cancel)
    batch_create = call(AsyncOrdersService.batch_create)
    batch_replace = call(AsyncOrdersService.batch_replace)
    cancel = call(AsyncOrdersService.cancel)
    cancel_all = call(AsyncOrdersService.cancel_all)
    cancel_all_after = call(AsyncOrdersService.cancel_all_after)
    if TYPE_CHECKING:
        # Overloads don't carry through ``call``: declared as on the async service.
        @overload
        def create(
            self, request: CreateOrderRequest, *, account: AccountScope | None = None
        ) -> OrderMutationResult: ...

        @overload
        def create(
            self, *, account: AccountScope | None = None, **kwargs: Unpack[CreateOrderParams]
        ) -> OrderMutationResult: ...

        def create(self, *args: Any, **kwargs: Any) -> OrderMutationResult: ...

    else:
        create = call(AsyncOrdersService.create)

    get = call(AsyncOrdersService.get)
    get_batch_replace_status = call(AsyncOrdersService.get_batch_replace_status)
    list_history = call(AsyncOrdersService.list_history)
    list_open = call(AsyncOrdersService.list_open)
    modify = call(AsyncOrdersService.modify)
    if TYPE_CHECKING:
        # Overloads don't carry through ``call``: declared as on the async service.
        @overload
        def preview_order(
            self, request: CreateOrderRequest, *, account: AccountScope | None = None
        ) -> PreviewOrderResult: ...

        @overload
        def preview_order(
            self, *, account: AccountScope | None = None, **kwargs: Unpack[CreateOrderParams]
        ) -> PreviewOrderResult: ...

        def preview_order(self, *args: Any, **kwargs: Any) -> PreviewOrderResult: ...

    else:
        preview_order = call(AsyncOrdersService.preview_order)

    stop_all_trading = call(AsyncOrdersService.stop_all_trading)
    subscribe = call(AsyncOrdersService.subscribe)
    wait_batch_replace = call(AsyncOrdersService.wait_batch_replace)
    wait_for_order_trades_complete = call(AsyncOrdersService.wait_for_order_trades_complete)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[PrivateOrdersEvent], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)


class SyncTradesService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncTradesService`."""

    list = call(AsyncTradesService.list)
    subscribe = call(AsyncTradesService.subscribe)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[UserTrade], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)


class SyncTriggersService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncTriggersService`."""

    cancel = call(AsyncTriggersService.cancel)
    create = call(AsyncTriggersService.create)
    get = call(AsyncTriggersService.get)
    list = call(AsyncTriggersService.list)
    list_events = call(AsyncTriggersService.list_events)
    modify = call(AsyncTriggersService.modify)
    pause = call(AsyncTriggersService.pause)
    resume = call(AsyncTriggersService.resume)
    subscribe = call(AsyncTriggersService.subscribe)
    subscribe_events = call(AsyncTriggersService.subscribe_events)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[Trigger], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)

    @subscribes("subscribe_events")
    def subscribe_events_sync(
        self,
        *,
        on_event: Callable[[TriggerEvent], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe_events", on_event, on_error, account_id=account_id)


class SyncTransfersService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncTransfersService`."""

    list = call(AsyncTransfersService.list)
    subscribe = call(AsyncTransfersService.subscribe)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[LedgerTransfer], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)


class SyncInternalTransfersService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncInternalTransfersService`."""

    create = call(AsyncInternalTransfersService.create)


class SyncDepositService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncDepositService`."""

    create_address = call(AsyncDepositService.create_address)
    list_addresses = call(AsyncDepositService.list_addresses)


class SyncFeeService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncFeeService`."""

    get_spot_fee_rates = call(AsyncFeeService.get_spot_fee_rates)


class SyncApiKeysService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncApiKeysService`."""

    generate_keypair = plain(AsyncApiKeysService.generate_keypair)
    get = call(AsyncApiKeysService.get)
    list = call(AsyncApiKeysService.list)
    subscribe = call(AsyncApiKeysService.subscribe)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[ApiKeySummary], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)


class SyncPoliciesService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncPoliciesService`."""

    subscribe_api_policies = call(AsyncPoliciesService.subscribe_api_policies)
    subscribe_subaccount_policies = call(AsyncPoliciesService.subscribe_subaccount_policies)

    @subscribes("subscribe_subaccount_policies")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[SubaccountPolicy], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_subaccount_policies", on_event, on_error, account_id=account_id
        )

    @subscribes("subscribe_api_policies")
    def subscribe_api_policies_sync(
        self,
        *,
        on_event: Callable[[ApiPolicy], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_api_policies", on_event, on_error, account_id=account_id
        )


class SyncSubAccountsService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncSubAccountsService`."""

    get = call(AsyncSubAccountsService.get)
    list = call(AsyncSubAccountsService.list)
    list_activity = call(AsyncSubAccountsService.list_activity)
    list_invites = call(AsyncSubAccountsService.list_invites)
    list_members = call(AsyncSubAccountsService.list_members)
    subscribe = call(AsyncSubAccountsService.subscribe)
    subscribe_api_keys = call(AsyncSubAccountsService.subscribe_api_keys)

    @subscribes("subscribe")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[SubAccount], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe", on_event, on_error, account_id=account_id)

    @subscribes("subscribe_api_keys")
    def subscribe_api_keys_sync(
        self,
        *,
        on_event: Callable[[ApiKeySummary], object],
        on_error: Callable[[Exception], object] | None = None,
        account_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync("subscribe_api_keys", on_event, on_error, account_id=account_id)


class SyncAddressBookService(_SyncSubscribeService):
    """``Polyester`` view of :class:`~polyester.services.AsyncAddressBookService`."""

    create_entry = call(AsyncAddressBookService.create_entry)
    create_tag = call(AsyncAddressBookService.create_tag)
    delete_entry = call(AsyncAddressBookService.delete_entry)
    delete_tag = call(AsyncAddressBookService.delete_tag)
    get_view = call(AsyncAddressBookService.get_view)
    get_withdraw_whitelist_view = call(AsyncAddressBookService.get_withdraw_whitelist_view)
    list_books = call(AsyncAddressBookService.list_books)
    list_entries = call(AsyncAddressBookService.list_entries)
    list_internal_transfer_whitelist_entries = call(
        AsyncAddressBookService.list_internal_transfer_whitelist_entries
    )
    list_transfer_counterparties = call(AsyncAddressBookService.list_transfer_counterparties)
    list_transfer_destinations = call(AsyncAddressBookService.list_transfer_destinations)
    subscribe_view_invalidations = call(AsyncAddressBookService.subscribe_view_invalidations)
    update_entry = call(AsyncAddressBookService.update_entry)
    update_tag = call(AsyncAddressBookService.update_tag)

    @subscribes("subscribe_view_invalidations")
    def subscribe_sync(
        self,
        *,
        on_event: Callable[[AddressBookViewInvalidation], object],
        on_error: Callable[[Exception], object] | None = None,
        root_account_public_id: str | int | None = None,
    ) -> SyncSubscription:
        return self._subscribe_sync(
            "subscribe_view_invalidations",
            on_event,
            on_error,
            root_account_public_id=root_account_public_id,
        )


class SyncSocialVerificationService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncSocialVerificationService`."""

    get = call(AsyncSocialVerificationService.get)
    mark_ready = call(AsyncSocialVerificationService.mark_ready)
    start = call(AsyncSocialVerificationService.start)


class SyncGuardSignerService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncGuardSignerService`."""

    batch_sign_protected_actions = call(AsyncGuardSignerService.batch_sign_protected_actions)
    create_wallet = call(AsyncGuardSignerService.create_wallet)
    export_wallet = call(AsyncGuardSignerService.export_wallet)
    get_status = call(AsyncGuardSignerService.get_status)
    rotate_wallet = call(AsyncGuardSignerService.rotate_wallet)
    sign_protected_action = call(AsyncGuardSignerService.sign_protected_action)


class SyncRateLimitService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncRateLimitService`."""

    get_rate_limit_config = call(AsyncRateLimitService.get_rate_limit_config)
    get_trading_rate_limits = call(AsyncRateLimitService.get_trading_rate_limits)


class SyncVIPService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncVIPService`."""

    get_vip_status = call(AsyncVIPService.get_vip_status)
    list_vip_tiers = call(AsyncVIPService.list_vip_tiers)


class SyncChangelogService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncChangelogService`."""

    action_required_since = call(AsyncChangelogService.action_required_since)
    breaking_changes_since = call(AsyncChangelogService.breaking_changes_since)
    get_post = call(AsyncChangelogService.get_post)
    iter_changes = iterate(AsyncChangelogService.iter_changes)
    iter_posts = iterate(AsyncChangelogService.iter_posts)
    list_changes = call(AsyncChangelogService.list_changes)
    list_posts = call(AsyncChangelogService.list_posts)


class SyncWithdrawService(_SyncService):
    """``Polyester`` view of :class:`~polyester.services.AsyncWithdrawService`."""

    create_api_key_to_external = call(AsyncWithdrawService.create_api_key_to_external)
    create_api_key_to_external_chain = call(AsyncWithdrawService.create_api_key_to_external_chain)
    create_api_key_to_funding = call(AsyncWithdrawService.create_api_key_to_funding)
    create_to_external_chain = call(AsyncWithdrawService.create_to_external_chain)
    create_to_funding = call(AsyncWithdrawService.create_to_funding)
    create_wallet_trading_withdraw = call(AsyncWithdrawService.create_wallet_trading_withdraw)
    prepare_api_key_to_external = plain(AsyncWithdrawService.prepare_api_key_to_external)
    prepare_api_key_to_external_chain = plain(
        AsyncWithdrawService.prepare_api_key_to_external_chain
    )
    prepare_api_key_to_funding = plain(AsyncWithdrawService.prepare_api_key_to_funding)
    submit_prepared = call(AsyncWithdrawService.submit_prepared)
    validate_destination = call(AsyncWithdrawService.validate_destination)


class SyncRealtimeClient(_SyncService):
    """``Polyester`` view of :class:`~polyester.realtime.client.AsyncRealtimeClient`."""

    aclose = call(AsyncRealtimeClient.aclose)
    subscribe_market_trades = call(AsyncRealtimeClient.subscribe_market_trades)
    subscribe_private_orders = call(AsyncRealtimeClient.subscribe_private_orders)
    subscribe_proto = call(AsyncRealtimeClient.subscribe_proto)
    subscribe_proto_batch = call(AsyncRealtimeClient.subscribe_proto_batch)
