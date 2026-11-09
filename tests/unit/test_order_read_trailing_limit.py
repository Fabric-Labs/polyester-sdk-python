"""Order reads keep an attached trailing stop's buy-back limit price.

GetOrder, open orders, order history and the order stream return
``limit_price_ticks`` on a selling order's attached trailing stop. Each read
exposes it exactly as ``TrailingStop.limit_price`` and leaves it unset when the
server sends none, as for a buying order's trailing stop.
"""

from __future__ import annotations

from typing import Any

import pytest
from google.protobuf import json_format

from polyester.codecs.decode.orders import get_order_from_proto, orders_list_from_proto
from polyester.codecs.decode.private_orders import private_orders_from_proto
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.models.trading import Order, TrailingStop

# 85000 quote units, scaled by 1e9, as GetOrder returns it.
_LIMIT_TICKS = 85_000_000_000_000


def _order(order_id: int, side: str, limit_ticks: int | None) -> orders_read_pb2.Order:
    policy: dict[str, Any] = {"trailingDistanceBps": 100, "triggerPriceSource": "LAST_PRICE"}
    if limit_ticks is not None:
        policy["limitPriceTicks"] = str(limit_ticks)
    return json_format.ParseDict(
        {
            "orderId": str(order_id),
            "symbolId": 1,
            "side": side,
            "status": "WORKING",
            "attachedRisk": {
                "trailingStop": {
                    "policy": policy,
                    "state": {"status": "CREATED", "triggerId": str(order_id + 100)},
                }
            },
        },
        orders_read_pb2.Order(),
    )


def _read_paths(msg: orders_read_pb2.Order) -> dict[str, Order]:
    get = get_order_from_proto(orders_read_pb2.GetOrderResponse(order=msg)).order
    assert get is not None
    return {
        "get": get,
        "open orders": orders_list_from_proto(
            orders_read_pb2.GetOpenOrdersResponse(orders=[msg])
        ).orders[0],
        "history": orders_list_from_proto(
            orders_read_pb2.GetOrderHistoryResponse(orders=[msg])
        ).orders[0],
        "order stream": private_orders_from_proto([msg])[0],
    }


def _trailing_stop(order: Order) -> TrailingStop:
    assert order.attached_risk is not None
    assert order.attached_risk.trailing_stop is not None
    return order.attached_risk.trailing_stop


def _unchanged_fields(stop: TrailingStop) -> dict[str, Any]:
    assert stop.state is not None
    return {
        "distance_bps": stop.distance_bps,
        "distance_ticks": stop.distance_ticks,
        "max_slippage_bps": stop.max_slippage_bps,
        "max_slippage_ticks": stop.max_slippage_ticks,
        "activation_price": stop.activation_price,
        "trigger_price_source": stop.trigger_price_source,
        "order_type": stop.order_type,
        "status": stop.state.status,
        "trigger_id": stop.state.trigger_id,
    }


def _expected_unchanged(order_id: int) -> dict[str, Any]:
    return {
        "distance_bps": 100,
        "distance_ticks": 0,
        "max_slippage_bps": 0,
        "max_slippage_ticks": 0,
        "activation_price": None,
        "trigger_price_source": "last",
        "order_type": "",
        "status": "created",
        "trigger_id": format_uint64_id(order_id + 100),
    }


@pytest.mark.parametrize("path", ["get", "open orders", "history", "order stream"])
def test_selling_order_reads_expose_the_trailing_stop_buy_back_limit(path: str) -> None:
    stop = _trailing_stop(_read_paths(_order(7001, "SELL", _LIMIT_TICKS))[path])
    assert stop.limit_price is not None, f"{path}: trailing stop lost its buy-back limit"
    assert stop.limit_price.ticks == _LIMIT_TICKS
    assert stop.limit_price.format() == "85000"
    assert _unchanged_fields(stop) == _expected_unchanged(7001)


@pytest.mark.parametrize("limit_ticks", [None, 0], ids=["absent", "zero"])
@pytest.mark.parametrize("path", ["get", "open orders", "history", "order stream"])
def test_trailing_stop_without_a_limit_reads_unset(path: str, limit_ticks: int | None) -> None:
    stop = _trailing_stop(_read_paths(_order(7002, "BUY", limit_ticks))[path])
    assert stop.limit_price is None
    assert _unchanged_fields(stop) == _expected_unchanged(7002)
