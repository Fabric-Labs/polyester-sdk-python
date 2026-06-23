from polyester.codecs.decode.orders import (
    get_order_from_proto,
    modify_order_from_proto,
    order_from_proto,
    order_mutation_from_proto,
    orders_list_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.orders.v1.orders_read_pb2 import (
    GetOpenOrdersResponse,
    GetOrderResponse,
    Order,
    OrderStatus,
    UserTrade,
)


def test_order_from_proto_maps_enums_and_ids() -> None:
    msg = Order(
        order_id=42,
        symbol_id=3,
        client_order_id="coid-1",
        side=orders_pb2.BUY,
        status=OrderStatus.WORKING,
        order_type=orders_pb2.LIMIT,
        time_in_force=orders_pb2.GTC,
        orig_qty_scaled=100,
        cum_qty_scaled=10,
        leaves_qty_scaled=90,
        price_ticks=5000,
        avg_price_ticks=4990,
        created_ts_ns=1_700_000_000_000,
    )
    order = order_from_proto(msg)
    assert order.order_id == format_id(42)
    assert order.side == "buy"
    assert order.status == "working"
    assert order.order_type == "limit"
    assert order.tif == "gtc"
    assert order.orig_qty == "100"


def test_orders_list_from_proto() -> None:
    msg = GetOpenOrdersResponse(
        orders=[Order(order_id=1, symbol_id=1, side=orders_pb2.SELL)],
        next_page_token="tok",
    )
    result = orders_list_from_proto(msg)
    assert len(result.orders) == 1
    assert result.next_page_token == "tok"


def test_get_order_from_proto_includes_trades() -> None:
    msg = GetOrderResponse(
        order=Order(order_id=7, symbol_id=2),
        trades=[UserTrade(symbol_id=2, match_id=99, order_id=7, side=orders_pb2.BUY)],
    )
    result = get_order_from_proto(msg)
    assert result.order is not None
    assert result.order.order_id == format_id(7)
    assert len(result.trades) == 1
    assert result.trades[0].match_id == "99"


def test_modify_order_from_proto_action_taken_enum() -> None:
    msg = orders_pb2.ModifyOrderResponse(
        action_taken=orders_pb2.AMENDED,
        old_order_id=10,
        final_order_id=11,
        code="ok",
    )
    result = modify_order_from_proto(msg)
    assert result.action_taken == "amended"
    assert result.old_order_id == format_id(10)
    assert result.final_order_id == format_id(11)


def test_order_mutation_from_proto_create_includes_client_order_id() -> None:
    msg = orders_pb2.CreateOrderResponse(
        status="accepted",
        order_id=42,
        client_order_id="coid-1",
    )
    result = order_mutation_from_proto(msg)
    assert result.status == "accepted"
    assert result.order_id == format_id(42)
    assert result.client_order_id == "coid-1"


def test_order_mutation_from_proto_cancel_omits_client_order_id() -> None:
    msg = orders_pb2.CancelOrderResponse(status="cancelled", order_id=42)
    result = order_mutation_from_proto(msg)
    assert result.status == "cancelled"
    assert result.order_id == format_id(42)
    assert result.client_order_id == ""
