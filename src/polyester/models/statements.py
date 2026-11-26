from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime

import msgspec

from polyester.errors import PolyesterResponseContractError
from polyester.models.secret import Secret

# Statement export types: the kind of file an export produces.
# ``statements.create_export`` takes one of them; a type newer than this SDK
# reads as ``"UNKNOWN(n)"`` on ``StatementExport.type``.
# An account statement: one row per entry, account bucket and asset, with the
# entry's net amount, the fees paid and the balance after it
# (:func:`parse_statement_csv`).
STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT = "account_statement"
# A ledger: one row per ledger movement, each transfer leg on its own, with
# its transfer reason, side, counterparty and the balance after it
# (:func:`parse_ledger_csv`).
STATEMENT_EXPORT_TYPE_LEDGER = "ledger"
# The account's balances over the period: one row per account bucket and
# asset, with its balance at the start and at the end of the period and the
# period's credits and debits (:func:`parse_balances_csv`). Its period must
# start inside the account history, or the create raises
# :class:`~polyester.errors.PolyesterStatementHistoryUnavailableError`.
STATEMENT_EXPORT_TYPE_BALANCES = "balances"

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
# The ledger columns every row carries, by header name. Later releases may
# append columns: read them by name, never by position.
LEDGER_COLUMNS = (
    "time",
    "transfer_id",
    "account",
    "asset",
    "type",
    "side",
    "amount",
    "counterparty",
    "balance",
    "link_id",
    "flow_id",
)
# The balances columns every row carries, by header name. Later releases may
# append columns: read them by name, never by position.
BALANCES_COLUMNS = (
    "account",
    "asset",
    "opening_balance",
    "credits",
    "debits",
    "closing_balance",
    "movements",
)


