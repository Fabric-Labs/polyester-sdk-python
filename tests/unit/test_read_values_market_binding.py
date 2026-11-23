"""Prices and quantities the SDK reads are bound to the market they belong to.

Wherever the market is known, from the message's ``symbol_id`` and the
catalogs, or from the request, every decoded ``Price`` carries the pair's
name and every ``Quantity`` its name and ID, so ``compatible_with`` refuses
reusing them for another market: order reads, user trades, private stream
orders and fills, triggers and trigger events, public trades, and a
preview's price bounds.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import msgspec
import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs import wire_decode
from polyester.codecs.decode.market_data import market_trades_from_proto
from polyester.codecs.decode.orders import (
    OrderMarket,
    get_order_from_proto,
    order_mutation_from_proto,
    orders_list_from_proto,
    preview_order_from_proto,
    user_trades_list_from_proto,
)
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.decode.triggers import (
    get_trigger_from_proto,
    trigger_event_from_proto,
    trigger_events_list_from_proto,
)
from polyester.codecs.realtime_decode import (
    decode_trigger_event_batch_bytes,
    decode_user_trade_batch_bytes,
)
from polyester.codecs.scalars import format_id
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.privatews.v1 import private_ws_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.order_key import OrderId
from polyester.services.orders import AsyncOrdersService
from polyester.services.trades import AsyncTradesService
from polyester.services.triggers import AsyncTriggersService
from polyester.types.money import Price, Quantity
from tests.unit.support import CaptureUnary

SYMBOL = "BTC-USDT"
SYMBOL_ID = 1
TICKS = 100_000_000_000


def _scales(symbol_id: int) -> tuple[int | None, int | None]:
    return (8, 6) if symbol_id == SYMBOL_ID else (None, None)


def _symbols(symbol_id: int) -> str:
    return SYMBOL if symbol_id == SYMBOL_ID else ""


def _money(value: Any) -> Iterator[Price | Quantity]:
    """Every Price and Quantity in a decoded model, however deep."""
    if isinstance(value, (Price, Quantity)):
        yield value
    elif isinstance(value, msgspec.Struct):
        for field in value.__struct_fields__:
            yield from _money(getattr(value, field))
    elif dataclasses.is_dataclass(value):
        for field in dataclasses.fields(value):
            yield from _money(getattr(value, field.name))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _money(item)


def _assert_bound(value: Any, *, count: int) -> None:
    found = list(_money(value))
    assert len(found) == count, found
    for money in found:
        assert money.symbol == SYMBOL, money
        if isinstance(money, Quantity):
            assert money.symbol_id == SYMBOL_ID, money


def _order(**fields: Any) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(
        order_id=11,
        symbol_id=SYMBOL_ID,
        price_ticks=TICKS,
        avg_price_ticks=TICKS,
        market_client_ref_price_ticks=TICKS,
        market_max_slippage_ticks=1_000_000,
        orig_qty_scaled=10,
        cum_qty_scaled=5,
        leaves_qty_scaled=5,
        fee_total=orders_read_pb2.OrderFeeTotal(qty_scaled=1),
        attached_risk=orders_read_pb2.AttachedRisk(
            take_profit=orders_read_pb2.AttachedRiskTakeProfit(
                policy=orders_pb2.TakeProfitPolicy(
                    trigger_price_ticks=TICKS,
                    child=orders_pb2.RiskExecution(
                        limit_gtc=orders_pb2.RiskLimitGtc(price_ticks=TICKS)
                    ),
                )
            ),
            stop_loss=orders_read_pb2.AttachedRiskStopLoss(
                policy=orders_pb2.StopLossPolicy(trigger_price_ticks=TICKS)
            ),
            trailing_stop=orders_read_pb2.AttachedRiskTrailingStop(
                policy=orders_pb2.TrailingStopPolicy(
                    trailing_distance_bps=50,
                    activation_price_ticks=TICKS,
                    limit_price_ticks=TICKS,
                )
            ),
        ),
        **fields,
    )


# Order: 4 prices, 6 quantities (orig, cum, inherited, leaves, display, hidden),
# the fee total's quantity and 5 attached risk prices.
ORDER_MONEY = 4 + 6 + 1 + 5


def _trade() -> orders_read_pb2.UserTrade:
    return orders_read_pb2.UserTrade(
        symbol_id=SYMBOL_ID, match_id=3, order_id=11, price_ticks=TICKS, qty_scaled=4
    )


def test_order_reads_bind_every_price_and_quantity() -> None:
    listed = orders_list_from_proto(
        orders_read_pb2.GetOpenOrdersResponse(orders=[_order()]),
        scales=_scales,
        symbols=_symbols,
    )
    _assert_bound(listed, count=ORDER_MONEY)
    got = get_order_from_proto(
        orders_read_pb2.GetOrderResponse(order=_order(), trades=[_trade()]),
        scales=_scales,
        symbols=_symbols,
    )
    _assert_bound(got, count=ORDER_MONEY + 2)


def test_order_json_reads_bind_like_the_protobuf_reads() -> None:
    from google.protobuf.json_format import MessageToDict

    message = orders_read_pb2.GetOrderResponse(order=_order(), trades=[_trade()])
    assert wire_decode.decode_get_order(
        MessageToDict(message), scales=_scales, symbols=_symbols
    ) == get_order_from_proto(message, scales=_scales, symbols=_symbols)


def test_user_trades_bind_price_and_quantity() -> None:
    page = user_trades_list_from_proto(
        orders_read_pb2.GetUserTradesResponse(trades=[_trade()]),
        scales=_scales,
        symbols=_symbols,
    )
    _assert_bound(page, count=2)
    streamed = decode_user_trade_batch_bytes(
        orders_read_pb2.UserTradeBatch(events=[_trade()]).SerializeToString(),
        scales=_scales,
        symbols=_symbols,
    )
    _assert_bound(streamed, count=2)


def test_private_stream_orders_and_fills_bind_to_their_order_market() -> None:
    unit = private_orders_unit_from_proto(
        private_ws_pb2.Unit(
            orders=[_order()],
            events=[
                private_ws_pb2.UnitEvent(
                    order=private_ws_pb2.OrderEvent(
                        order_id=11,
                        fill=private_ws_pb2.Fill(match_id=3, qty_scaled=4, price_ticks=TICKS),
                    )
                )
            ],
        ),
        scales=_scales,
        symbols=_symbols,
    )
    _assert_bound(unit, count=ORDER_MONEY + 2)
    fill = unit.events[0].fill  # type: ignore[union-attr]
    assert fill is not None and fill.qty.scale == 8


def _trigger() -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=7,
        symbol_id=SYMBOL_ID,
        status=triggers_pb2.STATUS_ARMED,
        qty_scaled=1_000,
        stop_loss=triggers_pb2.ConditionalTrigger(
            trigger_price_ticks=TICKS,
            side=orders_pb2.SELL,
            child=triggers_pb2.ConditionalChildExecution(
                limit_gtc=triggers_pb2.TriggerLimitGtc(price_ticks=TICKS)
            ),
        ),
        stop=triggers_pb2.StopDetails(trigger_price_ticks=TICKS),
    )


def test_triggers_bind_their_prices_and_quantity() -> None:
    trigger = get_trigger_from_proto(
        triggers_pb2.GetTriggerResponse(trigger=_trigger()), scales=_scales, symbols=_symbols
    )
    # qty, limit_price, trigger_price and the stop details' trigger_price.
    _assert_bound(trigger, count=4)


def test_trigger_events_bind_their_fire_price() -> None:
    event = triggers_pb2.TriggerEvent(
        trigger_id=7,
        symbol_id=SYMBOL_ID,
        event_type=triggers_pb2.EVENT_FIRED,
        fire_price_ticks=TICKS,
    )
    _assert_bound(trigger_event_from_proto(event, symbols=_symbols), count=1)
    _assert_bound(
        trigger_events_list_from_proto(
            triggers_pb2.ListTriggerEventsResponse(events=[event]), symbols=_symbols
        ),
        count=1,
    )
    _assert_bound(
        decode_trigger_event_batch_bytes(
            triggers_pb2.TriggerEventBatch(events=[event]).SerializeToString(), symbols=_symbols
        ),
        count=1,
    )


def test_public_trades_bind_price_and_quantity() -> None:
    trade = marketdata_pb2.MarketTrade(
        symbol_id=SYMBOL_ID, match_id=3, price_ticks=TICKS, qty_scaled=4
    )
    _assert_bound(
        market_trades_from_proto(
            marketdata_pb2.GetTradesResponse(trades=[trade]), quantity_scale=8, symbol=SYMBOL
        ),
        count=2,
    )
    _assert_bound(
        wire_decode.decode_market_trade_bytes(
            trade.SerializeToString(), quantity_scale=8, symbol=SYMBOL
        ),
        count=2,
    )


def test_preview_binds_its_price_bounds() -> None:
    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            admissible=False,
            rejection=orders_pb2.ErrorDetail(
                code=orders_pb2.ERROR_CODE_PRICE_BAND_VIOLATION, price_band_limit_ticks=TICKS
            ),
            resolved_base_qty_scaled=10,
            protected_price_bound_ticks=TICKS,
            evaluated_at=Timestamp(seconds=1_700_000_000),
        ),
        market=OrderMarket(SYMBOL, SYMBOL_ID, 8),
    )
    _assert_bound(preview, count=3)


def test_a_create_answer_with_a_resolved_quantity_needs_the_market() -> None:
    answer = orders_pb2.CreateOrderResponse(order_id=7, resolved_base_qty_scaled=10)
    with pytest.raises(ValueError, match="needs the order's market"):
        order_mutation_from_proto(answer, market=None)
    # A cancel answer has no quantity and needs none.
    canceled = order_mutation_from_proto(
        orders_pb2.CancelOrderResponse(order_id=7, status=orders_pb2.CancelOrderResponse.ACCEPTED),
        market=None,
    )
    assert canceled.resolved_base_qty is None


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": SYMBOL,
                    "symbol_id": SYMBOL_ID,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    return catalogs


@pytest.mark.asyncio
async def test_services_bind_reads_to_the_catalog_market() -> None:
    catalogs = _catalogs()
    orders = AsyncOrdersService(MagicMock(), catalogs, None)
    with patch(
        "polyester.services.orders.unary_auth_decoded",
        CaptureUnary(orders_read_pb2.GetOpenOrdersResponse(orders=[_order()])),
    ):
        _assert_bound(await orders.list_open(), count=ORDER_MONEY)
    with patch(
        "polyester.services.orders.unary_auth_decoded",
        CaptureUnary(orders_read_pb2.GetOrderHistoryResponse(orders=[_order()])),
    ):
        _assert_bound(await orders.list_history(), count=ORDER_MONEY)
    with patch(
        "polyester.services.orders.unary_auth_decoded",
        CaptureUnary(orders_read_pb2.GetOrderResponse(order=_order(), trades=[_trade()])),
    ):
        _assert_bound(await orders.get(key=OrderId(format_id(11))), count=ORDER_MONEY + 2)
    trades = AsyncTradesService(MagicMock(), catalogs, None)
    with patch(
        "polyester.services.trades.unary_auth_decoded",
        CaptureUnary(orders_read_pb2.GetUserTradesResponse(trades=[_trade()])),
    ):
        _assert_bound(await trades.list(), count=2)
    triggers = AsyncTriggersService(MagicMock(), catalogs, None)
    with patch(
        "polyester.services.triggers.unary_auth_decoded_retry_unavailable",
        CaptureUnary(
            triggers_pb2.ListTriggerEventsResponse(
                events=[
                    triggers_pb2.TriggerEvent(
                        trigger_id=7, symbol_id=SYMBOL_ID, fire_price_ticks=TICKS
                    )
                ]
            )
        ),
    ):
        _assert_bound(await triggers.list_events(trigger_id=format_id(7)), count=1)
