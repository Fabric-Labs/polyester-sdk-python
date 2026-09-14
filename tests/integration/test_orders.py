import pytest

from polyester.models import ClientOrderId, OrderId, OrdersList


@pytest.mark.integration
@pytest.mark.smoke
async def test_orders_get_accepts_execution_history_flags(live_client):
    """New GetOrder fields must be accepted by the live API even with no orders."""
    from polyester.errors import PolyesterApiError, is_not_found

    try:
        result = await live_client.orders.get(
            key=OrderId(1),
            include_execution_history=False,
        )
    except PolyesterApiError as exc:
        assert is_not_found(exc) or "not found" in str(exc).lower()
    else:
        assert result.trades == []
        assert result.transfers == []

    try:
        result = await live_client.orders.get(
            key=OrderId(1),
            include_execution_history=True,
            limit=5,
        )
    except PolyesterApiError as exc:
        assert is_not_found(exc) or "not found" in str(exc).lower()
    else:
        assert isinstance(result.transfers, list)
        assert isinstance(result.next_page_token, str)


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
async def test_orders_get_state_only_and_execution_history(live_client):
    listed = await live_client.orders.list_history(limit=10)
    if not listed.orders:
        listed = await live_client.orders.list_open(limit=10)
    if not listed.orders:
        pytest.skip("no orders on devnet; cannot exercise lineage get")
    sample = listed.orders[0]
    state_only = await live_client.orders.get(
        key=OrderId(sample.order_id),
        include_execution_history=False,
    )
    assert state_only.order is not None
    assert state_only.order.order_id == sample.order_id
    assert state_only.trades == []
    assert state_only.transfers == []
    assert state_only.next_page_token == ""

    with_history = await live_client.orders.get(
        key=OrderId(sample.order_id),
        include_execution_history=True,
        limit=5,
    )
    assert with_history.order is not None
    assert with_history.order.order_id == sample.order_id
    if with_history.order.lineage is not None:
        assert with_history.order.lineage.id
        assert with_history.order.lineage.generation >= 1
    for trade in with_history.trades:
        assert trade.symbol_id > 0
        assert trade.match_id
        if trade.lineage is not None:
            assert trade.lineage.id
            assert trade.lineage.generation >= 1
    seen_tx: set[str] = set()
    for transfer in with_history.transfers:
        assert transfer.symbol_id > 0
        if transfer.tx_id:
            assert transfer.tx_id not in seen_tx
            seen_tx.add(transfer.tx_id)
    if with_history.next_page_token:
        page_two = await live_client.orders.get(
            key=OrderId(sample.order_id),
            include_execution_history=True,
            limit=5,
            page_token=with_history.next_page_token,
        )
        assert page_two.order is not None
        assert page_two.order.order_id == sample.order_id


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
@pytest.mark.asyncio(loop_scope="session")
async def test_orders_cancel_all_dry_run(live_client, smoke_symbol):
    result = await live_client.orders.cancel_all(symbol=smoke_symbol, dry_run=True)
    assert result.status
    assert result.matched_orders >= 0
    assert result.submitted_cancels == 0