class StatementRow(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One account statement row (``"account_statement"``): the effect of one
    ledger entry on one account bucket in one asset.

    ``time`` is the entry time, an aware UTC datetime exact to the
    microsecond. ``entry_id`` is the entry's unsigned 128-bit identifier as a
    decimal string, the ``transfer_id`` of its first transfer leg on the
    account within the export's period, the same whichever asset the export
    keeps. A period boundary can fall between the legs of one entry: each
    export then holds its own part of it, under the ``transfer_id`` of that
    part's first leg, so do not join rows of different periods on
    ``entry_id`` alone. ``type`` is ``"trade"`` for a trade's settlement and
    its fees, otherwise the transfer reason (``"deposit"``, ``"withdraw"``,
    ``"internal_transfer"``, ...). ``account`` is the bucket, ``"funding"`` or
    ``"trading"``. ``amount`` (the signed balance change, fees in ``fee``
    excluded), ``fee`` (fees the account paid) and ``balance`` (the bucket's
    balance after the entry) are exact decimal strings in whole units of
    ``asset``; never parse them as floats. ``link_id`` correlates related legs
    (a trade's match ID); ``flow_id`` is the public lifecycle flow ID of a
    deposit, withdrawal or internal transfer linked before the export was
    created; a flow linked later shows in ``transfers.list`` and in a new
    export. Both are "" when there is none.
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


class LedgerRow(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One ledger row (``"ledger"``): one ledger movement, one transfer leg on
    the account, as ``transfers.list`` returns it. A trade's settlement is
    several rows, such as its base and quote legs and each fee.

    ``time`` is the transfer time, an aware UTC datetime exact to the
    microsecond. ``transfer_id`` is the transfer's unsigned 128-bit
    identifier as a decimal string; with ``account`` and ``side`` it
    identifies the row. ``account`` is the bucket, ``"funding"`` or
    ``"trading"``. ``type`` is the transfer reason (``"trade_base"``,
    ``"trade_quote"``, ``"maker_fee"``, ``"taker_fee"``, ``"rebate"``,
    ``"deposit"``, ``"withdraw"``, ...). ``side`` is ``"debit"`` when the
    movement takes from the bucket, ``"credit"`` when it adds to it.
    ``amount`` (the signed balance change: negative for a debit) and
    ``balance`` (the bucket's balance after the movement: the previous
    balance of the same bucket and asset plus ``amount``) are exact decimal
    strings in whole units of ``asset``; never parse them as floats.
    ``counterparty`` is the kind of the transfer's other side
    (``"funding_account"``, ``"trading_account"``, ``"external_address"``,
    ``"private_counterparty"``, ``"fee_account"`` or ``"system_account"``),
    "" when unknown. ``link_id`` correlates related legs (a trade's match ID)
    and ``flow_id`` is the lifecycle flow linked before the export was
    created, as on :class:`StatementRow`; both are "" when there is none.
    """

    time: datetime
    transfer_id: str = ""
    account: str = ""
    asset: str = ""
    type: str = ""
    side: str = ""
    amount: str = ""
    counterparty: str = ""
    balance: str = ""
    link_id: str = ""
    flow_id: str = ""


class BalancesRow(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One balances row (``"balances"``): one account bucket in one asset over
    the export's period.

    ``account`` is the bucket, ``"funding"`` or ``"trading"``.
    ``opening_balance`` is its balance at ``start_time`` and
    ``closing_balance`` at ``complete_through``. ``credits`` and ``debits``
    are the totals the period's movements added and took, both as positive
    amounts: the sums of the ledger file's credit and debit rows of that
    bucket and asset. Every row reconciles: ``closing_balance`` is
    ``opening_balance`` plus ``credits`` minus ``debits``. Amounts are exact
    decimal strings in whole units of ``asset``; never parse them as floats.
    ``movements`` counts the period's ledger movements on the bucket.
    """

    account: str
    asset: str = ""
    opening_balance: str = ""
    credits: str = ""
    debits: str = ""
    closing_balance: str = ""
    movements: int = 0


def parse_statement_csv(text: str) -> list[StatementRow]:
    """Parse an account statement export's CSV file, which starts with its
    header row; :func:`parse_ledger_csv` reads a ledger.

    Columns are read by header name: their order does not matter, and columns
    this SDK does not know are ignored. A statement without a ``flow_id``
    column reads it as "". Fields are read strictly as RFC 4180: content after
    a closing quote or an unterminated quoted field, a missing required column,
    a row whose field count differs from the header's, or an unreadable
    ``time`` raises :class:`~polyester.errors.PolyesterResponseContractError`.
    Empty text yields no rows.
    """
    return [
        StatementRow(
            time=_statement_time(value["time"], line, "statement"),
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
        for line, value in _csv_records(text, "statement", STATEMENT_COLUMNS)
    ]


def parse_ledger_csv(text: str) -> list[LedgerRow]:
    """Parse a ledger export's CSV file, which starts with its header row.

    Read as :func:`parse_statement_csv` reads an account statement: columns
    by header name, columns this SDK does not know ignored, fields strictly
    as RFC 4180. A missing ledger column (an account statement lacks
    ``transfer_id`` and ``side``), a row whose field count differs from the
    header's, invalid CSV or an unreadable ``time`` raises
    :class:`~polyester.errors.PolyesterResponseContractError`. Empty text
    yields no rows.
    """
    return [
        LedgerRow(
            time=_statement_time(value["time"], line, "ledger"),
            transfer_id=value["transfer_id"],
            account=value["account"],
            asset=value["asset"],
            type=value["type"],
            side=value["side"],
            amount=value["amount"],
            counterparty=value["counterparty"],
            balance=value["balance"],
            link_id=value["link_id"],
            flow_id=value["flow_id"],
        )
        for line, value in _csv_records(text, "ledger", LEDGER_COLUMNS)
    ]


def parse_balances_csv(text: str) -> list[BalancesRow]:
    """Parse a balances export's CSV file, which starts with its header row.

    Read as :func:`parse_statement_csv` reads an account statement: columns
    by header name, columns this SDK does not know ignored, fields strictly
    as RFC 4180. Rows come sorted by ``account``, then ``asset``; a bucket
    and asset with a zero balance at both ends and no movement has no row. A
    missing balances column, a row whose field count differs from the
    header's, invalid CSV or a ``movements`` that is not a count raises
    :class:`~polyester.errors.PolyesterResponseContractError`. Empty text
    yields no rows.
    """
    return [
        BalancesRow(
            account=value["account"],
            asset=value["asset"],
            opening_balance=value["opening_balance"],
            credits=value["credits"],
            debits=value["debits"],
            closing_balance=value["closing_balance"],
            movements=_count(value["movements"], line),
        )
        for line, value in _csv_records(text, "balances", BALANCES_COLUMNS)
    ]


def _count(value: str, line: int) -> int:
    if value.isascii() and value.isdigit():
        try:
            return int(value)
        except ValueError:
            # Longer than the interpreter converts (sys.get_int_max_str_digits).
            pass
    raise PolyesterResponseContractError(
        "StatementExportFile", f"balances line {line} has an unreadable movements {value[:40]!r}"
    )


def _csv_records(
    text: str, kind: str, required: tuple[str, ...]
) -> list[tuple[int, dict[str, str]]]:
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        return _records(reader, kind, required)
    except csv.Error as exc:
        raise PolyesterResponseContractError(
            "StatementExportFile", f"{kind} line {reader.line_num} is not valid CSV: {exc}"
        ) from exc


def _records(
    reader: Iterator[list[str]], kind: str, required: tuple[str, ...]
) -> list[tuple[int, dict[str, str]]]:
    header: list[str] | None = None
    index: dict[str, int] = {}
    records: list[tuple[int, dict[str, str]]] = []
    for line, fields in enumerate(reader, start=1):
        if not fields:
            continue
        if header is None:
            header = fields
            index = {name: position for position, name in enumerate(fields)}
            missing = [name for name in required if name not in index]
            if missing:
                raise PolyesterResponseContractError(
                    "StatementExportFile", f"{kind} header lacks column(s) {', '.join(missing)}"
                )
            continue
        if len(fields) != len(header):
            raise PolyesterResponseContractError(
                "StatementExportFile",
                f"{kind} line {line} has {len(fields)} fields, the header {len(header)}",
            )
        records.append((line, {name: fields[position] for name, position in index.items()}))
    return records


def _statement_time(value: str, line: int, kind: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        raise PolyesterResponseContractError(
            "StatementExportFile", f"{kind} line {line} has an unreadable time {value!r}"
        )
    return parsed.astimezone(UTC)


class StatementExport(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A whole-period account statement, ledger or balances file produced in
    the background as one CSV file (``StatementExportService``).

    ``type`` is the kind of file, as requested:
    ``STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT`` (``"account_statement"``,
    read with :func:`parse_statement_csv`) or ``STATEMENT_EXPORT_TYPE_LEDGER``
    (``"ledger"``, read with :func:`parse_ledger_csv`) or
    ``STATEMENT_EXPORT_TYPE_BALANCES`` (``"balances"``, read with
    :func:`parse_balances_csv`); ``"UNKNOWN(n)"`` for
    a type this SDK does not know, which never fails the read. Exports created
    before types existed are account statements.

    ``status`` is ``"queued"`` (waiting until account history covers the
    period and no other export of the account is being produced),
    ``"processing"`` (``movements`` and ``bytes`` count its progress),
    ``"ready"`` (downloadable until ``expires_at``), ``"failed"``
    (``failure_reason`` says why: ``"too_large"``, the period holds more than
    4,000,000 ledger movements of the account, counting every asset's even
    when the export keeps one, so split the period; or ``"unavailable"``,
    create a new export), ``"expired"`` (the file was deleted; create a new
    export) or ``"canceled"`` (stopped by ``statements.cancel_export``; any
    partial file was deleted). The last four are final. A balances export
    also fails with ``failure_reason`` ``"history_unavailable"`` when the
    account history moved later than its start after it was created:
    ``history_available_from`` then says where a new export must start: the
    earliest acceptable ``start_time``, rounded up to the next microsecond
    when the server's instant has sub-microsecond digits; ``None`` when no
    ``datetime`` represents that. ""
    when the server names none; ``"UNKNOWN(n)"`` for a value this SDK does
    not know.

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
    does not wrap the download; :func:`parse_statement_csv` reads an account
    statement, :func:`parse_ledger_csv` a ledger and
    :func:`parse_balances_csv` balances.
    """

    export_id: str
    subaccount_id: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    asset_id: int = 0
    idempotency_key: str = ""
    type: str = ""
    status: str = ""
    complete_through: datetime | None = None
    movements: int = 0
    bytes: int = 0
    created_at: datetime | None = None
    ready_at: datetime | None = None
    expires_at: datetime | None = None
    failure_reason: str = ""
    history_available_from: datetime | None = None


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
    ``filename`` is the name the download saves the file as, by the export's
    type: ``account-statement-<export_id>.csv``, ``ledger-<export_id>.csv`` or
    ``balances-<export_id>.csv``.
    """

    url: Secret[str]
    expires_at: datetime
    filename: str
