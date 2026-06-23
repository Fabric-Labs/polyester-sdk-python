import pytest

from polyester.models import UserTradesList


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
        assert int(trade.price_ticks) > 0
        assert int(trade.qty_scaled) > 0
        assert int(trade.ts_ns) > 0
