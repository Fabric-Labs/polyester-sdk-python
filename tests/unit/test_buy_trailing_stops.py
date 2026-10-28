"""Standalone buy trailing stops carry their maximum price (Q9)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from polyester import Price
from polyester.catalogs import CatalogManager
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary


def _trailing(**overrides: object):
    kwargs: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "trailing_stop",
        "side": "buy",
        "qty": "0.01",
        "quantity_scale": 8,
        "trailing_distance_bps": 100,
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "limit_price",
    ["84000.5", Decimal("84000.5"), Price.from_ticks(84_000_500_000_000)],
    ids=["str", "decimal", "ticks"],
)
def test_buy_trailing_stop_sends_its_maximum_price(limit_price: object) -> None:
    proto = _trailing(limit_price=limit_price, activation_price="83000")
    trailing = proto.trigger.trailing_stop
    assert trailing.side == orders_pb2.BUY
    assert trailing.limit_price_ticks == 84_000_500_000_000
    assert trailing.activation_price_ticks == 83_000_000_000_000
    assert trailing.trailing_distance_bps == 100


def test_buy_trailing_stop_keeps_nine_decimals() -> None:
    proto = _trailing(limit_price="0.000000001")
    assert proto.trigger.trailing_stop.limit_price_ticks == 1
    with pytest.raises(PolyesterValidationError, match="at most 9 decimal places"):
        _trailing(limit_price="84000.0000000001")


def test_buy_trailing_stop_requires_a_maximum_price() -> None:
    with pytest.raises(PolyesterValidationError, match="side=buy requires limit_price"):
        _trailing()


def test_sell_trailing_stop_rejects_a_maximum_price() -> None:
    with pytest.raises(PolyesterValidationError, match="side=sell does not take limit_price"):
        _trailing(side="sell", limit_price="84000")


def test_sell_trailing_stop_leaves_the_maximum_price_unset() -> None:
    trailing = _trailing(side="sell", max_slippage_bps=25).trigger.trailing_stop
    assert trailing.side == orders_pb2.SELL
    assert trailing.limit_price_ticks == 0
    assert trailing.max_slippage_bps == 25


@pytest.mark.asyncio
async def test_triggers_create_sends_a_buy_trailing_stop() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=9))
    service = AsyncTriggersService(MagicMock(), catalogs, None)
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            trigger_type="trailing_stop",
            side="buy",
            qty="0.01",
            trailing_distance_ticks=500_000_000_000,
            limit_price="84000",
        )
    trailing = capture.request.trigger.trailing_stop
    assert trailing.side == orders_pb2.BUY
    assert trailing.limit_price_ticks == 84_000_000_000_000
    assert trailing.trailing_distance_ticks == 500_000_000_000
    assert capture.request.trigger.qty_scaled == 1_000_000


def test_buy_trailing_stop_read_exposes_side_maximum_and_trough() -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=9,
            symbol_id=1,
            status=triggers_pb2.STATUS_ARMED,
            qty_scaled=1_000_000,
            trailing_stop=triggers_pb2.TrailingStopTrigger(
                side=orders_pb2.BUY,
                trailing_distance_bps=100,
                limit_price_ticks=84_000_500_000_000,
            ),
            trailing=triggers_pb2.TrailingDetails(
                trailing_distance_bps=100,
                trough_price_ticks=82_750_000_000_000,
            ),
        )
    )
    assert trigger.trigger_type == "trailing_stop"
    assert trigger.side == "buy"
    assert trigger.order_type == "limit"
    assert trigger.time_in_force == "ioc"
    assert trigger.limit_price is not None
    assert trigger.limit_price.format() == "84000.5"
    assert trigger.details is not None and trigger.details.trailing is not None
    assert trigger.details.trailing.trough_price is not None
    assert trigger.details.trailing.trough_price.format() == "82750"


def test_sell_trailing_stop_read_stays_a_market_child() -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=9,
            symbol_id=1,
            trailing_stop=triggers_pb2.TrailingStopTrigger(
                side=orders_pb2.SELL, trailing_distance_bps=100
            ),
            trailing=triggers_pb2.TrailingDetails(peak_price_ticks=85_000_000_000_000),
        )
    )
    assert trigger.side == "sell"
    assert trigger.order_type == "market"
    assert trigger.limit_price is None
    assert trigger.details is not None and trigger.details.trailing is not None
    assert trigger.details.trailing.peak_price is not None
    assert trigger.details.trailing.peak_price.format() == "85000"
