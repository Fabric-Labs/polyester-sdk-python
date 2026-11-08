"""POLY-3746: MAX_PROTOCOL_SCALE rejects pathological scales (no huge zfill/10**scale)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polyester import MAX_PROTOCOL_SCALE, Quantity, format_ledger_u128
from polyester.codecs.scalars import (
    format_qty_scaled,
    format_scaled,
    parse_qty_scaled,
    validate_protocol_scale,
)
from polyester.errors import PolyesterValidationError

_BAD_SCALES = (37, 65534, 65535, 65536, 2**32 - 1)


def test_max_protocol_scale_constant() -> None:
    assert MAX_PROTOCOL_SCALE == 36


@pytest.mark.parametrize("scale", [0, 6, 18, 36])
def test_format_qty_scaled_accepts_protocol_scales(scale: int) -> None:
    assert format_qty_scaled(1, scale) is not None


@pytest.mark.parametrize("scale", _BAD_SCALES)
def test_format_qty_scaled_rejects_over_max(scale: int) -> None:
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        format_qty_scaled(1, scale)


@pytest.mark.parametrize("scale", _BAD_SCALES)
def test_format_ledger_u128_rejects_over_max(scale: int) -> None:
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        format_ledger_u128("1", scale=scale)


def test_format_ledger_u128_accepts_18_and_36() -> None:
    assert format_ledger_u128(str(10**18), scale=18) == "1"
    assert format_ledger_u128("1", scale=36).startswith("0.")


@pytest.mark.parametrize("scale", _BAD_SCALES)
def test_quantity_format_rejects_over_max(scale: int) -> None:
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        Quantity.from_scaled(1, scale=scale)
    qty = Quantity.from_scaled(1, scale=6)
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        qty.format(scale)


@pytest.mark.parametrize("scale", _BAD_SCALES)
def test_parse_qty_scaled_rejects_over_max(scale: int) -> None:
    with pytest.raises(PolyesterValidationError, match="maximum protocol scale"):
        parse_qty_scaled("1", scale)


def test_validate_protocol_scale_rejects_bool() -> None:
    with pytest.raises(PolyesterValidationError):
        validate_protocol_scale(True)  # type: ignore[arg-type]


@pytest.mark.parametrize("scale", [-1, -2, -36])
def test_format_scaled_refuses_a_negative_scale(scale: int) -> None:
    with pytest.raises(PolyesterValidationError, match="scale must be non-negative"):
        format_scaled(12345, scale)


@pytest.mark.parametrize(
    "value,scale,want", [(12345, 0, "12345"), (12345, 2, "123.45"), (-5, 45, "-5e-45")]
)
def test_format_scaled_formats_a_non_negative_scale(value: int, scale: int, want: str) -> None:
    assert Decimal(format_scaled(value, scale)) == Decimal(want)
