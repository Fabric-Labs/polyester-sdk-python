"""Trigger price source: reads report it and writes send it back unchanged."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.decode.orders import order_from_proto
from polyester.codecs.decode.triggers import trigger_from_proto
from polyester.codecs.orders import risk_policy_from_dict
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import ClientOrderId
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary

LAST = orders_pb2.LAST_PRICE
INDEX = orders_pb2.INDEX_PRICE


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return catalogs


def _order_read(take_profit_source: int, stop_source: int) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(
        order_id=1,
        symbol_id=1,
        attached_risk=orders_read_pb2.AttachedRisk(
            take_profit=orders_read_pb2.AttachedRiskTakeProfit(
                policy=orders_pb2.TakeProfitPolicy(
                    trigger_price_ticks=140_000_000_000,
                    trigger_price_source=take_profit_source,
                    child=orders_pb2.RiskExecution(market_ioc=orders_pb2.RiskMarketIoc()),
                )
            ),
            stop_loss=orders_read_pb2.AttachedRiskStopLoss(
                policy=orders_pb2.StopLossPolicy(
                    trigger_price_ticks=80_000_000_000,
                    trigger_price_source=stop_source,
                    child=orders_pb2.RiskExecution(market_ioc=orders_pb2.RiskMarketIoc()),
                )
            ),
        ),
    )


def _trailing_read(source: int) -> orders_read_pb2.Order:
    return orders_read_pb2.Order(
        order_id=1,
        symbol_id=1,
        attached_risk=orders_read_pb2.AttachedRisk(
            trailing_stop=orders_read_pb2.AttachedRiskTrailingStop(
                policy=orders_pb2.TrailingStopPolicy(
                    trailing_distance_bps=25, trigger_price_source=source
                )
            ),
        ),
    )


@pytest.mark.parametrize(("source", "label"), [(INDEX, "index"), (LAST, "last")])
@pytest.mark.asyncio
async def test_attached_legs_round_trip_into_create_and_modify(source: int, label: str) -> None:
    order = order_from_proto(_order_read(source, source))
    trailing = order_from_proto(_trailing_read(source))
    assert order.attached_risk is not None and trailing.attached_risk is not None
    assert order.attached_risk.take_profit is not None
    assert order.attached_risk.stop_loss is not None
    assert trailing.attached_risk.trailing_stop is not None
    assert order.attached_risk.take_profit.trigger_price_source == label
    assert order.attached_risk.stop_loss.trigger_price_source == label
    assert trailing.attached_risk.trailing_stop.trigger_price_source == label

    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    create = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=7))
    with patch("polyester.services.orders.unary_auth_decoded", create):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="100",
            attached_risk=order.attached_risk,
        )
    assert create.request is not None
    sent = create.request.order.attached_risk
    assert sent.take_profit.trigger_price_source == source
    assert sent.stop_loss.trigger_price_source == source

    modify = CaptureUnary(
        orders_pb2.ModifyOrderResponse(
            action_taken=orders_pb2.AMENDED, old_order_id=1, final_order_id=1
        )
    )
    with patch("polyester.services.orders.unary_auth_decoded", modify):
        await service.modify(
            key=ClientOrderId("bot-1"),
            symbol="BTC-USDT",
            new_attached_risk=trailing.attached_risk,
        )
    assert modify.request is not None
    assert modify.request.new_attached_risk.trailing_stop.trigger_price_source == source


def test_attached_legs_without_a_source_send_none() -> None:
    risk = risk_policy_from_dict(
        {
            "take_profit": {"trigger_price_ticks": 10},
            "trailing_stop": {"trailing_distance_bps": 25},
        }
    )
    assert risk is not None
    assert risk.take_profit.trigger_price_source == orders_pb2.TRIGGER_PRICE_SOURCE_UNSPECIFIED
    assert risk.trailing_stop.trigger_price_source == orders_pb2.TRIGGER_PRICE_SOURCE_UNSPECIFIED


def test_attached_trailing_stop_rejects_unknown_source() -> None:
    with pytest.raises(
        PolyesterValidationError,
        match="attached_risk.trailing_stop.trigger_price_source must be last, index, or mark",
    ):
        risk_policy_from_dict(
            {"trailing_stop": {"trailing_distance_bps": 25, "triggerPriceSource": "oracle"}}
        )


def test_stop_loss_trigger_read_round_trips_into_create() -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=1,
            symbol_id=1,
            stop_loss=triggers_pb2.ConditionalTrigger(
                trigger_price_ticks=80_000_000_000,
                side=orders_pb2.SELL,
                trigger_price_source=INDEX,
                child=triggers_pb2.ConditionalChildExecution(
                    market_ioc=triggers_pb2.TriggerMarketIoc()
                ),
            ),
        )
    )
    assert trigger.trigger_price_source == "index"
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type=trigger.trigger_type,
        side=trigger.side,
        qty="0.1",
        quantity_scale=8,
        trigger_price=trigger.trigger_price,
        trigger_price_source=trigger.trigger_price_source,
    )
    assert proto.trigger.stop_loss.trigger_price_source == INDEX


def test_trailing_stop_trigger_read_round_trips_into_create() -> None:
    trigger = trigger_from_proto(
        triggers_pb2.Trigger(
            trigger_id=2,
            symbol_id=1,
            trailing_stop=triggers_pb2.TrailingStopTrigger(
                side=orders_pb2.SELL, trailing_distance_bps=25, trigger_price_source=INDEX
            ),
            trailing=triggers_pb2.TrailingDetails(
                trailing_distance_bps=25, trigger_price_source=INDEX
            ),
        )
    )
    assert trigger.trigger_price_source == "index"
    assert trigger.details is not None and trigger.details.trailing is not None
    assert trigger.details.trailing.trigger_price_source == "index"
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type=trigger.trigger_type,
        side=trigger.side,
        qty="0.1",
        quantity_scale=8,
        trailing_distance_bps=trigger.details.trailing.trailing_distance_bps,
        trigger_price_source=trigger.trigger_price_source,
    )
    assert proto.trigger.trailing_stop.trigger_price_source == INDEX


def test_trigger_without_a_source_sends_none() -> None:
    proto = create_trigger_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        trigger_type="take_profit",
        side="sell",
        qty="0.1",
        quantity_scale=8,
        trigger_price="140",
    )
    assert proto.trigger.take_profit.trigger_price_source == (
        orders_pb2.TRIGGER_PRICE_SOURCE_UNSPECIFIED
    )


@pytest.mark.parametrize(
    ("trigger_type", "source", "match"),
    [
        ("stop_loss", "oracle", "trigger_price_source must be last, index, or mark"),
        ("twap", "index", "applies to stop_loss, take_profit and trailing_stop only"),
    ],
)
def test_trigger_price_source_rejections(trigger_type: str, source: str, match: str) -> None:
    with pytest.raises(PolyesterValidationError, match=match):
        create_trigger_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            trigger_type=trigger_type,
            side="sell",
            qty="0.1",
            quantity_scale=8,
            trigger_price="80",
            twap_duration_ms=60_000,
            twap_slice_interval_ms=10_000,
            trigger_price_source=source,
        )
