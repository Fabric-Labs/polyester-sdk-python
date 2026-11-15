"""A catalog scale that is not an exact integer is not a scale.

The getter reports it missing instead of truncating it, as the Go SDK does.
"""

from __future__ import annotations

from typing import Any

import pytest

from polyester.catalogs import CatalogManager


@pytest.mark.parametrize(
    ("value", "want"),
    [(2, 2), (0, 0), (2.0, 2), (1.9, None), (float(2**60), None), (-1, None), ("x", None)],
)
def test_inexact_optional_scale_reads_as_missing(value: Any, want: int | None) -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                    "reference_price_scale": value,
                }
            ]
        }
    )
    assert catalogs.reference_price_scale_for_symbol_id(1) == want
