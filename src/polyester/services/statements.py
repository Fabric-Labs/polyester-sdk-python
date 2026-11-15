from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from polyester.codecs.contract_limits import (
    contract_string_length,
    contract_string_pattern,
    contract_uint32_max,
)
from polyester.codecs.decode.statements import (
    created_statement_export_from_proto,
    statement_export_from_get_response,
    statement_exports_page_from_proto,
    statement_page_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.scalars import UINT32_MAX, exact_integer, id_to_int
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.read.v1 import statement_export_pb2 as export_pb2
from polyester.gen.ledger.read.v1.ledger_read_connect import LedgerReadServiceClient
from polyester.gen.ledger.read.v1.statement_export_connect import StatementExportServiceClient
from polyester.models.statements import (
    Statement,
    StatementExport,
    StatementExportsPage,
    StatementPage,
)
from polyester.services._base import BaseService
from polyester.services._generated import unary_auth_decoded
from polyester.services._scope import AccountScope, ScopedSubAccountMixin
from polyester.services.changelog import _timestamp

# Statement export request limits, from the contract's validation rules.
EXPORT_IDEMPOTENCY_KEY_MIN_LEN, EXPORT_IDEMPOTENCY_KEY_MAX_LEN = contract_string_length(
    export_pb2.CreateStatementExportRequest, "idempotency_key"
)
_EXPORT_IDEMPOTENCY_KEY_PATTERN = re.compile(
    contract_string_pattern(export_pb2.CreateStatementExportRequest, "idempotency_key")
)
LIST_EXPORTS_MAX_LIMIT = contract_uint32_max(export_pb2.ListStatementExportsRequest, "limit")
_EXPORT_PAGE_TOKEN_MAX_LEN = contract_string_length(
    export_pb2.ListStatementExportsRequest, "page_token"
)[1]
# The longest period one export covers. The contract states it as a rule on
# the whole request: end_time - start_time <= duration('8784h'), 366 days.
EXPORT_MAX_PERIOD = timedelta(hours=8784)


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
            statement_page_from_proto,
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
        complete_through: datetime | None = None
        while True:
            page = await self.export_page(
                start_time=start_time,
                end_time=end_time,
                account=account,
                sub_account_id=sub_account_id,
                asset_id=asset_id,
                page_token=token,
            )
            if not parts:
                complete_through = page.complete_through
            elif page.complete_through != complete_through:
                # Every page of one statement covers the same period.
                raise PolyesterResponseContractError(
                    "ExportStatement", "a later page changes complete_through"
                )
            parts.append(page.csv)
            if not page.next_page_token:
                return Statement(csv="".join(parts), complete_through=complete_through)
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ExportStatement", "next_page_token repeats an earlier page_token"
                )
            requested.add(page.next_page_token)
            token = page.next_page_token

    async def create_export(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        idempotency_key: str,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
        asset_id: int | None = None,
    ) -> StatementExport:
        """Ask for the whole statement of ``start_time`` (inclusive) to
        ``end_time`` (exclusive) as one CSV file, produced in the background
        (``StatementExportService/CreateStatementExport``).

        The period must be non-empty and at most ``EXPORT_MAX_PERIOD`` (366
        days); both times are timezone-aware and sent exact to the
        microsecond. A period still open at create time ends then: the
        export's ``complete_through`` says where. ``asset_id`` keeps one asset;
        ``None`` or 0 covers every asset. The account resolves as for
        :meth:`export`. Signed; an API key needs ``READ_STATEMENTS``.

        ``idempotency_key`` is 1 to 64 letters, digits, ``.``, ``_``, ``:`` or
        ``-``, unique per root account, sent exactly as given: repeating the
        create with it returns the same export, and the same key with other
        fields is refused with ``ERROR_CODE_IDEMPOTENCY_KEY_REUSED``. A root
        account has at most 5 exports queued or processing; another create is
        refused with ``ERROR_CODE_STATEMENT_EXPORT_LIMIT_REACHED``, which is not
        retryable: wait for one to finish. Poll :meth:`get_export` until the
        export is ``"ready"`` or ``"failed"``; the file is downloaded over REST
        (see :class:`~polyester.models.StatementExport`).
        """
        for name, value in (("start_time", start_time), ("end_time", end_time)):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise PolyesterValidationError(f"{name} is required (a timezone-aware datetime)")
        if not start_time < end_time <= start_time + EXPORT_MAX_PERIOD:
            raise PolyesterValidationError(
                "end_time must be after start_time and at most 366 days after it"
            )
        if (
            not isinstance(idempotency_key, str)
            or not EXPORT_IDEMPOTENCY_KEY_MIN_LEN
            <= len(idempotency_key)
            <= EXPORT_IDEMPOTENCY_KEY_MAX_LEN
            or _EXPORT_IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key) is None
        ):
            raise PolyesterValidationError(
                f"idempotency_key must be {EXPORT_IDEMPOTENCY_KEY_MIN_LEN} to "
                f"{EXPORT_IDEMPOTENCY_KEY_MAX_LEN} characters: letters, digits, '.', '_', ':' "
                "or '-'"
            )
        request = export_pb2.CreateStatementExportRequest(idempotency_key=idempotency_key)
        request.start_time.CopyFrom(_timestamp(start_time))
        request.end_time.CopyFrom(_timestamp(end_time))
        if asset_id is not None:
            request.asset_id = exact_integer(
                asset_id, "asset_id", min_value=0, max_value=UINT32_MAX
            )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            StatementExportServiceClient,
            lambda client, req: client.create_statement_export(req),
            request,
            created_statement_export_from_proto,
        )

    async def get_export(self, *, export_id: str) -> StatementExport:
        """One statement export by its public ``export_id``: its status,
        progress and expiry. Signed; an API key needs ``READ_STATEMENTS``."""
        request = export_pb2.GetStatementExportRequest(export_id=id_to_int(export_id, "export_id"))
        return await unary_auth_decoded(
            self._transport,
            StatementExportServiceClient,
            lambda client, req: client.get_statement_export(req),
            request,
            statement_export_from_get_response,
        )

    async def list_exports(
        self,
        *,
        limit: int = 0,
        page_token: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> StatementExportsPage:
        """One page of the account's statement exports, newest first.
        ``limit`` is 0 (the server's 20) to ``LIST_EXPORTS_MAX_LIMIT`` (100);
        pass ``next_page_token`` back as ``page_token``. The account resolves
        as for :meth:`export`."""
        token = page_token or ""
        if not isinstance(token, str) or len(token) > _EXPORT_PAGE_TOKEN_MAX_LEN:
            raise PolyesterValidationError(
                f"page_token must be a string of at most {_EXPORT_PAGE_TOKEN_MAX_LEN} characters"
            )
        request = export_pb2.ListStatementExportsRequest(
            limit=exact_integer(limit, "limit", min_value=0, max_value=LIST_EXPORTS_MAX_LIMIT),
            page_token=token,
        )
        parsed_sub = parse_optional_subaccount_id(
            self._resolve_sub_account_id(sub_account_id, account=account)
        )
        if parsed_sub is not None:
            request.subaccount_id = parsed_sub
        return await unary_auth_decoded(
            self._transport,
            StatementExportServiceClient,
            lambda client, req: client.list_statement_exports(req),
            request,
            statement_exports_page_from_proto,
        )

    async def iter_exports(
        self,
        *,
        limit: int = 0,
        page_token: str | None = None,
        account: AccountScope | None = None,
        sub_account_id: str | int | None = None,
    ) -> AsyncIterator[StatementExport]:
        """Every statement export of the account, newest first, fetching
        pages as needed with the same arguments."""
        requested: set[str] = set()
        token = page_token
        while True:
            if token:
                requested.add(token)
            page = await self.list_exports(
                limit=limit, page_token=token, account=account, sub_account_id=sub_account_id
            )
            for item in page.exports:
                yield item
            if not page.next_page_token:
                return
            if page.next_page_token in requested:
                raise PolyesterResponseContractError(
                    "ListStatementExports", "next_page_token repeats an earlier page token"
                )
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
