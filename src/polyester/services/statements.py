from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Literal

from polyester.codecs.contract_limits import (
    contract_string_length,
    contract_string_pattern,
    contract_uint32_max,
)
from polyester.codecs.decode.statements import (
    canceled_statement_export_from_proto,
    created_statement_export_from_proto,
    statement_export_download_url_from_proto,
    statement_export_from_get_response,
    statement_exports_page_from_proto,
)
from polyester.codecs.orders import parse_optional_subaccount_id
from polyester.codecs.proto_helpers import datetime_to_timestamp
from polyester.codecs.scalars import UINT32_MAX, exact_integer, format_id, id_to_int
from polyester.errors import (
    PolyesterResponseContractError,
    PolyesterValidationError,
)
from polyester.gen.ledger.read.v1 import statement_export_pb2 as export_pb2
from polyester.gen.ledger.read.v1.statement_export_connect import StatementExportServiceClient
from polyester.models.statements import (
    STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT,
    STATEMENT_EXPORT_TYPE_BALANCES,
    STATEMENT_EXPORT_TYPE_LEDGER,
    StatementExport,
    StatementExportDownloadUrl,
    StatementExportsPage,
)
from polyester.services._base import BaseService
from polyester.services._echo import echoed
from polyester.services._generated import unary_auth_decoded
from polyester.services._poll import poll_until_final
from polyester.services._scope import AccountScope, ScopedSubAccountMixin

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
# An export in one of these statuses never changes again.
EXPORT_FINAL_STATUSES = frozenset({"ready", "failed", "expired", "canceled"})
# The file types a create may ask for. The contract refuses the unspecified
# type, so there is no default.
_EXPORT_TYPES = {
    STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT: export_pb2.ACCOUNT_STATEMENT,
    STATEMENT_EXPORT_TYPE_LEDGER: export_pb2.LEDGER,
    STATEMENT_EXPORT_TYPE_BALANCES: export_pb2.BALANCES,
}
_EXPORT_POLL_INITIAL = 1.0
_EXPORT_POLL_MAX = 15.0


