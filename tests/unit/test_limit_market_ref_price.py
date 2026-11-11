"""market_client_ref_price is a market-order field: the public contract carries
client_ref_price_ticks on MarketIoc only. A limit order with it is refused
before sending instead of having the reference price silently dropped."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary

REFUSAL = "market_client_ref_price is only valid for market orders"

RESPONSES: dict[str, Message] = {
    "create": orders_pb2.CreateOrderResponse(order_id=42),
    "preview": orders_pb2.PreviewOrderResponse(
        admissible=True, evaluated_at=Timestamp(seconds=1_700_000_000)
    ),
    "batch_create": orders_pb2.BatchCreateOrdersResponse(),
}


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


def _order(side: str, order_type: str, tif: str | None = None) -> dict[str, object]:
    order: dict[str, object] = {
        "symbol": "BTC-USDT",
        "side": side,
        "order_type": order_type,
        "qty": "0.01",
        "market_client_ref_price": "100",
    }
    if order_type == "limit":
        order["tif"] = tif
        order["price"] = "100"
        if tif == "gtd":
            expires = datetime.now(UTC) + timedelta(hours=1)
            order["expires_at"] = expires.strftime("%Y-%m-%dT%H:%M:%SZ")
    return order


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["create", "preview", "batch_create"])
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("tif", ["gtc", "gtd", "ioc", "fok"])
async def test_limit_order_refuses_market_client_ref_price_before_sending(
    method: str, side: str, tif: str
) -> None:
    capture = CaptureUnary(RESPONSES[method])
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    order = _order(side, "limit", tif)
    with (
        patch("polyester.services.orders.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match=REFUSAL),
    ):
        if method == "batch_create":
            await service.batch_create(items=[order])  # type: ignore[list-item]
        else:
            await getattr(service, method)(**order)
    assert capture.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("side", ["buy", "sell"])
async def test_market_order_sends_market_client_ref_price(side: str) -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        await service.create(**_order(side, "market"))  # type: ignore[arg-type]
    assert capture.calls == 1
    assert capture.request is not None
    assert capture.request.order.market_ioc.client_ref_price_ticks == 100_000_000_000
