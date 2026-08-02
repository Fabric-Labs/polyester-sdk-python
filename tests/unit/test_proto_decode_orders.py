import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.orders import (
    get_order_from_proto,
    modify_order_from_proto,
    order_from_proto,
    order_mutation_from_proto,
    orders_list_from_proto,
    preview_order_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
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


def test_order_from_proto_omits_trailing_stop_without_distance() -> None:
    from polyester.gen.orders.v1.orders_read_pb2 import (
        AttachedRisk as ProtoAttachedRisk,
    )
    from polyester.gen.orders.v1.orders_read_pb2 import (
        AttachedRiskTrailingStop,
    )

    msg = Order(
        order_id=3,
        symbol_id=1,
        attached_risk=ProtoAttachedRisk(
            trailing_stop=AttachedRiskTrailingStop(
                policy=orders_pb2.TrailingStopPolicy(activation_price_ticks=5500)
            )
        ),
    )
    order = order_from_proto(msg)
    assert order.attached_risk is None


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


def test_order_mutation_exposes_explicit_sizing() -> None:
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


def test_preview_order_admissible_with_protected_bound() -> None:
    evaluated_at = Timestamp(seconds=1_700_000_000, nanos=500_000_000)
    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            admissible=True,
            resolved_base_qty_scaled=100,
            protected_price_bound_ticks=42_000,
            evaluated_at=evaluated_at,
        ),
        quantity_scale=8,
        symbol="BTC-USDT",
        symbol_id=1,
    )
    assert preview.admissible is True
    assert preview.rejection is None
    assert preview.resolved_base_qty is not None
    assert preview.resolved_base_qty.scaled == 100
    assert preview.resolved_base_qty_scaled == "100"
    assert preview.protected_price_bound is not None
    assert preview.protected_price_bound.ticks == 42_000
    assert preview.evaluated_at_ms == 1_700_000_000_500


def test_preview_order_rejection_with_violations() -> None:
    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            admissible=False,
            rejection=orders_pb2.ErrorDetail(
                code=orders_pb2.ERROR_CODE_BAD_QTY,
                violations=[
                    orders_pb2.FieldViolation(
                        field_path="order.qty",
                        rule_id="qty.min",
                        message="quantity below minimum",
                    )
                ],
            ),
            evaluated_at=Timestamp(seconds=1),
        )
    )
    assert preview.admissible is False
    assert preview.rejection is not None
    assert preview.rejection.code == "BAD_QTY"
    assert len(preview.rejection.violations) == 1
    assert preview.rejection.violations[0].field_path == "order.qty"
    assert preview.rejection.violations[0].rule_id == "qty.min"
    assert preview.rejection.violations[0].message == "quantity below minimum"
    assert preview.resolved_base_qty is None
    assert preview.resolved_base_qty_scaled == ""
    assert preview.protected_price_bound is None
    assert preview.evaluated_at_ms == 1_000


def test_preview_order_unknown_rejection_code() -> None:
    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            admissible=False,
            rejection=orders_pb2.ErrorDetail(code=99_999),
            evaluated_at=Timestamp(seconds=1),
        )
    )
    assert preview.rejection is not None
    assert preview.rejection.code == "UNKNOWN_ERROR_CODE(99999)"


def test_preview_order_without_scale_keeps_scaled_string() -> None:
    preview = preview_order_from_proto(
        orders_pb2.PreviewOrderResponse(
            resolved_base_qty_scaled=250,
            evaluated_at=Timestamp(seconds=1),
        )
    )
    assert preview.resolved_base_qty_scaled == "250"
    assert preview.resolved_base_qty is None


def test_preview_order_rejects_missing_evaluated_at() -> None:
    with pytest.raises(PolyesterResponseContractError, match="missing evaluated_at"):
        preview_order_from_proto(orders_pb2.PreviewOrderResponse(admissible=True))


def test_order_mutation_from_proto_cancel_omits_client_order_id() -> None:
    msg = orders_pb2.CancelOrderResponse(status="cancelled", order_id=42)
    result = order_mutation_from_proto(msg)
    assert result.status == "cancelled"
    assert result.order_id == format_id(42)
    assert result.client_order_id == ""
