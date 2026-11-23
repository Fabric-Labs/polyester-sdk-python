from __future__ import annotations

import time

import msgspec

from polyester.models.common import PriceBand
from polyester.types.money import Price, Quantity


class MarketTrade(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    match_id: str = ""
    is_buy: bool = False
    price: Price | None = None
    qty: Quantity | None = None
    ts_ns: str = ""


class TradeEpochEnd(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Where one epoch of a market's trade IDs ended.

    Trade IDs of epoch ``e`` lie between ``(e-1) * 2**40`` and ``e * 2**40``;
    ``last_trade_id`` is ``(epoch-1) * 2**40`` for an epoch without trades.
    """

    epoch: int
    last_trade_id: int


class MarketTradesResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Public trades. ``next_page_token`` pages a newest-first listing.

    The backfill fields are set only for a call with ``after_trade_id``:
    every trade up to ``complete_through_trade_id`` exists and is returned;
    ``next_after_trade_id`` is the next call's ``after_trade_id`` (equal to the
    one sent when nothing newer is available yet); ``epoch_ends`` lists the
    epochs that ended in the walked range.
    """

    trades: list[MarketTrade]
    next_page_token: str = ""
    complete_through_trade_id: int = 0
    next_after_trade_id: int = 0
    epoch_ends: list[TradeEpochEnd] = []


class Candle(msgspec.Struct, kw_only=True, omit_defaults=True):
    ts_sec: int
    open: str = ""
    high: str = ""
    low: str = ""
    close: str = ""
    volume: str = ""
    quote_volume: str = ""
    is_closed: bool = False


class CandlesResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int = 0
    timeframe: str = ""
    candles: list[Candle]
    reference_candles: list[Candle] = msgspec.field(default_factory=list)
    next_page_token: str = ""


class IndexPriceCandle(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One closed candle of a spot market's index price series.

    ``source`` is ``"reference"`` for the market's composite reference candle
    (buckets before the one containing its listing time) or ``"index"`` for
    its index price candle (from that bucket on); a value this SDK does not
    know reads as its number. Prices are decimal strings decoded with the
    pair's ``reference_price_scale``. There is no volume.
    """

    ts_sec: int
    open: str = ""
    high: str = ""
    low: str = ""
    close: str = ""
    source: str = ""


class IndexPriceCandlesResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of index price candles, newest first. A missing ``ts_sec``
    is a gap. ``next_page_token`` continues toward older candles with the
    same ``symbol_id``, ``timeframe``, ``start_time`` and ``end_time``; it is
    empty when no older candle exists in the range."""

    symbol_id: int = 0
    timeframe: str = ""
    candles: list[IndexPriceCandle]
    next_page_token: str = ""


class MarketOverviewSparkline(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A market's recent closing prices over ``interval``, newest first."""

    interval: str = ""
    """``SPARKLINE_1H``, ``SPARKLINE_24H``, ``SPARKLINE_1W`` or ``SPARKLINE_1M``."""
    close_prices: list[Price] = []


class LivePriceBand(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A pair's live price band as of ``as_of_ts_ns``: its reference price and
    the limit prices the pair admits, inclusive and side-specific.

    It is advisory: the pair checks every order against its own band when the
    order arrives. ``state`` is ``"active"``, ``"off"`` (no band), ``"empty"``
    (no price lies inside it: every order that adds exposure is refused
    ``PRICE_BAND_VIOLATION``) or ``"unknown"``; a value this SDK does not know
    reads as its number. A buy limit is checked against ``max_buy_price`` and
    a sell limit against ``min_sell_price`` (both only while ``active``);
    ``min_buy_price`` and ``max_sell_price`` apply only when present.
    ``reference_source`` is ``"last_trade"``, ``"listing_reference"`` or
    ``"index_price"``, ``""`` when the band is off. ``parameters`` are the
    band's settings, ``None`` when it is off or they cannot be expressed in
    basis points and milliseconds. Of two bands of the pair, the one with the
    greater ``epoch``, then ``update_id``, is newer. Times are nanoseconds
    since the Unix epoch. After ``valid_until_ts_ns`` the band is unknown: see
    :meth:`is_fresh`.
    """

    symbol_id: int
    state: str = ""
    reference_price: Price | None = None
    reference_source: str = ""
    max_buy_price: Price | None = None
    min_sell_price: Price | None = None
    min_buy_price: Price | None = None
    max_sell_price: Price | None = None
    updated_ts_ns: int = 0
    reanchor_eligible_ts_ns: int | None = None
    reanchor_pending: bool = False
    parameters: PriceBand | None = None
    epoch: int = 0
    update_id: int = 0
    as_of_ts_ns: int = 0
    valid_until_ts_ns: int = 0

    def is_fresh(self, now_ns: int | None = None) -> bool:
        """Whether the band is still known at ``now_ns`` (default: now): it was
        confirmed and ``valid_until_ts_ns`` has not passed. A band that is not
        fresh is unknown, not absent; read it again."""
        now = time.time_ns() if now_ns is None else now_ns
        return self.state not in ("", "unknown") and now <= self.valid_until_ts_ns


class MarketOverviewEntry(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    symbol: str = ""
    last_price: Price | None = None
    index_price: Price | None = None
    change_24h_bp: str = ""
    volume_24h_base_scaled: str | None = None
    volume_24h_base: str | None = None
    volume_24h_quote_scaled: str | None = None
    volume_24h_usd_scaled: str | None = None
    sparklines: list[MarketOverviewSparkline] = []
    """Sparklines the server sent, only when ``include_sparklines`` was requested."""
    high_24h: Price | None = None
    """Highest trade price over the last 24 hours; ``None`` when the server sent none."""
    low_24h: Price | None = None
    """Lowest trade price over the last 24 hours; ``None`` when the server sent none."""
    best_bid: Price | None = None
    """Best bid price; ``None`` when the bid side of the book is empty."""
    best_bid_qty: Quantity | None = None
    """Base quantity at the best bid, at the pair's base quantity scale when the
    catalogs know it; ``None`` when the bid side is empty."""
    best_ask: Price | None = None
    """Best ask price; ``None`` when the ask side of the book is empty."""
    best_ask_qty: Quantity | None = None
    """Base quantity at the best ask, at the pair's base quantity scale when the
    catalogs know it; ``None`` when the ask side is empty."""
    last_trade_ts_ns: str = ""
    """Time of the last trade, in epoch nanoseconds; empty when there was none."""
    listed_ts_ns: str = ""
    """Time the market was listed, in epoch nanoseconds; empty when unknown."""
    price_band: LivePriceBand | None = None
    """The pair's live price band, present only while one was confirmed current
    within the last 5 seconds. ``None``, or a band that is no longer
    :meth:`~LivePriceBand.is_fresh`, means no fresh band is known, not that the
    pair has no band. The overview stream sends a row again when its band
    changes, appears or lapses, not on each confirmation. To check an order
    price, read the price band itself."""


class MarketOverviewList(msgspec.Struct, kw_only=True, omit_defaults=True):
    markets: list[MarketOverviewEntry]
    total: int = 0
    next_page_token: str = ""


class SpotPairVolumeSeries(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    symbol: str = ""
    volume_usd_scaled: list[int] = []


class SpotVolumeHistory(msgspec.Struct, kw_only=True, omit_defaults=True):
    bucket: str = ""
    start_ts_sec: int = 0
    end_ts_sec: int = 0
    points: int = 0
    pairs: list[SpotPairVolumeSeries] = []
    total_volume_usd_scaled: list[int] = []


class CurrencyMetadata(msgspec.Struct, kw_only=True, omit_defaults=True):
    code: str = ""
    default_english_name: str = ""
    symbol: str = ""
    fraction_digits: int = 0


class CurrencyConversionConfig(msgspec.Struct, kw_only=True, omit_defaults=True):
    fiat: list[CurrencyMetadata] = msgspec.field(default_factory=list)
    stablecoins: list[CurrencyMetadata] = msgspec.field(default_factory=list)


class FiatConversionRate(msgspec.Struct, kw_only=True, omit_defaults=True):
    code: str = ""
    units_per_usd_e8: int = 0


class FiatConversionSnapshot(msgspec.Struct, kw_only=True, omit_defaults=True):
    rates: list[FiatConversionRate] = msgspec.field(default_factory=list)
    source_ts_sec: int = 0
    stale: bool = False


class StablecoinConversionRate(msgspec.Struct, kw_only=True, omit_defaults=True):
    code: str = ""
    usd_per_unit_e8: int = 0
    source_ts_sec: int = 0
    stale: bool = False


class CurrencyConversionRates(msgspec.Struct, kw_only=True, omit_defaults=True):
    fiat: FiatConversionSnapshot | None = None
    stablecoins: list[StablecoinConversionRate] = msgspec.field(default_factory=list)
    snapshot_ts_sec: int = 0
