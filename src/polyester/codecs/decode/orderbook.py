from __future__ import annotations

from polyester.codecs.orderbook import require_served_tier
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models import OrderbookData, OrderbookLevel
from polyester.orderbook.local_book import format_orderbook_level


def orderbook_level_from_proto(
    msg: orderbook_pb2.PriceLevel,
    *,
    quantity_scale: int,
    symbol: str | None = None,
) -> OrderbookLevel:
    return format_orderbook_level(
        price_ticks=int(msg.price_ticks),
        qty_scaled=int(msg.qty_scaled),
        quantity_scale=quantity_scale,
        symbol=symbol,
    )


def orderbook_from_proto(
    msg: orderbook_pb2.GetOrderBookResponse,
    *,
    symbol: str,
    depth: int,
    quantity_scale: int,
) -> OrderbookData:
    """Decode a snapshot requested at ``depth`` levels per side. The response
    names the tier it served in every answer: one without it, or with another
    tier than the one requested, breaks the contract."""
    served = require_served_tier("GetOrderBook", int(msg.depth), depth)
    return OrderbookData(
        symbol=symbol,
        depth=served,
        book_seq=str(msg.book_seq),
        bids=[
            orderbook_level_from_proto(item, quantity_scale=quantity_scale, symbol=symbol)
            for item in msg.bids
        ],
        asks=[
            orderbook_level_from_proto(item, quantity_scale=quantity_scale, symbol=symbol)
            for item in msg.asks
        ],
        available=bool(msg.available),
        book_epoch=str(msg.book_epoch),
    )
