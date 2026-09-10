from __future__ import annotations

import msgspec

from polyester.types.money import Price, Quantity


class MarketTrade(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    match_id: str = ""
    is_buy: bool = False
    price: Price | None = None
    qty: Quantity | None = None
    ts_ns: str = ""


class MarketTradesResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    trades: list[MarketTrade]
    next_match_id: str = ""


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


class MarketOverviewEntry(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol_id: int
    symbol: str = ""
    last_price: Price | None = None
    index_price: Price | None = None
    change_24h_bp: str = ""
    volume_24h_base_scaled: str | None = None
    volume_24h_quote_scaled: str | None = None
    volume_24h_usd_scaled: str | None = None


class MarketOverviewList(msgspec.Struct, kw_only=True, omit_defaults=True):
    markets: list[MarketOverviewEntry]
    total: int = 0


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
