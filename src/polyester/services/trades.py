from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import user_trades_list_from_proto
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.realtime_decode import decode_user_trade_bytes
from polyester.gen.orders.v1.orders_read_connect import OrdersReadServiceClient
from polyester.gen.orders.v1.orders_read_pb2 import GetUserTradesRequest
from polyester.models import UserTrade, UserTradesList
from polyester.realtime.client import AsyncRealtimeClient, AsyncSubscription
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._realtime_subscribe import subscribe_account_proto
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services._symbols import resolve_symbol_id


class AsyncTradesService(ScopedSubAccountMixin, BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager,
        default_sub_account_id: str | None,
        *,
        default_account_id: str | int | None = None,
        realtime: AsyncRealtimeClient | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id
        self._realtime = realtime

    async def list(
        self,
        *,
        account: AccountScope | None = None,
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
            self._resolve_sub_account_id(sub_account_id, account=account)
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

    async def subscribe(
        self,
        *,
        account_id: str | int | None = None,
    ) -> AsyncSubscription[UserTrade]:
        return await subscribe_account_proto(
            self._realtime,
            channel_template="private:spot:trades:{account_id}:proto",
            account_id=account_id,
            default_account_id=self._default_account_id,
            decode=decode_user_trade_bytes,
        )
