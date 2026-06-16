from __future__ import annotations

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.balances import balances_list_from_proto, ledger_health_from_proto
from polyester.codecs.ledger import resolve_balance_range, resolve_equity_group_by
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.wire_decode import (
    decode_balance_history,
    decode_equity_history,
    decode_holds_list,
)
from polyester.gen.ledger.read.v1.ledger_read_connect import LedgerReadServiceClient
from polyester.gen.ledger.read.v1.ledger_read_pb2 import (
    GetBalanceHistoryRequest,
    GetBalancesRequest,
    GetEquityHistorySeriesRequest,
    GetHealthRequest,
    ListHoldsRequest,
)
from polyester.models import (
    BalanceHistory,
    BalancesList,
    EquityHistory,
    HoldsList,
    LedgerHealth,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth, unary_auth_decoded
from polyester.services._scope import resolve_sub_account_id


class AsyncBalancesService(BaseService):
    def __init__(
        self,
        transport,
        catalogs: CatalogManager | None = None,
        default_sub_account_id: str | None = None,
        default_account_id: str | int | None = None,
    ) -> None:
        super().__init__(transport)
        self._catalogs = catalogs or CatalogManager()
        self._default_sub_account_id = default_sub_account_id
        self._default_account_id = default_account_id

    async def get_health(self) -> LedgerHealth:
        return await unary_auth_decoded(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.get_health(req),
            GetHealthRequest(),
            ledger_health_from_proto,
        )

    async def list(
        self,
        *,
        sub_account_id: str | int | None = None,
    ) -> BalancesList:
        request = GetBalancesRequest()
        resolved = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if resolved is not None:
            request.subaccount_id = resolved
        return await unary_auth_decoded(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.get_balances(req),
            request,
            balances_list_from_proto,
        )

    async def get_balance_history(
        self,
        *,
        range: str = "7d",
        sub_account_id: str | None = None,
        ledger: int = 0,
        account_codes: list[int] | None = None,
    ) -> BalanceHistory:
        request = GetBalanceHistoryRequest(
            range=resolve_balance_range(range),
            ledger=ledger,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if account_codes:
            request.account_codes.extend(account_codes)
        data = await unary_auth(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.get_balance_history(req),
            request,
        )
        return decode_balance_history(data)

    async def get_equity_history(
        self,
        *,
        range: str = "7d",
        sub_account_id: str | None = None,
        account_codes: list[int] | None = None,
        group_by: str = "account",
    ) -> EquityHistory:
        request = GetEquityHistorySeriesRequest(
            range=resolve_balance_range(range),
            group_by=resolve_equity_group_by(group_by),
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        if account_codes:
            request.account_codes.extend(account_codes)
        data = await unary_auth(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.get_equity_history_series(req),
            request,
        )
        return decode_equity_history(data)

    async def list_holds(
        self,
        *,
        sub_account_id: str | None = None,
        limit: int = 50,
        reversed: bool = False,
    ) -> HoldsList:
        request = ListHoldsRequest(limit=limit, reversed=reversed)
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        data = await unary_auth(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.list_holds(req),
            request,
        )
        return decode_holds_list(data)

    def _resolve_sub_account_id(self, value: str | None) -> str | None:
        return resolve_sub_account_id(value, self._default_sub_account_id)
