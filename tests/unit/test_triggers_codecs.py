import pytest

from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2


def test_create_trigger_stop_loss_maps_core_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="stop_loss",
        trigger_price="50000",
        side="sell",
        qty="0.1",
        quantity_scale=8,
        order_type="limit",
        limit_price="49900",
        tif="gtc",
        client_trigger_id="trg-1",
        post_only=True,
    )
    trigger = proto.trigger
    assert trigger.symbol_id == 1
    assert trigger.WhichOneof("strategy") == "stop_loss"
    stop = trigger.stop_loss
    assert stop.trigger_price_ticks == 50_000_000_000
    assert stop.side == orders_pb2.SELL
    assert stop.child.WhichOneof("execution") == "limit_gtc"
    assert stop.child.limit_gtc.price_ticks == 49_900_000_000
    assert stop.child.limit_gtc.post_only is True
    assert trigger.client_trigger_id == "trg-1"


def test_create_trigger_rejects_post_only_on_non_gtc_child() -> None:
    with pytest.raises(PolyesterValidationError):
        create_trigger_to_proto(
            symbol="BTC-USDT",
        symbol_id=1,
            trigger_type="stop_loss",
            trigger_price="50000",
            side="sell",
            qty="0.1",
            quantity_scale=8,
            order_type="limit",
            limit_price="49900",
            tif="ioc",
            post_only=True,
        )


def test_create_trigger_stop_loss_market_child() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="take_profit",
        trigger_price="60000",
        side="sell",
        qty="0.1",
        quantity_scale=8,
        order_type="market",
    )
    trigger = proto.trigger
    assert trigger.WhichOneof("strategy") == "take_profit"
    assert trigger.take_profit.trigger_price_ticks == 60_000_000_000
    assert trigger.take_profit.child.WhichOneof("execution") == "market_ioc"


def test_create_trigger_trailing_stop_maps_strategy_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="trailing_stop",
        side="sell",
        qty="0.1",
        quantity_scale=8,
        trailing_distance_ticks=500_000,
        activation_price="51000",
        max_slippage_bps=25,
        fee_asset="quote",
        self_trade_prevention_mode="expire_maker",
    )
    trigger = proto.trigger
    assert trigger.WhichOneof("strategy") == "trailing_stop"
    trailing = trigger.trailing_stop
    assert trailing.side == orders_pb2.SELL
    assert trailing.trailing_distance_ticks == 500_000
    assert trailing.activation_price_ticks == 51_000_000_000
    assert trailing.max_slippage_bps == 25
    assert trigger.fee_asset == orders_pb2.QUOTE
    assert trigger.self_trade_prevention_mode == orders_pb2.EXPIRE_MAKER


def test_create_trigger_trailing_stop_rejects_buy() -> None:
    with pytest.raises(PolyesterValidationError, match="only supports side=sell"):
        create_trigger_to_proto(
            symbol="BTC-USDT",
        symbol_id=1,
            trigger_type="trailing_stop",
            side="buy",
            qty="0.1",
            quantity_scale=8,
            trailing_distance_bps=100,
        )


def test_create_trigger_twap_maps_window_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="twap",
        side="buy",
        qty="1",
        quantity_scale=8,
        twap_duration_ms=60_000,
        twap_slice_interval_ms=5_000,
    )
    trigger = proto.trigger
    assert trigger.WhichOneof("strategy") == "twap"
    twap = trigger.twap
    assert twap.duration_ms == 60_000
    assert twap.slice_interval_ms == 5_000
    assert twap.side == orders_pb2.BUY
    assert twap.WhichOneof("execution") == "market_ioc"


def test_create_trigger_ladder_maps_range_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="ladder",
        side="buy",
        qty="1",
        quantity_scale=8,
        ladder_price_min="48000",
        ladder_price_max="52000",
        ladder_levels=5,
        ladder_distribution="linear",
    )
    trigger = proto.trigger
    assert trigger.WhichOneof("strategy") == "ladder"
    ladder = trigger.ladder
    assert ladder.price_min_ticks == 48_000_000_000
    assert ladder.price_max_ticks == 52_000_000_000
    assert ladder.levels == 5
    assert ladder.side == orders_pb2.BUY


def test_create_trigger_rejects_non_linear_ladder_distribution() -> None:
    for distribution in ("geometric", "even"):
        try:
            create_trigger_to_proto(
                symbol="BTC-USDT",
        symbol_id=1,
                trigger_type="ladder",
                side="buy",
                qty="1",
                quantity_scale=8,
                ladder_distribution=distribution,
            )
        except PolyesterValidationError as exc:
            assert "ladder_distribution" in str(exc)
        else:
            raise AssertionError("expected PolyesterValidationError")
