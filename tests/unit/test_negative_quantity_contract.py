"""A negative quantity on the wire breaks the response contract.

No quantity can be negative, so every decoder refuses one with
``PolyesterResponseContractError`` naming the field, never with the
``PolyesterValidationError`` a caller's own bad input gets, and never by
reading it as an absent or missing quantity. A quantity of 0, or one the wire
omits, is still a zero quantity.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.market_data import market_trade_from_proto
from polyester.codecs.decode.market_overview import market_overview_entry_from_proto
from polyester.codecs.decode.orderbook import orderbook_from_proto
from polyester.codecs.decode.orders import (
    OrderMarket,
    batch_create_from_proto,
    order_from_proto,
    order_mutation_from_proto,
    preview_order_from_proto,
    user_trade_from_proto,
)
from polyester.codecs.decode.private_orders import private_orders_unit_from_proto
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.wire_decode import (
    decode_market_overview_entry,
    decode_market_trade,
    decode_trigger,
    decode_triggers_list,
)
from polyester.errors import PolyesterResponseContractError, PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.polyester.type.v1 import depth_tier_pb2
from polyester.gen.privatews.v1 import private_ws_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.orderbook.local_book import levels_from_proto_levels

MARKET = OrderMarket(symbol="BTC-USDT", symbol_id=3, quantity_scale=8)


def _refused(decode: Callable[[], Any], field: str, scaled: int) -> None:
    with pytest.raises(PolyesterResponseContractError) as caught:
        decode()
    assert not isinstance(caught.value, PolyesterValidationError)
    assert caught.value.context == field
    assert str(caught.value) == f"{field}: negative quantity {scaled}"


@pytest.mark.parametrize(
    "field", ["orig_qty_scaled", "cum_qty_scaled", "leaves_qty_scaled", "hidden_qty_scaled"]
)
def test_order_refuses_a_negative_quantity(field: str) -> None:
    msg = orders_read_pb2.Order(order_id=1, symbol_id=3, **{field: -1})
    _refused(lambda: order_from_proto(msg, quantity_scale=8), f"Order.{field}", -1)


def test_order_fee_total_refuses_a_negative_quantity() -> None:
    msg = orders_read_pb2.Order(order_id=1, symbol_id=3)
    msg.fee_total.qty_scaled = -2
    _refused(lambda: order_from_proto(msg), "OrderFeeTotal.qty_scaled", -2)


def test_a_zero_or_omitted_order_quantity_is_still_zero() -> None:
    order = order_from_proto(orders_read_pb2.Order(order_id=1, symbol_id=3), quantity_scale=8)
    assert order.orig_qty is not None and order.orig_qty.scaled == 0


def test_user_trade_refuses_a_negative_quantity() -> None:
    msg = orders_read_pb2.UserTrade(order_id=1, symbol_id=3, qty_scaled=-5)
    _refused(lambda: user_trade_from_proto(msg), "UserTrade.qty_scaled", -5)


@pytest.mark.parametrize("market", [MARKET, None])
def test_create_refuses_a_negative_resolved_base_quantity(market: OrderMarket | None) -> None:
    msg = orders_pb2.CreateOrderResponse(order_id=1, resolved_base_qty_scaled=-6)
    _refused(
        lambda: order_mutation_from_proto(msg, market=market),
        "CreateOrderResponse.resolved_base_qty_scaled",
        -6,
    )


@pytest.mark.parametrize("scale", [8, None])
def test_preview_refuses_a_negative_resolved_base_quantity(scale: int | None) -> None:
    msg = orders_pb2.PreviewOrderResponse(
        admissible=True, resolved_base_qty_scaled=-8, evaluated_at=Timestamp(seconds=1)
    )
    market = MARKET._replace(quantity_scale=scale)
    _refused(
        lambda: preview_order_from_proto(msg, market=market),
        "PreviewOrderResponse.resolved_base_qty_scaled",
        -8,
    )


def test_batch_create_refuses_a_negative_resolved_base_quantity() -> None:
    msg = orders_pb2.BatchCreateOrdersResponse(accepted_count=1)
    item = msg.results.add(client_order_id="a")
    item.accepted.order_id = 9
    item.accepted.resolved_base_qty_scaled = -9
    _refused(
        lambda: batch_create_from_proto(msg, markets=[MARKET]),
        "BatchCreateResultItem.accepted.resolved_base_qty_scaled",
        -9,
    )


def test_order_stream_fill_refuses_a_negative_quantity() -> None:
    unit = private_ws_pb2.Unit()
    event = unit.events.add().order
    event.order_id = 1
    event.kind = private_ws_pb2.OrderEvent.FILLED
    event.fill.match_id = 9
    event.fill.qty_scaled = -7
    event.fill.price_ticks = 1_000_000_000
    _refused(lambda: private_orders_unit_from_proto(unit), "OrderEvent.fill.qty_scaled", -7)


def test_market_trade_refuses_a_negative_quantity() -> None:
    msg = marketdata_pb2.MarketTrade(symbol_id=1, match_id=1, price_ticks=5, qty_scaled=-1)
    _refused(lambda: market_trade_from_proto(msg, quantity_scale=8), "MarketTrade.qty_scaled", -1)
    data = {"symbolId": 1, "matchId": "1", "priceTicks": "5", "qtyScaled": "-1"}
    _refused(lambda: decode_market_trade(data, quantity_scale=8), "MarketTrade.qty_scaled", -1)


@pytest.mark.parametrize("priced", [True, False])
def test_market_overview_refuses_a_negative_best_size(priced: bool) -> None:
    """With or without a price on that side: an omitted price does not hide it."""
    msg = marketoverview_pb2.MarketOverview(
        symbol_id=1,
        best_bid_ticks=74_800,
        best_bid_qty_scaled=12,
        best_ask_ticks=75_000 if priced else 0,
        best_ask_qty_scaled=-3,
    )
    field = "MarketOverview.best_ask_qty_scaled"
    _refused(lambda: market_overview_entry_from_proto(msg), field, -3)
    data = {
        "symbolId": 1,
        "bestBidTicks": "74800",
        "bestBidQtyScaled": "12",
        "bestAskQtyScaled": "-3",
    }
    if priced:
        data["bestAskTicks"] = "75000"
    _refused(lambda: decode_market_overview_entry(data), field, -3)


def test_market_overview_empty_side_is_still_no_side() -> None:
    entry = market_overview_entry_from_proto(
        marketoverview_pb2.MarketOverview(
            symbol_id=1, best_bid_ticks=74_800, best_bid_qty_scaled=12
        )
    )
    assert entry.best_ask is None and entry.best_ask_qty is None


def test_trigger_refuses_a_negative_quantity() -> None:
    msg = triggers_pb2.Trigger(trigger_id=1, symbol_id=3, qty_scaled=-1)
    _refused(lambda: trigger_from_proto(msg), "Trigger.qty_scaled", -1)
    _refused(
        lambda: decode_trigger({"triggerId": "1", "symbolId": 3, "qtyScaled": "-1"}),
        "Trigger.qty_scaled",
        -1,
    )


@pytest.mark.parametrize("state", ["twap_state", "ladder_state"])
def test_trigger_refuses_a_negative_executed_quantity(state: str) -> None:
    msg = triggers_pb2.Trigger(trigger_id=1, symbol_id=3, qty_scaled=100)
    getattr(msg, state).executed_qty_scaled = -2
    _refused(lambda: trigger_from_proto(msg), f"Trigger.{state}.executed_qty_scaled", -2)


@pytest.mark.parametrize(
    ("key", "field"),
    [
        ("twapState", "Trigger.twap_state.executed_qty_scaled"),
        ("ladderState", "Trigger.ladder_state.executed_qty_scaled"),
        ("twap_state", "Trigger.twap_state.executed_qty_scaled"),
        ("ladder_state", "Trigger.ladder_state.executed_qty_scaled"),
    ],
)
def test_json_trigger_refuses_a_negative_executed_quantity(key: str, field: str) -> None:
    """The proto-JSON trigger and trigger list refuse it as the protobuf decode does."""
    data = {"triggerId": "1", "symbolId": 3, "qtyScaled": "100", key: {"executedQtyScaled": "-2"}}
    _refused(lambda: decode_trigger(data), field, -2)
    _refused(lambda: decode_triggers_list({"triggers": [data]}), field, -2)
    # A zero or omitted executed quantity is not reported, and still decodes.
    for executed in ({"executedQtyScaled": "0"}, {}):
        assert decode_trigger({**data, key: executed}).qty.scaled == 100


@pytest.mark.parametrize("price_ticks", [101, 0])
def test_orderbook_refuses_a_negative_level_quantity(price_ticks: int) -> None:
    """In an otherwise valid snapshot, with or without the level's price."""
    msg = orderbook_pb2.GetOrderBookResponse(symbol_id=1, book_seq=7, depth=depth_tier_pb2.DEPTH_50)
    msg.bids.add(price_ticks=100, qty_scaled=5)
    msg.asks.add(price_ticks=price_ticks, qty_scaled=-3)
    decode = lambda: orderbook_from_proto(msg, symbol="BTC-USD", depth=50, quantity_scale=8)  # noqa: E731
    _refused(decode, "PriceLevel.qty_scaled", -3)
    _refused(lambda: levels_from_proto_levels(list(msg.asks)), "PriceLevel.qty_scaled", -3)


