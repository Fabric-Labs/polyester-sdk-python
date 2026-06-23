import pytest

from tests.e2e.helpers import (
    unique_client_order_id,
    usdt_funded_buy_limit_params,
    wait_for_no_open_order,
    wait_for_open_order,
)
from tests.helpers import (
    DevnetOrderNotIndexedError,
    devnet_order_read_index_skip_message,
    devnet_order_skip_message,
    is_devnet_order_internal_error,
)


@pytest.mark.integration
@pytest.mark.mutation
async def test_order_round_trip(
    live_client, trade_symbol, mutation_enabled, require_trade_trading_balance
):
    price, qty = await usdt_funded_buy_limit_params(live_client, trade_symbol)
    client_order_id = unique_client_order_id("e2e")

    try:
        created = await live_client.orders.create(
            symbol=trade_symbol,
            side="buy",
            order_type="limit",
            tif="gtc",
            qty=qty,
            price=price,
            post_only=True,
            client_order_id=client_order_id,
        )
    except Exception as exc:
        if is_devnet_order_internal_error(exc):
            pytest.skip(devnet_order_skip_message())
        raise
    assert created.status
    assert created.client_order_id == client_order_id
    assert created.order_id

    try:
        open_order = await wait_for_open_order(live_client, client_order_id)
    except DevnetOrderNotIndexedError:
        pytest.skip(devnet_order_read_index_skip_message())
    assert open_order.client_order_id == client_order_id
    assert open_order.order_id == created.order_id
    assert open_order.status

    order_detail = await live_client.orders.get(client_order_id=client_order_id)
    assert order_detail.order is not None
    assert order_detail.order.client_order_id == client_order_id
    assert order_detail.order.order_id == created.order_id

    try:
        cancelled = await live_client.orders.cancel(
            client_order_id=client_order_id,
            symbol=trade_symbol,
        )
        assert cancelled.status
        assert (
            cancelled.client_order_id == client_order_id
            or cancelled.order_id == created.order_id
        )
        await wait_for_no_open_order(live_client, client_order_id)
    finally:
        await live_client.orders.cancel_all(symbol=trade_symbol, dry_run=False)
