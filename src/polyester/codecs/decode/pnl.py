"""Decode ``pnl.v1.ProfitAndLossService`` replies.

Every USD figure, quantity and ratio is a base-10 decimal string on the wire
and an exact ``Decimal`` here. A text that is not one is a contract violation,
never a float or a zero. An optional figure the server left out is ``None``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal

from google.protobuf.message import Message

from polyester.codecs.proto_helpers import has_field, optional_timestamp
from polyester.errors import PolyesterResponseContractError
from polyester.gen.pnl.v1 import pnl_pb2
from polyester.models.pnl import (
    DailyProfitAndLoss,
    DailyProfitAndLossPage,
    HoldingProfitAndLoss,
    MarketProfitAndLoss,
    ProductProfitAndLoss,
    ProfitAndLoss,
    TradingStatistics,
)

SymbolNames = Callable[[int], str]

# A signed base-10 decimal: digits, an optional fraction, no exponent.
_DECIMAL = re.compile(r"-?[0-9]+(\.[0-9]+)?")


def _decimal(method: str, field: str, text: str) -> Decimal:
    if _DECIMAL.fullmatch(text) is None:
        raise PolyesterResponseContractError(
            method, f"{field} is not a base-10 decimal string: {text!r}"
        )
    return Decimal(text)


def _optional_decimal(method: str, msg: Message, field: str) -> Decimal | None:
    if not has_field(msg, field):
        return None
    return _decimal(method, field, getattr(msg, field))


def _label(enum, value: int, prefix: str) -> str:
    try:
        name: str = enum.Name(value)
    except ValueError:
        return str(value)
    return name.removeprefix(prefix).lower()


def _product(value: int) -> str:
    if value == 0:
        return ""
    return _label(pnl_pb2.ProfitAndLossProduct, value, "PROFIT_AND_LOSS_PRODUCT_")


def _notices(values) -> list[str]:
    return [
        _label(pnl_pb2.ProfitAndLossNotice, int(value), "PROFIT_AND_LOSS_NOTICE_")
        for value in values
    ]


def _product_from_proto(method: str, msg: pnl_pb2.ProductProfitAndLoss) -> ProductProfitAndLoss:
    return ProductProfitAndLoss(
        product=_product(int(msg.product)),
        realized_pnl_usd=_decimal(method, "realized_pnl_usd", msg.realized_pnl_usd),
        fees_usd=_decimal(method, "fees_usd", msg.fees_usd),
        volume_usd=_decimal(method, "volume_usd", msg.volume_usd),
    )


def _market_from_proto(
    method: str, msg: pnl_pb2.MarketProfitAndLoss, symbols: SymbolNames | None
) -> MarketProfitAndLoss:
    symbol_id = int(msg.symbol_id)
    return MarketProfitAndLoss(
        symbol_id=symbol_id,
        symbol=symbols(symbol_id) if symbols is not None else "",
        product=_product(int(msg.product)),
        realized_pnl_usd=_decimal(method, "realized_pnl_usd", msg.realized_pnl_usd),
        fees_usd=_decimal(method, "fees_usd", msg.fees_usd),
        volume_usd=_decimal(method, "volume_usd", msg.volume_usd),
        trade_count=int(msg.trade_count),
    )


def _holding_from_proto(method: str, msg: pnl_pb2.HoldingProfitAndLoss) -> HoldingProfitAndLoss:
    return HoldingProfitAndLoss(
        asset_id=int(msg.asset_id),
        position_quantity=_decimal(method, "position_quantity", msg.position_quantity),
        untracked_quantity=_decimal(method, "untracked_quantity", msg.untracked_quantity),
        cost_usd=_decimal(method, "cost_usd", msg.cost_usd),
        entry_price_usd=_optional_decimal(method, msg, "entry_price_usd"),
        mark_price_usd=_optional_decimal(method, msg, "mark_price_usd"),
        unrealized_pnl_usd=_optional_decimal(method, msg, "unrealized_pnl_usd"),
    )


def profit_and_loss_from_proto(
    msg: pnl_pb2.GetProfitAndLossResponse, *, symbols: SymbolNames | None = None
) -> ProfitAndLoss:
    method = "GetProfitAndLoss"
    return ProfitAndLoss(
        window_start=optional_timestamp(msg, "window_start"),
        as_of=optional_timestamp(msg, "as_of"),
        mark_time=optional_timestamp(msg, "mark_time"),
        pnl_usd=_optional_decimal(method, msg, "pnl_usd"),
        realized_pnl_usd=_decimal(method, "realized_pnl_usd", msg.realized_pnl_usd),
        unrealized_pnl_change_usd=_optional_decimal(method, msg, "unrealized_pnl_change_usd"),
        unrealized_pnl_usd=_optional_decimal(method, msg, "unrealized_pnl_usd"),
        fees_usd=_decimal(method, "fees_usd", msg.fees_usd),
        volume_usd=_decimal(method, "volume_usd", msg.volume_usd),
        products=[_product_from_proto(method, item) for item in msg.products],
        markets=[_market_from_proto(method, item, symbols) for item in msg.markets],
        holdings=[_holding_from_proto(method, item) for item in msg.holdings],
        notices=_notices(msg.notices),
    )


def daily_profit_and_loss_from_proto(msg: pnl_pb2.DailyProfitAndLoss) -> DailyProfitAndLoss:
    method = "ListDailyProfitAndLoss"
    return DailyProfitAndLoss(
        day=optional_timestamp(msg, "day"),
        pnl_usd=_optional_decimal(method, msg, "pnl_usd"),
        realized_pnl_usd=_decimal(method, "realized_pnl_usd", msg.realized_pnl_usd),
        unrealized_pnl_at_close_usd=_optional_decimal(method, msg, "unrealized_pnl_at_close_usd"),
        fees_usd=_decimal(method, "fees_usd", msg.fees_usd),
        volume_usd=_decimal(method, "volume_usd", msg.volume_usd),
        trade_count=int(msg.trade_count),
        notices=_notices(msg.notices),
        start_equity_usd=_optional_decimal(method, msg, "start_equity_usd"),
        end_equity_usd=_optional_decimal(method, msg, "end_equity_usd"),
        net_flow_usd=_optional_decimal(method, msg, "net_flow_usd"),
    )


def daily_profit_and_loss_page_from_proto(
    msg: pnl_pb2.ListDailyProfitAndLossResponse,
) -> DailyProfitAndLossPage:
    return DailyProfitAndLossPage(
        days=[daily_profit_and_loss_from_proto(item) for item in msg.days],
        next_page_token=msg.next_page_token,
        as_of=optional_timestamp(msg, "as_of"),
    )


def trading_statistics_from_proto(msg: pnl_pb2.GetTradingStatisticsResponse) -> TradingStatistics:
    method = "GetTradingStatistics"
    return TradingStatistics(
        window_start=optional_timestamp(msg, "window_start"),
        as_of=optional_timestamp(msg, "as_of"),
        trade_count=int(msg.trade_count),
        volume_usd=_decimal(method, "volume_usd", msg.volume_usd),
        fees_usd=_decimal(method, "fees_usd", msg.fees_usd),
        realized_pnl_usd=_decimal(method, "realized_pnl_usd", msg.realized_pnl_usd),
        notices=_notices(msg.notices),
        return_pct=_optional_decimal(method, msg, "return_pct"),
        max_drawdown_pct=_optional_decimal(method, msg, "max_drawdown_pct"),
        sharpe=_optional_decimal(method, msg, "sharpe"),
        return_days=int(msg.return_days),
    )
