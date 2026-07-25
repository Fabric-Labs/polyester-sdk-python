"""POLY-3549: catalog scale must not invent 8 for unhydrated symbols."""

from __future__ import annotations

import pytest

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import quantity_scale_for_symbol, resolve_quantity_scale
from polyester.errors import PolyesterValidationError
from polyester.types import Quantity, QuantityDomain


def test_empty_catalog_does_not_default_eth_usdt_to_scale_8() -> None:
    catalogs = CatalogManager()
    assert catalogs.base_quantity_scale_for_symbol("ETH-USDT") is None
    with pytest.raises(PolyesterValidationError, match="unavailable"):
        quantity_scale_for_symbol(catalogs, "ETH-USDT")


def test_hydrated_eth_usdt_uses_scale_6() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "ETH-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 6,
                }
            ]
        }
    )
    assert catalogs.base_quantity_scale_for_symbol("ETH-USDT") == 6
    assert quantity_scale_for_symbol(catalogs, "ETH-USDT") == 6


def test_resolve_quantity_scale_errors_when_catalog_missing_symbol() -> None:
    catalogs = CatalogManager()
    with pytest.raises(PolyesterValidationError, match="unavailable"):
        resolve_quantity_scale(catalogs, "ETH-USDT", "0.006")


def test_scaled_quantity_skips_catalog_lookup() -> None:
    catalogs = CatalogManager()
    qty = Quantity.from_scaled(1000, scale=6, domain=QuantityDomain.ORDER_BASE)
    assert resolve_quantity_scale(catalogs, "ETH-USDT", qty) == 6
