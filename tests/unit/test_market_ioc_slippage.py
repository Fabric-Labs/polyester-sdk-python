from unittest.mock import MagicMock, patch

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.codecs.orders import (
    batch_create_orders_to_proto,
    create_order_to_proto,
    normalize_create_order_request,
    preview_order_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary


def _market_kwargs(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "side": "buy",
        "order_type": "market",
        "qty": "0.01",
    }
    payload.update(overrides)
    return payload


def test_market_ioc_omits_slippage_when_unset() -> None:
    req = normalize_create_order_request(**_market_kwargs())
    proto = create_order_to_proto(req, quantity_scale=8)
    market = proto.order.market_ioc
    assert proto.order.WhichOneof("execution") == "market_ioc"
    assert market.WhichOneof("max_slippage") is None
    assert market.max_slippage_ticks == 0
    assert market.max_slippage_bps == 0


def test_market_ioc_serializes_max_slippage_bps() -> None:
    req = normalize_create_order_request(**_market_kwargs(max_slippage_bps=25))
    proto = create_order_to_proto(req, quantity_scale=8)
    market = proto.order.market_ioc
    assert market.WhichOneof("max_slippage") == "max_slippage_bps"
    assert market.max_slippage_bps == 25
    assert market.max_slippage_ticks == 0


def test_market_ioc_serializes_max_slippage_ticks() -> None:
    req = normalize_create_order_request(**_market_kwargs(max_slippage_ticks=10))
    proto = create_order_to_proto(req, quantity_scale=8)
    market = proto.order.market_ioc
    assert market.WhichOneof("max_slippage") == "max_slippage_ticks"
    assert market.max_slippage_ticks == 10
    assert market.max_slippage_bps == 0


@pytest.mark.parametrize("bps", [1, 10_000])
def test_market_ioc_accepts_bps_bounds(bps: int) -> None:
    req = normalize_create_order_request(**_market_kwargs(max_slippage_bps=bps))
    proto = create_order_to_proto(req, quantity_scale=8)
    assert proto.order.market_ioc.max_slippage_bps == bps


@pytest.mark.parametrize("bps", [0, 10_001])
def test_market_ioc_rejects_bps_out_of_range(bps: int) -> None:
    req = normalize_create_order_request(**_market_kwargs(max_slippage_bps=bps))
    with pytest.raises(PolyesterValidationError, match="max_slippage_bps.*1.*10000"):
        create_order_to_proto(req, quantity_scale=8)


def test_market_ioc_rejects_both_slippage_overrides() -> None:
    req = normalize_create_order_request(
        **_market_kwargs(max_slippage_bps=25, max_slippage_ticks=10)
    )
    with pytest.raises(
        PolyesterValidationError,
        match="at most one of max_slippage_ticks or max_slippage_bps",
    ):
        create_order_to_proto(req, quantity_scale=8)


def test_market_ioc_rejects_non_positive_ticks() -> None:
    req = normalize_create_order_request(**_market_kwargs(max_slippage_ticks=0))
    with pytest.raises(PolyesterValidationError, match="max_slippage_ticks must be positive"):
        create_order_to_proto(req, quantity_scale=8)


def test_limit_order_rejects_market_slippage() -> None:
    req = normalize_create_order_request(
        symbol="BTC-USDT",
        symbol_id=1,
        side="buy",
        order_type="limit",
        tif="gtc",
        qty="0.01",
        price="100",
        max_slippage_bps=25,
    )
    with pytest.raises(PolyesterValidationError, match="only valid for market orders"):
        create_order_to_proto(req, quantity_scale=8)


def test_normalizer_rejects_unsupported_create_arguments() -> None:
    with pytest.raises(
        PolyesterValidationError,
        match="unsupported create order argument\\(s\\): maxSlippageBps",
    ):
        normalize_create_order_request(**_market_kwargs(maxSlippageBps=25))


def test_preview_and_batch_create_preserve_market_slippage() -> None:
    req = normalize_create_order_request(**_market_kwargs(max_slippage_bps=25))
    preview = preview_order_to_proto(req, quantity_scale=8)
    assert preview.order.market_ioc.max_slippage_bps == 25

    batch = batch_create_orders_to_proto(
        items=[_market_kwargs(symbol_id=1, max_slippage_ticks=10)],
        quantity_scale=8,
    )
    assert batch.items[0].market_ioc.max_slippage_ticks == 10


def _catalogs() -> CatalogManager:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    return catalogs


@pytest.mark.asyncio
async def test_create_service_sends_market_slippage_on_wire() -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), "123")
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(
            symbol="BTC-USDT",
            side="buy",
            order_type="market",
            qty="0.01",
            max_slippage_bps=25,
        )
    assert capture.calls == 1
    market = capture.request.order.market_ioc
    assert capture.request.subaccount_id == 123
    assert market.WhichOneof("max_slippage") == "max_slippage_bps"
    assert market.max_slippage_bps == 25


@pytest.mark.asyncio
async def test_preview_service_sends_market_slippage_ticks_on_wire() -> None:
    capture = CaptureUnary(
        orders_pb2.PreviewOrderResponse(
            admissible=True,
            evaluated_at=Timestamp(seconds=1_700_000_000),
        )
    )
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.preview_order(
            symbol="BTC-USDT",
            side="buy",
            order_type="market",
            qty="0.01",
            max_slippage_ticks=10,
        )
    market = capture.request.order.market_ioc
    assert market.WhichOneof("max_slippage") == "max_slippage_ticks"
    assert market.max_slippage_ticks == 10
