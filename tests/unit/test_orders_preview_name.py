"""Order preview is ``orders.preview``, as in the TypeScript, Rust and Go SDKs.

The old ``preview_order`` name is removed, not kept as an alias, on
``AsyncPolyester`` and ``Polyester`` alike."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from polyester._sync_services import SyncOrdersService
from polyester.catalogs import CatalogManager
from polyester.gen.orders.v1 import orders_pb2
from polyester.services.orders import AsyncOrdersService
from tests.unit.support import CaptureUnary


def test_async_and_sync_orders_name_preview_and_not_preview_order() -> None:
    for cls in (AsyncOrdersService, SyncOrdersService):
        assert "preview" in vars(cls), cls
        assert not hasattr(cls, "preview_order"), cls


@pytest.mark.asyncio
async def test_preview_sends_a_preview_order_request() -> None:
    catalogs = CatalogManager()
    catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    capture = CaptureUnary(
        orders_pb2.PreviewOrderResponse(
            admissible=True,
            resolved_base_qty_scaled=10_000,
            evaluated_at=Timestamp(seconds=1_700_000_000),
        )
    )
    service = AsyncOrdersService(MagicMock(), catalogs, None)
    with patch("polyester.services.orders.unary_auth_decoded", capture):
        result = await service.preview(
            symbol="BTC-USDT", side="buy", order_type="market", qty="0.0001"
        )
    assert isinstance(capture.request, orders_pb2.PreviewOrderRequest)
    assert capture.request.order.base_qty_scaled == 10_000
    assert result.admissible is True
