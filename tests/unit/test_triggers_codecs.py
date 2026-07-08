from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2


def test_create_trigger_stop_loss_maps_core_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        trigger_price="50000",
        side="sell",
        qty="0.1",
        order_type="limit",
        limit_price="49900",
        trigger_price_source="mark",
        tif="ioc",
        client_trigger_id="trg-1",
        post_only=True,
    )
    assert proto.symbol == "BTC-USDT"
    assert proto.trigger_type == triggers_pb2.STOP_LOSS
    assert proto.trigger_price_ticks == 50_000_000_000
    assert proto.side == orders_pb2.SELL
    assert proto.order_type == orders_pb2.LIMIT
    assert proto.limit_price_ticks == 49_900_000_000
    assert proto.trigger_price_source == orders_pb2.MARK_PRICE
    assert proto.time_in_force == orders_pb2.IOC
    assert proto.client_trigger_id == "trg-1"
    assert proto.post_only is True


def test_create_trigger_trailing_stop_maps_strategy_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        trigger_type="trailing_stop",
        side="sell",
        qty="0.1",
        trailing_distance_ticks=500_000,
        activation_price="51000",
        max_slippage_bps=25,
        fee_source="quote",
        self_trade_prevention_mode="expire_maker",
    )
    assert proto.trigger_type == triggers_pb2.TRAILING_STOP
    assert proto.trailing_distance_ticks == 500_000
    assert proto.activation_price_ticks == 51_000_000_000
    assert proto.max_slippage_bps == 25
    assert proto.fee_source == orders_pb2.QUOTE
    assert proto.self_trade_prevention_mode == orders_pb2.EXPIRE_MAKER


def test_create_trigger_twap_maps_window_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        trigger_type="twap",
        side="buy",
        qty="1",
        twap_duration_ms=60_000,
        twap_slice_interval_ms=5_000,
        max_slippage_ticks=100_000,
    )
    assert proto.trigger_type == triggers_pb2.TWAP
    assert proto.twap_duration_ms == 60_000
    assert proto.twap_slice_interval_ms == 5_000
    assert proto.max_slippage_ticks == 100_000


def test_create_trigger_ladder_maps_range_fields() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        trigger_type="ladder",
        side="buy",
        qty="1",
        ladder_price_min="48000",
        ladder_price_max="52000",
        ladder_levels=5,
        ladder_distribution="geometric",
    )
    assert proto.trigger_type == triggers_pb2.LADDER
    assert proto.ladder_price_min_ticks == 48_000_000_000
    assert proto.ladder_price_max_ticks == 52_000_000_000
    assert proto.ladder_levels == 5
    assert proto.ladder_distribution == triggers_pb2.GEOMETRIC


def test_create_trigger_rejects_invalid_ladder_distribution() -> None:
    try:
        create_trigger_to_proto(
            symbol="BTC-USDT",
            trigger_type="ladder",
            side="buy",
            qty="1",
            ladder_distribution="even",
        )
    except PolyesterValidationError as exc:
        assert "ladder_distribution" in str(exc)
    else:
        raise AssertionError("expected PolyesterValidationError")
