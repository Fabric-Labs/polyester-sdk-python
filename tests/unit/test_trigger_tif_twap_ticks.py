"""Trigger create refusals Python already applies: no GTD child, positive TWAP ticks.

POLY-8758 and POLY-8748 were found in the Go and Rust encoders; these cases
pin the same rules here.
"""

from __future__ import annotations

from typing import Any

import pytest

from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError

STRATEGIES: dict[str, dict[str, Any]] = {
    "market-stop": {"trigger_type": "stop_loss", "trigger_price": "60000"},
    "limit-stop": {
        "trigger_type": "stop_loss",
        "trigger_price": "60000",
        "order_type": "limit",
        "limit_price": "59950",
    },
    "twap-market": {
        "trigger_type": "twap",
        "twap_duration_ms": 60_000,
        "twap_slice_interval_ms": 10_000,
    },
    "twap-limit": {
        "trigger_type": "twap",
        "order_type": "limit",
        "limit_price": "59950",
        "twap_duration_ms": 60_000,
        "twap_slice_interval_ms": 10_000,
    },
    "trailing-stop": {"trigger_type": "trailing_stop", "trailing_distance_bps": 100},
    "ladder": {
        "trigger_type": "ladder",
        "ladder_price_min": "58000",
        "ladder_price_max": "59000",
        "ladder_levels": 4,
    },
}


def _create(**kwargs: Any):
    fields: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "sell",
        "qty": "0.01",
        "quantity_scale": 8,
        "client_trigger_id": "tif-ticks",
    }
    fields.update(kwargs)
    return create_trigger_to_proto(**fields)


@pytest.mark.parametrize("strategy", list(STRATEGIES))
def test_poly_8758_gtd_is_refused_for_every_trigger_strategy(strategy: str) -> None:
    _create(**STRATEGIES[strategy])
    with pytest.raises(PolyesterValidationError, match="tif must be"):
        _create(**STRATEGIES[strategy], tif="gtd")


@pytest.mark.parametrize("ticks", [-5, 0])
def test_poly_8748_twap_market_refuses_nonpositive_slippage_ticks(ticks: int) -> None:
    with pytest.raises(PolyesterValidationError, match="max_slippage_ticks"):
        _create(**STRATEGIES["twap-market"], max_slippage_ticks=ticks)


def test_poly_8748_twap_market_sends_a_positive_tick_cap() -> None:
    proto = _create(**STRATEGIES["twap-market"], max_slippage_ticks=1)
    assert proto.trigger.twap.market_ioc.max_slippage_ticks == 1
    assert not _create(**STRATEGIES["twap-market"]).trigger.twap.market_ioc.HasField(
        "max_slippage_ticks"
    )
    with pytest.raises(PolyesterValidationError, match="at most one"):
        _create(**STRATEGIES["twap-market"], max_slippage_ticks=1, max_slippage_bps=1)
