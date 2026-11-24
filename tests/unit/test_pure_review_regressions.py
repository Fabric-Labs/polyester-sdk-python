"""Regressions for cases the shared builders got wrong once.

An int subclass is read for its true value, as ``operator.index`` reads it, never
through an operator it overrides; ``triggers.modify`` takes ``symbol`` and
``symbol_id`` as the SDK does; ``triggers.cancel`` takes a market spec; a Price
or Quantity built directly around a float is refused; a pair served with a zero
scale (which proto-JSON leaves out) is read as such, and any other field a
GetSpotConfig pair carries is ignored; a decimal too long for ``int()`` is
refused as invalid.
"""

from __future__ import annotations

import operator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from google.protobuf import json_format
from google.protobuf.timestamp_pb2 import Timestamp
from pydantic_monty import Monty

from polyester import pure as pure_module
from polyester.codecs.scalars import exact_integer, market_id, tick_count
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models.order_key import OrderId
from polyester.pure import polyester as pure
from polyester.types.money import Price, Quantity
from tests.unit.pure_equivalence import (
    MARKET,
    WeirdInt,
    assert_same,
    pure_outcome,
    sdk_client,
    sdk_outcome,
)

SOURCE = Path(pure_module.__file__).read_text(encoding="utf-8")


async def test_an_int_subclass_cancels_the_trigger_it_is() -> None:
    async with sdk_client() as client:
        sdk = await sdk_outcome(lambda: client.triggers.cancel(trigger_id=WeirdInt(7)))
        assert sdk.request.trigger_id == 7
        assert_same(sdk, pure_outcome(lambda: pure.triggers.cancel(trigger_id=WeirdInt(7))))
        sdk = await sdk_outcome(lambda: client.orders.cancel(key=OrderId(WeirdInt(7))))
        assert sdk.request.order_id == 7
        built = pure_outcome(lambda: pure.orders.cancel(key=pure.OrderId(WeirdInt(7))))
        assert_same(sdk, built)


def test_int_subclasses_read_as_operator_index_reads_them() -> None:
    value = WeirdInt(7)
    assert (operator.neg(operator.neg(value)), int(value), operator.index(value)) == (9, 1, 7)
    results = [
        Price.from_ticks(value).ticks,
        Quantity.from_scaled(value).scaled,
        pure.Price.from_ticks(value).ticks,
        pure.Quantity.from_scaled(value).scaled,
        market_id(value, "market"),
        exact_integer(value, "n", min_value=0, max_value=100),
        tick_count(value, "ticks"),
    ]
    assert results == [7] * len(results)
    assert {type(result) for result in results} == {int}


@pytest.mark.parametrize("selector", [{"symbol": "BTC-USDT"}, {"symbol_id": 7}])
async def test_trigger_modify_takes_the_sdk_selectors(selector: dict[str, Any]) -> None:
    built = pure.triggers.modify(MARKET, trigger_id=42, trigger_price="1", **selector)
    assert built == {"triggerId": "42", "symbolId": 7, "triggerPriceTicks": "1000000000"}
    async with sdk_client() as client:
        sdk = await sdk_outcome(
            lambda: client.triggers.modify(trigger_id=42, trigger_price="1", **selector)
        )
    assert_same(sdk, pure_outcome(lambda: built))


async def test_trigger_modify_refuses_a_float_market_id() -> None:
    message = "triggers.modify symbol_id must be an integer market ID, not float"
    for market in (None, MARKET):
        with pytest.raises(ValueError) as refused:
            pure.triggers.modify(market, trigger_id=42, symbol_id=7.9, trigger_price="1")
        assert str(refused.value) == message
    async with sdk_client() as client:
        with pytest.raises(PolyesterValidationError, match=message):
            await client.triggers.modify(trigger_id=42, symbol_id=7.9, trigger_price="1")


def test_trigger_cancel_takes_a_market_spec() -> None:
    assert pure.triggers.cancel(MARKET, trigger_id=42) == {"triggerId": "42"}
    assert pure.triggers.cancel(trigger_id=42) == {"triggerId": "42"}
    with pytest.raises(ValueError, match="market symbol must be a non-empty string"):
        pure.triggers.cancel({"symbolId": 7}, trigger_id=42)


_FLOATS = [
    (
        "qty",
        lambda sdk: Quantity(1.5, 8) if sdk else pure.Quantity(1.5),
        "qty.scaled must be an int",
    ),
    ("price", lambda sdk: Price(1.5) if sdk else pure.Price(1.5), "price.ticks must be an int"),
    ("price", lambda sdk: Price(True) if sdk else pure.Price(True), "price.ticks must be an int"),
]


