from __future__ import annotations

import csv
import io
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
    """

    csv: str = ""
    next_page_token: str = ""


class Statement(msgspec.Struct, kw_only=True, omit_defaults=True):
    """A whole account statement: every page's ``csv`` concatenated in order,
    starting with the header row. A period without movements holds the header
    row alone."""

    csv: str = ""

    def rows(self) -> list[StatementRow]:
        """The statement's rows, oldest first; see :func:`parse_statement_csv`."""
        return parse_statement_csv(self.csv)


def parse_statement_csv(text: str) -> list[StatementRow]:
    """Parse a statement CSV that starts with its header row.

    Columns are read by header name: their order does not matter, and columns
    this SDK does not know are ignored. A statement without a ``flow_id``
    column reads it as "". A missing required column, a row whose field count
    differs from the header's, or an unreadable ``time`` raises
    :class:`~polyester.errors.PolyesterResponseContractError`. Empty text
    yields no rows.
    """
    reader = csv.reader(io.StringIO(text, newline=""))
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
