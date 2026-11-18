"""A string public ID is base58, read byte-wise as the server reads it.

There is no decimal reading of a string: a digit-only string is base58 too, and
a string with ``0`` (not in the base58 alphabet) is refused. Only the
canonical spelling, as ``format_id`` writes it, is accepted: a leading ``1`` is
a base58 zero, so ``"123"`` would name the same ID as ``"23"``, and is refused.
Nothing is trimmed: whitespace anywhere is refused. A typed ``int`` names the
ID it is.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from polyester.codecs.address_book import tag_ids_from_public
from polyester.codecs.orders import parse_optional_subaccount_id, set_order_key
from polyester.codecs.scalars import format_id, id_to_int, parse_account_id
from polyester.codecs.triggers import modify_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.models import OrderId

_REFUSED = ["100", "00023", "0", "10", " 23", "23 ", "\t23", "2 3", "23\n", "\n", " "]
_NON_CANONICAL = ["123", "1123", "12", "111111111112", "1z"]


@pytest.mark.parametrize("value", _REFUSED)
def test_a_string_id_that_is_not_base58_is_refused(value: str) -> None:
    with pytest.raises(PolyesterValidationError, match="order_id"):
        id_to_int(value, "order_id")


@pytest.mark.parametrize(("value", "expected"), [("23", 60), ("2", 1), ("z", 57)])
def test_a_digit_only_string_id_is_base58(value: str, expected: int) -> None:
    assert id_to_int(value, "order_id") == expected


@pytest.mark.parametrize("value", _NON_CANONICAL)
def test_a_string_id_not_in_canonical_form_is_refused(value: str) -> None:
    with pytest.raises(PolyesterValidationError, match="order_id.*canonical"):
        id_to_int(value, "order_id")
    with pytest.raises(PolyesterValidationError, match="sub_account_id.*canonical"):
        parse_account_id(value, "sub_account_id")
    with pytest.raises(PolyesterValidationError, match="canonical"):
        format_id(value)


def test_canonical_ids_round_trip() -> None:
    ids = [
        *range(1, 5000),
        *(1 << shift for shift in range(64)),
        *((1 << shift) - 1 for shift in range(1, 65)),
        *(58**power for power in range(1, 11)),
    ]
    for value in ids:
        text = format_id(value)
        assert id_to_int(text, "order_id") == value
        assert format_id(text) == text
        with pytest.raises(PolyesterValidationError):
            id_to_int("1" + text, "order_id")


@pytest.mark.parametrize("value", [100, 23, 2**64 - 1])
def test_a_typed_integer_id_names_that_id(value: int) -> None:
    assert id_to_int(value, "order_id") == value
    assert parse_account_id(value, "sub_account_id") == value
    assert id_to_int(format_id(value), "order_id") == value


def test_the_largest_base58_id_decodes_and_one_past_it_is_refused() -> None:
    largest = format_id(2**64 - 1)
    assert id_to_int(largest, "order_id") == 2**64 - 1
    with pytest.raises(PolyesterValidationError, match="order_id"):
        id_to_int(largest + "1", "order_id")


@pytest.mark.parametrize("value", ["100", " 23"])
def test_format_id_refuses_a_string_that_is_not_base58(value: str) -> None:
    with pytest.raises(PolyesterValidationError):
        format_id(value)


@pytest.mark.parametrize(
    "call",
    [
        lambda v: set_order_key(orders_read_pb2.GetOrderRequest(), OrderId(v), op="get"),
        lambda v: modify_trigger_to_proto(trigger_id=v, trailing_distance_ticks=1),
        lambda v: parse_optional_subaccount_id(v),
        lambda v: tag_ids_from_public([v]),
    ],
)
@pytest.mark.parametrize("value", ["100", "00023", " 23", "23 ", "123", "1123"])
def test_id_paths_refuse_a_string_that_is_not_base58(
    call: Callable[[Any], Any], value: str
) -> None:
    with pytest.raises(PolyesterValidationError):
        call(value)


def test_id_paths_take_typed_integers() -> None:
    request = orders_read_pb2.GetOrderRequest()
    set_order_key(request, OrderId(100), op="get")
    assert request.order_id == 100
    assert modify_trigger_to_proto(trigger_id=23, trailing_distance_ticks=1).trigger_id == 23
    assert parse_optional_subaccount_id(100) == 100
    assert tag_ids_from_public([23, "23"]) == [23, 60]
