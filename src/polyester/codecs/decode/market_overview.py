from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.invariants import ts_ns_string_from_response
from polyester.codecs.proto_helpers import has_field
from polyester.codecs.scalars import format_qty_scaled
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.models.market import (
    CurrencyConversionConfig,
    CurrencyConversionRates,
    CurrencyMetadata,
    FiatConversionRate,
    FiatConversionSnapshot,
    MarketOverviewEntry,
    MarketOverviewList,
    MarketOverviewSparkline,
    SpotPairVolumeSeries,
    SpotVolumeHistory,
    StablecoinConversionRate,
)
from polyester.types.money import Price, Quantity


def _optional_scaled(msg: marketoverview_pb2.MarketOverview, field_name: str) -> str | None:
    if not has_field(msg, field_name):
        return None
    return str(getattr(msg, field_name))


def _decoded_base_volume(
    msg: marketoverview_pb2.MarketOverview,
    catalogs: CatalogManager | None,
) -> str | None:
    if catalogs is None or not has_field(msg, "volume_24h_base_scaled"):
        return None
    scale = catalogs.market_data_volume_scale_for_symbol_id(int(msg.symbol_id))
    if scale is None:
        return None
    return format_qty_scaled(int(msg.volume_24h_base_scaled), scale)


def _price_or_none(ticks: int, symbol: str | None) -> Price | None:
    """A price the server sent, or ``None`` for 0, which means none."""
    return Price.from_ticks(int(ticks), symbol=symbol) if ticks else None


def _book_side(
    ticks: int,
    qty_scaled: int,
    *,
    scale: int | None,
    symbol: str | None,
    symbol_id: int,
) -> tuple[Price | None, Quantity | None]:
    """The best price of one book side and the base quantity at it; both
    ``None`` when that side is empty."""
    if not ticks:
        return None, None
    return Price.from_ticks(int(ticks), symbol=symbol), Quantity.from_scaled(
        int(qty_scaled), scale=scale, symbol=symbol, symbol_id=symbol_id
    )


def market_overview_sparkline_from_proto(
    msg: marketoverview_pb2.Sparkline, symbol: str | None = None
) -> MarketOverviewSparkline:
    return MarketOverviewSparkline(
        interval=marketoverview_pb2.SparklineInterval.Name(msg.interval)
        if msg.interval in marketoverview_pb2.SparklineInterval.values()
        else str(msg.interval),
        close_prices=[Price.from_ticks(int(ticks), symbol=symbol) for ticks in msg.close_ticks],
    )


def market_overview_entry_from_proto(
    msg: marketoverview_pb2.MarketOverview,
    catalogs: CatalogManager | None = None,
) -> MarketOverviewEntry:
    symbol_id = int(msg.symbol_id)
    symbol = catalogs.symbol_for_symbol_id(symbol_id) if catalogs is not None else None
    symbol = symbol or ""
    base_scale = (
        catalogs.base_quantity_scale_for_symbol_id(symbol_id) if catalogs is not None else None
    )
    best_bid, best_bid_qty = _book_side(
        msg.best_bid_ticks,
        msg.best_bid_qty_scaled,
        scale=base_scale,
        symbol=symbol or None,
        symbol_id=symbol_id,
    )
    best_ask, best_ask_qty = _book_side(
        msg.best_ask_ticks,
        msg.best_ask_qty_scaled,
        scale=base_scale,
        symbol=symbol or None,
        symbol_id=symbol_id,
    )
    return MarketOverviewEntry(
        symbol_id=symbol_id,
        symbol=symbol,
        last_price=Price.from_ticks(int(msg.last_price_ticks), symbol=symbol or None)
        if msg.last_price_ticks
        else None,
        index_price=Price.from_ticks(int(msg.index_price_ticks), symbol=symbol or None)
        if msg.index_price_ticks
        else None,
        change_24h_bp=str(msg.change_24h_bps),
        volume_24h_base_scaled=_optional_scaled(msg, "volume_24h_base_scaled"),
        volume_24h_base=_decoded_base_volume(msg, catalogs),
        volume_24h_quote_scaled=_optional_scaled(msg, "volume_24h_quote_scaled"),
        volume_24h_usd_scaled=_optional_scaled(msg, "volume_24h_usd_scaled"),
        sparklines=[
            market_overview_sparkline_from_proto(item, symbol or None) for item in msg.sparklines
        ],
        high_24h=_price_or_none(msg.high_24h_ticks, symbol or None),
        low_24h=_price_or_none(msg.low_24h_ticks, symbol or None),
        best_bid=best_bid,
        best_bid_qty=best_bid_qty,
        best_ask=best_ask,
        best_ask_qty=best_ask_qty,
        last_trade_ts_ns=ts_ns_string_from_response(
            msg.last_trade_ts_ns,
            context="MarketOverview",
            field_name="last_trade_ts_ns",
            empty_when_zero=True,
        ),
        listed_ts_ns=ts_ns_string_from_response(
            msg.listed_ts_ns,
            context="MarketOverview",
            field_name="listed_ts_ns",
            empty_when_zero=True,
        ),
    )


