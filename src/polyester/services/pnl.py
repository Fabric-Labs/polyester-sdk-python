from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, time, timedelta

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.pnl import (
    daily_profit_and_loss_page_from_proto,
    profit_and_loss_from_proto,
    trading_statistics_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.scalars import datetime_to_timestamp_dict, exact_integer
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.pnl.v1 import pnl_pb2
from polyester.gen.pnl.v1.pnl_connect import ProfitAndLossServiceClient
from polyester.models.pnl import (
    DailyProfitAndLoss,
    DailyProfitAndLossPage,
    ProfitAndLoss,
    TradingStatistics,
)
from polyester.services._base import BaseService, CatalogWait
from polyester.services._retry import UnavailableRetry, unary_auth_decoded_retry_unavailable
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._symbols import (
    check_optional_symbol,
    display_symbol_for_id,
    resolve_optional_symbol_id,
)

# Profit and loss reads answer UNAVAILABLE while their figures cannot be read;
# the contract says to retry the same request.
PNL_READ_RETRY = UnavailableRetry()

# The contract's bounds on ListDailyProfitAndLoss.
DAILY_MAX_DAYS = 366
DAILY_MAX_LIMIT = 366
_PAGE_TOKEN_MAX_LEN = 512

_WINDOWS = {
    "today": pnl_pb2.PROFIT_AND_LOSS_WINDOW_TODAY,
    "7d": pnl_pb2.PROFIT_AND_LOSS_WINDOW_DAYS_7,
    "days_7": pnl_pb2.PROFIT_AND_LOSS_WINDOW_DAYS_7,
    "30d": pnl_pb2.PROFIT_AND_LOSS_WINDOW_DAYS_30,
    "days_30": pnl_pb2.PROFIT_AND_LOSS_WINDOW_DAYS_30,
    "lifetime": pnl_pb2.PROFIT_AND_LOSS_WINDOW_LIFETIME,
}
_PRODUCTS = {"spot": pnl_pb2.PROFIT_AND_LOSS_PRODUCT_SPOT}


def _window(value: object) -> pnl_pb2.ProfitAndLossWindow:
    key = value.strip().lower() if isinstance(value, str) else ""
    if key not in _WINDOWS:
        raise PolyesterValidationError('window must be "today", "7d", "30d" or "lifetime"')
    return _WINDOWS[key]


def _product(value: object) -> pnl_pb2.ProfitAndLossProduct:
    if value is None:
        return pnl_pb2.PROFIT_AND_LOSS_PRODUCT_UNSPECIFIED
    key = value.strip().lower() if isinstance(value, str) else ""
    if key not in _PRODUCTS:
        raise PolyesterValidationError('product must be "spot", or None for every product')
    return _PRODUCTS[key]


def _utc_day(value: object, name: str) -> datetime:
    """``value`` as 00:00 UTC of a day: a ``date``, or an aware ``datetime``
    at 00:00 UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise PolyesterValidationError(f"{name} must be a timezone-aware datetime or a date")
        try:
            moment = value.astimezone(UTC)
        except OverflowError:
            # An offset that moves the time past year 1 or 9999 names no UTC day.
            raise PolyesterValidationError(f"{name} is outside the supported date range") from None
        if moment.time() != time(0):
            raise PolyesterValidationError(f"{name} must be 00:00 UTC of a day")
        return moment
    if isinstance(value, date):
        return datetime.combine(value, time(0), tzinfo=UTC)
    raise PolyesterValidationError(f"{name} must be a date or a timezone-aware datetime")


def _timestamp(value: datetime) -> Timestamp:
    parts = datetime_to_timestamp_dict(value)
    return Timestamp(seconds=parts["seconds"], nanos=parts["nanos"])


class AsyncProfitAndLossService(ScopedSubAccountMixin, BaseService):
    """Profit and loss in USD (``pnl.v1.ProfitAndLossService``).

    Spot profit and loss uses each asset's weighted average cost: every trade
    is valued at its execution time, every fee is a realized expense, and
    deposits, withdrawals and transfers are never profit or loss. The figures
    follow settled trades within seconds; ``as_of`` says when they were last
    published.

    Without ``account`` or ``sub_account_id`` (and no client default), a
    main-account key reads the main account together with every sub-account
    it owns, and a sub-account key its own sub-account. ``account="main"``
    reads the same as no selection; a sub-account ID reads that sub-account.
    An API key needs ``READ_PNL`` on its policy. Reads that answer
    ``unavailable`` are retried for about 2 seconds, then raise.
    """

    def __init__(
        self,
        transport,
        default_sub_account_id: str | None,
        catalogs: CatalogManager | None = None,
        *,
        wait_for_catalogs: CatalogWait | None = None,
    ) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id
        self._catalogs = catalogs or CatalogManager()
        self._wait_for_catalogs = wait_for_catalogs

    def _subaccount(self, account: AccountScope | None, sub_account_id: str | int | None):
        return parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )

    async def _symbol_id(self, symbol: str | None, symbol_id: int | None, label: str) -> int:
        # A blank symbol would read every market: refused before any wait.
        if check_optional_symbol(symbol, label=f"{label} symbol") is not None:
            await self._ensure_catalogs()
        return (
            resolve_optional_symbol_id(
                self._catalogs, symbol=symbol, symbol_id=symbol_id, label=label
            )
            or 0
        )

    async def get(
        self,
        *,
        window: str,
        product: str | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> ProfitAndLoss:
        """The account's profit and loss over ``window``: ``"today"``,
        ``"7d"`` (today and the 6 days before), ``"30d"`` or ``"lifetime"``
        (since the day of the account's first trade or transfer), each from
        00:00 UTC. ``product`` (``"spot"``) filters every figure; ``symbol``
        or ``symbol_id`` filters ``markets`` only, never the totals or
        holdings."""
        request = pnl_pb2.GetProfitAndLossRequest(
            window=_window(window),
            product=_product(product),
            symbol_id=await self._symbol_id(symbol, symbol_id, "pnl.get symbol"),
        )
        parsed_sub = self._subaccount(account, sub_account_id)
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        # Markets are labelled with their symbol from the catalogs.
        await self._ensure_catalogs(required=False)
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            ProfitAndLossServiceClient,
            lambda client, req: client.get_profit_and_loss(req),
            request,
            lambda msg: profit_and_loss_from_proto(
                msg, symbols=lambda value: display_symbol_for_id(self._catalogs, value)
            ),
            policy=PNL_READ_RETRY,
        )

    async def get_trading_statistics(
        self,
        *,
        window: str,
        product: str | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> TradingStatistics:
        """The account's trade count, volume, fees and realized profit and
        loss over ``window`` (as in :meth:`get`), filtered by ``product`` and
        market, with the return, maximum drawdown and Sharpe ratio of the
        whole account's closed days in that window."""
        request = pnl_pb2.GetTradingStatisticsRequest(
            window=_window(window),
            product=_product(product),
            symbol_id=await self._symbol_id(symbol, symbol_id, "pnl.get_trading_statistics symbol"),
        )
        parsed_sub = self._subaccount(account, sub_account_id)
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            ProfitAndLossServiceClient,
            lambda client, req: client.get_trading_statistics(req),
            request,
            trading_statistics_from_proto,
            policy=PNL_READ_RETRY,
        )

    async def list_daily(
        self,
        *,
        start: date | datetime,
        end: date | datetime,
        limit: int = 0,
        page_token: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> DailyProfitAndLossPage:
        """One page of the account's profit and loss per UTC day, oldest
        first, from ``start`` (inclusive) to ``end`` (exclusive).

        ``start`` and ``end`` are UTC days: a ``date``, or an aware
        ``datetime`` at 00:00 UTC; ``end`` is after ``start`` and at most 366
        days after it. ``limit`` is 0 (the server's 31) to 366 days. Pass
        ``next_page_token`` back as ``page_token`` with the same days and
        account.
        """
        start_day = _utc_day(start, "start")
        end_day = _utc_day(end, "end")
        # Compared as a difference: start + 366 days overflows near year 9999.
        if not start_day < end_day or end_day - start_day > timedelta(days=DAILY_MAX_DAYS):
            raise PolyesterValidationError(
                f"end must be after start and at most {DAILY_MAX_DAYS} days after it"
            )
        token = page_token or ""
        if not isinstance(token, str) or len(token) > _PAGE_TOKEN_MAX_LEN:
            raise PolyesterValidationError(
                f"page_token must be a string of at most {_PAGE_TOKEN_MAX_LEN} characters"
            )
        request = pnl_pb2.ListDailyProfitAndLossRequest(
            start_time=_timestamp(start_day),
            end_time=_timestamp(end_day),
            limit=exact_integer(limit, "limit", min_value=0, max_value=DAILY_MAX_LIMIT),
            page_token=token,
        )
        parsed_sub = self._subaccount(account, sub_account_id)
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded_retry_unavailable(
            self._transport,
            ProfitAndLossServiceClient,
            lambda client, req: client.list_daily_profit_and_loss(req),
            request,
            daily_profit_and_loss_page_from_proto,
            policy=PNL_READ_RETRY,
        )

    async def iter_daily(
        self,
        *,
        start: date | datetime,
        end: date | datetime,
        limit: int = 0,
        page_token: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> AsyncIterator[DailyProfitAndLoss]:
        """Every day from ``start`` to ``end``, oldest first, fetching pages as
        needed with the same arguments. Days without activity are included."""
        requested: set[str] = set()
        token = page_token
        while True:
            if token:
                requested.add(token)
            page = await self.list_daily(
                start=start,
                end=end,
                limit=limit,
                page_token=token,
                account=account,
                sub_account_id=sub_account_id,
            )
            for day in page.days:
                yield day
            if not page.next_page_token:
                return
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ListDailyProfitAndLoss", "next_page_token repeats an earlier page token"
                )
            token = page.next_page_token
