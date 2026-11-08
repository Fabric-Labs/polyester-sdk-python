"""A replacement price or quantity finer than its tick or step is refused
with the code and field the server answers, as create and modify price are."""

from __future__ import annotations

from typing import Any

import pytest

from polyester.codecs.orders import batch_replace_orders_to_proto, modify_order_to_proto
from polyester.errors import PolyesterValidationError
from polyester.models import ClientOrderId

TICK = ("ERROR_CODE_PRICE_TICK_SIZE", "tick_size")
STEP = ("ERROR_CODE_QTY_STEP_SIZE", "step_size")


def _modify(**fields: Any) -> Any:
    return modify_order_to_proto(
        symbol="BTC-USDT",
        symbol_id=1,
        key=ClientOrderId("cid-1"),
        quantity_scale=8,
        **fields,
    )


def _replace(**fields: Any) -> Any:
    return batch_replace_orders_to_proto(
        items=[{"key": ClientOrderId("cid-1"), **fields}],
        symbol_id=1,
        symbol="BTC-USDT",
        quantity_scale=8,
    )


@pytest.mark.parametrize(
    ("encode", "fields", "expected", "field_path"),
    [
        (_modify, {"new_price": "70000.0000000001"}, TICK, "new_price_ticks"),
        (_modify, {"new_qty": "0.000000001"}, STEP, "new_qty_scaled"),
        (_replace, {"new_price": "70000.0000000001"}, TICK, "new_price_ticks"),
        (_replace, {"new_qty": "0.000000001"}, STEP, "new_qty_scaled"),
    ],
    ids=["modify_price", "modify_qty", "replace_price", "replace_qty"],
)
def test_off_grid_replacement_names_the_code_and_field(
    encode: Any, fields: dict[str, Any], expected: tuple[str, str], field_path: str
) -> None:
    code, rule_id = expected
    with pytest.raises(PolyesterValidationError) as caught:
        encode(**fields)
    assert caught.value.code == code
    assert [(v.field_path, v.rule_id) for v in caught.value.violations] == [(field_path, rule_id)]


@pytest.mark.parametrize("encode", [_modify, _replace], ids=["modify", "replace"])
def test_trailing_zeros_stay_on_grid(encode: Any) -> None:
    proto = encode(new_price="70000.000000000000", new_qty="0.0100000000")
    item = proto if hasattr(proto, "new_price_ticks") else proto.items[0]
    assert item.new_price_ticks == 70_000_000_000_000
    assert item.new_qty_scaled == 1_000_000
