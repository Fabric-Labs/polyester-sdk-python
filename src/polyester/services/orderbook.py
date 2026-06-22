from __future__ import annotations

from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.orderbook import depth_to_connect_enum
from polyester.gen.orderbook.v1.orderbook_connect import OrderbookServiceClient
from polyester.gen.orderbook.v1.orderbook_pb2 import GetOrderBookRequest
from polyester.models import OrderbookData
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded


class AsyncOrderbookService(BaseService):
    async def get(self, *, symbol: str, depth: int = 50) -> OrderbookData:
        from polyester.gen.orderbook.v1 import orderbook_pb2

        depth_enum = getattr(orderbook_pb2, depth_to_connect_enum(depth))
        request = GetOrderBookRequest(symbol=symbol, depth=depth_enum)
        return await unary_public_decoded(
            self._transport,
            OrderbookServiceClient,
            lambda client, req: client.get_order_book(req),
            request,
            lambda msg: orderbook_from_proto(msg, symbol=symbol, depth=depth),
        )
