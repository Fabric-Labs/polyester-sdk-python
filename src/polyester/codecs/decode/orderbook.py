from __future__ import annotations

from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models import OrderbookData, OrderbookLevel


def orderbook_level_from_proto(msg: orderbook_pb2.PriceLevel) -> OrderbookLevel:
    return OrderbookLevel(
        price_ticks=str(msg.price_ticks),
        qty_scaled=str(msg.qty_scaled),
    )


def orderbook_from_proto(
    msg: orderbook_pb2.GetOrderBookResponse,
    *,
    symbol: str,
    depth: int,
) -> OrderbookData:
    return OrderbookData(
        symbol=symbol,
        depth=depth,
        book_seq=str(msg.book_seq),
        bids=[orderbook_level_from_proto(item) for item in msg.bids],
        asks=[orderbook_level_from_proto(item) for item in msg.asks],
    )
