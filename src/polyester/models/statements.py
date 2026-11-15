from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime

import msgspec

from polyester.errors import PolyesterResponseContractError

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


class StatementPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of an account statement (``ExportStatement``).

    ``csv`` is RFC 4180 CSV in UTF-8 with CRLF line endings, kept as text. Only
    the first page starts with the header row, so concatenating the pages in
    order yields the whole statement. ``next_page_token`` is "" on the last
    page.

    ``complete_through`` is how far the statement is complete: it covers the
    movements from ``start_time`` up to ``complete_through``, exclusive. That
    is the earliest of ``end_time``, the time of the first page's request and
    the time through which account history was complete then, never before
    ``start_time``; every page of one statement carries the same value. When
    it is before ``end_time``, request the rest (from ``complete_through`` to
    ``end_time``) later. ``None`` when the server sent none.
    """

    csv: str = ""
    next_page_token: str = ""
    complete_through: datetime | None = None


class Statement(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A whole account statement: every page's ``csv`` concatenated in order,
    starting with the header row. A period without movements holds the header
    row alone. ``complete_through`` is the end of what it covers, as on
    :class:`StatementPage`."""

    csv: str = ""
    complete_through: datetime | None = None

    def rows(self) -> list[StatementRow]:
        """The statement's rows, oldest first; see :func:`parse_statement_csv`."""
        return parse_statement_csv(self.csv)


def parse_statement_csv(text: str) -> list[StatementRow]:
    """Parse a statement CSV that starts with its header row.

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
            "ExportStatement", f"statement line {reader.line_num} is not valid CSV: {exc}"
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
                    "ExportStatement", f"statement header lacks column(s) {', '.join(missing)}"
                )
            continue
        if len(fields) != len(header):
            raise PolyesterResponseContractError(
                "ExportStatement",
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
            "ExportStatement", f"statement line {line} has an unreadable time {value!r}"
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
    export) or ``"expired"`` (the file was deleted; create a new export).
    "" when the server names none; ``"UNKNOWN(n)"`` for a value this SDK does
    not know.

    ``export_id`` and ``subaccount_id`` are public IDs; ``subaccount_id`` is
    "" for a root account. ``asset_id`` is 0 for every asset. The file covers
    ``start_time`` up to ``complete_through``, exclusive: the earlier of
    ``end_time`` and the instant the export was created. ``ready_at`` and
    ``expires_at`` (7 days after ``ready_at``) are ``None`` before the file is
    ready.

    The file itself is downloaded over REST only, with an authenticated
    ``GET /v1/statements/exports/{export_id}/file``: ``text/csv``, byte for
    byte the ``statements.export`` pages for the same account, asset and
    period up to ``complete_through``, with ``Range`` and ``If-Range``
    support. This SDK does not wrap the download.
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
    ``next_page_token`` is "" on the last page."""

    exports: list[StatementExport] = []
    next_page_token: str = ""