class AsyncStatementsService(ScopedSubAccountMixin, BaseService):
    """Account statements (``ledger.read.v1.StatementExportService``): an
    account's balance movements for a period, produced in the background as
    one CSV file, an account statement, a ledger or the account's balances,
    for reconciliation and tax reporting.

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

    async def create_export(
        self,
        *,
        type: Literal["account_statement", "ledger", "balances"],
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

        ``type`` is the kind of file, and is required:
        ``STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT`` (``"account_statement"``,
        one row per entry with its fees), ``STATEMENT_EXPORT_TYPE_LEDGER``
        (``"ledger"``, one row per transfer leg) or
        ``STATEMENT_EXPORT_TYPE_BALANCES`` (``"balances"``, one row per account
        bucket and asset with its opening and closing balance). Every type has
        the same period, asset filter, limits and lifecycle. A balances period
        must also start inside the account history: an earlier start raises
        :class:`~polyester.errors.PolyesterStatementHistoryUnavailableError`,
        whose ``history_available_from`` says where to start. Any other value raises
        :class:`PolyesterValidationError` before sending, and repeating an
        ``idempotency_key`` with another type is refused with
        ``ERROR_CODE_IDEMPOTENCY_KEY_REUSED``.

        The period must be non-empty and at most ``EXPORT_MAX_PERIOD`` (366
        days); both times are timezone-aware ``datetime`` objects, sent exact
        to the microsecond (``None``, any other type or a naive datetime raises
        :class:`PolyesterValidationError` before sending). A period still open
        at create time ends then: the export's ``complete_through`` says where.
        ``asset_id`` keeps one asset; ``None`` or 0 covers every asset. The
        account resolves as described on the class. Signed; an API key needs
        ``READ_STATEMENTS``.

        ``idempotency_key`` is 1 to 64 letters, digits, ``.``, ``_``, ``:`` or
        ``-``, unique per root account, sent exactly as given: repeating the
        create with it returns the same export, and the same key with other
        fields is refused with ``ERROR_CODE_IDEMPOTENCY_KEY_REUSED``. A root
        account has at most 5 exports queued or processing; another create is
        refused with ``ERROR_CODE_STATEMENT_EXPORT_LIMIT_REACHED``, which is not
        retryable: wait for one to finish, or cancel one with
        :meth:`cancel_export`. :meth:`wait_export` reads the export until it
        is final; the file is downloaded over REST (see
        :class:`~polyester.models.StatementExport`).
        """
        export_type = _EXPORT_TYPES.get(type) if isinstance(type, str) else None
        if export_type is None:
            raise PolyesterValidationError(
                f"type must be {STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT!r}, "
                f"{STATEMENT_EXPORT_TYPE_LEDGER!r} or {STATEMENT_EXPORT_TYPE_BALANCES!r}, "
                f"not {type!r}"
            )
        start_ts = datetime_to_timestamp(start_time, "start_time")
        end_ts = datetime_to_timestamp(end_time, "end_time")
        # The span, never start_time + 366 days: that overflows near year 9999.
        if not timedelta(0) < end_time - start_time <= EXPORT_MAX_PERIOD:
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
        request = export_pb2.CreateStatementExportRequest(
            type=export_type, idempotency_key=idempotency_key
        )
        request.start_time.CopyFrom(start_ts)
        request.end_time.CopyFrom(end_ts)
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
            echoed(
                "GetStatementExport",
                "export_id",
                format_id(request.export_id),
                lambda msg: format_id(msg.export.export_id) if msg.HasField("export") else None,
                statement_export_from_get_response,
            ),
        )

    async def cancel_export(self, *, export_id: str) -> StatementExport:
        """Stop a ``"queued"`` or ``"processing"`` export
        (``StatementExportService/CancelStatementExport``) and return it,
        ``"canceled"``.

        It stops counting toward the root account's exports in progress at
        once, so the next export can start, and any partial file is deleted.
        Canceling a ``"ready"``, ``"failed"`` or ``"expired"`` export raises
        ``ERROR_CODE_STATEMENT_EXPORT_NOT_CANCELABLE``. Signed; an API key
        needs ``READ_STATEMENTS``."""
        request = export_pb2.CancelStatementExportRequest(
            export_id=id_to_int(export_id, "export_id")
        )
        return await unary_auth_decoded(
            self._transport,
            StatementExportServiceClient,
            lambda client, req: client.cancel_statement_export(req),
            request,
            echoed(
                "CancelStatementExport",
                "export_id",
                format_id(request.export_id),
                lambda msg: format_id(msg.export.export_id) if msg.HasField("export") else None,
                canceled_statement_export_from_proto,
            ),
        )

    async def get_export_download_url(self, *, export_id: str) -> StatementExportDownloadUrl:
        """A short-lived URL of a ``"ready"`` export's file that needs no
        credentials (``StatementExportService/GetStatementExportDownloadUrl``),
        for a browser to save the file.

        The URL is a :class:`~polyester.models.Secret`: anyone who holds it can
        download the file until its ``expires_at``, at most 60 seconds after
        it was signed, so never share, store or log it. An export not ready
        raises ``ERROR_CODE_STATEMENT_EXPORT_NOT_READY``; an expired, failed or
        canceled one ``ERROR_CODE_STATEMENT_EXPORT_EXPIRED``,
        ``ERROR_CODE_STATEMENT_EXPORT_FAILED`` or
        ``ERROR_CODE_STATEMENT_EXPORT_CANCELED``. Servers and scripts that hold
        credentials download with the authenticated
        ``GET /v1/statements/exports/{export_id}/file`` instead. Signed; an API
        key needs ``READ_STATEMENTS``."""
        request = export_pb2.GetStatementExportDownloadUrlRequest(
            export_id=id_to_int(export_id, "export_id")
        )
        return await unary_auth_decoded(
            self._transport,
            StatementExportServiceClient,
            lambda client, req: client.get_statement_export_download_url(req),
            request,
            statement_export_download_url_from_proto,
        )

    async def wait_export(self, *, export_id: str, timeout: float | None = None) -> StatementExport:
        """Read the export with :meth:`get_export` until it is final
        (``"ready"``, ``"failed"``, ``"expired"`` or ``"canceled"``, the
        statuses in ``EXPORT_FINAL_STATUSES``) and return it.

        Reads start 1 s apart and back off to 15 s. Errors are raised as they
        come. After ``timeout`` seconds (``None`` waits for as long as the
        export runs), :class:`~polyester.errors.PolyesterTimeoutError` is
        raised; the export keeps running. The timeout bounds each read and
        wait: a read still in flight at the deadline is cancelled, and none
        is returned after it. Cancelling the call cancels the
        wait, not the export: use :meth:`cancel_export` for that.
        """
        return await poll_until_final(
            lambda: self.get_export(export_id=export_id),
            lambda export: export.status in EXPORT_FINAL_STATUSES,
            timeout=timeout,
            initial=_EXPORT_POLL_INITIAL,
            maximum=_EXPORT_POLL_MAX,
            expired=lambda last: (
                f"statement export {export_id} is still "
                f"{(last.status if last else '') or 'in progress'}"
            ),
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
        as for :meth:`create_export`. The page also counts the root account's
        exports in progress against its limit."""
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
