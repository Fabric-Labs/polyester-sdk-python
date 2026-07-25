from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polyester.errors import PolyesterValidationError
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
