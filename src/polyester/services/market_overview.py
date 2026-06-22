from __future__ import annotations

from polyester.codecs.decode.market_overview import market_overview_list_from_proto
from polyester.gen.marketoverview.v1.marketoverview_connect import MarketOverviewServiceClient
from polyester.gen.marketoverview.v1.marketoverview_pb2 import ListMarketOverviewRequest
from polyester.models import MarketOverviewList
from polyester.services._base import BaseService
from polyester.services._generated import unary_public_decoded


class AsyncMarketOverviewService(BaseService):
    async def list(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 50,
        page_token: str = "",
        include_sparklines: bool = False,
    ) -> MarketOverviewList:
        request = ListMarketOverviewRequest(
            limit=limit,
            page_token=page_token,
            include_sparklines=include_sparklines,
        )
        if symbols:
            request.symbols.extend(symbols)
        return await unary_public_decoded(
            self._transport,
            MarketOverviewServiceClient,
            lambda client, req: client.list_market_overview(req),
            request,
            market_overview_list_from_proto,
        )
