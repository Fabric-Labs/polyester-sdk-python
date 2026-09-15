from __future__ import annotations

import asyncio
import contextlib

import pytest

from polyester.codecs.scalars import format_price_ticks, parse_price_ticks
from polyester.models import ClientOrderId, OrderId
from tests.e2e.helpers import (
    unique_client_order_id,
    usdt_funded_buy_limit_params,
    wait_for_no_open_order,
)
from tests.helpers import (
    DevnetOrderNotIndexedError,
    devnet_order_read_index_skip_message,
    devnet_order_skip_message,
    is_devnet_order_internal_error,
    pair_tick_size,
)


async def _wait_listed_open(client, client_order_id: str, *, timeout: float = 15):
    """Poll list_open only. Default GetOrder now loads execution history and can SQL-timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        listed = await client.orders.list_open(limit=50)
        for order in listed.orders:
            if order.client_order_id == client_order_id:
                return order
        await asyncio.sleep(0.5)
    raise DevnetOrderNotIndexedError(
        f"Open order {client_order_id} was not visible in list_open within {timeout}s"
    )


@pytest.mark.integration
@pytest.mark.mutation
@pytest.mark.funded
async def test_modify_order_advances_lineage(
    live_client,
    trade_symbol,
    mutation_enabled,
    funded_enabled,
    require_trade_trading_balance,
):
    """Create a post-only limit, replace it, and assert lineage stays stable."""
    price, qty = await usdt_funded_buy_limit_params(live_client, trade_symbol)
    original_cid = unique_client_order_id("lin")
    replacement_cid = unique_client_order_id("linr")
    new_price = price
    created_order_id = ""
    final_order_id = ""

    try:
        try:
            created = await live_client.orders.create(
                symbol=trade_symbol,
                side="buy",
                order_type="limit",
                tif="gtc",
                qty=qty,
                price=price,
                post_only=True,
                client_order_id=original_cid,
            )
        except Exception as exc:
            if is_devnet_order_internal_error(exc):
                pytest.skip(devnet_order_skip_message())
            raise
        assert created.order_id
        created_order_id = created.order_id

        try:
            opened = await _wait_listed_open(live_client, original_cid)
        except DevnetOrderNotIndexedError:
            pytest.skip(devnet_order_read_index_skip_message())
        first = await live_client.orders.get(
            key=ClientOrderId(original_cid),
            include_execution_history=False,
        )
        assert first.order is not None
        assert first.order.order_id == opened.order_id
        original_lineage_id = (
            first.order.lineage.id if first.order.lineage is not None else created.order_id
        )
        original_generation = (
            first.order.lineage.generation if first.order.lineage is not None else 1
        )
        assert original_generation >= 1
        spot = await live_client.market_data.get_spot_config()
        pair = next(
            (item for item in spot.raw.get("pairs") or [] if item.get("symbol") == trade_symbol),
            {},
        )
        step = parse_price_ticks(pair_tick_size(pair), "tick_size")
        current_ticks = (
            first.order.price.ticks
            if first.order.price is not None
            else parse_price_ticks(price, "price")
        )
        new_price = format_price_ticks(max(current_ticks - step, step))

        try:
            modified = await live_client.orders.modify(
                key=ClientOrderId(original_cid),
                symbol=trade_symbol,
                new_price=new_price,
                behavior="replace_only",
                new_client_order_id=replacement_cid,
            )
        except Exception as exc:
            if is_devnet_order_internal_error(exc):
                pytest.skip(devnet_order_skip_message())
            raise
        assert modified.action_taken
        assert modified.old_order_id == created.order_id
        assert modified.final_order_id
        final_order_id = modified.final_order_id

        try:
            replaced = await _wait_listed_open(live_client, replacement_cid)
        except DevnetOrderNotIndexedError:
            pytest.skip(devnet_order_read_index_skip_message())
        assert replaced.order_id == modified.final_order_id

        history = await live_client.orders.get(
            key=OrderId(modified.final_order_id),
            include_execution_history=False,
        )
        assert history.order is not None
        assert history.order.order_id == modified.final_order_id
        assert history.order.lineage is not None
        assert history.order.lineage.id == original_lineage_id
        if modified.final_order_id != created.order_id:
            assert history.order.lineage.generation == original_generation + 1
            assert modified.action_taken.lower() in {"replaced", "amended"}
        else:
            assert history.order.lineage.generation >= original_generation
    finally:
        for cid in (replacement_cid, original_cid):
            with contextlib.suppress(Exception):
                await live_client.orders.cancel(
                    key=ClientOrderId(cid),
                    symbol=trade_symbol,
                )
                await wait_for_no_open_order(live_client, cid, timeout=8)
        for order_id in (final_order_id, created_order_id):
            if not order_id:
                continue
            with contextlib.suppress(Exception):
                await live_client.orders.cancel(
                    key=OrderId(order_id),
                    symbol=trade_symbol,
                )
