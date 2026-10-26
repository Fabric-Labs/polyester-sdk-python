"""Q9 price acceptance fixtures.

Every trading price is Q9: one tick is 1e-9 quote units. The expected integers
below are written out by hand on purpose. They must never be derived from the
SDK's own scale constant, so a scale regression fails here instead of moving
the fixture with it.

Reference candle prices (per-pair ``reference_price_scale``), base quantities
(``base_quantity_scale``) and market-overview USD volumes (1e6) keep their own
scales and are pinned here too.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import PolyesterValidationError, Price
from polyester.catalogs import CatalogManager
from polyester.codecs import format_price_ticks, parse_price_ticks
from polyester.codecs.scalars import format_qty_scaled
from polyester.codecs.wire_decode import decode_market_trade_bytes
from polyester.gen.marketdata.v1 import marketdata_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
from polyester.gen.orderbook.v1 import orderbook_pb2
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import OrderId
from polyester.services.market_data import AsyncMarketDataService
from polyester.services.market_overview import AsyncMarketOverviewService
from polyester.services.orderbook import AsyncOrderbookService
from polyester.services.orders import AsyncOrdersService
from polyester.services.trades import AsyncTradesService
from polyester.services.triggers import AsyncTriggersService
from tests.unit.support import CaptureUnary

BTC_SYMBOL_ID = 1
ETH_SYMBOL_ID = 2
SOL_SYMBOL_ID = 3

# (decimal price, Q9 ticks), written out by hand.
ACCEPTANCE_PRICES = [
    ("2420", 2_420_000_000_000),
    ("83589", 83_589_000_000_000),
    ("185.25", 185_250_000_000),
    ("0.000000001", 1),
    ("0.002315", 2_315_000),
    ("9223372036.854775807", 9_223_372_036_854_775_807),
]


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": BTC_SYMBOL_ID,
                    "base_asset": "BTC",
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                    "reference_price_scale": 8,
                },
                {
                    "symbol": "ETH-USDT",
                    "symbol_id": ETH_SYMBOL_ID,
                    "base_asset": "ETH",
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
                {
                    "symbol": "SOL-USDT",
                    "symbol_id": SOL_SYMBOL_ID,
                    "base_asset": "SOL",
                    "base_quantity_scale": 6,
                    "quote_quantity_scale": 6,
                },
            ],
            "assets": [{"asset": "BTC", "market_data_volume_scale": 8}],
        }
    )
    return catalogs


# --- Scalar codec ---------------------------------------------------------


@pytest.mark.parametrize(("decimal", "ticks"), ACCEPTANCE_PRICES)
def test_decimal_price_encodes_to_q9_ticks(decimal: str, ticks: int) -> None:
    assert parse_price_ticks(decimal) == ticks
    assert parse_price_ticks(Decimal(decimal)) == ticks


@pytest.mark.parametrize(("decimal", "ticks"), ACCEPTANCE_PRICES)
def test_q9_ticks_decode_to_exact_decimal(decimal: str, ticks: int) -> None:
    assert format_price_ticks(ticks) == decimal
    price = Price.from_ticks(ticks)
    assert price.format() == decimal
    assert price.as_decimal() == Decimal(decimal)


def test_trailing_zeros_do_not_count_as_precision() -> None:
    assert parse_price_ticks("2420.000000000000") == 2_420_000_000_000
    assert parse_price_ticks("185.2500") == 185_250_000_000


@pytest.mark.parametrize("raw", ["0.0000000001", "2420.0000000001", "185.2500000001"])
def test_tenth_decimal_place_is_rejected_not_rounded(raw: str) -> None:
    with pytest.raises(PolyesterValidationError, match="at most 9 decimal places"):
        parse_price_ticks(raw)
    with pytest.raises(PolyesterValidationError, match="at most 9 decimal places"):
        parse_price_ticks(Decimal(raw))


def test_int64_overflow_is_rejected() -> None:
    # INT64_MAX + 1 tick.
    with pytest.raises(PolyesterValidationError, match="exceeds int64 range"):
        parse_price_ticks("9223372036.854775808")
    with pytest.raises(PolyesterValidationError, match="exceeds int64 range"):
        Price.from_ticks(9_223_372_036_854_775_808)


def test_float_prices_are_rejected() -> None:
    with pytest.raises(PolyesterValidationError):
        parse_price_ticks(2420.0)  # type: ignore[arg-type]


# --- Public encode paths --------------------------------------------------


@pytest.mark.asyncio
async def test_order_create_limit_price_is_q9_and_qty_keeps_base_scale() -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(
            symbol="ETH-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002315",
            price="2420",
        )
    intent = capture.request.order
    assert intent.symbol_id == ETH_SYMBOL_ID
    assert intent.limit_gtc.price_ticks == 2_420_000_000_000
    # ETH-USDT base_quantity_scale is 8: 0.002315 ETH is 231500.
    assert intent.base_qty_scaled == 231_500


@pytest.mark.asyncio
async def test_order_preview_limit_price_is_q9() -> None:
    capture = CaptureUnary(
        orders_pb2.PreviewOrderResponse(
            admissible=True,
            evaluated_at=Timestamp(seconds=1_700_000_000),
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.preview_order(
            symbol="ETH-USDT",
            side="buy",
            order_type="limit",
            tif="gtc",
            qty="0.002315",
            price="2420",
        )
    intent = capture.request.order
    assert intent.limit_gtc.price_ticks == 2_420_000_000_000
    assert intent.base_qty_scaled == 231_500


@pytest.mark.asyncio
async def test_order_preview_decodes_protected_price_bound_as_q9() -> None:
    capture = CaptureUnary(
        orders_pb2.PreviewOrderResponse(
            admissible=True,
            evaluated_at=Timestamp(seconds=1_700_000_000),
            protected_price_bound_ticks=83_589_000_000_000,
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        result = await service.preview_order(
            symbol="BTC-USDT",
            side="buy",
            order_type="market",
            qty="0.01",
        )
    assert result.protected_price_bound is not None
    assert result.protected_price_bound.format() == "83589"


@pytest.mark.asyncio
async def test_order_modify_new_price_is_q9() -> None:
    capture = CaptureUnary(
        orders_pb2.ModifyOrderResponse(
            action_taken=orders_pb2.AMENDED,
            old_order_id=7,
            final_order_id=7,
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.modify(
            key=OrderId("7"),
            symbol="SOL-USDT",
            new_price="185.25",
        )
    assert capture.request.new_price_ticks == 185_250_000_000


@pytest.mark.asyncio
async def test_trigger_create_trigger_and_limit_prices_are_q9() -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=9))
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            trigger_type="stop_loss",
            side="sell",
            qty="0.01",
            trigger_price="83589",
            order_type="limit",
            limit_price="83588.5",
        )
    stop = capture.request.trigger.stop_loss
    assert stop.trigger_price_ticks == 83_589_000_000_000
    assert stop.child.limit_gtc.price_ticks == 83_588_500_000_000
    # BTC-USDT base_quantity_scale is 8: 0.01 BTC is 1000000.
    assert capture.request.trigger.qty_scaled == 1_000_000


@pytest.mark.asyncio
async def test_trailing_trigger_activation_price_is_q9() -> None:
    capture = CaptureUnary(triggers_pb2.CreateTriggerResponse(trigger_id=10))
    service = AsyncTriggersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.triggers.unary_auth_decoded", capture):
        await service.create(
            symbol="ETH-USDT",
            trigger_type="trailing_stop",
            side="sell",
            qty="0.002315",
            trailing_distance_bps=50,
            activation_price="2420",
        )
    trailing = capture.request.trigger.trailing_stop
    assert trailing.activation_price_ticks == 2_420_000_000_000
    assert capture.request.trigger.qty_scaled == 231_500


# --- Public decode paths --------------------------------------------------


@pytest.mark.asyncio
async def test_order_read_price_decodes_from_q9() -> None:
    order = orders_read_pb2.Order(
        order_id=5,
        symbol_id=ETH_SYMBOL_ID,
        side=orders_pb2.BUY,
        status=orders_read_pb2.WORKING,
        order_type=orders_pb2.LIMIT,
        price_ticks=2_420_000_000_000,
        avg_price_ticks=2_419_990_000_000,
        orig_qty_scaled=231_500,
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)

    get_capture = CaptureUnary(orders_read_pb2.GetOrderResponse(order=order))
    with patch("polyester.services.orders.unary_auth_decoded", get_capture):
        result = await service.get(key=OrderId("5"))
    assert result.order is not None
    assert result.order.price is not None
    assert result.order.price.format() == "2420"
    assert result.order.avg_px is not None
    assert result.order.avg_px.format() == "2419.99"

    list_capture = CaptureUnary(orders_read_pb2.GetOpenOrdersResponse(orders=[order]))
    with patch("polyester.services.orders.unary_auth_decoded", list_capture):
        listed = await service.list_open()
    listed_price = listed.orders[0].price
    assert listed_price is not None
    assert listed_price.as_decimal() == Decimal("2420")


@pytest.mark.asyncio
async def test_user_trade_price_decodes_from_q9() -> None:
    capture = CaptureUnary(
        orders_read_pb2.GetUserTradesResponse(
            trades=[
                orders_read_pb2.UserTrade(
                    symbol_id=SOL_SYMBOL_ID,
                    match_id=11,
                    order_id=5,
                    side=orders_pb2.SELL,
                    price_ticks=185_250_000_000,
                    qty_scaled=1_500_000,
                )
            ]
        )
    )
    service = AsyncTradesService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.trades.unary_auth_decoded", capture):
        result = await service.list()
    trade = result.trades[0]
    assert trade.price is not None
    assert trade.price.format() == "185.25"


@pytest.mark.asyncio
async def test_public_trade_price_decodes_from_q9_and_qty_keeps_base_scale() -> None:
    capture = CaptureUnary(
        marketdata_pb2.GetTradesResponse(
            trades=[
                marketdata_pb2.MarketTrade(
                    symbol_id=BTC_SYMBOL_ID,
                    match_id=12,
                    is_buy=True,
                    price_ticks=83_589_000_000_000,
                    qty_scaled=2_500_000,
                )
            ]
        )
    )
    service = AsyncMarketDataService(MagicMock(), _catalogs())
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await service.get_trades(symbol="BTC-USDT")
    trade = result.trades[0]
    assert trade.price.format() == "83589"
    # BTC-USDT base_quantity_scale is 8: 2500000 is 0.025 BTC.
    assert trade.qty.scaled == 2_500_000
    assert trade.qty.format() == "0.025"


def test_realtime_public_trade_price_decodes_from_q9() -> None:
    payload = marketdata_pb2.MarketTrade(
        symbol_id=ETH_SYMBOL_ID,
        match_id=13,
        is_buy=False,
        price_ticks=2_420_000_000_000,
        qty_scaled=231_500,
    ).SerializeToString()
    trade = decode_market_trade_bytes(payload, quantity_scale=8)
    assert trade.price.format() == "2420"
    assert trade.qty.format() == "0.002315"


@pytest.mark.asyncio
async def test_orderbook_level_price_decodes_from_q9() -> None:
    capture = CaptureUnary(
        orderbook_pb2.GetOrderBookResponse(
            book_seq=1,
            bids=[orderbook_pb2.PriceLevel(price_ticks=185_250_000_000, qty_scaled=1_000_000)],
            asks=[orderbook_pb2.PriceLevel(price_ticks=185_260_000_000, qty_scaled=2_000_000)],
        )
    )
    service = AsyncOrderbookService(MagicMock(), catalogs=_catalogs())
    with patch("polyester.services.orderbook.unary_public_decoded", capture):
        book = await service.get(symbol="SOL-USDT", depth=50)
    assert book.bids[0].price.format() == "185.25"
    assert book.asks[0].price.format() == "185.26"
    # SOL-USDT base_quantity_scale is 6: 1000000 is 1 SOL.
    assert book.bids[0].qty.format() == "1"


@pytest.mark.asyncio
async def test_execution_candle_is_q9_and_reference_candle_keeps_reference_scale() -> None:
    capture = CaptureUnary(
        marketdata_pb2.GetCandlesResponse(
            symbol_id=BTC_SYMBOL_ID,
            timeframe=marketdata_pb2.MIN_1,
            candles=[
                marketdata_pb2.CandlePoint(
                    ts_sec=1_700_000_000,
                    open=83_589_000_000_000,
                    high=83_600_500_000_000,
                    low=83_500_000_000_000,
                    close=83_589_000_000_000,
                    volume=150_000_000,
                )
            ],
            reference_candles=[
                marketdata_pb2.CandlePoint(
                    ts_sec=1_700_000_000,
                    # reference_price_scale 8, not Q9.
                    open=8_358_900_000_000,
                    high=8_360_050_000_000,
                    low=8_350_000_000_000,
                    close=8_358_900_000_000,
                    volume=150_000_000,
                )
            ],
        )
    )
    service = AsyncMarketDataService(MagicMock(), _catalogs())
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await service.get_candles(symbol="BTC-USDT", include_reference=True)
    candle = result.candles[0]
    assert (candle.open, candle.high, candle.low, candle.close) == (
        "83589",
        "83600.5",
        "83500",
        "83589",
    )
    # BTC market_data_volume_scale is 8: 150000000 is 1.5 BTC.
    assert candle.volume == "1.5"
    reference = result.reference_candles[0]
    assert (reference.open, reference.high, reference.low, reference.close) == (
        "83589",
        "83600.5",
        "83500",
        "83589",
    )


@pytest.mark.asyncio
async def test_columnar_candles_are_q9_and_reference_keeps_reference_scale() -> None:
    capture = CaptureUnary(
        marketdata_pb2.GetCandlesColumnsResponse(
            symbol_id=BTC_SYMBOL_ID,
            timeframe=marketdata_pb2.MIN_1,
            ts_sec=[1_700_000_000],
            open=[83_589_000_000_000],
            high=[83_600_500_000_000],
            low=[83_500_000_000_000],
            close=[83_589_000_000_000],
            volume=[150_000_000],
            reference_ts_sec=[1_700_000_000],
            reference_open=[8_358_900_000_000],
            reference_high=[8_360_050_000_000],
            reference_low=[8_350_000_000_000],
            reference_close=[8_358_900_000_000],
            reference_volume=[150_000_000],
        )
    )
    service = AsyncMarketDataService(MagicMock(), _catalogs())
    with patch("polyester.services.market_data.unary_public_decoded", capture):
        result = await service.get_candles_columns(symbol="BTC-USDT", include_reference=True)
    candle = result.candles[0]
    assert (candle.open, candle.high, candle.low, candle.close) == (
        "83589",
        "83600.5",
        "83500",
        "83589",
    )
    reference = result.reference_candles[0]
    assert (reference.open, reference.close) == ("83589", "83589")


@pytest.mark.asyncio
async def test_market_overview_price_is_q9_and_usd_volume_stays_1e6() -> None:
    capture = CaptureUnary(
        marketoverview_pb2.ListMarketOverviewResponse(
            markets=[
                marketoverview_pb2.MarketOverview(
                    symbol_id=ETH_SYMBOL_ID,
                    last_price_ticks=2_420_000_000_000,
                    index_price_ticks=2_419_500_000_000,
                    # 1e6 USD scale: 1234567.89 USD.
                    volume_24h_usd_scaled=1_234_567_890_000,
                )
            ]
        )
    )
    service = AsyncMarketOverviewService(MagicMock(), catalogs=_catalogs())
    with patch("polyester.services.market_overview.unary_public_decoded", capture):
        result = await service.list()
    market = result.markets[0]
    assert market.last_price is not None
    assert market.last_price.format() == "2420"
    assert market.index_price is not None
    assert market.index_price.format() == "2419.5"
    # The USD volume is passed through unscaled; it is not a Q9 price.
    assert market.volume_24h_usd_scaled == "1234567890000"
    assert format_qty_scaled(int(market.volume_24h_usd_scaled), 6) == "1234567.89"
