"""Regression tests for base58/decimal ID ambiguity in format_id / id_to_int."""

from __future__ import annotations

import pytest

from polyester.codecs.scalars import format_id, id_to_int
from polyester.errors import PolyesterValidationError

# Known collisions: format_id(n) is all-digit and must round-trip via id_to_int.
# 0 (encoded "1") is no public ID: id_to_int refuses it.
_KNOWN_ALL_DIGIT_COLLISIONS = (1, 2, 3, 4, 5, 6, 7, 8, 58, 59, 116, 174)


def test_format_id_4_round_trips_through_id_to_int() -> None:
    encoded = format_id(4)
    assert encoded == "5"
    assert id_to_int(encoded) == 4


@pytest.mark.parametrize("value", _KNOWN_ALL_DIGIT_COLLISIONS)
def test_known_all_digit_format_id_round_trips(value: int) -> None:
    encoded = format_id(value)
    assert encoded.isdigit()
    assert id_to_int(encoded) == value


def test_format_id_id_to_int_round_trip_0_to_200() -> None:
    for value in range(1, 201):
        assert id_to_int(format_id(value)) == value


def test_a_digit_only_string_is_base58_never_decimal() -> None:
    # "10" has '0', which is not base58: refused, never read as decimal 10.
    assert not format_id(10).isdigit()
    with pytest.raises(PolyesterValidationError):
        id_to_int("10")
    # "123" would be base58 60, another spelling of format_id(60) == "23":
    # only the canonical spelling is accepted.
    assert id_to_int("23") == 60
    with pytest.raises(PolyesterValidationError, match="canonical"):
        id_to_int("123")
    # The integer names the ID it is.
    assert id_to_int(10) == 10
    assert id_to_int(123) == 123


def test_non_digit_ids_are_base58_only() -> None:
    assert id_to_int(format_id(123456)) == 123456
    assert id_to_int("A") == 9  # format_id(9) == "A"


def test_invalid_ids_still_error() -> None:
    with pytest.raises(PolyesterValidationError):
        id_to_int("not a valid id")
    with pytest.raises(PolyesterValidationError):
        id_to_int("")
    with pytest.raises(PolyesterValidationError):
        id_to_int(True)  # type: ignore[arg-type]
    with pytest.raises(PolyesterValidationError):
        id_to_int(-1)
