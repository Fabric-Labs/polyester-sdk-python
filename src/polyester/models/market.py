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
