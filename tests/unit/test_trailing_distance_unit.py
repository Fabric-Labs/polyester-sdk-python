"""Trailing distance in ticks is a price delta in 1e-9 quote units, sent as given.

A distance of 50 USDT on BTC-USDT is 50 * 10**9 = 50_000_000_000 ticks, and 0.5 USDT is
500_000_000: the same scale as every price tick. Each write path sends the tick count
unchanged, and trigger reads decode it back as that price distance.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from polyester.codecs.decode.triggers import _trigger_details
from polyester.codecs.orders import risk_policy_from_dict
from polyester.codecs.triggers import create_trigger_to_proto, modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.trading import AttachedRisk, TrailingStop

CASES = [
    (Decimal("50"), 50_000_000_000),
    (Decimal("0.5"), 500_000_000),
    (Decimal("0.000000001"), 1),
]


def _ticks(distance: Decimal) -> int:
    """The README's conversion: a quote-unit distance scaled by 10**9."""
    ticks = distance.scaleb(9)
    assert ticks == ticks.to_integral_value()
    return int(ticks)


@pytest.mark.parametrize(("distance", "ticks"), CASES)
def test_documented_conversion(distance: Decimal, ticks: int) -> None:
    assert _ticks(distance) == ticks


@pytest.mark.parametrize(("distance", "ticks"), CASES)
def test_standalone_trailing_stop_sends_the_tick_count(distance: Decimal, ticks: int) -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="trailing_stop",
        side="sell",
        qty="0.1",
        quantity_scale=8,
        trailing_distance_ticks=_ticks(distance),
    )
    assert proto.trigger.trailing_stop.trailing_distance_ticks == ticks


@pytest.mark.parametrize(("distance", "ticks"), CASES)
def test_trigger_modify_sends_the_tick_count(distance: Decimal, ticks: int) -> None:
    proto = modify_trigger_to_proto(trigger_id="7", trailing_distance_ticks=_ticks(distance))
    assert proto.trailing_distance_ticks == ticks


@pytest.mark.parametrize(("distance", "ticks"), CASES)
def test_attached_trailing_stop_sends_the_tick_count(distance: Decimal, ticks: int) -> None:
    from_dict = risk_policy_from_dict(
        {"trailing_stop": {"trailing_distance_ticks": _ticks(distance)}}, side="buy"
    )
    from_model = risk_policy_from_dict(
        AttachedRisk(trailing_stop=TrailingStop(distance_ticks=_ticks(distance))), side="buy"
    )
    assert from_dict is not None and from_model is not None
    assert from_dict.trailing_stop.trailing_distance_ticks == ticks
    assert from_model.trailing_stop.trailing_distance_ticks == ticks


def test_trigger_read_decodes_ticks_as_the_price_distance() -> None:
    msg = triggers_pb2.Trigger(
        trailing=triggers_pb2.TrailingDetails(trailing_distance_ticks=50_000_000_000)
    )
    details = _trigger_details(msg)
    assert details is not None and details.trailing is not None
    distance = details.trailing.trailing_distance
    assert distance is not None and distance.as_decimal() == Decimal("50")


@pytest.mark.parametrize("value", ["0.5", 0.5, Decimal("0.5"), True, 0, -1])
def test_a_decimal_distance_in_the_ticks_field_is_refused(value: object) -> None:
    # A decimal belongs in quote units only after conversion to ticks.
    with pytest.raises(PolyesterValidationError, match="trailing_distance_ticks"):
        create_trigger_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            trigger_type="trailing_stop",
            side="sell",
            qty="0.1",
            quantity_scale=8,
            trailing_distance_ticks=value,  # type: ignore[arg-type]
        )
