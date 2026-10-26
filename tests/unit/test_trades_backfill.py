"""Public trades: gap-free backfill by trade ID, and the listing filters."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.models.market import TradeEpochEnd
from polyester.services.market_data import AsyncMarketDataService
from tests.unit.support import CaptureUnary

EPOCH_2_START = 2**40  # trade IDs of epoch 2 are greater than 2**40


def _service() -> AsyncMarketDataService:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    return AsyncMarketDataService(MagicMock(), catalogs)


@pytest.mark.asyncio
async def test_backfill_sends_after_trade_id_and_decodes_the_walk() -> None:
    capture = CaptureUnary(
        marketdata_pb2.GetTradesResponse(
            trades=[
                marketdata_pb2.MarketTrade(
                    symbol_id=1, match_id=41, price_ticks=83_589_000_000_000, qty_scaled=1
                ),
                marketdata_pb2.MarketTrade(
                    symbol_id=1,
                    match_id=EPOCH_2_START + 1,
                    price_ticks=83_590_000_000_000,
                    qty_scaled=2,
                ),
            ],
            complete_through_trade_id=EPOCH_2_START + 5,
            next_after_trade_id=EPOCH_2_START + 5,
            epoch_ends=[marketdata_pb2.TradeEpochEnd(epoch=1, last_trade_id=41)],
        )
    )
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await _service().get_trades(symbol="BTC-USDT", after_trade_id=40, limit=500)
    request = capture.request
    assert request.HasField("after_trade_id")
    assert request.after_trade_id == 40
    assert request.limit == 500
    assert [t.match_id for t in result.trades] == ["41", str(EPOCH_2_START + 1)]
    assert result.trades[0].price.format() == "83589"
    assert result.complete_through_trade_id == EPOCH_2_START + 5
    assert result.next_after_trade_id == EPOCH_2_START + 5
    assert result.epoch_ends == [TradeEpochEnd(epoch=1, last_trade_id=41)]
    assert result.next_page_token == ""


@pytest.mark.asyncio
async def test_backfill_from_the_first_trade_sends_zero() -> None:
    capture = CaptureUnary(marketdata_pb2.GetTradesResponse())
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await _service().get_trades(symbol="BTC-USDT", after_trade_id=0)
    assert capture.request.HasField("after_trade_id")
    assert capture.request.after_trade_id == 0
    assert result.trades == []


@pytest.mark.asyncio
async def test_listing_without_after_trade_id_leaves_it_unset() -> None:
    capture = CaptureUnary(marketdata_pb2.GetTradesResponse(next_page_token="cursor-2"))
    start = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
    end = datetime(2026, 10, 27, 12, 5, tzinfo=UTC)
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await _service().get_trades(
            symbol="BTC-USDT",
            start_time=start,
            end_time=end,
            side="sell",
            page_token="cursor-1",
        )
    request = capture.request
    assert not request.HasField("after_trade_id")
    assert request.start_time.ToDatetime(tzinfo=UTC) == start
    assert request.end_time.ToDatetime(tzinfo=UTC) == end
    assert request.side == marketdata_pb2.SELL
    assert request.page_token == "cursor-1"
    assert result.next_page_token == "cursor-2"


@pytest.mark.parametrize(
    "conflict",
    [
        {"start_time": datetime(2026, 10, 27, tzinfo=UTC)},
        {"end_time": datetime(2026, 10, 27, tzinfo=UTC)},
        {"side": "buy"},
        {"page_token": "cursor-1"},
    ],
    ids=["start_time", "end_time", "side", "page_token"],
)
@pytest.mark.asyncio
async def test_after_trade_id_rejects_listing_filters(conflict: dict[str, object]) -> None:
    capture = CaptureUnary(marketdata_pb2.GetTradesResponse())
    with (
        patch("polyester.services.market_data.unary_public_decoded", capture),
        pytest.raises(PolyesterValidationError, match="cannot be combined"),
    ):
        await _service().get_trades(symbol="BTC-USDT", after_trade_id=1, **conflict)  # type: ignore[arg-type]
    assert capture.calls == 0


@pytest.mark.parametrize("bad", [-1, 2**64, True, "5"])
@pytest.mark.asyncio
async def test_after_trade_id_must_be_a_uint64(bad: object) -> None:
    with pytest.raises(PolyesterValidationError, match="after_trade_id"):
        await _service().get_trades(symbol="BTC-USDT", after_trade_id=bad)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_side_must_be_buy_or_sell() -> None:
    with pytest.raises(PolyesterValidationError, match="side must be"):
        await _service().get_trades(symbol="BTC-USDT", side="both")