def market_overview_list_from_proto(
    msg: marketoverview_pb2.ListMarketOverviewResponse,
    catalogs: CatalogManager | None = None,
) -> MarketOverviewList:
    markets = [market_overview_entry_from_proto(item, catalogs) for item in msg.markets]
    return MarketOverviewList(
        markets=markets, total=len(markets), next_page_token=msg.next_page_token
    )


def spot_volume_history_from_proto(
    msg: marketoverview_pb2.GetSpotVolumeHistoryResponse,
    catalogs: CatalogManager | None = None,
) -> SpotVolumeHistory:
    pairs: list[SpotPairVolumeSeries] = []
    for item in msg.pairs:
        symbol_id = int(item.symbol_id)
        symbol = catalogs.symbol_for_symbol_id(symbol_id) if catalogs is not None else None
        pairs.append(
            SpotPairVolumeSeries(
                symbol_id=symbol_id,
                symbol=symbol or "",
                volume_usd_scaled=[int(value) for value in item.volume_usd_scaled],
            )
        )
    return SpotVolumeHistory(
        bucket=str(msg.bucket),
        start_ts_sec=int(msg.start_ts_sec),
        end_ts_sec=int(msg.end_ts_sec),
        points=int(msg.points),
        pairs=pairs,
        total_volume_usd_scaled=[int(value) for value in msg.total_volume_usd_scaled],
    )


def currency_metadata_from_proto(msg: marketoverview_pb2.CurrencyMetadata) -> CurrencyMetadata:
    return CurrencyMetadata(
        code=str(msg.code),
        default_english_name=str(msg.default_english_name),
        symbol=str(msg.symbol),
        fraction_digits=int(msg.fraction_digits),
    )


def currency_conversion_config_from_proto(
    msg: marketoverview_pb2.GetCurrencyConversionConfigResponse,
) -> CurrencyConversionConfig:
    return CurrencyConversionConfig(
        fiat=[currency_metadata_from_proto(item) for item in msg.fiat],
        stablecoins=[currency_metadata_from_proto(item) for item in msg.stablecoins],
    )


def fiat_conversion_snapshot_from_proto(
    msg: marketoverview_pb2.FiatConversionSnapshot,
) -> FiatConversionSnapshot:
    return FiatConversionSnapshot(
        rates=[
            FiatConversionRate(
                code=str(item.code),
                units_per_usd_e8=int(item.units_per_usd_e8),
            )
            for item in msg.rates
        ],
        source_ts_sec=int(msg.source_ts_sec),
        stale=bool(msg.stale),
    )


def currency_conversion_rates_from_proto(
    msg: marketoverview_pb2.GetCurrencyConversionRatesResponse,
) -> CurrencyConversionRates:
    fiat = fiat_conversion_snapshot_from_proto(msg.fiat) if has_field(msg, "fiat") else None
    return CurrencyConversionRates(
        fiat=fiat,
        stablecoins=[
            StablecoinConversionRate(
                code=str(item.code),
                usd_per_unit_e8=int(item.usd_per_unit_e8),
                source_ts_sec=int(item.source_ts_sec),
                stale=bool(item.stale),
            )
            for item in msg.stablecoins
        ],
        snapshot_ts_sec=int(msg.snapshot_ts_sec),
    )
