from __future__ import annotations

import asyncio
import builtins
import contextlib
from collections.abc import Callable
from typing import Any

import msgspec

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.market_overview import (
    currency_conversion_config_from_proto,
    currency_conversion_rates_from_proto,
    market_overview_list_from_proto,
    spot_volume_history_from_proto,
)
from polyester.codecs.realtime_decode import decode_market_overview_batch_bytes
from polyester.codecs.scalars import market_ids
from polyester.errors import PolyesterValidationError
from polyester.gen.marketoverview.v1.marketoverview_connect import MarketOverviewServiceClient
from polyester.gen.marketoverview.v1.marketoverview_pb2 import (
    ORDER_BY_CHANGE_24H_BPS,
    ORDER_BY_DATE_ADDED,
    ORDER_BY_LAST_PRICE,
    ORDER_BY_VOLUME_24H_USD,
    SORT_ASC,
    SORT_DESC,
    SPARKLINE_1H,
    SPARKLINE_1M,
    SPARKLINE_1W,
    SPARKLINE_24H,
    GetCurrencyConversionConfigRequest,
    GetCurrencyConversionRatesRequest,
    GetSpotVolumeHistoryRequest,
    ListMarketOverviewRequest,
)
from polyester.market_overview.subscription import MarketOverviewSubscription
from polyester.models.market import (
    CurrencyConversionConfig,
    CurrencyConversionRates,
    MarketOverviewEntry,
    MarketOverviewList,
    SpotVolumeHistory,
)
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription
from polyester.services._base import BaseService, CatalogWait
from polyester.services._generated import unary_public_decoded
from polyester.services._realtime_subscribe import require_realtime, subscribe_public_proto
from polyester.services._symbols import resolve_symbol_ids
from polyester.services._validation import validate_limit

# The contract's MarketOrderBy and SortDirection, by the label list() takes.
MARKET_OVERVIEW_ORDER_BY: dict[str, Any] = {
    "change_24h_bps": ORDER_BY_CHANGE_24H_BPS,
    "volume_24h_usd": ORDER_BY_VOLUME_24H_USD,
    "last_price": ORDER_BY_LAST_PRICE,
    "date_added": ORDER_BY_DATE_ADDED,
}
MARKET_OVERVIEW_SORT: dict[str, Any] = {"asc": SORT_ASC, "desc": SORT_DESC}
# The contract's SparklineInterval, by the name MarketOverviewSparkline.interval reads.
MARKET_OVERVIEW_SPARKLINE_INTERVALS: dict[str, Any] = {
    "SPARKLINE_1H": SPARKLINE_1H,
    "SPARKLINE_24H": SPARKLINE_24H,
    "SPARKLINE_1W": SPARKLINE_1W,
    "SPARKLINE_1M": SPARKLINE_1M,
}


def _label(value: object, labels: dict[str, Any], field: str) -> Any:
    """The enum value a label names; anything else is refused before sending."""
    if not isinstance(value, str) or value not in labels:
        raise PolyesterValidationError(
            f"market_overview.list {field} must be one of {', '.join(sorted(labels))}, "
            f"got {value!r}"
        )
    return labels[value]


def _trade_ts_ns(row: MarketOverviewEntry) -> int:
    """A row's last-trade time in nanoseconds; 0 when the market has no trade."""
    return int(row.last_trade_ts_ns or 0)


