from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.models.market import MarketOverviewEntry, MarketOverviewList
from polyester.types.money import Price


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
        volume_24h_quote_scaled=str(msg.volume_24h_quote_scaled),
    )


def market_overview_list_from_proto(
    msg: marketoverview_pb2.ListMarketOverviewResponse,
    catalogs: CatalogManager | None = None,
) -> MarketOverviewList:
    markets = [market_overview_entry_from_proto(item, catalogs) for item in msg.markets]
    return MarketOverviewList(markets=markets, total=len(markets))
