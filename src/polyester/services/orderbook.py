from __future__ import annotations

from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.orderbook import depth_to_connect_enum
from polyester.codecs.realtime_decode import decode_orderbook_delta_bytes
from polyester.gen.orderbook.v1.orderbook_connect import OrderbookServiceClient
from polyester.gen.orderbook.v1.orderbook_pb2 import GetOrderBookRequest
from polyester.models import OrderbookData
from polyester.models.realtime import OrderBookDeltaUpdate
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded
from polyester.services._realtime_subscribe import subscribe_public_proto


class AsyncOrderbookService(BaseService):
    def __init__(self, transport, *, realtime: AsyncRealtimeClient | None = None) -> None:
        super().__init__(transport)
        self._realtime = realtime

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

    async def subscribe_deltas(
        self,
        *,
        symbol_id: int,
        depth: int = 50,
    ) -> AsyncSubscription[OrderBookDeltaUpdate]:
        ws_depth = min(500, max(1, int(depth)))
        channel = f"public:spot:orderbook:deltas:depth:{ws_depth}:{symbol_id}:proto"
        return await subscribe_public_proto(
            self._realtime,
            channel=channel,
            decode=decode_orderbook_delta_bytes,
        )
