from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import user_trades_list_from_proto
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.gen.orders.v1.orders_read_connect import OrdersReadServiceClient
from polyester.gen.orders.v1.orders_read_pb2 import GetUserTradesRequest
from polyester.models import UserTradesList
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._symbols import resolve_symbol_id


class AsyncTradesService(BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager,
        default_sub_account_id: str | None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id

    async def list(
        self,
        *,
        sub_account_id: str | None = None,
        symbol: str | None = None,
        symbol_id: int | None = None,
        limit: int = 100,
        page_token: str | None = None,
    ) -> UserTradesList:
        request = GetUserTradesRequest(limit=limit)
        if symbol is not None or symbol_id is not None:
            request.symbol_id = resolve_symbol_id(
                self._catalogs,
                symbol=symbol,
                symbol_id=symbol_id,
                label="trades.list",
            )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if page_token:
            request.page_token = page_token
        return await unary_auth_decoded(
            self._transport,
            OrdersReadServiceClient,
            lambda client, req: client.get_user_trades(req),
            request,
            user_trades_list_from_proto,
        )

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        if value == "":
            return None
        return value if value is not None else self._default_sub_account_id
