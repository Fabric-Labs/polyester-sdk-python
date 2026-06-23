import pytest

from tests.e2e.helpers import (
    unique_client_order_id,
    usdt_funded_buy_limit_params,
    wait_for_no_open_order,
    wait_for_open_order,
)
from tests.helpers import (
    DevnetOrderNotIndexedError,
    batch_results_are_all_internal_error,
    devnet_order_read_index_skip_message,
    devnet_order_skip_message,
)


@pytest.mark.integration
@pytest.mark.funded
async def test_batch_create_and_cancel(
    live_client, trade_symbol, funded_enabled, require_trade_trading_balance
):
    price, qty = await usdt_funded_buy_limit_params(live_client, trade_symbol)
    cid1 = unique_client_order_id("b1")
    cid2 = unique_client_order_id("b2")

    created = await live_client.orders.batch_create(
        symbol=trade_symbol,
        items=[
            {
                "symbol": trade_symbol,
                "side": "buy",
                "order_type": "limit",
                "tif": "gtc",
                "qty": qty,
                "price": price,
                "post_only": True,
                "client_order_id": cid1,
            },
            {
                "symbol": trade_symbol,
                "side": "buy",
                "order_type": "limit",
                "tif": "gtc",
                "qty": qty,
                "price": price,
                "post_only": True,
                "client_order_id": cid2,
            },
        ],
    )
    if created.accepted_count == 0 and batch_results_are_all_internal_error(created.results):
        pytest.skip(devnet_order_skip_message())
    assert created.accepted_count == 2
    results_by_cid = {item.client_order_id: item for item in created.results}
    assert set(results_by_cid) == {cid1, cid2}
    assert results_by_cid[cid1].order_id
    assert results_by_cid[cid2].order_id
    assert not results_by_cid[cid1].code
    assert not results_by_cid[cid2].code

    try:
        await wait_for_open_order(live_client, cid1)
        await wait_for_open_order(live_client, cid2)
    except DevnetOrderNotIndexedError:
        pytest.skip(devnet_order_read_index_skip_message())

    symbol_id = live_client.catalogs.symbol_id_for_symbol(trade_symbol)
    try:
        cancelled = await live_client.orders.batch_cancel(
            items=[
                {"client_order_id": cid1, "symbol_id": symbol_id},
                {"client_order_id": cid2, "symbol_id": symbol_id},
            ],
        )
        assert cancelled.accepted_count == 2
        cancelled_by_cid = {item.client_order_id: item for item in cancelled.results}
        assert set(cancelled_by_cid) == {cid1, cid2}
        assert not cancelled_by_cid[cid1].code
        assert not cancelled_by_cid[cid2].code
        await wait_for_no_open_order(live_client, cid1)
        await wait_for_no_open_order(live_client, cid2)
    finally:
        await live_client.orders.cancel_all(symbol=trade_symbol, dry_run=False)
