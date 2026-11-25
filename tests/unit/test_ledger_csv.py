"""Ledger and balances statement files, read by header name."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polyester.errors import PolyesterResponseContractError
from polyester.models import (
    STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT,
    STATEMENT_EXPORT_TYPE_BALANCES,
    STATEMENT_EXPORT_TYPE_LEDGER,
    BalancesRow,
    LedgerRow,
    parse_balances_csv,
    parse_ledger_csv,
    parse_statement_csv,
)

HEADER = "time,transfer_id,account,asset,type,side,amount,counterparty,balance,link_id,flow_id\r\n"
TRADE = datetime(2026, 10, 3, 8, 12, 45, 123456, tzinfo=UTC)


def test_export_type_labels() -> None:
    assert STATEMENT_EXPORT_TYPE_ACCOUNT_STATEMENT == "account_statement"
    assert STATEMENT_EXPORT_TYPE_LEDGER == "ledger"
    assert STATEMENT_EXPORT_TYPE_BALANCES == "balances"


def test_ledger_csv_reads_columns_by_header_name() -> None:
    # A trade's quote debit and its taker fee, then a deposit credit, with
    # reordered columns and a column a later release appends.
    text = (
        "side,flow_id,time,transfer_id,account,asset,type,amount,counterparty,balance,"
        "link_id,future_column\r\n"
        "debit,,2026-10-03T08:12:45.123456Z,27419385013475392811,trading,USDT,trade_quote,"
        '-100.5,trading_account,899.5,77,"x,y"\r\n'
        "debit,,2026-10-03T08:12:45.123456Z,27419385013475392812,trading,USDT,taker_fee,"
        "-0.1,fee_account,899.4,77,y\r\n"
        "credit,flow_1,2026-10-04T00:00:00.000001Z,27419385013475392900,funding,BTC,deposit,"
        "0.25,,0.25,,z\r\n"
    )
    assert parse_ledger_csv(text) == [
        LedgerRow(
            time=TRADE,
            transfer_id="27419385013475392811",
            account="trading",
            asset="USDT",
            type="trade_quote",
            side="debit",
            amount="-100.5",
            counterparty="trading_account",
            balance="899.5",
            link_id="77",
        ),
        LedgerRow(
            time=TRADE,
            transfer_id="27419385013475392812",
            account="trading",
            asset="USDT",
            type="taker_fee",
            side="debit",
            amount="-0.1",
            counterparty="fee_account",
            balance="899.4",
            link_id="77",
        ),
        LedgerRow(
            time=datetime(2026, 10, 4, 0, 0, 0, 1, tzinfo=UTC),
            transfer_id="27419385013475392900",
            account="funding",
            asset="BTC",
            type="deposit",
            side="credit",
            amount="0.25",
            balance="0.25",
            flow_id="flow_1",
        ),
    ]


def test_ledger_with_only_the_header_has_no_rows() -> None:
    assert parse_ledger_csv(HEADER) == []
    assert parse_ledger_csv("") == []


@pytest.mark.parametrize(
    "text",
    [
        # Missing flow_id.
        "time,transfer_id,account,asset,type,side,amount,counterparty,balance,link_id\r\n",
        # An account statement is not a ledger.
        "time,entry_id,type,account,asset,amount,fee,balance,link_id,flow_id\r\n",
        HEADER + "2026-10-03T08:12:45Z,1,trading\r\n",
        HEADER + "yesterday,1,trading,BTC,deposit,credit,1,,1,,\r\n",
        HEADER + "2026-10-03T08:12:45,1,trading,BTC,deposit,credit,1,,1,,\r\n",
        HEADER + '2026-10-03T08:12:45Z,"1"x,trading,BTC,deposit,credit,1,,1,,\r\n',
    ],
)
def test_ledger_csv_refuses_what_it_cannot_read(text: str) -> None:
    with pytest.raises(PolyesterResponseContractError):
        parse_ledger_csv(text)


def test_statement_csv_refuses_a_ledger() -> None:
    with pytest.raises(PolyesterResponseContractError):
        parse_statement_csv(HEADER)


BALANCES_HEADER = "account,asset,opening_balance,credits,debits,closing_balance,movements\r\n"


def test_balances_csv_reads_columns_by_header_name() -> None:
    text = (
        "movements,asset,account,closing_balance,debits,credits,opening_balance,future\r\n"
        "3,BTC,funding,0.75,0.25,1,0,x\r\n"
        "12,USDT,trading,899.4,100.6,0,1000,y\r\n"
    )
    assert parse_balances_csv(text) == [
        BalancesRow(
            account="funding",
            asset="BTC",
            opening_balance="0",
            credits="1",
            debits="0.25",
            closing_balance="0.75",
            movements=3,
        ),
        BalancesRow(
            account="trading",
            asset="USDT",
            opening_balance="1000",
            credits="0",
            debits="100.6",
            closing_balance="899.4",
            movements=12,
        ),
    ]


def test_balances_with_only_the_header_have_no_rows() -> None:
    assert parse_balances_csv(BALANCES_HEADER) == []
    assert parse_balances_csv("") == []


@pytest.mark.parametrize(
    "text",
    [
        "account,asset,opening_balance,credits,debits,closing_balance\r\n",
        HEADER,
        BALANCES_HEADER + "funding,BTC\r\n",
        BALANCES_HEADER + "funding,BTC,0,1,0,1,three\r\n",
        BALANCES_HEADER + "funding,BTC,0,1,0,1,-1\r\n",
        BALANCES_HEADER + "funding,BTC,0,1,0,1,\u0663\r\n",
    ],
)
def test_balances_csv_refuses_what_it_cannot_read(text: str) -> None:
    with pytest.raises(PolyesterResponseContractError):
        parse_balances_csv(text)