class AsyncMarketOverviewService(BaseService):
    def __init__(
        self,
        transport,
        *,
        catalogs: CatalogManager | None = None,
        realtime: AsyncRealtimeClient | None = None,
        wait_for_catalogs: CatalogWait | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs or CatalogManager()
        self._realtime = realtime
        self._wait_for_catalogs = wait_for_catalogs

    async def list(
        self,
        *,
        symbols: builtins.list[str] | None = None,
        limit: int = 50,
        page_token: str = "",
        include_sparklines: bool = False,
        order_by: str | None = None,
        sort: str | None = None,
        sparkline_intervals: builtins.list[str] | tuple[str, ...] | None = None,
    ) -> MarketOverviewList:
        """One page of market overview rows.

        ``order_by`` is the sort key: ``"change_24h_bps"`` (absolute 24h
        change), ``"volume_24h_usd"`` (24h USD volume; markets without a USD
        volume sort last either way), ``"last_price"`` or ``"date_added"``
        (listing time). ``sort`` is ``"asc"`` or ``"desc"``. Left ``None``,
        each is not sent and the server applies its default: descending 24h
        USD volume. ``sparkline_intervals`` picks the sparklines that
        ``include_sparklines`` returns: ``"SPARKLINE_1H"``, ``"SPARKLINE_24H"``,
        ``"SPARKLINE_1W"`` or ``"SPARKLINE_1M"``, as
        ``MarketOverviewSparkline.interval`` reads them, in a list or tuple;
        left ``None`` or empty, the server returns the 24h one. Any other
        value or container raises :class:`PolyesterValidationError` before
        anything is sent.

        ``next_page_token`` is bound to ``symbols``, ``order_by`` and ``sort``:
        pass it back with the same ones, or the server refuses it; request the
        first page again to change them. Each page is cut from current values,
        so a market whose sort value changes between pages can appear twice or
        not at all; for a consistent list, read one page with the largest
        ``limit``.
        """
        validated_limit = validate_limit(limit, ListMarketOverviewRequest)
        order_by_value = (
            None if order_by is None else _label(order_by, MARKET_OVERVIEW_ORDER_BY, "order_by")
        )
        sort_value = None if sort is None else _label(sort, MARKET_OVERVIEW_SORT, "sort")
        if sparkline_intervals is not None and not isinstance(sparkline_intervals, (list, tuple)):
            raise PolyesterValidationError(
                "market_overview.list sparkline_intervals must be None or a list or tuple "
                f"of intervals, got {sparkline_intervals!r}"
            )
        interval_values = [
            _label(interval, MARKET_OVERVIEW_SPARKLINE_INTERVALS, "sparkline_intervals")
            for interval in sparkline_intervals or ()
        ]
        # Rows are labelled and scaled from the catalogs; only a symbol filter needs them.
        await self._ensure_catalogs(required=bool(symbols))
        request = ListMarketOverviewRequest(
            limit=validated_limit,
            page_token=page_token,
            include_sparklines=include_sparklines,
        )
        if order_by_value is not None:
            request.order_by = order_by_value
        if sort_value is not None:
            request.sort = sort_value
        request.sparkline_intervals.extend(interval_values)
        resolved_ids = resolve_symbol_ids(
            self._catalogs, symbols, label="market_overview.list symbols"
        )
        if resolved_ids:
            request.symbol_id.extend(resolved_ids)
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.list_market_overview(req),
            request,
            lambda msg: market_overview_list_from_proto(msg, self._catalogs),
        )

    async def get_spot_volume_history(
        self,
        *,
        symbols: builtins.list[str] | None = None,
        symbol_ids: builtins.list[int] | None = None,
    ) -> SpotVolumeHistory:
        """Trailing 24-hour USD volume samples for configured spot pairs.

        Omit both filters to select every configured pair. Send at most 2,000
        distinct positive pair IDs. Do not sum the overlapping samples.
        """
        ids = (
            market_ids(symbol_ids, "market_overview.get_spot_volume_history symbol_ids")
            if symbol_ids is not None
            else []
        )
        if symbols and ids:
            raise PolyesterValidationError(
                "market_overview.get_spot_volume_history accepts only one of symbols or symbol_ids"
            )
        request = GetSpotVolumeHistoryRequest()
        selected: list[int] = []
        if ids:
            for sid in ids:
                if sid <= 0:
                    raise PolyesterValidationError(
                        "market_overview.get_spot_volume_history symbol_ids must be positive"
                    )
            selected = ids
        elif symbols:
            await self._ensure_catalogs()
            selected = resolve_symbol_ids(
                self._catalogs, symbols, label="market_overview.get_spot_volume_history symbols"
            )
        # Each pair is sent once, however it was named: the server refuses repeated IDs and
        # the 2,000 limit counts distinct pairs.
        resolved = list(dict.fromkeys(selected))
        if len(resolved) > 2_000:
            raise PolyesterValidationError(
                "market_overview.get_spot_volume_history accepts at most 2000 symbol_ids"
            )
        if resolved:
            request.symbol_id.extend(resolved)
        # Pairs are labelled from the catalogs.
        await self._ensure_catalogs(required=False)
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.get_spot_volume_history(req),
            request,
            lambda msg: spot_volume_history_from_proto(msg, self._catalogs),
        )

    async def get_currency_conversion_config(self) -> CurrencyConversionConfig:
        """Supported fiat and stablecoin display metadata.

        Entries are ordered by code. Names, symbols, and fraction digits are
        presentation defaults; fraction digits do not specify rate precision.
        Configuration remains available before rates are observed.
        """
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.get_currency_conversion_config(req),
            GetCurrencyConversionConfigRequest(),
            currency_conversion_config_from_proto,
        )

    async def get_currency_conversion_rates(self) -> CurrencyConversionRates:
        """Fiat units per USD and USD per stablecoin unit.

        Fiat ``units_per_usd_e8`` is currency units per 1 USD, scaled by 1e8
        (USD identity is 100_000_000). Stablecoin ``usd_per_unit_e8`` is
        observed USD per unit at the same scale. A missing fiat snapshot or
        omitted stablecoin is unobserved, not zero. The request fails with
        unavailable (HTTP 503) before any observation exists.
        """
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.get_currency_conversion_rates(req),
            GetCurrencyConversionRatesRequest(),
            currency_conversion_rates_from_proto,
        )

    async def subscribe(self) -> AsyncSubscription[MarketOverviewList]:
        """Raw Centrifugo batches (no snapshot merge). Prefer ``create_subscription``."""
        # Rows are labelled and scaled from the catalogs.
        await self._ensure_catalogs(required=False)
        return await subscribe_public_proto(
            self._realtime,
            channel="public:spot:market_overview:updates:proto",
            decode=lambda payload: decode_market_overview_batch_bytes(payload, self._catalogs),
        )

    async def create_subscription(
        self,
        *,
        symbols: builtins.list[str] | None = None,
        limit: int = 50,
        include_sparklines: bool = False,
        on_event: Callable[[builtins.list[MarketOverviewEntry]], None] | None = None,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> MarketOverviewSubscription:
        """Snapshot-then-stream merged overview rows (TS parity).

        ``limit`` applies only to the snapshot request, as for :meth:`list`:
        a positive ``limit`` asks for at most that many markets, and
        ``limit=0`` is sent as no limit, which the server reads as its
        default, 50. It does not cap what the subscription holds or emits:
        updates buffered while the snapshot loads are merged into it, so even
        the first emitted view can hold more than ``limit`` markets, and every
        later live update is merged in too. It is not a cap on the live market
        count and not a dynamic top-N. A snapshot refresh, manual
        (``refresh_snapshot()``) or after a reconnect, sends the same request
        again and starts from its result.

        ``symbols`` filters both the snapshot and the live updates: with it,
        the snapshot and every live or buffered update keep only those
        markets (the channel itself publishes all markets). Without it, every
        market is included as its updates arrive. To follow a fixed set of
        markets, pass ``symbols``.
        """
        realtime = require_realtime(self._realtime)
        channel = "public:spot:market_overview:updates:proto"
        await self._ensure_catalogs(required=bool(symbols))
        wanted_ids = set(
            resolve_symbol_ids(self._catalogs, symbols, label="market_overview.subscribe symbols")
        )
        by_symbol_id: dict[int, MarketOverviewEntry] = {}
        queue: asyncio.Queue[list[MarketOverviewEntry] | None] = asyncio.Queue(maxsize=50)
        close = asyncio.Event()
        stream_holder: dict[str, AsyncSnapshotThenStreamSubscription | None] = {"stream": None}

        def emit() -> None:
            if close.is_set():
                return
            snapshot = list(by_symbol_id.values())
            if on_event is not None:
                on_event(snapshot)
            if close.is_set():
                return
            try:
                from polyester.realtime.client import enqueue_or_overflow

                enqueue_or_overflow(
                    queue,
                    snapshot,
                    close=close,
                    message="market overview subscription queue full; consumer too slow",
                )
            except Exception as exc:
                stream = stream_holder["stream"]
                if stream is not None:
                    stream._fail_closed(exc)

        def matches_symbol(row: MarketOverviewEntry) -> bool:
            return not wanted_ids or row.symbol_id in wanted_ids

        def apply_rows(rows: list[MarketOverviewEntry], *, buffered: bool = False) -> None:
            for row in rows:
                if matches_symbol(row):
                    previous = by_symbol_id.get(row.symbol_id)
                    # A row buffered while the snapshot loaded may predate it: one
                    # whose last trade is older than the row it would replace was
                    # published before that row and does not replace it. An equal
                    # last-trade time still does, with the index, volume and book
                    # changes made since.
                    if (
                        buffered
                        and previous is not None
                        and _trade_ts_ns(row) < _trade_ts_ns(previous)
                    ):
                        continue
                    # Live publications carry no sparklines: keep the snapshot's.
                    if not row.sparklines and previous is not None and previous.sparklines:
                        row = msgspec.structs.replace(row, sparklines=previous.sparklines)
                    by_symbol_id[row.symbol_id] = row

        async def fetch_snapshot() -> MarketOverviewList:
            return await self.list(
                symbols=symbols,
                limit=limit,
                include_sparklines=include_sparklines,
            )

        def apply_snapshot(
            snapshot: MarketOverviewList,
            buffered: list[MarketOverviewEntry],
        ) -> None:
            by_symbol_id.clear()
            apply_rows(snapshot.markets)
            apply_rows(buffered, buffered=True)
            emit()

        def apply_drained(rows: list[MarketOverviewEntry]) -> None:
            # Publications that arrived while the snapshot was being applied,
            # drained before the stream is ready: they may predate it too.
            apply_rows(rows, buffered=True)
            emit()

        def apply_live(rows: list[MarketOverviewEntry]) -> None:
            apply_rows(rows)
            emit()

        def terminal_close() -> None:
            close.set()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(None)

        stream = AsyncSnapshotThenStreamSubscription(
            realtime=realtime,
            channel=channel,
            decode=lambda payload: decode_market_overview_batch_bytes(payload, self._catalogs),
            fetch_snapshot=fetch_snapshot,
            read_publication=lambda batch: [row for row in batch.markets if matches_symbol(row)],
            apply_snapshot=apply_snapshot,
            apply_live_publications=apply_live,
            apply_drained_publications=apply_drained,
            max_buffered_publications=2000,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error,
            on_terminal=terminal_close,
        )
        stream_holder["stream"] = stream

        subscription = MarketOverviewSubscription(
            queue=queue,
            close=close,
            stream=stream,
        )
        try:
            await stream.start()
        except BaseException:
            await subscription.aclose()
            raise
        return subscription
