"""Public calls that must type-check under ``mypy --strict``.

``tests/unit/test_public_typing.py`` type-checks this file; it is never run.
"""

from __future__ import annotations

from polyester import AsyncPolyester
from polyester.models import CreateOrderParams, CreateOrderRequest, OrderId

SUB = 42  # a numeric sub-account ID


def order(sub_account_id: str | int | None = None) -> CreateOrderRequest:
    return CreateOrderRequest(
        symbol="BTC-USDT",
        side="buy",
        order_type="market",
        qty="0.01",
        sub_account_id=sub_account_id,
    )


async def int_sub_account_ids(client: AsyncPolyester) -> None:
    await client.orders.list_open(sub_account_id=SUB)
    await client.orders.list_history(sub_account_id=SUB)
    await client.orders.get(key=OrderId(7), sub_account_id=SUB)
    await client.orders.cancel(key=OrderId(7), sub_account_id=SUB)
    await client.orders.cancel_all(dry_run=True, sub_account_id=SUB)
    await client.orders.cancel_all_after(timeout_sec=15, sub_account_id=SUB)
    await client.orders.stop_all_trading(sub_account_id=SUB)
    await client.orders.batch_cancel(items=[{"key": OrderId(7)}], sub_account_id=SUB)
    await client.orders.wait_for_order_trades_complete(key=OrderId(7), sub_account_id=SUB)
    await client.triggers.list(sub_account_id=SUB)
    await client.triggers.get(trigger_id=9, sub_account_id=SUB)
    await client.triggers.cancel(trigger_id=9, sub_account_id=SUB)
    await client.triggers.pause(trigger_id=9, sub_account_id=SUB)
    await client.trades.list(sub_account_id=SUB)
    await client.transfers.list(sub_account_id=SUB)
    await client.balances.list(sub_account_id=SUB)
    await client.balances.get_balance_history(sub_account_id=SUB)
    await client.balances.get_equity_history(sub_account_id=SUB)
    await client.fees.get_spot_fee_rates(sub_account_id=SUB)
    await client.rate_limits.get_trading_rate_limits(sub_account_id=SUB)
    await client.sub_accounts.get(sub_account_id=SUB)
    await client.sub_accounts.list_members(sub_account_id=SUB)
    await client.api_keys.list(sub_account_id=SUB)
    await client.address_book.list_entries(sub_account_id=SUB)
    await client.guard_signer.get_status(sub_account_id=SUB)
    await client.deposit.list_addresses(chain_id=1, sub_account_id=SUB)
    await client.orders.subscribe(account_id=SUB)


async def account_selectors(client: AsyncPolyester, scope: dict[str, str | int]) -> None:
    await client.orders.list_open(account={"subaccountId": SUB})
    await client.orders.list_open(account={"sub_account_id": "2"})
    await client.orders.list_open(account=scope)
    await client.orders.create(order(), account={"subaccountId": SUB})
    await client.orders.preview_order(order(), account=scope)


async def create_keywords(client: AsyncPolyester) -> None:
    await client.orders.create(
        symbol="BTC-USDT", side="buy", order_type="market", qty="0.01", sub_account_id=SUB
    )
    await client.orders.create(
        symbol_id=1,
        side="sell",
        order_type="limit",
        qty="0.01",
        price="100",
        client_order_id="c1",
        account="main",
    )
    await client.orders.preview_order(
        symbol="BTC-USDT", side="buy", order_type="market", qty="0.01", sub_account_id=SUB
    )
    await client.orders.create(order(SUB))
    await client.orders.preview_order(order("2"))
    params: CreateOrderParams = {
        "symbol": "BTC-USDT",
        "side": "buy",
        "order_type": "market",
        "qty": "0.01",
    }
    await client.orders.create(**params)
    await client.orders.batch_create(
        items=[
            {"symbol": "BTC-USDT", "side": "buy", "order_type": "limit", "qty": "1", "price": "1"},
            order(),
        ],
        sub_account_id=SUB,
    )
    await client.triggers.create(
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="0.01",
        trigger_price="100",
        sub_account_id=SUB,
    )
    await client.withdraw.create_api_key_to_funding(asset_id=1, quantity="1", idempotency_key="k")
