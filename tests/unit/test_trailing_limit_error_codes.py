"""Client-side checks of an attached trailing stop's maximum raise the server's
codes, rule IDs and field paths (contract note 1812Z)."""

from __future__ import annotations

from typing import Any

import pytest

from polyester import Price
from polyester.codecs.orders import modify_order_to_proto, order_intent_from_request
from polyester.errors import PolyesterValidationError
from polyester.models import AttachedRisk, ClientOrderId, CreateOrderRequest
from polyester.models.trading import TrailingStop

CREATE_PATH = "order.attached_risk.trailing_stop.limit_price_ticks"


def _create(side: str, trailing_stop: dict[str, Any]) -> Any:
    return order_intent_from_request(
        CreateOrderRequest(
            symbol="BTC-USDT",
            symbol_id=1,
            side=side,
            order_type="limit",
            tif="gtc",
            qty="0.002",
            price="100",
            attached_risk={"trailing_stop": trailing_stop},
        ),
        quantity_scale=8,
    )


@pytest.mark.parametrize(
    ("side", "trailing_stop", "code", "rule_id"),
    [
        ("buy", {"trailing_distance_bps": 100, "limit_price": "105"},
         "ERROR_CODE_BAD_PRICE", "sell_unset"),
        ("sell", {"trailing_distance_bps": 100},
         "ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT", "buy_required"),
        ("sell", {"trailing_distance_bps": 100, "limit_price": "0"},
         "ERROR_CODE_TRIGGER_BUY_REQUIRES_LIMIT", "buy_required"),
        ("sell", {"trailing_distance_bps": 100, "activation_price": "106", "limit_price": "105"},
         "ERROR_CODE_BAD_PRICE", "buy_at_least_activation"),
    ],
    ids=["set-on-buy", "missing-on-sell", "zero-on-sell", "below-activation"],
)
def test_create_refusals_read_like_the_server(
    side: str, trailing_stop: dict[str, Any], code: str, rule_id: str
) -> None:
    with pytest.raises(PolyesterValidationError) as caught:
        _create(side, trailing_stop)

    assert caught.value.code == code
    [violation] = caught.value.violations
    assert (violation.field_path, violation.rule_id) == (CREATE_PATH, rule_id)


def test_modify_names_the_new_attached_risk_field() -> None:
    with pytest.raises(PolyesterValidationError) as caught:
        modify_order_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            key=ClientOrderId("cid-1"),
            new_attached_risk=AttachedRisk(
                trailing_stop=TrailingStop(
                    distance_bps=100,
                    activation_price=Price.from_ticks(106),
                    limit_price=Price.from_ticks(105),
                )
            ),
        )

    assert caught.value.code == "ERROR_CODE_BAD_PRICE"
    [violation] = caught.value.violations
    assert violation.field_path == "new_attached_risk.trailing_stop.limit_price_ticks"
    assert violation.rule_id == "buy_at_least_activation"


def test_sdk_only_validation_errors_carry_no_code() -> None:
    with pytest.raises(PolyesterValidationError) as caught:
        _create("sell", {})
    assert caught.value.code is None
    assert caught.value.violations == []
