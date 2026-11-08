"""Order and withdraw create helpers refuse an unknown keyword by name.

``test_public_typing.py`` proves mypy rejects these calls; this proves the
runtime does too, before anything is sent.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from polyester.catalogs import CatalogManager
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CreateOrderRequest
from polyester.services.orders import AsyncOrdersService
from polyester.services.withdraw import AsyncWithdrawService
from tests.unit.support import CaptureUnary


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


def _order(**extra: Any) -> dict[str, Any]:
    return {"symbol": "BTC-USDT", "side": "buy", "order_type": "market", "qty": "0.01", **extra}


@pytest.mark.asyncio
@pytest.mark.parametrize("helper", ["create", "preview_order"])
async def test_order_keyword_helpers_refuse_an_unknown_keyword(helper: str) -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch("polyester.services.orders.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match=r"argument\(s\): qyt"),
    ):
        await getattr(service, helper)(**_order(qyt="0.01"))
    assert capture.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("helper", ["create", "preview_order"])
async def test_order_keyword_helpers_refuse_request_and_keywords(helper: str) -> None:
    capture = CaptureUnary(orders_pb2.CreateOrderResponse(order_id=42))
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    request = CreateOrderRequest(symbol="BTC-USDT", side="buy", order_type="market", qty="1")
    with (
        patch("polyester.services.orders.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match="either request or keyword"),
    ):
        await getattr(service, helper)(request, qty="0.01")
    assert capture.calls == 0


@pytest.mark.asyncio
async def test_batch_create_refuses_an_unknown_item_key() -> None:
    capture = CaptureUnary(orders_pb2.BatchCreateOrdersResponse())
    service = AsyncOrdersService(MagicMock(), _catalogs(), None)
    with (
        patch("polyester.services.orders.unary_auth_decoded", capture),
        pytest.raises(PolyesterValidationError, match=r"argument\(s\): qyt"),
    ):
        await service.batch_create(items=[_order(qyt="0.01")])
    assert capture.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "helper,arguments",
    [
        ("create_api_key_to_funding", {}),
        (
            "create_api_key_to_external_chain",
            {"destination_chain_id": 1, "destination_address": "0x0"},
        ),
    ],
)
async def test_withdraw_create_helpers_refuse_an_unknown_keyword(
    helper: str, arguments: dict[str, Any]
) -> None:
    transport = MagicMock()
    service = AsyncWithdrawService(transport=transport, default_sub_account_id=None)
    with pytest.raises(TypeError, match="amout_scale"):
        await getattr(service, helper)(
            asset_id=1, quantity="1", idempotency_key="k", amout_scale=6, **arguments
        )
    transport.assert_not_called()
    transport.credentials.sign_payload.assert_not_called()

