"""Public calls that ``mypy --strict`` must reject.

``tests/unit/test_public_typing.py`` type-checks this file; it is never run.
A statement whose first line ends in ``# E: <text>`` must get a mypy error
containing ``<text>``; every other statement must get none.
"""

from __future__ import annotations

from datetime import UTC, datetime

from polyester import AsyncPolyester, Polyester
from polyester.models import CreateOrderRequest, OrderId, PrivateOrdersEvent


def order() -> CreateOrderRequest:
    return CreateOrderRequest(symbol="BTC-USDT", side="buy", order_type="market", qty="0.01")


async def misspelt_keywords(client: AsyncPolyester) -> None:
    await client.orders.create(  # E: "qyt"
        symbol="BTC-USDT", side="buy", order_type="market", qyt="0.01"
    )
    await client.orders.preview(  # E: "qyt"
        symbol="BTC-USDT", side="buy", order_type="market", qyt="0.01"
    )
    await client.orders.batch_create(  # E: CreateOrderItem
        items=[{"symbol": "BTC-USDT", "side": "buy", "order_type": "market", "qyt": "0.01"}]
    )
    await client.orders.batch_create(items=[order()], allow_partial=False)  # E: "allow_partial"
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
    await client.orders.preview(order(), side="sell")  # E: overload
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


def sync_misspelt_keywords(client: Polyester) -> None:
    client.orders.create(  # E: "qyt"
        symbol="BTC-USDT", side="buy", order_type="market", qyt="0.01"
    )
    client.orders.list_open(sub_acount_id=42)  # E: "sub_acount_id"
    client.triggers.create(  # E: "trigger_prcie"
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="0.01",
        trigger_prcie="100",
    )
    client.withdraw.create_api_key_to_funding(  # E: "amout_scale"
        asset_id=1, quantity="1", idempotency_key="k", amout_scale=6
    )
    list(client.changelog.iter_posts(limt=5))  # E: "limt"
    client.balances.subscribe_sync(on_event=print, acount_id=42)  # E: "acount_id"
    client.orders.list_opne()  # E: "list_opne"
    Polyester(api_ky_id="k")  # E: "api_ky_id"


def _on_int(event: int) -> None:
    print(event)


def sync_wrong_types(client: Polyester) -> None:
    client.orders.list_open(sub_account_id=4.2)  # E: "float"
    client.orders.get(key=OrderId(7), limit="10")  # E: "limit"
    found: int = client.orders.get(key=OrderId(7))  # E: GetOrderResult
    client.orders.create(order(), qty="0.01")  # E: overload
    client.orders.subscribe_sync(on_event=_on_int)  # E: "on_event"
    client.orders.subscribe_sync(account_id=42)  # E: "on_event"
    Polyester(timeout="10")  # E: "timeout"
    client.sub_accounts.list_account_activity(api_key_id=34)  # E: "api_key_id"
    client.market_data.get_index_price_candles(symbol="BTC-USDT", start_time=0)  # E: "start_time"
    print(found, PrivateOrdersEvent)


async def statement_export_without_type(client: AsyncPolyester) -> None:
    # The type has no default: the server refuses a create without one.
    await client.statements.create_export(  # E: "type"
        start_time=datetime(2026, 1, 1, tzinfo=UTC),
        end_time=datetime(2026, 2, 1, tzinfo=UTC),
        idempotency_key="k",
    )
