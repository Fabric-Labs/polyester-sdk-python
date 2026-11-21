"""Profit and loss (``pnl.v1.ProfitAndLossService``) models.

USD amounts, quantities, prices and percentages are exact
:class:`~decimal.Decimal` values parsed from the server's base-10 strings,
never floats. A figure the server omits because a price it needs is not
available reads ``None``: unknown, never zero, and ``notices`` says why.
Notices are lowercase labels such as ``"mark_unavailable"``; a notice this
SDK does not know reads as its number.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import msgspec


class ProductProfitAndLoss(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The profit and loss of one product (``"spot"``) in the period.

    ``realized_pnl_usd`` is after fees; ``fees_usd`` is net of rebates and
    negative when rebates exceed fees.
    """

    product: str = ""
    realized_pnl_usd: Decimal = Decimal(0)
    fees_usd: Decimal = Decimal(0)
    volume_usd: Decimal = Decimal(0)


class MarketProfitAndLoss(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The realized side of one market in the period.

    ``symbol`` is the pair's name the loaded catalogs know, ``""`` before they
    load. ``realized_pnl_usd`` is after fees: each sale realizes its proceeds
    minus the average cost of what it sold, and each fee is a realized
    expense. ``trade_count`` counts the account's fills.
    """

    symbol_id: int = 0
    symbol: str = ""
    product: str = ""
    realized_pnl_usd: Decimal = Decimal(0)
    fees_usd: Decimal = Decimal(0)
    volume_usd: Decimal = Decimal(0)
    trade_count: int = 0


class HoldingProfitAndLoss(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One asset the account holds now, in whole units of the asset.

    ``position_quantity`` is the quantity with a known cost plus
    ``untracked_quantity``, the quantity whose cost is unknown (deposited
    coins, for example), which never counts toward profit and loss.
    ``cost_usd`` is the cost of the quantity with a known cost.
    ``entry_price_usd`` (average entry price) is ``None`` when no quantity has
    a known cost; ``mark_price_usd`` and ``unrealized_pnl_usd`` are ``None``
    when no current price is available.
    """

    asset_id: int = 0
    position_quantity: Decimal = Decimal(0)
    untracked_quantity: Decimal = Decimal(0)
    cost_usd: Decimal = Decimal(0)
    entry_price_usd: Decimal | None = None
    mark_price_usd: Decimal | None = None
    unrealized_pnl_usd: Decimal | None = None


class ProfitAndLoss(msgspec.Struct, kw_only=True, omit_defaults=True):
    """``pnl.get``: the account's profit and loss in USD over a window.

    ``pnl_usd`` is ``realized_pnl_usd`` plus ``unrealized_pnl_change_usd``,
    the change in unrealized profit and loss since ``window_start``, with
    deposits, withdrawals and transfers neutral. ``unrealized_pnl_usd`` is
    the holdings' unrealized profit and loss now, valued at ``mark_time``.
    The three are ``None`` when a price they need is not available.
    ``as_of`` is when the figures were last published: a trade settled just
    before it may not be included yet. ``markets`` is ordered by symbol ID,
    ``holdings`` by asset ID; the totals and holdings are never filtered by
    market.
    """

    window_start: datetime | None = None
    as_of: datetime | None = None
    mark_time: datetime | None = None
    pnl_usd: Decimal | None = None
    realized_pnl_usd: Decimal = Decimal(0)
    unrealized_pnl_change_usd: Decimal | None = None
    unrealized_pnl_usd: Decimal | None = None
    fees_usd: Decimal = Decimal(0)
    volume_usd: Decimal = Decimal(0)
    products: list[ProductProfitAndLoss] = []
    markets: list[MarketProfitAndLoss] = []
    holdings: list[HoldingProfitAndLoss] = []
    notices: list[str] = []


class DailyProfitAndLoss(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One UTC day of the account; ``day`` is its 00:00 UTC.

    ``pnl_usd`` is the day's realized profit and loss plus the change in
    unrealized profit and loss from the previous close.
    ``unrealized_pnl_at_close_usd`` is ``None`` for today until it closes.
    ``start_equity_usd`` and ``end_equity_usd`` are the account's equity at
    the 00:00 UTC that starts and ends the day; ``net_flow_usd`` its deposits
    and transfers in minus withdrawals and transfers out. A day's return is
    ``(end - start - flow) / (start + flow / 2)``. Each is ``None`` when a
    price it needs is not available (``end_equity_usd`` also for today).
    """

    day: datetime | None = None
    pnl_usd: Decimal | None = None
    realized_pnl_usd: Decimal = Decimal(0)
    unrealized_pnl_at_close_usd: Decimal | None = None
    fees_usd: Decimal = Decimal(0)
    volume_usd: Decimal = Decimal(0)
    trade_count: int = 0
    notices: list[str] = []
    start_equity_usd: Decimal | None = None
    end_equity_usd: Decimal | None = None
    net_flow_usd: Decimal | None = None


class DailyProfitAndLossPage(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One page of ``pnl.list_daily``, oldest day first. Every day of the
    range is listed, days without activity included. Pass
    ``next_page_token`` back as ``page_token``; empty on the last page."""

    days: list[DailyProfitAndLoss] = []
    next_page_token: str = ""
    as_of: datetime | None = None


class TradingStatistics(msgspec.Struct, kw_only=True, omit_defaults=True):
    """``pnl.get_trading_statistics``: the account's trading over a window.

    ``trade_count``, ``volume_usd``, ``fees_usd`` and ``realized_pnl_usd``
    cover the window, today included, filtered by product and market.
    The return figures cover the whole account over closed UTC days only
    (none for ``today``), and ``return_days`` counts the daily returns they
    use. ``return_pct`` is the time-weighted return and ``max_drawdown_pct``
    the largest fall from a previous peak, both in percent (``1.25`` is
    1.25%). ``sharpe`` is the annualized Sharpe ratio, a plain ratio; it needs
    at least 7 daily returns (notice ``"sharpe_insufficient_days"``). Each is
    ``None`` when it cannot be computed.
    """

    window_start: datetime | None = None
    as_of: datetime | None = None
    trade_count: int = 0
    volume_usd: Decimal = Decimal(0)
    fees_usd: Decimal = Decimal(0)
    realized_pnl_usd: Decimal = Decimal(0)
    notices: list[str] = []
    return_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    sharpe: Decimal | None = None
    return_days: int = 0
