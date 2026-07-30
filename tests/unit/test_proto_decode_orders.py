from polyester.codecs.decode.orders import (
    get_order_from_proto,
    modify_order_from_proto,
    order_from_proto,
    order_mutation_from_proto,
    orders_list_from_proto,
    preview_order_from_proto,
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
        post_only=True,
    )
    order = order_from_proto(msg)
    assert order.order_id == format_id(42)
    assert order.side == "buy"
    assert order.status == "working"
    assert order.order_type == "limit"
    assert order.tif == "gtc"
    assert order.post_only is True
    assert order.attached_risk is None
    assert order.orig_qty is not None and order.orig_qty.scaled == 100
    msg.version = 7
    order = order_from_proto(msg)
    assert order.version == 7


def test_order_from_proto_maps_attached_risk() -> None:
    from polyester.gen.orders.v1.orders_read_pb2 import (
        AttachedRisk as ProtoAttachedRisk,
    )
    from polyester.gen.orders.v1.orders_read_pb2 import (
        AttachedRiskTakeProfit,
        AttachedRiskTrailingStop,
    )

    msg = Order(
        order_id=1,
        symbol_id=1,
        attached_risk=ProtoAttachedRisk(
            take_profit=AttachedRiskTakeProfit(
                policy=orders_pb2.TakeProfitPolicy(
                    trigger_price_ticks=6000,
                    child=orders_pb2.RiskExecution(market_ioc=orders_pb2.RiskMarketIoc()),
                )
            ),
            trailing_stop=AttachedRiskTrailingStop(
                policy=orders_pb2.TrailingStopPolicy(
                    activation_price_ticks=5500,
                    trailing_distance_bps=25,
                    max_slippage_ticks=10,
                )
            ),
            oco=True,
        ),
    )
    order = order_from_proto(msg)
    assert order.attached_risk is not None
    assert order.attached_risk.oco is True
    assert order.attached_risk.take_profit is not None
    assert order.attached_risk.take_profit.trigger_price is not None
    assert order.attached_risk.take_profit.trigger_price.ticks == 6000
    assert order.attached_risk.take_profit.order_type == "market"
    assert order.attached_risk.stop_loss is None
    assert order.attached_risk.trailing_stop is not None
    assert order.attached_risk.trailing_stop.distance_bps == 25
    assert order.attached_risk.trailing_stop.max_slippage_ticks == 10


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
        trades=[
            UserTrade(
                symbol_id=2,
                match_id=99,
                order_id=7,
                side=orders_pb2.BUY,
                fee_scaled=5,
                fee_asset=orders_pb2.BASE,
                referral_share_scaled=2,
            )
        ],
    )
    result = get_order_from_proto(msg)
    assert result.order is not None
    assert result.order.order_id == format_id(7)
    assert len(result.trades) == 1
    assert result.trades[0].match_id == "99"
    assert result.trades[0].fee_scaled == "5"
    assert result.trades[0].fee_asset == "base"
    assert result.trades[0].referral_share_scaled == "2"


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
    # CreateOrderResponse no longer carries a status field; decode synthesizes
    # "accepted" (POLY-3701).
    msg = orders_pb2.CreateOrderResponse(
        order_id=42,
        client_order_id="coid-1",
    )
    result = order_mutation_from_proto(msg)
    assert result.status == "accepted"
    assert result.order_id == format_id(42)
    assert result.client_order_id == "coid-1"


def test_order_mutation_and_preview_expose_explicit_sizing() -> None:
    create = order_mutation_from_proto(
        orders_pb2.CreateOrderResponse(
            order_id=42,
            resolved_base_qty_scaled=100,
            submitted_max_quote_debit_scaled=500,
        ),
        quantity_scale=2,
    )
    assert create.resolved_base_qty is not None
    assert create.resolved_base_qty.scaled == 100
    assert create.resolved_base_qty_scaled == "100"
    assert create.submitted_max_quote_debit_scaled == "500"

    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            resolved_base_qty_scaled=100,
            estimated_quote_debit_scaled=500,
            estimated_fee_scaled=2,
            estimated_net_base_qty_scaled=98,
            fee_asset=orders_pb2.BASE,
        ),
        quantity_scale=2,
    )
    assert preview.resolved_base_qty is not None
    assert preview.resolved_base_qty.scaled == 100
    assert preview.resolved_base_qty_scaled == "100"
    assert preview.estimated_quote_debit_scaled == "500"
    assert preview.fee_asset == "base"


def test_order_mutation_from_proto_cancel_omits_client_order_id() -> None:
    msg = orders_pb2.CancelOrderResponse(status="cancelled", order_id=42)
    result = order_mutation_from_proto(msg)
    assert result.status == "cancelled"
    assert result.order_id == format_id(42)
    assert result.client_order_id == ""
