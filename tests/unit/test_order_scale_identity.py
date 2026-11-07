"""Order writes check a scaled quantity against the market they resolve.

A padded symbol is not the catalog's market, so it is refused instead of
being resolved for the ID while the scale comes from somewhere else, and a
quantity scaled for another scale than the market's is refused, all before
transport. 1 BTC at scale 6 or 10 sent to a scale-8 market would mean 0.01
or 100 BTC.
"""

from __future__ import annotations

from typing import Any

import pytest

from polyester import AsyncPolyester, Quantity
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.models import CreateOrderRequest
from polyester.models.order_key import OrderId
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

REQUESTS: dict[str, Any] = {
    "CreateOrder": orders_pb2.CreateOrderRequest,
    "PreviewOrder": orders_pb2.PreviewOrderRequest,
    "BatchCreateOrders": orders_pb2.BatchCreateOrdersRequest,
    "ModifyOrder": orders_pb2.ModifyOrderRequest,
}


def one_btc(scale: int) -> Quantity:
    return Quantity.from_scaled(10**scale, scale=scale)


def order(symbol: str, scale: int) -> CreateOrderRequest:
    return CreateOrderRequest(
        symbol=symbol, side="buy", order_type="limit", price="100", qty=one_btc(scale)
    )


WRITES = {
    "create": lambda c, symbol, scale: c.orders.create(order(symbol, scale)),
    "preview_order": lambda c, symbol, scale: c.orders.preview_order(order(symbol, scale)),
    "batch_create": lambda c, symbol, scale: c.orders.batch_create(
        items=[order("BTC-USDT", 8), order(symbol, scale)]
    ),
    "modify": lambda c, symbol, scale: c.orders.modify(
        key=OrderId("9"), symbol=symbol, new_qty=one_btc(scale)
    ),
}


async def _run(call) -> tuple[BaseException | None, list[tuple[str, Any]]]:
    seen: list[tuple[str, Any]] = []

    async def handler(req: ParsedRequest):
        rpc = req.path.rsplit("/", 1)[-1]
        seen.append((rpc, REQUESTS[rpc].FromString(req.body)))
        return connect_proto_response(b"")

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
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
    error: BaseException | None = None
    try:
        await call(client)
    except Exception as exc:
        error = exc
    finally:
        await client.aclose()
        await http.aclose()
    return error, seen


@pytest.mark.asyncio
@pytest.mark.parametrize("write", sorted(WRITES))
@pytest.mark.parametrize(
    ("symbol", "scale"),
    [
        (symbol, scale)
        for symbol in (" BTC-USDT", "BTC-USDT ", " BTC-USDT ", "BTC-USDT")
        for scale in (6, 8, 10)
        if (symbol, scale) != ("BTC-USDT", 8)
    ],
)
async def test_order_writes_refuse_padded_symbols_and_foreign_scales(
    write: str, symbol: str, scale: int
) -> None:
    error, seen = await _run(lambda c: WRITES[write](c, symbol, scale))
    assert isinstance(error, PolyesterValidationError), error
    assert seen == []


@pytest.mark.asyncio
async def test_batch_create_sends_the_market_scale() -> None:
    _, seen = await _run(lambda c: WRITES["batch_create"](c, "BTC-USDT", 8))
    [(rpc, req)] = seen
    assert [(item.symbol_id, item.base_qty_scaled) for item in req.items] == [
        (1, 10**8),
        (1, 10**8),
    ]
