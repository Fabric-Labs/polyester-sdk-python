"""A refusal of a whole batch replace request, the SDK's own check before
sending included, names a batch item's field under its index (``items[i]``),
as the contract's ``FieldViolation.field_path`` says and as the Rust SDK names
it. A modify has no items and names the field alone."""

from __future__ import annotations

import pytest

from polyester import Price
from polyester.codecs.orders import batch_replace_orders_to_proto, modify_order_to_proto
from polyester.errors import PolyesterValidationError
from polyester.models import AttachedRisk, BatchReplaceItem, ClientOrderId
from polyester.models.trading import TrailingStop

_BELOW_ACTIVATION = AttachedRisk(
    trailing_stop=TrailingStop(
        distance_bps=100,
        activation_price=Price.from_ticks(106),
        limit_price=Price.from_ticks(105),
    )
)
_VALID = BatchReplaceItem(key=ClientOrderId("cid-0"), new_price=Price.from_ticks(100))


def _batch(second: BatchReplaceItem) -> None:
    batch_replace_orders_to_proto(
        items=[_VALID, second], symbol_id=1, symbol="BTC-USDT", quantity_scale=8
    )


def test_batch_replace_names_the_refused_items_index() -> None:
    with pytest.raises(PolyesterValidationError) as caught:
        _batch(BatchReplaceItem(key=ClientOrderId("cid-1"), new_attached_risk=_BELOW_ACTIVATION))
    assert caught.value.code == "ERROR_CODE_BAD_PRICE"
    [violation] = caught.value.violations
    assert (violation.field_path, violation.rule_id) == (
        "items[1].new_attached_risk.trailing_stop.limit_price_ticks",
        "buy_at_least_activation",
    )


def test_batch_replace_set_and_clear_names_the_items_index() -> None:
    with pytest.raises(PolyesterValidationError, match=r"items\[1\]\.new_attached_risk"):
        _batch(
            BatchReplaceItem(
                key=ClientOrderId("cid-1"),
                new_attached_risk=_BELOW_ACTIVATION,
                clear_attached_risk=True,
            )
        )


def test_modify_still_names_the_field_alone() -> None:
    with pytest.raises(PolyesterValidationError) as caught:
        modify_order_to_proto(
            symbol="BTC-USDT",
            symbol_id=1,
            key=ClientOrderId("cid-1"),
            new_attached_risk=_BELOW_ACTIVATION,
        )
    [violation] = caught.value.violations
    assert violation.field_path == "new_attached_risk.trailing_stop.limit_price_ticks"
