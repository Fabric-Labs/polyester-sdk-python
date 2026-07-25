"""Regression: decimal qty must not silently fall back to scale 8."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polyester.codecs.orders import (
    batch_create_orders_to_proto,
    batch_modify_orders_to_proto,
    modify_order_to_proto,
    quantity_scale_for_symbol,
    resolve_quantity_scale,
)
from polyester.codecs.triggers import quantity_scale_for_symbol as trigger_quantity_scale
from polyester.errors import PolyesterValidationError
from polyester.types.money import Quantity


def test_quantity_scale_for_symbol_raises_without_symbol_or_catalogs() -> None:
    catalogs = MagicMock()
    catalogs.base_quantity_scale_for_symbol.return_value = 6

    with pytest.raises(PolyesterValidationError, match="symbol"):
        quantity_scale_for_symbol(None, "BTC-USD")
    with pytest.raises(PolyesterValidationError, match="symbol"):
        quantity_scale_for_symbol(catalogs, None)
    with pytest.raises(PolyesterValidationError, match="symbol"):
        quantity_scale_for_symbol(catalogs, "")
    with pytest.raises(PolyesterValidationError, match="symbol"):
        trigger_quantity_scale(None, None)


def test_quantity_scale_for_symbol_raises_when_catalog_scale_missing() -> None:
    catalogs = MagicMock()
    catalogs.base_quantity_scale_for_symbol.return_value = None
    with pytest.raises(PolyesterValidationError, match="unavailable"):
        quantity_scale_for_symbol(catalogs, "ETH-USDT")
    with pytest.raises(PolyesterValidationError, match="unavailable"):
        trigger_quantity_scale(catalogs, "ETH-USDT")


def test_quantity_scale_for_symbol_resolves_when_present() -> None:
    catalogs = MagicMock()
    catalogs.base_quantity_scale_for_symbol.return_value = 6
    assert quantity_scale_for_symbol(catalogs, "BTC-USD") == 6
    catalogs.base_quantity_scale_for_symbol.assert_called_once_with("BTC-USD")


def test_resolve_quantity_scale_raises_for_decimal_qty_without_catalog() -> None:
    with pytest.raises(PolyesterValidationError, match="symbol"):
        resolve_quantity_scale(None, "BTC-USD", "0.1")
    with pytest.raises(PolyesterValidationError, match="symbol"):
        resolve_quantity_scale(MagicMock(), None, "0.1")


def test_resolve_quantity_scale_allows_scaled_quantity_without_catalog() -> None:
    qty = Quantity.from_scaled(100_000, scale=6, symbol="BTC-USD")
    assert resolve_quantity_scale(None, None, qty) == 6


def test_batch_modify_decimal_qty_without_resolved_scale_raises() -> None:
    with pytest.raises(PolyesterValidationError, match="symbol"):
        scale = resolve_quantity_scale(None, None, "0.25")
        batch_modify_orders_to_proto(
            items=[{"order_id": 10, "new_qty": "0.25"}],
            quantity_scale=scale,
        )


def test_batch_create_decimal_qty_without_resolved_scale_raises() -> None:
    with pytest.raises(PolyesterValidationError, match="symbol"):
        scale = resolve_quantity_scale(None, None, "0.1")
        batch_create_orders_to_proto(
            items=[
                {
                    "symbol": "BTC-USD",
                    "side": "buy",
                    "order_type": "limit",
                    "qty": "0.1",
                    "price": "100",
                }
            ],
            quantity_scale=scale,
        )


def test_modify_decimal_qty_without_resolved_scale_raises() -> None:
    with pytest.raises(PolyesterValidationError, match="symbol"):
        scale = resolve_quantity_scale(None, "BTC-USD", "0.5")
        modify_order_to_proto(
            symbol="BTC-USD",
            order_id=1,
            new_qty="0.5",
            quantity_scale=scale,
        )
