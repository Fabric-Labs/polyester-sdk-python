from __future__ import annotations

from datetime import datetime

from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.read.v1.ledger_read_connect import LedgerReadServiceClient
from polyester.models.statements import Statement, StatementPage
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services.changelog import _timestamp


def _statement_page_from_proto(msg: ledger_read_pb2.ExportStatementResponse) -> StatementPage:
    return StatementPage(csv=msg.csv, next_page_token=msg.next_page_token)


class AsyncStatementsService(ScopedSubAccountMixin, BaseService):
    """Account statements (``ledger.read.v1.LedgerReadService/ExportStatement``):
    an account's balance movements for a period as CSV, for reconciliation and
    tax reporting.

    Signed like the other ledger reads; an API key needs ``READ_STATEMENTS``
    on its policy (``READ_BALANCES`` does not grant it). A statement covers
    one account, the main account or one sub-account, resolved as
    ``transfers.list`` resolves it: with neither ``account`` nor
    ``sub_account_id``, the client's default sub-account, else the account the
    key is scoped to.
    """

    def __init__(self, transport, default_sub_account_id: str | None) -> None:
        super().__init__(transport)
        self._default_sub_account_id = default_sub_account_id

    async def export_page(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        asset_id: int | None = None,
        page_token: str | None = None,
    ) -> StatementPage:
        """One page of the statement for ``start_time`` (inclusive) to
        ``end_time`` (exclusive), both timezone-aware and sent exact to the
        microsecond; the server allows at most 366 days. ``asset_id`` keeps
        one asset (its ``ledger_id``); ``None`` or 0 covers every asset. A
        page holds at most 2000 ledger movements and never splits an entry;
        only the first page carries the header row. Pass ``next_page_token``
        back as ``page_token`` with the same other arguments."""
        request = self._request(
            start_time=start_time,
            end_time=end_time,
            account=account,
            sub_account_id=sub_account_id,
            asset_id=asset_id,
        )
        request.page_token = page_token or ""
        return await unary_auth_decoded(
            self._transport,
            LedgerReadServiceClient,
            lambda client, req: client.export_statement(req),
            request,
            _statement_page_from_proto,
        )

    async def export(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        asset_id: int | None = None,
    ) -> Statement:
        """The whole statement: every page of ``export_page`` requested with
        the same arguments and concatenated in order, the header row first.
        Read its rows with :meth:`Statement.rows`, by column name."""
        parts: list[str] = []
        requested: set[str] = set()
        token = ""
        while True:
            page = await self.export_page(
                start_time=start_time,
                end_time=end_time,
                account=account,
                sub_account_id=sub_account_id,
                asset_id=asset_id,
                page_token=token,
            )
            parts.append(page.csv)
            if not page.next_page_token:
                return Statement(csv="".join(parts))
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ExportStatement", "next_page_token repeats an earlier page_token"
                )
            requested.add(page.next_page_token)
            token = page.next_page_token

    def _request(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        account: AccountScope | None,
        sub_account_id: str | int | None,
        asset_id: int | None,
    ) -> ledger_read_pb2.ExportStatementRequest:
        for name, value in (("start_time", start_time), ("end_time", end_time)):
            if not isinstance(value, datetime):
                raise PolyesterValidationError(f"{name} is required (a timezone-aware datetime)")
        request = ledger_read_pb2.ExportStatementRequest()
        request.start_time.CopyFrom(_timestamp(start_time))
        request.end_time.CopyFrom(_timestamp(end_time))
        if asset_id is not None:
            if (
                isinstance(asset_id, bool)
                or not isinstance(asset_id, int)
                or not (0 <= asset_id < 2**32)
            ):
                raise PolyesterValidationError(
                    "asset_id must be an integer between 0 and 2**32 - 1"
                )
            request.asset_id = asset_id
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return request
