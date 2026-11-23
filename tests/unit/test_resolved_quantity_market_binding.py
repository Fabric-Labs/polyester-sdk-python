"""An order write's resolved base quantity is bound to the order's market.

``orders.create``, ``orders.preview`` and each accepted ``orders.batch_create``
item report ``resolved_base_qty``. Their answers do not name the pair, so the
SDK binds the quantity to the market the order was sent to: the create value
equals the preview value for the same order, and ``compatible_with`` (the
check every order write runs on a typed quantity) refuses it for another
market. A batch over several pairs binds each item to its own market.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester import AsyncPolyester, Polyester, Quantity
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CreateOrderRequest
from polyester.types.money import QuantityDomain

ORDERS = "/orders.v1.OrdersService/"
TEST_KEY_ID = "ak_resolved_market"
TEST_PRIVATE_KEY = "11" * 32
PAIRS = {
    "pairs": [
        {
            "symbol": "BTC-USDT",
            "symbol_id": 1,
            "base_quantity_scale": 8,
            "quote_quantity_scale": 6,
        },
        {
            "symbol": "SOL-USDT",
            "symbol_id": 2,
            "base_quantity_scale": 4,
            "quote_quantity_scale": 6,
        },
    ]
}
BTC_QTY = 31_567  # 0.00031567 BTC at scale 8
SOL_QTY = 12_345  # 1.2345 SOL at scale 4


def _order(symbol: str, qty: str) -> CreateOrderRequest:
    return CreateOrderRequest(
        symbol=symbol,
        side="buy",
        order_type="limit",
        tif="gtc",
        qty=qty,
        price="100",
        post_only=True,
    )


BTC_ORDER = _order("BTC-USDT", "0.00031567")
SOL_ORDER = _order("SOL-USDT", "1.2345")

ANSWERS: dict[str, Message] = {
    "CreateOrder": orders_pb2.CreateOrderResponse(order_id=7, resolved_base_qty_scaled=BTC_QTY),
    "PreviewOrder": orders_pb2.PreviewOrderResponse(
        admissible=True,
        resolved_base_qty_scaled=BTC_QTY,
        evaluated_at=Timestamp(seconds=1_700_000_000),
    ),
    "BatchCreateOrders": orders_pb2.BatchCreateOrdersResponse(
        results=[
            orders_pb2.BatchCreateResultItem(
                accepted=orders_pb2.BatchCreateAccepted(
                    order_id=8, resolved_base_qty_scaled=BTC_QTY
                )
            ),
            orders_pb2.BatchCreateResultItem(
                accepted=orders_pb2.BatchCreateAccepted(
                    order_id=9, resolved_base_qty_scaled=SOL_QTY
                )
            ),
        ],
        accepted_count=2,
    ),
}

BTC = Quantity(
    scaled=BTC_QTY, scale=8, domain=QuantityDomain.ORDER_BASE, symbol="BTC-USDT", symbol_id=1
)
SOL = Quantity(
    scaled=SOL_QTY, scale=4, domain=QuantityDomain.ORDER_BASE, symbol="SOL-USDT", symbol_id=2
)


def _answer(request: Request) -> Response:
    rpc = request.path.removeprefix(ORDERS)
    return Response(ANSWERS[rpc].SerializeToString(), status=200, content_type="application/proto")


@pytest.fixture
def api_url(httpserver: HTTPServer) -> str:
    for rpc in ANSWERS:
        httpserver.expect_request(ORDERS + rpc, method="POST").respond_with_handler(_answer)
    return httpserver.url_for("").rstrip("/")


def _client_options(api_url: str) -> dict[str, Any]:
    return {
        "api_url": api_url,
        "api_key_id": TEST_KEY_ID,
        "api_private_key": TEST_PRIVATE_KEY,
        "hydrate_catalogs": False,
    }


Writes = tuple[Any, Any, Any]
"""``(create, preview, batch_create)`` answers for the BTC order (and SOL)."""


async def _async_writes(api_url: str) -> Writes:
    async with AsyncPolyester(**_client_options(api_url)) as client:
        client.catalogs.hydrate_spot_config(PAIRS)
        return (
            await client.orders.create(BTC_ORDER),
            await client.orders.preview(BTC_ORDER),
            await client.orders.batch_create(items=[BTC_ORDER, SOL_ORDER]),
        )


def _sync_writes(api_url: str) -> Writes:
    with Polyester(**_client_options(api_url)) as client:
        client.catalogs.hydrate_spot_config(PAIRS)
        return (
            client.orders.create(BTC_ORDER),
            client.orders.preview(BTC_ORDER),
            client.orders.batch_create(items=[BTC_ORDER, SOL_ORDER]),
        )


@pytest.fixture(params=["async", "sync"])
def writes(request: pytest.FixtureRequest, api_url: str) -> Iterator[Writes]:
    if request.param == "async":
        import asyncio

        yield asyncio.run(_async_writes(api_url))
    else:
        yield _sync_writes(api_url)


def test_create_and_preview_of_one_order_report_equal_quantities(writes: Writes) -> None:
    create, preview, _ = writes
    assert create.resolved_base_qty == BTC
    assert preview.resolved_base_qty == BTC
    assert create.resolved_base_qty == preview.resolved_base_qty


@pytest.mark.parametrize(
    ("check", "message"),
    [
        (lambda qty: qty.compatible_with(symbol="SOL-USDT"), "quantity symbol mismatch"),
        (lambda qty: qty.compatible_with(symbol_id=2), "quantity symbol_id mismatch"),
    ],
)
def test_create_quantity_is_refused_for_another_market(
    writes: Writes, check: Callable[[Quantity], None], message: str
) -> None:
    create, preview, batch = writes
    for qty in (create.resolved_base_qty, preview.resolved_base_qty):
        with pytest.raises(PolyesterValidationError, match=message):
            check(qty)
    with pytest.raises(PolyesterValidationError, match=message):
        check(batch.results[0].resolved_base_qty)
    # Its own market accepts it.
    create.resolved_base_qty.compatible_with(symbol="BTC-USDT", symbol_id=1, scale=8)


def test_mixed_symbol_batch_binds_each_item_to_its_own_market(writes: Writes) -> None:
    _, _, batch = writes
    assert [item.resolved_base_qty for item in batch.results] == [BTC, SOL]
    with pytest.raises(PolyesterValidationError, match="quantity symbol mismatch"):
        batch.results[1].resolved_base_qty.compatible_with(symbol="BTC-USDT")
