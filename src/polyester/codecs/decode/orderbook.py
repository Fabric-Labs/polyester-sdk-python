from __future__ import annotations

from polyester.codecs.decode.invariants import qty_scaled_from_response
from polyester.codecs.orderbook import require_served_tier
from polyester.codecs.proto_helpers import optional_timestamp
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.models import OrderbookData, OrderbookLevel
from polyester.orderbook.local_book import format_orderbook_level


def orderbook_level_from_proto(
    msg: orderbook_pb2.PriceLevel,
    *,
    quantity_scale: int,
    symbol: str | None = None,
    symbol_id: int | None = None,
) -> OrderbookLevel:
    return format_orderbook_level(
        price_ticks=int(msg.price_ticks),
        # A negative quantity is corrupt, not a missing one: refuse it before
        # the level's own checks refuse an omitted (0) price or quantity.
        qty_scaled=qty_scaled_from_response(msg.qty_scaled, field="PriceLevel.qty_scaled"),
        quantity_scale=quantity_scale,
        symbol=symbol,
        symbol_id=symbol_id,
    )


def orderbook_from_proto(
    msg: orderbook_pb2.GetOrderBookResponse,
    *,
    symbol: str,
    depth: int,
    quantity_scale: int,
    symbol_id: int | None = None,
) -> OrderbookData:
    """Decode a snapshot requested at ``depth`` levels per side. The response
    names the tier it served in every answer: one without it, or with another
    tier than the one requested, breaks the contract. Its ``ts`` is the
    snapshot's time, ``None`` when the response has none. Level quantities
    carry ``symbol_id``, the requested market's ID, or the response's when
    none is given."""
    served = require_served_tier("GetOrderBook", int(msg.depth), depth)
    market_id = symbol_id or int(msg.symbol_id) or None
    return OrderbookData(
        symbol=symbol,
        depth=served,
        book_seq=str(msg.book_seq),
        bids=[
            orderbook_level_from_proto(
                item, quantity_scale=quantity_scale, symbol=symbol, symbol_id=market_id
            )
            for item in msg.bids
        ],
        asks=[
            orderbook_level_from_proto(
                item, quantity_scale=quantity_scale, symbol=symbol, symbol_id=market_id
            )
            for item in msg.asks
        ],
        available=bool(msg.available),
        book_epoch=str(msg.book_epoch),
        ts=optional_timestamp(msg, "ts"),
    )
