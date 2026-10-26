"""Tick counts stay within int64 before sending; trigger reads keep the market cap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.orders import (
    create_order_to_proto,
    normalize_create_order_request,
    risk_policy_from_dict,
)
from polyester.codecs.realtime_decode import decode_trigger_bytes
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary

INT64_MAX = 9_223_372_036_854_775_807
OVERFLOW = INT64_MAX + 1


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return catalogs


# --- int64 bounds -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_triggers_create_rejects_overflowing_market_cap_without_sending() -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=1))
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    with (
        patch("polyester.services.triggers.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match="max_slippage_ticks exceeds int64 range"),
    ):
        await service.create(
            symbol="BTC-USDT",
            trigger_type="stop_loss",
            side="sell",
            qty="0.01",
            trigger_price="83000",
            order_type="market",
            max_slippage_ticks=OVERFLOW,
        )
    assert capture.calls == 0


def _trigger(**overrides: object):
    kwargs: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "sell",
        "qty": "0.01",
        "quantity_scale": 8,
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)  # type: ignore[arg-type]


CREATE_CASES = {
    "stop_market_cap": {
        "trigger_type": "stop_loss",
        "trigger_price": "83000",
        "order_type": "market",
        "max_slippage_ticks": "{v}",
    },
    "trailing_distance": {"trigger_type": "trailing_stop", "trailing_distance_ticks": "{v}"},
    "trailing_cap": {
        "trigger_type": "trailing_stop",
        "trailing_distance_bps": 100,
        "max_slippage_ticks": "{v}",
    },
    "twap_cap": {
        "trigger_type": "twap",
        "twap_duration_ms": 60_000,
        "twap_slice_interval_ms": 10_000,
        "max_slippage_ticks": "{v}",
    },
}


def _fill(case: dict[str, object], value: int) -> dict[str, object]:
    return {k: (value if v == "{v}" else v) for k, v in case.items()}


@pytest.mark.parametrize("case", CREATE_CASES.values(), ids=CREATE_CASES.keys())
def test_trigger_create_tick_counts_are_int64_bounded(case: dict[str, object]) -> None:
    _trigger(**_fill(case, INT64_MAX))
    with pytest.raises(PolyesterValidationError, match="exceeds int64 range"):
        _trigger(**_fill(case, OVERFLOW))


@pytest.mark.parametrize("field", ["trailing_distance_ticks", "max_slippage_ticks"])
def test_trigger_modify_tick_counts_are_int64_bounded(field: str) -> None:
    proto = modify_trigger_to_proto(trigger_id="1", symbol_id=1, **{field: INT64_MAX})
    assert getattr(proto, field) == INT64_MAX
    with pytest.raises(PolyesterValidationError, match="exceeds int64 range"):
        modify_trigger_to_proto(trigger_id="1", symbol_id=1, **{field: OVERFLOW})


def test_trigger_modify_still_clears_a_cap_with_zero() -> None:
    proto = modify_trigger_to_proto(trigger_id="1", symbol_id=1, max_slippage_ticks=0)
    assert proto.WhichOneof("max_slippage") == "max_slippage_ticks"
    with pytest.raises(PolyesterValidationError, match="non-negative"):
        modify_trigger_to_proto(trigger_id="1", symbol_id=1, max_slippage_ticks=-1)


def test_order_market_cap_is_int64_bounded() -> None:
    def market(ticks: int):
        return create_order_to_proto(
            normalize_create_order_request(
                symbol="BTC-USDT",
                symbol_id=1,
                side="buy",
                order_type="market",
                qty="0.01",
                max_slippage_ticks=ticks,
            ),
            quantity_scale=8,
        )

    assert market(INT64_MAX).order.market_ioc.max_slippage_ticks == INT64_MAX
    with pytest.raises(PolyesterValidationError, match="exceeds int64 range"):
        market(OVERFLOW)


RISK_CASES = {
    "take_profit_trigger": {"take_profit": {"trigger_price_ticks": "{v}"}},
    "stop_loss_limit": {
        "stop_loss": {
            "trigger_price_ticks": 1,
            "child": {"limit_gtc": {"price_ticks": "{v}"}},
        }
    },
    "trailing_distance": {"trailing_stop": {"trailing_distance_ticks": "{v}"}},
    "trailing_cap": {
        "trailing_stop": {"trailing_distance_bps": 100, "max_slippage_ticks": "{v}"}
    },
    "trailing_activation": {
        "trailing_stop": {"trailing_distance_bps": 100, "activation_price_ticks": "{v}"}
    },
}


def _fill_risk(case: object, value: int) -> object:
    if isinstance(case, dict):
        return {key: _fill_risk(item, value) for key, item in case.items()}
    return value if case == "{v}" else case


@pytest.mark.parametrize("case", RISK_CASES.values(), ids=RISK_CASES.keys())
def test_attached_risk_tick_counts_are_int64_bounded(case: dict[str, object]) -> None:
    assert risk_policy_from_dict(_fill_risk(case, INT64_MAX)) is not None  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError, match="exceeds int64 range"):
        risk_policy_from_dict(_fill_risk(case, OVERFLOW))  # type: ignore[arg-type]


# --- reads keep the market child's cap -----------------------------------------


def _stop_with(market: triggers_pb2.TriggerMarketIoc) -> triggers_pb2.Trigger:
    return triggers_pb2.Trigger(
        trigger_id=5,
        symbol_id=1,
        status=triggers_pb2.STATUS_ARMED,
        stop_loss=triggers_pb2.ConditionalTrigger(
            trigger_price_ticks=83_000_000_000_000,
            side=orders_pb2.SELL,
            child=triggers_pb2.ConditionalChildExecution(market_ioc=market),
        ),
    )


CAPS = {
    "bps_10": triggers_pb2.TriggerMarketIoc(max_slippage_bps=10),
    "bps_50": triggers_pb2.TriggerMarketIoc(max_slippage_bps=50),
    "ticks": triggers_pb2.TriggerMarketIoc(max_slippage_ticks=2_500_000_000),
    "unset": triggers_pb2.TriggerMarketIoc(),
}


def test_stop_market_caps_decode_distinctly() -> None:
    decoded = {name: trigger_from_proto(_stop_with(cap)) for name, cap in CAPS.items()}
    assert len({repr(trigger) for trigger in decoded.values()}) == len(CAPS)
    assert (decoded["bps_10"].max_slippage_bps, decoded["bps_10"].max_slippage) == (10, None)
    assert decoded["bps_50"].max_slippage_bps == 50
    ticks = decoded["ticks"]
    assert ticks.max_slippage_bps == 0
    assert ticks.max_slippage is not None and ticks.max_slippage.ticks == 2_500_000_000
    assert ticks.max_slippage.format() == "2.5"
    assert (decoded["unset"].max_slippage_bps, decoded["unset"].max_slippage) == (0, None)
    for trigger in decoded.values():
        assert (trigger.order_type, trigger.time_in_force) == ("market", "ioc")


def test_take_profit_market_cap_decodes() -> None:
    msg = triggers_pb2.Trigger(
        trigger_id=6,
        symbol_id=1,
        take_profit=triggers_pb2.ConditionalTrigger(
            trigger_price_ticks=90_000_000_000_000,
            side=orders_pb2.BUY,
            child=triggers_pb2.ConditionalChildExecution(
                market_ioc=triggers_pb2.TriggerMarketIoc(max_slippage_bps=10_000)
            ),
        ),
    )
    assert trigger_from_proto(msg).max_slippage_bps == 10_000


def test_stream_decode_keeps_the_market_cap() -> None:
    trigger = decode_trigger_bytes(_stop_with(CAPS["bps_50"]).SerializeToString())
    assert trigger.max_slippage_bps == 50


@pytest.mark.asyncio
async def test_triggers_get_and_list_keep_the_market_cap() -> None:
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    get_capture = CaptureUnary(triggers_pb2.GetTriggerResponse(trigger=_stop_with(CAPS["bps_10"])))
    with patch("polyester.services.triggers.unary_auth_decoded", get_capture):
        got = await service.get(trigger_id="5")
    assert got is not None and got.max_slippage_bps == 10

    list_capture = CaptureUnary(
        triggers_pb2.ListTriggersResponse(
            triggers=[_stop_with(CAPS["ticks"]), _stop_with(CAPS["bps_50"])]
        )
    )
    with patch("polyester.services.triggers.unary_auth_decoded", list_capture):
        listed = await service.list()
    first, second = listed.triggers
    assert first.max_slippage is not None and first.max_slippage.ticks == 2_500_000_000
    assert second.max_slippage_bps == 50
