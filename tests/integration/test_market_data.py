from decimal import Decimal

import pytest

from polyester.models import CandlesResult, MarketTradesResult, SpotConfig


@pytest.mark.integration
async def test_get_spot_config(live_client):
    result = await live_client.market_data.get_spot_config()
    assert isinstance(result, SpotConfig)
    assert result.raw
    pairs = result.raw.get("pairs") or []
    assert pairs
    assert all(pair.get("symbol") for pair in pairs)


@pytest.mark.integration
async def test_get_trades(live_client, smoke_symbol):
    result = await live_client.market_data.get_trades(symbol=smoke_symbol, limit=5)
    assert isinstance(result, MarketTradesResult)
    assert isinstance(result.trades, list)
    for trade in result.trades:
        assert trade.symbol_id > 0
        assert trade.match_id
        assert trade.price is not None and trade.price.ticks > 0
        assert trade.qty is not None and trade.qty.scaled > 0
        assert int(trade.ts_ns) > 0


@pytest.mark.integration
async def test_get_candles(live_client, smoke_symbol):
    result = await live_client.market_data.get_candles(symbol=smoke_symbol, limit=5)
    assert isinstance(result, CandlesResult)
    assert result.symbol_id > 0
    assert result.timeframe
    for candle in result.candles:
        assert candle.ts_sec >= 0
        high = Decimal(candle.high or "0")
        low = Decimal(candle.low or "0")
        assert high >= low


@pytest.mark.integration
@pytest.mark.optional
async def test_get_current_candle(live_client, smoke_symbol, capabilities):
    if not capabilities["get_current_candle"]:
        pytest.skip("get_current_candle unavailable on devnet")
    candle = await live_client.market_data.get_current_candle(symbol=smoke_symbol)
    assert candle.ts_sec >= 0
    assert Decimal(candle.high or "0") >= Decimal(candle.low or "0")
