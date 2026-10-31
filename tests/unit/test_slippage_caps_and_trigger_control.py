"""TS-parity slippage caps, trigger modify/resume without a symbol, VIP metric quality."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.vip import vip_status_from_proto
from polyester.codecs.orders import (
    create_order_to_proto,
    normalize_create_order_request,
    risk_policy_from_dict,
)
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.gen.vip.v1 import vip_pb2
from polyester.models.vip import VIPMetricQuality
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary

CAP_ERROR = "max_slippage_bps must be between 1 and 9999"


def _market_order(side: str, bps: int) -> Any:
    request = normalize_create_order_request(
        symbol="BTC-USDT",
        symbol_id=1,
        side=side,
        order_type="market",
        qty="0.01",
        max_slippage_bps=bps,
    )
    return create_order_to_proto(request, quantity_scale=8)


def _trigger(trigger_type: str, side: str, **overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": trigger_type,
        "side": side,
        "qty": "0.01",
        "quantity_scale": 8,
    }
    if trigger_type in ("stop_loss", "take_profit"):
        kwargs["trigger_price"] = "100"
    if trigger_type == "trailing_stop":
        kwargs["trailing_distance_bps"] = 100
        if side == "buy":
            kwargs["limit_price"] = "120"
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)


# --- Market orders ----------------------------------------------------------


def test_buy_market_order_accepts_10000_bps() -> None:
    assert _market_order("buy", 10_000).order.market_ioc.max_slippage_bps == 10_000


def test_sell_market_order_rejects_10000_bps() -> None:
    assert _market_order("sell", 9_999).order.market_ioc.max_slippage_bps == 9_999
    with pytest.raises(PolyesterValidationError, match=CAP_ERROR):
        _market_order("sell", 10_000)


# --- Attached trailing stop -------------------------------------------------


def test_attached_trailing_stop_caps_slippage_at_9999_bps() -> None:
    risk = risk_policy_from_dict(
        {"trailing_stop": {"trailing_distance_bps": 100, "max_slippage_bps": 9_999}}
    )
    assert risk.trailing_stop.max_slippage_bps == 9_999
    with pytest.raises(PolyesterValidationError, match=CAP_ERROR):
        risk_policy_from_dict(
            {"trailing_stop": {"trailing_distance_bps": 100, "max_slippage_bps": 10_000}}
        )


# --- Triggers ---------------------------------------------------------------


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_buy_conditional_market_child_accepts_10000_bps(trigger_type: str) -> None:
    proto = _trigger(trigger_type, "buy", max_slippage_bps=10_000)
    child = getattr(proto.trigger, trigger_type).child
    assert child.market_ioc.max_slippage_bps == 10_000


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_sell_conditional_market_child_rejects_10000_bps(trigger_type: str) -> None:
    _trigger(trigger_type, "sell", max_slippage_bps=9_999)
    with pytest.raises(PolyesterValidationError, match=CAP_ERROR):
        _trigger(trigger_type, "sell", max_slippage_bps=10_000)


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_standalone_trailing_stop_rejects_10000_bps(side: str) -> None:
    assert _trigger("trailing_stop", side, max_slippage_bps=9_999).trigger.trailing_stop
    with pytest.raises(PolyesterValidationError, match=CAP_ERROR):
        _trigger("trailing_stop", side, max_slippage_bps=10_000)


def test_twap_market_slices_still_accept_10000_bps() -> None:
    proto = _trigger(
        "twap",
        "sell",
        twap_duration_ms=60_000,
        twap_slice_interval_ms=1_000,
        max_slippage_bps=10_000,
    )
    assert proto.trigger.twap.market_ioc.max_slippage_bps == 10_000


def test_buy_trailing_stop_limit_price_must_reach_activation_price() -> None:
    proto = _trigger("trailing_stop", "buy", limit_price="120", activation_price="120")
    assert proto.trigger.trailing_stop.activation_price_ticks == 120_000_000_000
    with pytest.raises(PolyesterValidationError, match="at least activation_price"):
        _trigger("trailing_stop", "buy", limit_price="119", activation_price="120")


def test_trigger_modify_caps_slippage_at_9999_and_zero_clears() -> None:
    assert modify_trigger_to_proto(trigger_id="1", max_slippage_bps=9_999).max_slippage_bps == (
        9_999
    )
    assert modify_trigger_to_proto(trigger_id="1", max_slippage_bps=0).max_slippage_bps == 0
    with pytest.raises(PolyesterValidationError, match=CAP_ERROR):
        modify_trigger_to_proto(trigger_id="1", max_slippage_bps=10_000)


def test_trigger_modify_no_longer_takes_a_limit_price() -> None:
    assert "limit_price" not in inspect.signature(modify_trigger_to_proto).parameters
    assert "limit_price" not in inspect.signature(AsyncTriggersService.modify).parameters
    with pytest.raises(TypeError):
        modify_trigger_to_proto(trigger_id="1", limit_price="100")  # type: ignore[call-arg]


def test_trigger_modify_without_symbol_targets_the_triggers_own_market() -> None:
    proto = modify_trigger_to_proto(trigger_id="1", trigger_price="100")
    assert proto.symbol_id == 0
    assert proto.trigger_price_ticks == 100_000_000_000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "response", "kwargs"),
    [
        ("modify", triggers_pb2.ModifyTriggerResponse(trigger_id=5), {"trigger_price": "100"}),
        ("resume", triggers_pb2.ResumeTriggerResponse(trigger_id=5), {}),
    ],
)
async def test_trigger_control_omits_symbol_without_catalogs(
    method: str, response: Any, kwargs: dict[str, Any]
) -> None:
    capture = CaptureUnary(response)
    service = AsyncTriggersService(MagicMock(), None, None)
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        result = await getattr(service, method)(trigger_id="5", **kwargs)

    assert result.trigger_id
    assert capture.request is not None
    assert capture.request.symbol_id == 0  # type: ignore[attr-defined]


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["modify", "resume"])
async def test_trigger_control_still_resolves_a_supplied_symbol(method: str) -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 7, "base_quantity_scale": 8}]}
    )
    response = (
        triggers_pb2.ModifyTriggerResponse(trigger_id=5)
        if method == "modify"
        else triggers_pb2.ResumeTriggerResponse(trigger_id=5)
    )
    capture = CaptureUnary(response)
    service = AsyncTriggersService(MagicMock(), catalogs, None)
    extra = {"trigger_price": "100"} if method == "modify" else {}
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await getattr(service, method)(trigger_id="5", symbol="BTC-USDT", **extra)

    assert capture.request.symbol_id == 7  # type: ignore[union-attr]


# --- VIP metric quality -----------------------------------------------------


def test_vip_status_exposes_metric_quality() -> None:
    status = vip_status_from_proto(
        vip_pb2.GetVIPStatusResponse(
            tier=2,
            settled_volume_quality=vip_pb2.VIPMetricQuality(
                status=vip_pb2.PRICE_UNAVAILABLE, incomplete_hours=3
            ),
            average_aop_quality=vip_pb2.VIPMetricQuality(
                status=vip_pb2.INCOMPLETE_HISTORY, incomplete_hours=48
            ),
        )
    )

    assert status.settled_volume_quality == VIPMetricQuality(
        status="price_unavailable", incomplete_hours=3
    )
    assert status.average_aop_quality == VIPMetricQuality(
        status="incomplete_history", incomplete_hours=48
    )


def test_vip_status_complete_and_absent_quality() -> None:
    complete = vip_status_from_proto(
        vip_pb2.GetVIPStatusResponse(
            settled_volume_quality=vip_pb2.VIPMetricQuality(status=vip_pb2.COMPLETE)
        )
    )
    assert complete.settled_volume_quality == VIPMetricQuality(status="complete")
    assert complete.average_aop_quality is None
    assert vip_status_from_proto(vip_pb2.GetVIPStatusResponse(tier=0)).settled_volume_quality is (
        None
    )
