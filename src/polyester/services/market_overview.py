from __future__ import annotations

from polyester.codecs.wire_decode import decode_market_overview_list
from polyester.gen.marketoverview.v1.marketoverview_connect import MarketOverviewServiceClient
from polyester.gen.marketoverview.v1.marketoverview_pb2 import ListMarketOverviewRequest
from polyester.models import MarketOverviewList
from polyester.services._base import BaseService
from polyester.services._generated import unary_public


class AsyncMarketOverviewService(BaseService):
    async def list(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 50,
        page: int = 0,
        include_sparklines: bool = False,
    ) -> MarketOverviewList:
        request = ListMarketOverviewRequest(
            limit=limit,
            page=page,
            include_sparklines=include_sparklines,
        )
        if symbols:
            request.symbols.extend(symbols)
        data = await unary_public(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.list_market_overview(req),
            request,
        )
        return decode_market_overview_list(data)
