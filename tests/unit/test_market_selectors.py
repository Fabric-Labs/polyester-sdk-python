"""Market selectors are integers: a malformed one is refused before transport.

A string such as ``"12"`` used to be iterated into markets 1 and 2, and
``8.9`` or ``True`` cast to markets 8 and 1, so a fee read, a preview or a
cancel-all could act on markets the caller never named.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from decimal import Decimal
from typing import Any

import pytest

from polyester import AsyncPolyester
from polyester.errors import PolyesterError, PolyesterValidationError
from polyester.gen.fees.v1 import fees_pb2
from polyester.gen.marketoverview.v1 import marketoverview_pb2
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
    "GetSpotFeeRates": fees_pb2.GetSpotFeeRatesRequest,
    "GetSpotVolumeHistory": marketoverview_pb2.GetSpotVolumeHistoryRequest,
    "CreateOrder": orders_pb2.CreateOrderRequest,
    "PreviewOrder": orders_pb2.PreviewOrderRequest,
    "BatchCreateOrders": orders_pb2.BatchCreateOrdersRequest,
    "CancelAllOrders": orders_pb2.CancelAllOrdersRequest,
    "BatchCancelOrders": orders_pb2.BatchCancelOrdersRequest,
}

# Neither a market ID nor a list of them. A str or bytes is iterable, a
# float or bool casts to an int; each used to select other markets.
MALFORMED_IDS: list[Any] = [
    "12",
    b"12",
    "7",
    8.9,
    7.0,
    Decimal(7),
    True,
    False,
    2**32 + 7,
    -7,
]
MALFORMED_ID_LISTS: list[Any] = [
    "12",
    b"12",
    [8.9],
    [7.0],
    [True],
    ["7"],
    [None],
    [2**32 + 7],
    {7: "BTC-USDT"},
    7.5,
]


@asynccontextmanager
async def selector_client() -> AsyncIterator[tuple[AsyncPolyester, list[tuple[str, Any]]]]:
    seen: list[tuple[str, Any]] = []

    async def handler(req: ParsedRequest):
        rpc = req.path.rsplit("/", 1)[-1]
        if rpc not in REQUESTS:
            raise AssertionError(f"unexpected request: {req.path}")
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
                    "symbol_id": 7,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
                {
                    "symbol": "ETH-USDT",
                    "symbol_id": 8,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
                {
                    "symbol": "SOL-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                },
            ]
        }
    )
    try:
        yield client, seen
    finally:
        await client.aclose()
        await http.aclose()


def _wire(seen: list[tuple[str, Any]]) -> list[str]:
    return [f"{rpc} {{{' '.join(str(req).split())}}}" for rpc, req in seen]


async def _refused(call) -> None:
    async with selector_client() as (client, seen):
        try:
            await call(client)
        except PolyesterValidationError:
            pass
        except Exception as exc:
            raise AssertionError(f"raised {exc!r} after sending {_wire(seen)}") from exc
        else:
            raise AssertionError(f"not refused; sent {_wire(seen)}")
        assert seen == [], f"malformed selector reached transport: {_wire(seen)}"


async def _sent(call) -> list[tuple[str, Any]]:
    async with selector_client() as (client, seen):
        with suppress(PolyesterError):
            await call(client)
        return seen


def _order(symbol_id: Any) -> CreateOrderRequest:
    return CreateOrderRequest(
        side="buy",
        order_type="limit",
        price="100",
        qty="0.01",
        symbol_id=symbol_id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("symbol_id", MALFORMED_IDS + MALFORMED_ID_LISTS[2:], ids=repr)
async def test_fee_rates_refuse_malformed_market_ids(symbol_id: Any) -> None:
    await _refused(lambda c: c.fees.get_spot_fee_rates(symbol_id=symbol_id))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("symbol_id", "expected"),
    [(12, [12]), (0, [0]), ([12], [12]), ([1, 2], [1, 2]), ((7, 8), [7, 8]), ([], [])],
    ids=repr,
)
async def test_fee_rates_send_integer_market_ids(symbol_id: Any, expected: list[int]) -> None:
    seen = await _sent(lambda c: c.fees.get_spot_fee_rates(symbol_id=symbol_id))
    assert [(rpc, list(req.symbol_id)) for rpc, req in seen] == [("GetSpotFeeRates", expected)]


@pytest.mark.asyncio
@pytest.mark.parametrize("symbol_ids", MALFORMED_ID_LISTS + [[0]], ids=repr)
async def test_cancel_all_refuses_malformed_market_ids(symbol_ids: Any) -> None:
    await _refused(lambda c: c.orders.cancel_all(symbol_ids=symbol_ids, dry_run=True))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("symbol_ids", "expected"),
    [([12], [12]), ([7, 8, 7], [7, 8]), ((7,), [7]), ([], []), (None, [])],
    ids=repr,
)
async def test_cancel_all_sends_integer_market_ids(symbol_ids: Any, expected: list[int]) -> None:
    seen = await _sent(lambda c: c.orders.cancel_all(symbol_ids=symbol_ids, dry_run=True))
    assert [(rpc, list(req.symbol_ids)) for rpc, req in seen] == [("CancelAllOrders", expected)]


@pytest.mark.asyncio
@pytest.mark.parametrize("symbol_id", MALFORMED_IDS, ids=repr)
async def test_batch_cancel_refuses_malformed_item_market_id(symbol_id: Any) -> None:
    await _refused(
        lambda c: c.orders.batch_cancel(items=[{"key": OrderId("9"), "symbol_id": symbol_id}])
    )


@pytest.mark.asyncio
async def test_batch_cancel_sends_integer_item_market_id() -> None:
    seen = await _sent(
        lambda c: c.orders.batch_cancel(items=[{"key": OrderId("9"), "symbol_id": 7}])
    )
    assert [(rpc, req.items[0].symbol_id) for rpc, req in seen] == [("BatchCancelOrders", 7)]


ORDER_WRITES = {
    "preview": lambda c, order: c.orders.preview(order),
    "create": lambda c, order: c.orders.create(order),
    "batch_create": lambda c, order: c.orders.batch_create(items=[order]),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("write", sorted(ORDER_WRITES))
@pytest.mark.parametrize("symbol_id", [8.9, 7.0, True, "7", Decimal(7), 2**32 + 7, -7], ids=repr)
async def test_order_request_objects_refuse_malformed_market_ids(
    write: str, symbol_id: Any
) -> None:
    await _refused(lambda c: ORDER_WRITES[write](c, _order(symbol_id)))


@pytest.mark.asyncio
@pytest.mark.parametrize("write", sorted(ORDER_WRITES))
async def test_order_request_objects_send_integer_market_id(write: str) -> None:
    seen = await _sent(lambda c: ORDER_WRITES[write](c, _order(8)))
    [(rpc, req)] = seen
    intent = req.items[0] if rpc == "BatchCreateOrders" else req.order
    assert intent.symbol_id == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("write", ["preview", "create"])
@pytest.mark.parametrize("symbol_id", [8.9, True, "7"], ids=repr)
async def test_order_keywords_refuse_malformed_market_ids(write: str, symbol_id: Any) -> None:
    await _refused(
        lambda c: getattr(c.orders, write)(
            side="buy", order_type="limit", price="100", qty="0.01", symbol_id=symbol_id
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("symbol_ids", MALFORMED_ID_LISTS[:-1], ids=repr)
async def test_volume_history_refuses_malformed_market_ids(symbol_ids: Any) -> None:
    await _refused(lambda c: c.market_overview.get_spot_volume_history(symbol_ids=symbol_ids))


@pytest.mark.asyncio
async def test_volume_history_sends_integer_market_ids() -> None:
    seen = await _sent(lambda c: c.market_overview.get_spot_volume_history(symbol_ids=[12, 7]))
    assert [(rpc, list(req.symbol_id)) for rpc, req in seen] == [("GetSpotVolumeHistory", [12, 7])]
