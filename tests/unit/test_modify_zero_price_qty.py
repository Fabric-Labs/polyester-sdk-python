"""A zero or negative new price or quantity is refused in every form, never sent as 0."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polyester.codecs.orders import (
    batch_replace_item_to_proto,
    batch_replace_orders_to_proto,
    modify_order_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.models import BatchReplaceItem, ClientOrderId
from polyester.types.money import Price, Quantity

NON_POSITIVE = [0, 0.0, -1, "0", "0.00", "-1", " 0 ", Decimal("0"), Decimal("-0"), Decimal("-1")]


def _modify(**kwargs):
    return modify_order_to_proto(
        symbol="BTC-USDT", symbol_id=1, key=ClientOrderId("cid-1"), quantity_scale=6, **kwargs
    )


def _replace_item(**kwargs):
    return batch_replace_item_to_proto(
        {"key": ClientOrderId("cid-1"), **kwargs},
        quantity_scale=6,
        symbol="BTC-USDT",
        symbol_id=1,
    )


@pytest.mark.parametrize("value", [*NON_POSITIVE, Price.from_ticks(0)])
def test_modify_refuses_non_positive_new_price(value) -> None:
    with pytest.raises(PolyesterValidationError, match="new_price must be positive"):
        _modify(new_price=value)
    with pytest.raises(PolyesterValidationError, match="new_price must be positive"):
        _modify(new_price=value, new_qty="1")


@pytest.mark.parametrize("value", NON_POSITIVE)
def test_modify_refuses_non_positive_new_qty(value) -> None:
    with pytest.raises(PolyesterValidationError, match="new_qty must be positive"):
        _modify(new_qty=value)
    with pytest.raises(PolyesterValidationError, match="new_qty must be positive"):
        _modify(new_qty=value, new_price="1")


@pytest.mark.parametrize("value", [*NON_POSITIVE, Price.from_ticks(0)])
def test_batch_replace_refuses_non_positive_new_price(value) -> None:
    with pytest.raises(PolyesterValidationError, match="new_price must be positive"):
        _replace_item(new_price=value)
    with pytest.raises(PolyesterValidationError, match="new_price must be positive"):
        batch_replace_orders_to_proto(
            items=[BatchReplaceItem(key=ClientOrderId("cid-1"), new_price=value)],
            symbol_id=1,
            symbol="BTC-USDT",
            quantity_scale=6,
        )


@pytest.mark.parametrize("value", NON_POSITIVE)
def test_batch_replace_refuses_non_positive_new_qty(value) -> None:
    with pytest.raises(PolyesterValidationError, match="new_qty must be positive"):
        _replace_item(new_qty=value)


def test_positive_values_still_encode() -> None:
    proto = _modify(new_price="0.000000001", new_qty=Decimal("0.000001"))
    assert (proto.new_price_ticks, proto.new_qty_scaled) == (1, 1)
    proto = _modify(new_price=Price.from_ticks(5), new_qty=Quantity.from_scaled(7, scale=6))
    assert (proto.new_price_ticks, proto.new_qty_scaled) == (5, 7)
    item = _replace_item(new_price=Decimal("2"), new_qty="3")
    assert (item.new_price_ticks, item.new_qty_scaled) == (2_000_000_000, 3_000_000)


def test_unset_price_and_quantity_still_need_another_change() -> None:
    with pytest.raises(PolyesterValidationError, match="modify requires new_price"):
        _modify()
    with pytest.raises(PolyesterValidationError, match="each batch item requires new_price"):
        _replace_item()
