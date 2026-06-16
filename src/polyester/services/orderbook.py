from __future__ import annotations

from polyester.codecs.orderbook import depth_to_connect_enum
from polyester.gen.orderbook.v1.orderbook_connect import OrderbookServiceClient
from polyester.gen.orderbook.v1.orderbook_pb2 import GetOrderBookRequest
from polyester.models import OrderbookData, OrderbookLevel
from polyester.services._base import BaseService
from polyester.services._generated import unary_public


class AsyncOrderbookService(BaseService):
    async def get(self, *, symbol: str, depth: int = 50) -> OrderbookData:
        from polyester.gen.orderbook.v1 import orderbook_pb2

        depth_enum = getattr(orderbook_pb2, depth_to_connect_enum(depth))
        data = await unary_public(
            self._transport,
            OrderbookServiceClient,
            lambda client, req: client.get_order_book(req),
            GetOrderBookRequest(symbol=symbol, depth=depth_enum),
        )
        return OrderbookData(
            symbol=symbol,
            depth=depth,
            book_seq=str(data.get("bookSeq") or data.get("book_seq") or "0"),
            bids=[_level_from_dict(level) for level in data.get("bids", [])],
            asks=[_level_from_dict(level) for level in data.get("asks", [])],
        )


def _level_from_dict(level: dict) -> OrderbookLevel:
    price = level.get("priceTicks") or level.get("price_ticks") or 0
    qty = level.get("qtyScaled") or level.get("qty_scaled") or 0
    return OrderbookLevel(price_ticks=str(price), qty_scaled=str(qty))
