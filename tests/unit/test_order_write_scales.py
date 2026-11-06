from decimal import Decimal

import pytest
import pytest_asyncio

from polyester import AsyncPolyester, Quantity
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from polyester.models import OrderId
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)


@pytest_asyncio.fixture(loop_scope="function")
async def order_client():
    seen = []

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.path.endswith("/CreateOrder"):
            request = orders.CreateOrderRequest.FromString(req.body)
            response = orders.CreateOrderResponse(
                order_id=42, resolved_base_qty_scaled=request.order.base_qty_scaled
            )
        elif req.path.endswith("/BatchCreateOrders"):
            request = orders.BatchCreateOrdersRequest.FromString(req.body)
            response = orders.BatchCreateOrdersResponse()
        elif req.path.endswith("/ModifyOrder"):
            request = orders.ModifyOrderRequest.FromString(req.body)
            response = orders.ModifyOrderResponse(
                old_order_id=42, final_order_id=42, action_taken=1
            )
        elif req.path.endswith("/BatchReplaceOrders"):
            request = orders.BatchReplaceOrdersRequest.FromString(req.body)
            response = orders.BatchReplaceOrdersResponse(batch_request_id=42, status=1)
        elif req.path.endswith("/CreateTrigger"):
            request = triggers.CreateTriggerRequest.FromString(req.body)
            response = triggers.CreateTriggerResponse(trigger_id=42)
        else:
            raise AssertionError(f"unexpected write: {req.path}")
        seen.append(request)
        return connect_proto_response(response.SerializeToString())

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
                },
                {
                    "symbol": "ETH-USDT",
                    "symbol_id": 2,
                    "base_quantity_scale": 6,
                    "quote_quantity_scale": 4,
                },
            ]
        }
    )
    try:
        yield client, seen
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("identity", [{"symbol_id": 1}, {"symbol": "BTC-USDT"}])
@pytest.mark.parametrize("scale", [None, 8, 6])
async def test_create_uses_catalog_scale_on_wire_and_result(order_client, identity, scale):
    client, seen = order_client
    kwargs = dict(
        **identity,
        side="buy",
        order_type="limit",
        price="100",
        qty=Quantity.from_scaled(16000, scale=scale),
    )
    if scale == 6:
        with pytest.raises(PolyesterValidationError, match="scale mismatch"):
            await client.orders.create(**kwargs)
        assert seen == []
        return
    result = await client.orders.create(**kwargs)
    assert len(seen) == 1
    assert seen[0].order.symbol_id == 1
    assert seen[0].order.base_qty_scaled == 16000
    assert seen[0].order.limit_gtc.price_ticks == 100_000_000_000
    assert result.resolved_base_qty.scaled == 16000
    assert result.resolved_base_qty.as_decimal() == Decimal("0.00016")


@pytest.mark.parametrize("scale", [None, 8])
async def test_create_unknown_id_refused_even_with_scaled_quantity(order_client, scale):
    client, seen = order_client
    with pytest.raises(PolyesterValidationError, match="scale.*unavailable"):
        await client.orders.create(
            symbol_id=99,
            side="buy",
            order_type="limit",
            price="100",
            qty=Quantity.from_scaled(16000, scale=scale),
        )
    assert seen == []


@pytest.mark.parametrize("operation", ["modify", "batch_replace", "trigger"])
@pytest.mark.parametrize("scale", [None, 8, 6])
async def test_named_writes_check_catalog_scale(order_client, operation, scale):
    client, seen = order_client
    qty = Quantity.from_scaled(16000, scale=scale)

    async def invoke():
        if operation == "modify":
            return await client.orders.modify(
                symbol="BTC-USDT", key=OrderId(42), new_qty=qty, new_price="100"
            )
        if operation == "batch_replace":
            return await client.orders.batch_replace(
                symbol="BTC-USDT", items=[dict(key=OrderId(42), new_qty=qty, new_price="100")]
            )
        return await client.triggers.create(
            symbol="BTC-USDT",
            trigger_type="stop_loss",
            side="sell",
            qty=qty,
            trigger_price="100",
            order_type="limit",
            limit_price="99",
        )

    if scale == 6:
        with pytest.raises(PolyesterValidationError, match="scale mismatch"):
            await invoke()
        assert seen == []
    else:
        await invoke()
        assert len(seen) == 1
        if operation == "modify":
            assert seen[0].new_qty_scaled == 16000
            assert seen[0].new_price_ticks == 100_000_000_000
        elif operation == "batch_replace":
            assert seen[0].items[0].new_qty_scaled == 16000
            assert seen[0].items[0].new_price_ticks == 100_000_000_000
        else:
            assert seen[0].trigger.qty_scaled == 16000


@pytest.mark.parametrize("batch", [False, True])
async def test_id_quote_budget_uses_catalog_scale(order_client, batch):
    client, seen = order_client
    kwargs = dict(
        symbol_id=1,
        side="buy",
        order_type="market",
        max_quote_debit=Quantity.from_quote_scaled(16000, scale=6),
    )
    if batch:
        await client.orders.batch_create(items=[kwargs])
        assert seen[0].items[0].max_quote_debit_scaled == 16000
    else:
        await client.orders.create(**kwargs)
        assert seen[0].order.max_quote_debit_scaled == 16000


@pytest.mark.parametrize("typed", [False, True])
async def test_batch_resolves_each_id_scale(order_client, typed):
    client, seen = order_client
    qtys = [Quantity.from_scaled(16000, scale=s) for s in (8, 6)] if typed else ["0.00016"] * 2
    await client.orders.batch_create(
        items=[
            dict(symbol_id=i, side="buy", order_type="limit", price="100", qty=q)
            for i, q in zip((1, 2), qtys, strict=True)
        ]
    )
    assert len(seen) == 1
    assert [item.symbol_id for item in seen[0].items] == [1, 2]
    assert [item.base_qty_scaled for item in seen[0].items] == (
        [16000, 16000] if typed else [16000, 160]
    )


async def test_batch_mismatched_scale_refused_before_send(order_client):
    client, seen = order_client
    with pytest.raises(PolyesterValidationError, match="scale mismatch"):
        await client.orders.batch_create(
            items=[
                dict(
                    symbol_id=1,
                    side="buy",
                    order_type="limit",
                    price="100",
                    qty=Quantity.from_scaled(16000, scale=6),
                )
            ]
        )
    assert seen == []
