"""Stop-loss and take-profit market children carry the user's slippage cap."""

from __future__ import annotations

import pytest

from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2


def _conditional(**overrides: object):
    kwargs: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "stop_loss",
        "trigger_price": "83589",
        "side": "sell",
        "qty": "0.01",
        "quantity_scale": 8,
        "order_type": "market",
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)  # type: ignore[arg-type]


def test_stop_loss_market_child_sends_slippage_bps() -> None:
    proto = _conditional(max_slippage_bps=50)
    market = proto.trigger.stop_loss.child.market_ioc
    assert proto.trigger.stop_loss.child.WhichOneof("execution") == "market_ioc"
    assert market.WhichOneof("max_slippage") == "max_slippage_bps"
    assert market.max_slippage_bps == 50


def test_take_profit_market_child_sends_slippage_ticks() -> None:
    # 2.5 quote units at Q9; above the old int32 range.
    proto = _conditional(trigger_type="take_profit", max_slippage_ticks=2_500_000_000)
    market = proto.trigger.take_profit.child.market_ioc
    assert market.WhichOneof("max_slippage") == "max_slippage_ticks"
    assert market.max_slippage_ticks == 2_500_000_000


def test_market_child_without_cap_leaves_the_pair_default() -> None:
    market = _conditional().trigger.stop_loss.child.market_ioc
    assert market.WhichOneof("max_slippage") is None


def test_buy_stop_loss_may_use_a_market_child_with_a_cap() -> None:
    proto = _conditional(side="buy", max_slippage_bps=10_000)
    stop = proto.trigger.stop_loss
    assert stop.side == orders_pb2.BUY
    assert stop.child.market_ioc.max_slippage_bps == 10_000


def test_market_child_rejects_both_caps() -> None:
    with pytest.raises(PolyesterValidationError, match="at most one of max_slippage"):
        _conditional(max_slippage_ticks=10, max_slippage_bps=50)


@pytest.mark.parametrize("ticks", [0, -5])
def test_market_child_rejects_non_positive_ticks(ticks: int) -> None:
    with pytest.raises(PolyesterValidationError, match="max_slippage_ticks must be positive"):
        _conditional(max_slippage_ticks=ticks)


@pytest.mark.parametrize("cap", [{"max_slippage_bps": 50}, {"max_slippage_ticks": 10}])
def test_limit_child_rejects_a_slippage_cap(cap: dict[str, int]) -> None:
    with pytest.raises(PolyesterValidationError, match="market child"):
        _conditional(order_type="limit", tif="gtc", limit_price="83500", **cap)


def test_modify_changes_and_clears_a_live_market_cap() -> None:
    changed = modify_trigger_to_proto(trigger_id="5", symbol_id=1, max_slippage_bps=75)
    assert changed.WhichOneof("max_slippage") == "max_slippage_bps"
    assert changed.max_slippage_bps == 75
    cleared = modify_trigger_to_proto(trigger_id="5", symbol_id=1, max_slippage_ticks=0)
    assert cleared.WhichOneof("max_slippage") == "max_slippage_ticks"
    assert cleared.max_slippage_ticks == 0
