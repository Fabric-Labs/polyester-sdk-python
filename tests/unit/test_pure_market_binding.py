"""Values the SDK reads are bound to their market, and that binding holds on
the ``polyester.pure`` path.

An order read binds its prices and quantities to the order's pair, and a
create's ``resolved_base_qty`` to the pair it was sent to. Fed back into a
write, the SDK and the pure builders accept a value of the same pair and build
the same request, and refuse one of another pair with the same message.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.codecs.decode.orders import OrderMarket, order_from_proto, order_mutation_from_proto
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.pure import polyester as pure
from tests.unit.pure_equivalence import (
    BASE_SCALE,
    MARKET,
    QUOTE_SCALE,
    SYMBOL,
    SYMBOL_ID,
    assert_same,
    pure_outcome,
    sdk_client,
    sdk_outcome,
)

OTHER = ("ETH-USDT", 8)


def _read(symbol: str, symbol_id: int) -> dict[str, Any]:
    """The bound values of one order read and one create answer for a pair."""
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=11,
            symbol_id=symbol_id,
            side=orders_pb2.SELL,
            orig_qty_scaled=40_000_000,
            leaves_qty_scaled=25_000_000,
            price_ticks=101_000_000_000,
            attached_risk=orders_read_pb2.AttachedRisk(
                take_profit=orders_read_pb2.AttachedRiskTakeProfit(
                    policy=orders_pb2.TakeProfitPolicy(trigger_price_ticks=90_000_000_000)
                )
            ),
        ),
        quantity_scale=BASE_SCALE,
        quote_quantity_scale=QUOTE_SCALE,
        symbol=symbol,
    )
    created = order_mutation_from_proto(
        orders_pb2.CreateOrderResponse(order_id=12, resolved_base_qty_scaled=30_000_000),
        market=OrderMarket(symbol, symbol_id, BASE_SCALE),
    )
    assert order.attached_risk is not None and order.attached_risk.take_profit is not None
    return {
        "price": order.price,
        "trigger_price": order.attached_risk.take_profit.trigger_price,
        "orig_qty": order.orig_qty,
        "leaves_qty": order.leaves_qty,
        "resolved_base_qty": created.resolved_base_qty,
    }


@pytest.fixture(scope="module")
async def client() -> AsyncIterator[AsyncPolyester]:
    async with sdk_client() as sdk:
        yield sdk


def _writes(
    values: dict[str, Any],
) -> list[
    tuple[
        str,
        Callable[[AsyncPolyester], Awaitable[Any]],
        Callable[[], Any],
        tuple[tuple[str, str], ...],
    ]
]:
    price, trigger = values["price"], values["trigger_price"]
    writes = []
    for name in ("orig_qty", "leaves_qty", "resolved_base_qty"):
        qty = values[name]
        order = dict(symbol=SYMBOL, side="buy", order_type="limit", qty=qty, price=price)
        writes += [
            (
                f"create-{name}",
                lambda c, a=order: c.orders.create(**a),
                lambda a=order: pure.orders.create(MARKET, **a),
                (),
            ),
            (
                f"modify-{name}",
                lambda c, q=qty: c.orders.modify(
                    key=pure_key_sdk(), symbol=SYMBOL, new_qty=q, new_price=price
                ),
                lambda q=qty: pure.orders.modify(
                    MARKET, key=pure.OrderId("2gX"), new_qty=q, new_price=price
                ),
                (("request_id", "mod-"),),
            ),
            (
                f"trigger-{name}",
                lambda c, q=qty: c.triggers.create(
                    symbol=SYMBOL,
                    trigger_type="stop_loss",
                    side="sell",
                    qty=q,
                    trigger_price=trigger,
                ),
                lambda q=qty: pure.triggers.create(
                    MARKET, trigger_type="stop_loss", side="sell", qty=q, trigger_price=trigger
                ),
                (("trigger.client_trigger_id", "trg-"),),
            ),
            (
                f"oco-{name}",
                lambda c, q=qty: c.triggers.create_oco(
                    symbol=SYMBOL,
                    side="sell",
                    qty=q,
                    take_profit={"trigger_price": price},
                    stop_loss={"trigger_price": trigger},
                ),
                lambda q=qty: pure.triggers.create_oco(
                    MARKET,
                    side="sell",
                    qty=q,
                    take_profit={"trigger_price": price},
                    stop_loss={"trigger_price": trigger},
                ),
                (("oco.client_list_id", "oco-"),),
            ),
        ]
    writes.append(
        (
            "trigger-modify",
            lambda c: c.triggers.modify(trigger_id="2gX", symbol=SYMBOL, trigger_price=trigger),
            lambda: pure.triggers.modify(MARKET, trigger_id="2gX", trigger_price=trigger),
            (),
        )
    )
    return writes


def pure_key_sdk() -> Any:
    from polyester.models.order_key import OrderId

    return OrderId("2gX")


@pytest.mark.parametrize("pair", [(SYMBOL, SYMBOL_ID), OTHER], ids=["same pair", "other pair"])
async def test_read_values_keep_their_market_through_the_builders(
    client: AsyncPolyester, pair: tuple[str, int]
) -> None:
    values = _read(*pair)
    assert values["orig_qty"].symbol == pair[0] and values["orig_qty"].symbol_id == pair[1]
    assert values["price"].symbol == pair[0]
    sent = refused = 0
    for name, sdk_call, pure_call, generated in _writes(values):
        sdk = await sdk_outcome(lambda call=sdk_call: call(client))
        built = pure_outcome(pure_call)
        assert_same(sdk, built, generated=generated)
        if sdk.error is None:
            sent += 1
        else:
            refused += 1
            assert "mismatch" in str(sdk.error), (name, sdk.error)
    if pair == OTHER:
        assert sent == 0
    else:
        assert refused == 0


def test_a_bound_value_from_the_market_spec_matches_a_read_one() -> None:
    market = pure.market(MARKET)
    read = _read(SYMBOL, SYMBOL_ID)
    assert market.qty("0.4").scaled == read["orig_qty"].scaled
    assert (market.qty("0.4").symbol, market.qty("0.4").symbol_id) == (SYMBOL, SYMBOL_ID)
    assert market.price("101").ticks == read["price"].ticks
    with pytest.raises(ValueError, match="quantity symbol mismatch"):
        market.qty(_read(*OTHER)["orig_qty"])
