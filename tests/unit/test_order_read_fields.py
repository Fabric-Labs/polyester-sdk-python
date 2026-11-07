"""Order reads keep the terminal time, origin and MARKET slippage protection
the server sends, and leave each one unset when the server does."""

from __future__ import annotations

from typing import Any

import pytest

from polyester.codecs.decode.orders import get_order_from_proto, orders_list_from_proto
from polyester.codecs.decode.private_orders import private_orders_from_proto
from polyester.codecs.proto_helpers import format_uint64_id
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.models.trading import Order


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


def _fields(order: Order) -> dict[str, Any]:
    origin = getattr(order, "origin", None)
    ref = getattr(order, "market_client_ref_price", None)
    cap = getattr(order, "market_max_slippage", None)
    return {
        "terminal_ts_ns": getattr(order, "terminal_ts_ns", None),
        "origin": None
        if origin is None
        else {
            "scope": origin.scope,
            "trigger_type": origin.trigger_type,
            "trigger_id": origin.trigger_id,
            "parent_order_id": origin.parent_order_id,
            "child_seq": origin.child_seq,
        },
        "market_client_ref_price": None if ref is None else ref.ticks,
        "market_max_slippage": None if cap is None else cap.ticks,
        "market_max_slippage_bps": getattr(order, "market_max_slippage_bps", None),
    }


_UNSET = {
    "terminal_ts_ns": "",
    "origin": None,
    "market_client_ref_price": None,
    "market_max_slippage": None,
    "market_max_slippage_bps": 0,
}


@pytest.mark.parametrize(
    ("msg", "want"),
    [
        pytest.param(
            orders_read_pb2.Order(
                order_id=11,
                symbol_id=1,
                status=orders_read_pb2.FILLED,
                created_ts_ns=1_700_000_000_000_000_000,
                terminal_ts_ns=1_700_000_000_250_000_000,
                origin=orders_read_pb2.OrderOrigin(
                    scope=orders_read_pb2.STANDALONE_TRIGGER,
                    trigger_type=orders_read_pb2.TWAP,
                    trigger_id=77,
                    child_seq=3,
                ),
                market_max_slippage_bps=100,
            ),
            {
                **_UNSET,
                "terminal_ts_ns": "1700000000250000000",
                "origin": {
                    "scope": "standalone_trigger",
                    "trigger_type": "twap",
                    "trigger_id": format_uint64_id(77),
                    "parent_order_id": "",
                    "child_seq": 3,
                },
                "market_max_slippage_bps": 100,
            },
            id="filled TWAP child with bps slippage",
        ),
        pytest.param(
            orders_read_pb2.Order(
                order_id=12,
                symbol_id=1,
                status=orders_read_pb2.CANCELED,
                terminal_ts_ns=1_700_000_001_000_000_000,
                origin=orders_read_pb2.OrderOrigin(
                    scope=orders_read_pb2.ATTACHED_RISK,
                    trigger_type=orders_read_pb2.STOP_LOSS,
                    trigger_id=78,
                    parent_order_id=10,
                ),
                market_client_ref_price_ticks=50_000_000_000,
                market_max_slippage_ticks=2_500_000,
            ),
            {
                **_UNSET,
                "terminal_ts_ns": "1700000001000000000",
                "origin": {
                    "scope": "attached_risk",
                    "trigger_type": "stop_loss",
                    "trigger_id": format_uint64_id(78),
                    "parent_order_id": format_uint64_id(10),
                    "child_seq": 0,
                },
                "market_client_ref_price": 50_000_000_000,
                "market_max_slippage": 2_500_000,
            },
            id="attached-risk market child with a tick cap",
        ),
        pytest.param(
            orders_read_pb2.Order(
                order_id=13,
                symbol_id=1,
                status=orders_read_pb2.FILLED,
                terminal_ts_ns=1_700_000_002_000_000_000,
                origin=orders_read_pb2.OrderOrigin(scope=orders_read_pb2.DIRECT),
            ),
            {
                **_UNSET,
                "terminal_ts_ns": "1700000002000000000",
                "origin": {
                    "scope": "direct",
                    "trigger_type": "",
                    "trigger_id": "",
                    "parent_order_id": "",
                    "child_seq": 0,
                },
            },
            id="direct order",
        ),
        pytest.param(
            orders_read_pb2.Order(order_id=14, symbol_id=1, status=orders_read_pb2.WORKING),
            _UNSET,
            id="open order without any of them",
        ),
    ],
)
def test_order_reads_keep_terminal_time_origin_and_market_slippage(
    msg: orders_read_pb2.Order, want: dict[str, Any]
) -> None:
    for path, order in _read_paths(msg).items():
        assert _fields(order) == want, path
