import pytest

from polyester.models import OrdersList


@pytest.mark.integration
async def test_orders_list_open(live_client):
    result = await live_client.orders.list_open(limit=10)
    assert isinstance(result, OrdersList)
    assert isinstance(result.orders, list)
    for order in result.orders:
        assert order.order_id
        assert order.symbol_id > 0
        assert order.status


@pytest.mark.integration
async def test_orders_list_history(live_client, smoke_symbol):
    result = await live_client.orders.list_history(symbol=smoke_symbol, limit=5)
    assert isinstance(result, OrdersList)
    for order in result.orders:
        assert order.order_id
        assert order.symbol_id > 0
        assert order.status


@pytest.mark.integration
async def test_orders_cancel_all_dry_run(live_client, smoke_symbol):
    result = await live_client.orders.cancel_all(symbol=smoke_symbol, dry_run=True)
    assert result.status
    assert result.matched_orders >= 0
    assert result.submitted_cancels == 0
