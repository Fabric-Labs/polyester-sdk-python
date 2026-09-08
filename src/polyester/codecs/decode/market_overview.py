from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.proto_helpers import has_field
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.models.market import (
    MarketOverviewEntry,
    MarketOverviewList,
    SpotPairVolumeSeries,
    SpotVolumeHistory,
)
from polyester.types.money import Price


def _optional_scaled(msg: marketoverview_pb2.MarketOverview, field_name: str) -> str | None:
    if not has_field(msg, field_name):
        return None
    return str(getattr(msg, field_name))


def market_overview_entry_from_proto(
    msg: marketoverview_pb2.MarketOverview,
    catalogs: CatalogManager | None = None,
) -> MarketOverviewEntry:
    symbol_id = int(msg.symbol_id)
    symbol = catalogs.symbol_for_symbol_id(symbol_id) if catalogs is not None else None
    symbol = symbol or ""
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
        volume_24h_quote_scaled=_optional_scaled(msg, "volume_24h_quote_scaled"),
        volume_24h_usd_scaled=_optional_scaled(msg, "volume_24h_usd_scaled"),
    )


def market_overview_list_from_proto(
    msg: marketoverview_pb2.ListMarketOverviewResponse,
    catalogs: CatalogManager | None = None,
) -> MarketOverviewList:
    markets = [market_overview_entry_from_proto(item, catalogs) for item in msg.markets]
    return MarketOverviewList(markets=markets, total=len(markets))


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
