"""Public calls that ``mypy --strict`` must reject.

``tests/unit/test_public_typing.py`` type-checks this file; it is never run.
A statement whose first line ends in ``# E: <text>`` must get a mypy error
containing ``<text>``; every other statement must get none.
"""

from __future__ import annotations

from polyester import AsyncPolyester
from polyester.models import CreateOrderRequest


def order() -> CreateOrderRequest:
    return CreateOrderRequest(symbol="BTC-USDT", side="buy", order_type="market", qty="0.01")


async def misspelt_keywords(client: AsyncPolyester) -> None:
    await client.orders.create(  # E: "qyt"
        symbol="BTC-USDT", side="buy", order_type="market", qyt="0.01"
    )
    await client.orders.preview_order(  # E: "qyt"
        symbol="BTC-USDT", side="buy", order_type="market", qyt="0.01"
    )
    await client.orders.batch_create(  # E: CreateOrderItem
        items=[{"symbol": "BTC-USDT", "side": "buy", "order_type": "market", "qyt": "0.01"}]
    )
    await client.triggers.create(  # E: "trigger_prcie"
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="0.01",
        trigger_prcie="100",
    )
    await client.withdraw.create_api_key_to_funding(  # E: "amout_scale"
        asset_id=1, quantity="1", idempotency_key="k", amout_scale=6
    )
    await client.withdraw.create_api_key_to_external_chain(  # E: "destination_adress"
        asset_id=1,
        quantity="1",
        idempotency_key="k",
        destination_chain_id=1,
        destination_adress="0x0",
    )
    await client.withdraw.create_api_key_to_external(  # E: "destination_adress"
        asset_id=1,
        quantity="1",
        idempotency_key="k",
        destination_chain_id=1,
        destination_adress="0x0",
    )


async def wrong_shapes(client: AsyncPolyester) -> None:
    # No side: neither overload matches.
    await client.orders.create(symbol="BTC-USDT", order_type="market", qty="0.01")  # E: overload
    await client.orders.create(order(), qty="0.01")  # E: overload
    await client.orders.preview_order(order(), side="sell")  # E: overload
    await client.orders.batch_create(  # E: CreateOrderItem
        items=[
            {
                "symbol": "BTC-USDT",
                "side": "buy",
                "order_type": "market",
                "qty": "0.01",
                "sub_account_id": 42,
            }
        ]
    )