def test_orderbook_omitted_level_quantity_is_still_missing() -> None:
    msg = orderbook_pb2.GetOrderBookResponse(symbol_id=1, book_seq=7, depth=depth_tier_pb2.DEPTH_50)
    msg.asks.add(price_ticks=101)
    with pytest.raises(PolyesterValidationError):
        orderbook_from_proto(msg, symbol="BTC-USD", depth=50, quantity_scale=8)
    with pytest.raises(PolyesterValidationError):
        levels_from_proto_levels(list(msg.asks))


@pytest.mark.parametrize(
    ("message", "field"),
    [
        (
            orders_read_pb2.Order(order_id=1, symbol_id=7, orig_qty_scaled=-1),
            "Order.orig_qty_scaled",
        ),
        (triggers_pb2.Trigger(trigger_id=1, symbol_id=7, qty_scaled=-1), "Trigger.qty_scaled"),
    ],
)
def test_restricted_runtime_decoders_name_the_field(message: Any, field: str) -> None:
    """The single-file decoders refuse as the SDK does, with its message."""
    from tests.unit import pure_models_support as support

    models = support.load()["polyester_models"]
    for bound in (True, False):
        want = ("error", f"{field}: negative quantity -1")
        assert support.sdk_decode(message, bound) == want
        assert support.file_decode(models, message, bound) == want