@pytest.mark.parametrize(("field", "typed", "message"), _FLOATS)
async def test_a_typed_float_is_refused_before_building(
    field: str, typed: Any, message: str
) -> None:
    """A Price or Quantity built directly around a float (or bool) is refused, by the
    builder and by the SDK, which used to fail inside protobuf instead."""
    args = {"side": "buy", "order_type": "limit", "qty": "1", "price": "1"}
    with pytest.raises(ValueError) as refused:
        pure.orders.create(MARKET, **{**args, field: typed(False)})
    assert str(refused.value) == message
    async with sdk_client() as client:
        sdk = await sdk_outcome(
            lambda: client.orders.create(symbol="BTC-USDT", **{**args, field: typed(True)})
        )
    assert isinstance(sdk.error, PolyesterValidationError)
    assert str(sdk.error) == message


def test_a_typed_float_is_refused_in_the_restricted_runtime() -> None:
    bot = """
spec = {"symbol": "BTC-USDT", "symbolId": 7, "baseQuantityScale": 8, "quoteQuantityScale": 6}
refused = []
for args in ({"qty": polyester.Quantity(1.5), "price": "1"},
             {"qty": "1", "price": polyester.Price(1.5)}):
  try:
    polyester.orders.create(spec, side="buy", order_type="limit", **args)
    refused.append("")
  except ValueError as exc:
    refused.append(str(exc))
refused
"""
    with Monty() as pool, pool.checkout() as session:
        session.feed_run(SOURCE)
        assert session.feed_run(bot) == ["qty.scaled must be an int", "price.ticks must be an int"]


def _pair(**fields: Any) -> dict[str, Any]:
    return json_format.MessageToDict(marketdata_pb2.PairConfig(**fields))


@pytest.mark.parametrize(
    ("fields", "args"),
    [
        (
            {
                "symbol": "WHOLE-USD",
                "symbol_id": 8,
                "base_quantity_scale": 0,
                "quote_quantity_scale": 2,
            },
            {"side": "buy", "order_type": "limit", "qty": "1", "price": "1"},
        ),
        (
            {
                "symbol": "CENT-USD",
                "symbol_id": 9,
                "base_quantity_scale": 2,
                "quote_quantity_scale": 0,
            },
            {"side": "buy", "order_type": "market", "max_quote_debit": "5"},
        ),
    ],
    ids=["zero base scale", "zero quote scale"],
)
async def test_a_zero_scale_pair_as_served(fields: dict[str, Any], args: dict[str, Any]) -> None:
    spec = _pair(**fields)
    # Proto-JSON leaves a zero scale out; the market reads it as zero.
    assert {"baseQuantityScale", "quoteQuantityScale"} - set(spec)
    market = pure.market(spec)
    assert (market.base_quantity_scale, market.quote_quantity_scale) == (
        fields["base_quantity_scale"],
        fields["quote_quantity_scale"],
    )
    async with sdk_client({"pairs": [fields]}) as client:
        sdk = await sdk_outcome(lambda: client.orders.create(symbol=fields["symbol"], **args))
    assert sdk.error is None
    assert_same(sdk, pure_outcome(lambda: pure.orders.create(spec, **args)))


def test_a_full_pair_config_is_accepted_and_its_other_fields_ignored() -> None:
    full = _pair(
        symbol="BTC-USDT",
        symbol_id=7,
        base_asset="BTC",
        quote_asset="USDT",
        tick_size="0.01",
        step_size="0.0001",
        min_notional_quote="5",
        min_qty_base="0.0001",
        allow_buy_fee_from_base=True,
        base_quantity_scale=8,
        quote_quantity_scale=6,
        listing_at=Timestamp(seconds=1_700_000_000),
        default_market_slippage_bps_buy=50,
        default_market_slippage_bps_sell=50,
        max_client_ref_drift_bps=100,
        reference_price_scale=9,
        max_limit_qty_base="100",
        max_market_qty_base="10",
        max_order_notional_quote="1000000",
        max_open_orders_per_pair=200,
        max_market_notional_quote="50000",
    )
    assert {"tickSize", "stepSize", "minQtyBase", "minNotionalQuote", "listingAt"} <= set(full)
    minimal = {"symbol": "BTC-USDT", "symbolId": 7, "baseQuantityScale": 8, "quoteQuantityScale": 6}
    args = {"side": "sell", "order_type": "limit", "qty": "0.12345678", "price": "65000.5"}
    assert pure.orders.create(full, **args) == pure.orders.create(minimal, **args)
    assert pure.market(full) == pure.market(minimal)


@pytest.mark.parametrize("field", ["qty", "price"])
def test_a_decimal_too_long_for_int_is_invalid(field: str) -> None:
    args = {"side": "buy", "order_type": "limit", "qty": "1", "price": "1", field: "1" * 5000}
    with pytest.raises(ValueError) as refused:
        pure.orders.create(MARKET, **args)
    assert str(refused.value) == f"{field} must be a valid decimal string"
    with pytest.raises(ValueError, match="market symbol_id 1111"):
        pure.market({**MARKET, "symbolId": "1" * 5000})
    assert pure.market({**MARKET, "symbolId": "7"}).symbol_id == 7
    assert Decimal("1")  # the decimal module stays the money type
