from contextlib import asynccontextmanager

import pytest

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.models import CreateOrderRequest
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)


def order_input():
    return dict(symbol="BTC-USDT", side="buy", order_type="limit", price="100", qty="0.01")


@asynccontextmanager
async def scope_client(default):
    seen = []

    async def handler(req: ParsedRequest):
        if req.path.endswith("/CreateOrder"):
            request = orders.CreateOrderRequest.FromString(req.body)
            response = orders.CreateOrderResponse(order_id=9)
        elif req.path.endswith("/PreviewOrder"):
            request = orders.PreviewOrderRequest.FromString(req.body)
            response = orders.PreviewOrderResponse(evaluated_at={"seconds": 1})
        elif req.path.endswith("/BatchCreateOrders"):
            request = orders.BatchCreateOrdersRequest.FromString(req.body)
            response = orders.BatchCreateOrdersResponse()
        else:
            raise AssertionError(f"unexpected request: {req.path}")
        seen.append(request)
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        default_sub_account_id=format_id(default),
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config({"pairs": [{
        "symbol": "BTC-USDT", "symbol_id": 1,
        "base_quantity_scale": 8, "quote_quantity_scale": 6,
    }]})
    try:
        yield client, seen
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("default", [42, 43])
@pytest.mark.parametrize("helper", ["create", "preview_order", "batch_create"])
@pytest.mark.parametrize("kwargs,expected", [
    ({}, "default"), ({"account": "main"}, "default"),
    ({"account": "active"}, "default"), ({"sub_account_id": ""}, None),
    ({"sub_account_id": format_id(44)}, 44),
])
async def test_order_scope_controls(default, helper, kwargs, expected):
    async with scope_client(default) as (client, seen):
        call = getattr(client.orders, helper)
        if helper == "batch_create":
            await call(items=[order_input()], **kwargs)
        else:
            await call(**order_input(), **kwargs)
        assert len(seen) == 1, "public helper never reached transport"
        want = default if expected == "default" else expected
        assert seen[0].HasField("subaccount_id") == (want is not None)
        assert seen[0].subaccount_id == (want or 0)


@pytest.mark.parametrize("helper", ["create", "preview_order"])
@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("account", ["main", "active"])
@pytest.mark.parametrize("override", ["", format_id(44)])
async def test_order_scope_conflicts(helper, typed, account, override):
    async with scope_client(42) as (client, seen):
        call = getattr(client.orders, helper)
        request = dict(**order_input(), sub_account_id=override)
        with pytest.raises(PolyesterValidationError, match="Pass account or sub_account_id"):
            if typed:
                await call(CreateOrderRequest(**request), account=account)
            else:
                await call(**request, account=account)
        assert seen == []


@pytest.mark.parametrize("typed", [False, True])
@pytest.mark.parametrize("override", ["", format_id(42), format_id(44)])
@pytest.mark.parametrize("top", [None, "", format_id(44)])
async def test_batch_refuses_item_scope(typed, override, top):
    async with scope_client(42) as (client, seen):
        item = dict(**order_input(), sub_account_id=override)
        if typed:
            item = CreateOrderRequest(**item)
        with pytest.raises(PolyesterValidationError, match="batch-level sub_account_id"):
            await client.orders.batch_create(items=[order_input(), item], sub_account_id=top)
        assert seen == []
