from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polyester.errors import PolyesterValidationError
from polyester.models import Candle, CandlesResult
from polyester.services.market_data import AsyncMarketDataService


@pytest.mark.parametrize("timeframe", ["1m", "MIN_1", "min1"])
@pytest.mark.asyncio
async def test_subscribe_candles_normalizes_channel_timeframe(timeframe: str) -> None:
    realtime = MagicMock()
    service = AsyncMarketDataService(
        transport=MagicMock(),
        catalogs=MagicMock(),
        realtime=realtime,
    )

    with patch(
        "polyester.services.market_data.subscribe_public_proto",
        new_callable=AsyncMock,
        return_value="subscription",
    ) as subscribe:
        result = await service.subscribe_candles(symbol_id=101, timeframe=timeframe)

    assert result == "subscription"
    assert subscribe.await_args.kwargs["channel"] == "public:spot:market:candles:1m:101:proto"


@pytest.mark.asyncio
async def test_subscribe_candles_rejects_unknown_timeframe() -> None:
    service = AsyncMarketDataService(
        transport=MagicMock(),
        catalogs=MagicMock(),
        realtime=MagicMock(),
    )
    with pytest.raises(PolyesterValidationError, match="Unknown candle timeframe"):
        await service.subscribe_candles(symbol_id=101, timeframe="not-a-tf")


@pytest.mark.asyncio
async def test_get_current_candle_returns_prepended_newest_row() -> None:
    service = AsyncMarketDataService(transport=MagicMock())
    service.get_candles = AsyncMock(  # type: ignore[method-assign]
        return_value=CandlesResult(
            candles=[Candle(ts_sec=200, is_closed=False), Candle(ts_sec=100, is_closed=True)]
        )
    )

    candle = await service.get_current_candle(symbol_id=101)

    assert candle is not None
    assert candle.ts_sec == 200


@pytest.mark.asyncio
async def test_get_current_candle_returns_none_when_empty() -> None:
    service = AsyncMarketDataService(transport=MagicMock())
    service.get_candles = AsyncMock(return_value=CandlesResult(candles=[]))  # type: ignore[method-assign]

    candle = await service.get_current_candle(symbol_id=101)

    assert candle is None
