import pytest

from polyester.models import UserTradesList


@pytest.mark.integration
@pytest.mark.smoke
async def test_user_trades_list_accepts_transfers_and_scope_fields(live_client):
    from polyester.errors import PolyesterApiError, is_not_found

    try:
        result = await live_client.trades.list(order_id=1, include_transfers=True, limit=5)
    except PolyesterApiError as exc:
        assert is_not_found(exc) or "not found" in str(exc).lower()
        return
    assert isinstance(result, UserTradesList)
    assert isinstance(result.transfers, list)
    assert isinstance(result.trades, list)


@pytest.mark.integration
@pytest.mark.smoke
async def test_user_trades_list(live_client, smoke_symbol):
    result = await live_client.trades.list(symbol=smoke_symbol, limit=5)
    assert isinstance(result, UserTradesList)
    assert isinstance(result.trades, list)
    for trade in result.trades:
        assert trade.symbol_id > 0
        assert trade.match_id
        assert trade.order_id
        assert trade.side in {"buy", "sell"}
        assert trade.price is not None and trade.price.ticks > 0
        assert trade.qty is not None and trade.qty.scaled > 0
        assert int(trade.ts_ns) > 0


@pytest.mark.integration
async def test_user_trades_list_order_and_lineage_filters(live_client, smoke_symbol):
    listed = await live_client.trades.list(symbol=smoke_symbol, limit=5, include_transfers=True)
    if not listed.trades:
        listed = await live_client.trades.list(limit=5, include_transfers=True)
    if not listed.trades:
        pytest.skip("no user trades on devnet; cannot exercise lineage filters")
    sample = listed.trades[0]
    assert sample.order_id
    by_order = await live_client.trades.list(
        order_id=sample.order_id,
        include_transfers=True,
        limit=5,
    )
    assert all(trade.order_id == sample.order_id for trade in by_order.trades)
    seen_tx: set[str] = set()
    for transfer in by_order.transfers:
        assert transfer.symbol_id > 0
        if transfer.tx_id:
            assert transfer.tx_id not in seen_tx
            seen_tx.add(transfer.tx_id)
    lineage_id = sample.lineage.id if sample.lineage is not None else None
    if lineage_id is None:
        return
    by_lineage = await live_client.trades.list(
        lineage_id=lineage_id,
        through_generation=sample.lineage.generation,
        include_transfers=True,
        limit=5,
    )
    for trade in by_lineage.trades:
        if trade.lineage is not None:
            assert trade.lineage.id == lineage_id
            assert trade.lineage.generation <= sample.lineage.generation
