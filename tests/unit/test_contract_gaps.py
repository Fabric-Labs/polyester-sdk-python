"""Contract rules for VIP metric quality, trigger modify and slippage ranges."""

from __future__ import annotations

import inspect

import pytest

from polyester.codecs.decode.vip import vip_status_from_proto
from polyester.codecs.orders import risk_policy_from_dict
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.vip.v1 import vip_pb2
from polyester.models.vip import VIPMetricQuality
from polyester.services.triggers import AsyncTriggersService

# --- VIP metric quality -------------------------------------------------------


def test_vip_status_exposes_metric_quality() -> None:
    status = vip_status_from_proto(
        vip_pb2.GetVIPStatusResponse(
            tier=2,
            settled_volume_30d_usd="1250000.5",
            settled_volume_quality=vip_pb2.VIPMetricQuality(
                status=vip_pb2.PRICE_UNAVAILABLE, incomplete_hours=3
            ),
            average_aop_quality=vip_pb2.VIPMetricQuality(
                status=vip_pb2.INCOMPLETE_HISTORY, incomplete_hours=48
            ),
        )
    )
    # A PRICE_UNAVAILABLE volume is a lower bound; the quality says so.
    assert status.settled_volume_30d_usd == "1250000.5"
    assert status.settled_volume_quality == VIPMetricQuality(
        status="price_unavailable", incomplete_hours=3
    )
    assert status.average_aop_quality == VIPMetricQuality(
        status="incomplete_history", incomplete_hours=48
    )
    assert status.average_aop_30d_usd is None


def test_vip_status_complete_quality() -> None:
    status = vip_status_from_proto(
        vip_pb2.GetVIPStatusResponse(
            settled_volume_quality=vip_pb2.VIPMetricQuality(status=vip_pb2.COMPLETE),
        )
    )
    assert status.settled_volume_quality == VIPMetricQuality(status="complete", incomplete_hours=0)


def test_vip_status_without_evidence_has_no_quality() -> None:
    status = vip_status_from_proto(vip_pb2.GetVIPStatusResponse(tier=0))
    assert status.settled_volume_quality is None
    assert status.average_aop_quality is None


# --- Trigger modify has no child limit price ---------------------------------------


def test_trigger_modify_no_longer_takes_a_limit_price() -> None:
    assert "limit_price" not in inspect.signature(modify_trigger_to_proto).parameters
    assert "limit_price" not in inspect.signature(AsyncTriggersService.modify).parameters
    proto = modify_trigger_to_proto(trigger_id="1", symbol_id=1, trigger_price="83000")
    assert not proto.HasField("limit_price_ticks")


# --- Slippage bps ranges ------------------------------------------------------------


def _create(**overrides: object):
    kwargs: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "stop_loss",
        "trigger_price": "83000",
        "side": "sell",
        "qty": "0.01",
        "quantity_scale": 8,
        "order_type": "market",
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_sell_market_child_rejects_10000_bps(trigger_type: str) -> None:
    with pytest.raises(PolyesterValidationError, match="between 1 and 9999"):
        _create(trigger_type=trigger_type, max_slippage_bps=10_000)
    proto = _create(trigger_type=trigger_type, max_slippage_bps=9_999)
    assert getattr(proto.trigger, trigger_type).child.market_ioc.max_slippage_bps == 9_999


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_buy_market_child_accepts_10000_bps(trigger_type: str) -> None:
    proto = _create(trigger_type=trigger_type, side="buy", max_slippage_bps=10_000)
    assert getattr(proto.trigger, trigger_type).child.market_ioc.max_slippage_bps == 10_000
    with pytest.raises(PolyesterValidationError, match="between 1 and 10000"):
        _create(trigger_type=trigger_type, side="buy", max_slippage_bps=10_001)


@pytest.mark.parametrize(
    ("side", "extra"), [("sell", {}), ("buy", {"limit_price": "85000"})]
)
def test_standalone_trailing_stop_rejects_10000_bps(side: str, extra: dict[str, str]) -> None:
    base: dict[str, object] = {
        "trigger_type": "trailing_stop",
        "side": side,
        "trailing_distance_bps": 100,
        **extra,
    }
    with pytest.raises(PolyesterValidationError, match="between 1 and 9999"):
        _create(max_slippage_bps=10_000, **base)
    proto = _create(max_slippage_bps=9_999, **base)
    assert proto.trigger.trailing_stop.max_slippage_bps == 9_999


def test_attached_trailing_stop_rejects_10000_bps() -> None:
    leg = {"trailing_distance_bps": 100}
    with pytest.raises(PolyesterValidationError, match="between 1 and 9999"):
        risk_policy_from_dict({"trailing_stop": {**leg, "max_slippage_bps": 10_000}})
    policy = risk_policy_from_dict({"trailing_stop": {**leg, "max_slippage_bps": 9_999}})
    assert policy is not None
    assert policy.trailing_stop.max_slippage_bps == 9_999


def test_twap_market_slices_still_accept_10000_bps() -> None:
    proto = _create(
        trigger_type="twap",
        twap_duration_ms=60_000,
        twap_slice_interval_ms=10_000,
        max_slippage_bps=10_000,
    )
    assert proto.trigger.twap.market_ioc.max_slippage_bps == 10_000
