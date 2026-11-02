"""An attached trailing stop on a selling order sends its buy-back limit price."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from polyester import Price
from polyester.codecs.orders import (
    batch_create_orders_to_proto,
    modify_order_to_proto,
    order_intent_from_request,
    risk_policy_from_dict,
)
from polyester.errors import PolyesterValidationError
from polyester.models import AttachedRisk, ClientOrderId, CreateOrderRequest
from polyester.models.trading import TrailingStop


def _intent(side: str, trailing_stop: Any) -> Any:
    risk = (
        AttachedRisk(trailing_stop=trailing_stop)
        if isinstance(trailing_stop, TrailingStop)
        else {"trailing_stop": trailing_stop}
    )
    return order_intent_from_request(
        CreateOrderRequest(
            symbol="BTC-USDT",
            symbol_id=1,
            side=side,
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="100",
            attached_risk=risk,
        ),
        quantity_scale=8,
    )


@pytest.mark.parametrize(
    "limit_price",
    ["105.5", Decimal("105.5"), Price.from_ticks(105_500_000_000)],
    ids=["str", "decimal", "ticks"],
)
def test_selling_order_sends_its_trailing_stop_buy_back_limit(limit_price: object) -> None:
    intent = _intent(
        "sell",
        {"trailing_distance_bps": 100, "activation_price": "95", "limit_price": limit_price},
    )
    trailing = intent.attached_risk.trailing_stop
    assert trailing.limit_price_ticks == 105_500_000_000
    assert trailing.activation_price_ticks == 95_000_000_000


def test_typed_trailing_stop_sends_its_buy_back_limit() -> None:
    intent = _intent(
        "sell",
        TrailingStop(distance_bps=100, limit_price=Price.from_ticks(105_000_000_000)),
    )
    assert intent.attached_risk.trailing_stop.limit_price_ticks == 105_000_000_000


def test_proto_json_limit_price_ticks_is_accepted() -> None:
    intent = _intent("sell", {"trailingDistanceBps": 100, "limitPriceTicks": 105_000_000_000})
    assert intent.attached_risk.trailing_stop.limit_price_ticks == 105_000_000_000


def test_selling_order_requires_the_buy_back_limit() -> None:
    with pytest.raises(
        PolyesterValidationError,
        match=r"attached_risk\.trailing_stop\.limit_price is required when the order sells",
    ):
        _intent("sell", {"trailing_distance_bps": 100})


def test_buying_order_rejects_a_limit() -> None:
    with pytest.raises(
        PolyesterValidationError,
        match=r"attached_risk\.trailing_stop\.limit_price must be unset when the order buys",
    ):
        _intent("buy", {"trailing_distance_bps": 100, "limit_price": "105"})


def test_buying_order_trailing_stop_is_unchanged() -> None:
    intent = _intent("buy", {"trailing_distance_bps": 100})
    assert intent.attached_risk.trailing_stop.limit_price_ticks == 0


def test_limit_below_activation_is_rejected() -> None:
    with pytest.raises(PolyesterValidationError, match="at least activation_price"):
        _intent(
            "sell",
            {"trailing_distance_bps": 100, "activation_price": "106", "limit_price": "105"},
        )


@pytest.mark.parametrize("limit", [Price.from_ticks(0), "0", "-1"], ids=["zero-ticks", "0", "-1"])
def test_non_positive_limit_is_rejected(limit: object) -> None:
    with pytest.raises(PolyesterValidationError):
        _intent("sell", {"trailing_distance_bps": 100, "limit_price": limit})


def test_limit_price_and_ticks_are_exclusive() -> None:
    with pytest.raises(PolyesterValidationError, match="limit_price or limit_price_ticks"):
        risk_policy_from_dict(
            {
                "trailing_stop": {
                    "trailing_distance_bps": 100,
                    "limit_price": "105",
                    "limit_price_ticks": 105_000_000_000,
                }
            }
        )


def test_batch_create_applies_the_side_rule_per_item() -> None:
    def item(side: str, trailing_stop: dict[str, Any]) -> dict[str, Any]:
        return {
            "symbol": "BTC-USDT",
            "symbol_id": 1,
            "side": side,
            "order_type": "limit",
            "tif": "gtc",
            "qty": "0.002",
            "price": "100",
            "attached_risk": {"trailing_stop": trailing_stop},
        }

    proto = batch_create_orders_to_proto(
        items=[item("sell", {"trailing_distance_bps": 100, "limit_price": "105"})],
        quantity_scale=8,
    )
    assert proto.items[0].attached_risk.trailing_stop.limit_price_ticks == 105_000_000_000
    with pytest.raises(PolyesterValidationError, match="required when the order sells"):
        batch_create_orders_to_proto(
            items=[item("sell", {"trailing_distance_bps": 100})], quantity_scale=8
        )


def test_modify_passes_the_limit_through() -> None:
    proto = modify_order_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        key=ClientOrderId("cid-1"),
        new_attached_risk=AttachedRisk(
            trailing_stop=TrailingStop(distance_bps=100, limit_price=Price.from_ticks(7))
        ),
    )
    assert proto.new_attached_risk.trailing_stop.limit_price_ticks == 7
