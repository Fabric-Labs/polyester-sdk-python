"""An empty default sub-account means no scope, on every public order path."""

from __future__ import annotations

import pytest
import pytest_asyncio

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_id
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.gen.orders.v1 import orders_read_pb2 as orders_read
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from polyester.models import OrderId
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

SUB_ACCOUNT = 77
PAIRS = {
    "pairs": [
        {"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8, "quote_quantity_scale": 6}
    ]
}
ANSWERS = {
    "/orders.v1.OrdersService/BatchReplaceOrders": (
        orders.BatchReplaceOrdersRequest,
        orders.BatchReplaceOrdersResponse(batch_request_id=42, status=1),
    ),
    "/orders.v1.OrdersService/ModifyOrder": (
        orders.ModifyOrderRequest,
        orders.ModifyOrderResponse(old_order_id=42, final_order_id=42, action_taken=1),
    ),
    "/orders.v1.OrdersReadService/GetBatchReplaceStatus": (
        orders_read.GetBatchReplaceStatusRequest,
        orders_read.GetBatchReplaceStatusResponse(
            batch_request_id=42,
            admission_status=orders.BATCH_REPLACE_ADMISSION_STATUS_ADMITTED,
        ),
    ),
    "/triggers.v1.TriggersService/CreateTrigger": (
        triggers.CreateTriggerRequest,
        triggers.CreateTriggerResponse(trigger_id=42),
    ),
}


def _scope(request: object) -> int | None:
    return request.subaccount_id if request.HasField("subaccount_id") else None  # type: ignore[attr-defined]


@pytest_asyncio.fixture(loop_scope="function")
async def serve():
    seen: list[object] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path not in ANSWERS:
            return HttpScript.not_found()
        request_type, response = ANSWERS[req.path]
        seen.append(request_type.FromString(req.body))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    clients: list[AsyncPolyester] = []

    def make(default: str | None) -> AsyncPolyester:
        creds = make_test_credentials()
        client = AsyncPolyester(
            api_url=http.base_url,
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            default_sub_account_id=default,
            hydrate_catalogs=False,
        )
        client.catalogs.hydrate_spot_config(PAIRS)
        clients.append(client)
        return client

    yield make, seen
    for client in clients:
        await client.aclose()
    await http.aclose()


async def _batch_replace(client: AsyncPolyester) -> None:
    await client.orders.batch_replace(
        symbol="BTC-USDT", items=[dict(key=OrderId(42), new_qty="1", new_price="100")]
    )


async def _modify(client: AsyncPolyester) -> None:
    await client.orders.modify(symbol="BTC-USDT", key=OrderId(42), new_qty="1", new_price="100")


async def _status(client: AsyncPolyester) -> None:
    await client.orders.get_batch_replace_status(batch_request_id="42")


async def _trigger(client: AsyncPolyester) -> None:
    await client.triggers.create(
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="1",
        trigger_price="100",
        client_trigger_id="trg-scope",
    )


PATHS = [_batch_replace, _modify, _status, _trigger]


@pytest.mark.parametrize("call", PATHS, ids=lambda call: call.__name__)
async def test_empty_default_sends_no_scope(serve, call) -> None:
    make, seen = serve
    await call(make(""))
    assert len(seen) == 1
    assert _scope(seen[0]) is None


@pytest.mark.parametrize("call", PATHS, ids=lambda call: call.__name__)
async def test_no_default_sends_no_scope_control(serve, call) -> None:
    make, seen = serve
    await call(make(None))
    assert len(seen) == 1
    assert _scope(seen[0]) is None


@pytest.mark.parametrize("call", PATHS, ids=lambda call: call.__name__)
async def test_real_default_still_scopes_control(serve, call) -> None:
    make, seen = serve
    await call(make(format_id(SUB_ACCOUNT)))
    assert len(seen) == 1
    assert _scope(seen[0]) == SUB_ACCOUNT
