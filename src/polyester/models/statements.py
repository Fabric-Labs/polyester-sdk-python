from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime

import msgspec

from polyester.errors import PolyesterResponseContractError
from polyester.models.secret import Secret

# The statement columns every row carries, by header name. Later releases may
# append columns: read them by name, never by position.
STATEMENT_COLUMNS = (
    "time",
    "entry_id",
    "type",
    "account",
    "asset",
    "amount",
    "fee",
    "balance",
    "link_id",
)
# Columns a statement may lack: a statement exported before ``flow_id`` existed
# reads it as "".
STATEMENT_OPTIONAL_COLUMNS = ("flow_id",)


class StatementRow(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One statement row: the effect of one ledger entry on one account bucket
    in one asset.

    ``time`` is the entry time, an aware UTC datetime exact to the
    microsecond. ``entry_id`` is the entry's unsigned 128-bit identifier as a
    decimal string, the ``transfer_id`` of its first transfer leg on the
    account. ``type`` is ``"trade"`` for a trade's settlement and its fees,
    otherwise the transfer reason (``"deposit"``, ``"withdraw"``,
    ``"internal_transfer"``, ...). ``account`` is the bucket, ``"funding"`` or
    ``"trading"``. ``amount`` (the signed balance change, fees in ``fee``
    excluded), ``fee`` (fees the account paid) and ``balance`` (the bucket's
    balance after the entry) are exact decimal strings in whole units of
    ``asset``; never parse them as floats. ``link_id`` correlates related legs
    (a trade's match ID); ``flow_id`` is the public lifecycle flow ID of a
    deposit, withdrawal or internal transfer. Both are "" when there is none.
    """

    time: datetime
    entry_id: str = ""
    type: str = ""
    account: str = ""
    asset: str = ""
    amount: str = ""
    fee: str = ""
    balance: str = ""
    link_id: str = ""
    flow_id: str = ""


def parse_statement_csv(text: str) -> list[StatementRow]:
    """Parse a statement export's CSV file, which starts with its header row.

    Columns are read by header name: their order does not matter, and columns
    this SDK does not know are ignored. A statement without a ``flow_id``
    column reads it as "". Fields are read strictly as RFC 4180: content after
    a closing quote or an unterminated quoted field, a missing required column,
    a row whose field count differs from the header's, or an unreadable
    ``time`` raises :class:`~polyester.errors.PolyesterResponseContractError`.
    Empty text yields no rows.
    """
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        return _statement_rows(reader)
    except csv.Error as exc:
        raise PolyesterResponseContractError(
            "StatementExportFile", f"statement line {reader.line_num} is not valid CSV: {exc}"
        ) from exc


def _statement_rows(reader: Iterator[list[str]]) -> list[StatementRow]:
    header: list[str] | None = None
    index: dict[str, int] = {}
    rows: list[StatementRow] = []
    for line, fields in enumerate(reader, start=1):
        if not fields:
            continue
        if header is None:
            header = fields
            index = {name: position for position, name in enumerate(fields)}
            missing = [name for name in STATEMENT_COLUMNS if name not in index]
            if missing:
                raise PolyesterResponseContractError(
                    "StatementExportFile", f"statement header lacks column(s) {', '.join(missing)}"
                )
            continue
        if len(fields) != len(header):
            raise PolyesterResponseContractError(
                "StatementExportFile",
                f"statement line {line} has {len(fields)} fields, the header {len(header)}",
            )

        value = {name: fields[position] for name, position in index.items()}
        rows.append(
            StatementRow(
                time=_statement_time(value["time"], line),
                entry_id=value["entry_id"],
                type=value["type"],
                account=value["account"],
                asset=value["asset"],
                amount=value["amount"],
                fee=value["fee"],
                balance=value["balance"],
                link_id=value["link_id"],
                flow_id=value.get("flow_id", ""),
            )
        )
    return rows


def _statement_time(value: str, line: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        raise PolyesterResponseContractError(
            "StatementExportFile", f"statement line {line} has an unreadable time {value!r}"
        )
    return parsed.astimezone(UTC)


class StatementExport(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A whole-period account statement produced in the background as one CSV
    file (``StatementExportService``).

    ``status`` is ``"queued"`` (waiting until account history covers the
    period and no other export of the account is being produced),
    ``"processing"`` (``movements`` and ``bytes`` count its progress),
    ``"ready"`` (downloadable until ``expires_at``), ``"failed"``
    (``failure_reason`` says why: ``"too_large"``, more than 4,000,000 ledger
    movements, so split the period; or ``"unavailable"``, create a new
    export), ``"expired"`` (the file was deleted; create a new export) or
    ``"canceled"`` (stopped by ``statements.cancel_export``; any partial file
    was deleted). The last four are final. "" when the server names none;
    ``"UNKNOWN(n)"`` for a value this SDK does not know.

    ``export_id`` and ``subaccount_id`` are public IDs; ``subaccount_id`` is
    "" for a root account. ``asset_id`` is 0 for every asset. The file covers
    ``start_time`` up to ``complete_through``, exclusive: the earlier of
    ``end_time`` and the instant the export was created. ``ready_at`` and
    ``expires_at`` (7 days after ``ready_at``) are ``None`` before the file is
    ready.

    The file itself is downloaded over REST, with an authenticated
    ``GET /v1/statements/exports/{export_id}/file`` (``text/csv``, with
    ``Range`` and ``If-Range`` support), or without credentials from the
    short-lived URL ``statements.get_export_download_url`` returns. This SDK
    does not wrap the download; :func:`parse_statement_csv` reads the file.
    """

    export_id: str
    subaccount_id: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    asset_id: int = 0
    idempotency_key: str = ""
    status: str = ""
    complete_through: datetime | None = None
    movements: int = 0
    bytes: int = 0
    created_at: datetime | None = None
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    failure_reason: str = ""


class StatementExportsPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of an account's statement exports, newest first;
    ``next_page_token`` is "" on the last page.

    ``in_progress_exports`` counts the root account's exports ``"queued"`` or
    ``"processing"`` across all its sub-accounts, and
    ``max_in_progress_exports`` is the most it may have at once; both cover
    the root account whichever account the page lists.
    """

    exports: list[StatementExport] = []
    next_page_token: str = ""
    in_progress_exports: int = 0
    max_in_progress_exports: int = 0


class StatementExportDownloadUrl(msgspec.Struct, kw_only=True):
    """A short-lived link to a ready export's file
    (``statements.get_export_download_url``).

    ``url`` needs no credentials, so a browser can open it to save the file:
    anyone who holds it can download the file until ``expires_at``. It is a
    :class:`~polyester.models.Secret`, so printing or logging the link shows
    ``[REDACTED]``; call ``url.reveal()`` to hand it on, and never share,
    store or log it. ``expires_at`` is when the link stops working, at most
    60 seconds after it was signed; request a new one after it.
    ``filename`` is the name the download saves the file as,
    ``statement-<export_id>.csv``.
    """

    url: Secret[str]
    expires_at: datetime | None = None
    filename: str = ""
