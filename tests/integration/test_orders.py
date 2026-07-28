import pytest

from polyester.models import ClientOrderId, OrderId, OrdersList


@pytest.mark.integration
@pytest.mark.smoke
async def test_orders_list_open(live_client):
    result = await live_client.orders.list_open(limit=10)
    assert isinstance(result, OrdersList)
    assert isinstance(result.orders, list)
    for order in result.orders:
        assert order.order_id
        assert order.symbol_id > 0
        assert order.status


@pytest.mark.integration
async def test_orders_get_round_trips_list_open(live_client):
    """When devnet has open orders, get must return the same order by id."""
    listed = await live_client.orders.list_open(limit=10)
    if not listed.orders:
        pytest.skip("no open orders on devnet; cannot round-trip orders.get")
    sample = listed.orders[0]
    by_order_id = await live_client.orders.get(key=OrderId(sample.order_id))
    assert by_order_id.order is not None
    assert by_order_id.order.order_id == sample.order_id
    assert by_order_id.order.symbol_id == sample.symbol_id
    if sample.client_order_id:
        by_client_id = await live_client.orders.get(key=ClientOrderId(sample.client_order_id))
        assert by_client_id.order is not None
        assert by_client_id.order.client_order_id == sample.client_order_id


@pytest.mark.integration
@pytest.mark.smoke
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
