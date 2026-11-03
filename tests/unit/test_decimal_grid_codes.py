"""Order decimals: zeros beyond a scale are the value they spell; a nonzero
digit beyond it is off the pair's step or tick and reads as the server's
``QTY_STEP_SIZE`` / ``PRICE_TICK_SIZE`` refusal of that value."""

from __future__ import annotations

from typing import Any

import pytest

from polyester.codecs.orders import (
    batch_create_orders_to_proto,
    modify_order_to_proto,
    normalize_create_order_request,
    order_intent_from_request,
)
from polyester.errors import PolyesterValidationError
from polyester.models.order_key import OrderId


def _intent(**overrides: Any):
    fields: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "buy",
        "order_type": "limit",
        "tif": "gtc",
        "qty": "0.0001",
        "price": "70000",
    }
    fields.update(overrides)
    return order_intent_from_request(normalize_create_order_request(**fields), quantity_scale=8)


def _refusal(exc: pytest.ExceptionInfo[PolyesterValidationError]) -> tuple[str | None, str, str]:
    [violation] = exc.value.violations
    return exc.value.code, violation.field_path, violation.rule_id


def test_zeros_beyond_the_scale_are_the_value_they_spell() -> None:
    intent = _intent(qty="0.000100000", price="70000.0000000000")
    assert intent.base_qty_scaled == 10_000
    assert intent.limit_gtc.price_ticks == 70_000 * 10**9
    risky = _intent(
        attached_risk={
            "take_profit": {"trigger_price": "80000.00000000000"},
            "stop_loss": {
                "trigger_price": "60000.0",
                "order_type": "limit",
                "limit_price": "59000.000000000000",
            },
        }
    )
    assert risky.attached_risk.stop_loss.child.limit_gtc.price_ticks == 59_000 * 10**9


def test_quantity_finer_than_the_base_scale_reads_qty_step_size() -> None:
    with pytest.raises(PolyesterValidationError) as exc:
        _intent(qty="0.000100001")
    assert _refusal(exc) == ("ERROR_CODE_QTY_STEP_SIZE", "order.base_qty_scaled", "step_size")


@pytest.mark.parametrize(
    ("tif", "path"),
    [
        ("gtc", "order.limit_gtc.price_ticks"),
        ("ioc", "order.limit_ioc.price_ticks"),
        ("fok", "order.limit_fok.price_ticks"),
    ],
)
def test_limit_price_finer_than_a_tick_reads_price_tick_size(tif: str, path: str) -> None:
    with pytest.raises(PolyesterValidationError) as exc:
        _intent(tif=tif, price="70000.0000000001")
    assert _refusal(exc) == ("ERROR_CODE_PRICE_TICK_SIZE", path, "tick_size")


@pytest.mark.parametrize(
    ("risk", "path"),
    [
        (
            {"take_profit": {"trigger_price": "80000.0000000001"}},
            "order.attached_risk.take_profit.trigger_price_ticks",
        ),
        (
            {
                "take_profit": {
                    "trigger_price": "80000",
                    "order_type": "limit",
                    "limit_price": "79000.0000000001",
                }
            },
            "order.attached_risk.take_profit.child.limit_gtc.price_ticks",
        ),
        (
            {"stop_loss": {"trigger_price": "60000.0000000001"}},
            "order.attached_risk.stop_loss.trigger_price_ticks",
        ),
        (
            {
                "stop_loss": {
                    "trigger_price": "60000",
                    "child": {"limit_gtc": {"price": "59000.0000000001"}},
                }
            },
            "order.attached_risk.stop_loss.child.limit_gtc.price_ticks",
        ),
        (
            {
                "trailing_stop": {
                    "trailing_distance_bps": 100,
                    "activation_price": "75000.0000000001",
                }
            },
            "order.attached_risk.trailing_stop.activation_price_ticks",
        ),
    ],
)
def test_attached_risk_price_finer_than_a_tick_reads_price_tick_size(
    risk: dict[str, Any], path: str
) -> None:
    with pytest.raises(PolyesterValidationError) as exc:
        _intent(attached_risk=risk)
    assert _refusal(exc) == ("ERROR_CODE_PRICE_TICK_SIZE", path, "tick_size")


def test_trailing_buy_back_limit_finer_than_a_tick_reads_price_tick_size() -> None:
    with pytest.raises(PolyesterValidationError) as exc:
        _intent(
            side="sell",
            attached_risk={
                "trailing_stop": {"trailing_distance_bps": 100, "limit_price": "71000.0000000001"}
            },
        )
    assert _refusal(exc) == (
        "ERROR_CODE_PRICE_TICK_SIZE",
        "order.attached_risk.trailing_stop.limit_price_ticks",
        "tick_size",
    )


def test_other_decimals_keep_a_plain_validation_error() -> None:
    # The server answers INVALID_ARGUMENT for these, not a step or tick code.
    with pytest.raises(PolyesterValidationError) as exc:
        order_intent_from_request(
            normalize_create_order_request(
                symbol="BTC-USDT",
                symbol_id=1,
                side="buy",
                order_type="market",
                max_quote_debit="50.0000001",
            ),
            quote_quantity_scale=6,
        )
    assert exc.value.code is None
    with pytest.raises(PolyesterValidationError) as exc:
        _intent(order_type="market", price=None, market_client_ref_price="70000.0000000001")
    assert exc.value.code is None


def test_batch_create_item_reads_the_same_code() -> None:
    with pytest.raises(PolyesterValidationError) as exc:
        batch_create_orders_to_proto(
            items=[
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "side": "buy",
                    "order_type": "limit",
                    "qty": "0.000100001",
                    "price": "70000",
                }
            ],
            quantity_scale=8,
        )
    assert _refusal(exc) == ("ERROR_CODE_QTY_STEP_SIZE", "order.base_qty_scaled", "step_size")


def test_modify_prices_finer_than_a_tick_read_price_tick_size() -> None:
    base: dict[str, Any] = {"symbol": "BTC-USDT", "symbol_id": 1, "key": OrderId("7")}
    with pytest.raises(PolyesterValidationError) as exc:
        modify_order_to_proto(**base, new_price="70000.0000000001")
    assert _refusal(exc) == ("ERROR_CODE_PRICE_TICK_SIZE", "new_price_ticks", "tick_size")
    with pytest.raises(PolyesterValidationError) as exc:
        modify_order_to_proto(
            **base, new_attached_risk={"take_profit": {"trigger_price": "80000.0000000001"}}
        )
    assert _refusal(exc) == (
        "ERROR_CODE_PRICE_TICK_SIZE",
        "new_attached_risk.take_profit.trigger_price_ticks",
        "tick_size",
    )
    proto = modify_order_to_proto(**base, new_price="70000.000000000000")
    assert proto.new_price_ticks == 70_000 * 10**9
