from contextlib import asynccontextmanager, suppress

import pytest

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterError, PolyesterValidationError
from polyester.gen.chain.guard.v1 import guard_signer_pb2 as guard
from polyester.gen.orders.v1 import orders_pb2 as orders
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from polyester.models import CreateOrderRequest
from polyester.models.order_key import OrderId
from tests.hardening_support import (
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

REQUESTS = {
    "CreateOrder": orders.CreateOrderRequest,
    "PreviewOrder": orders.PreviewOrderRequest,
    "ModifyOrder": orders.ModifyOrderRequest,
    "CancelOrder": orders.CancelOrderRequest,
    "CancelAllOrders": orders.CancelAllOrdersRequest,
    "CancelAllAfter": orders.CancelAllAfterRequest,
    "BatchCreateOrders": orders.BatchCreateOrdersRequest,
    "BatchCancelOrders": orders.BatchCancelOrdersRequest,
    "BatchReplaceOrders": orders.BatchReplaceOrdersRequest,
    "CreateTrigger": triggers.CreateTriggerRequest,
    "ModifyTrigger": triggers.ModifyTriggerRequest,
    "CancelTrigger": triggers.CancelTriggerRequest,
    "PauseTrigger": triggers.PauseTriggerRequest,
    "ResumeTrigger": triggers.ResumeTriggerRequest,
    "ListTriggers": triggers.ListTriggersRequest,
    "BatchSignProtectedActions": guard.BatchSignProtectedActionsRequest,
}


def order_input():
    return dict(symbol="BTC-USDT", side="buy", order_type="limit", price="100", qty="0.01")


def key_item():
    return {"key": OrderId(format_id(9))}


def replace_item():
    return {**key_item(), "new_price": "100"}


@asynccontextmanager
async def scope_client(default):
    seen = []

    async def handler(req: ParsedRequest):
        rpc = req.path.rsplit("/", 1)[-1]
        if rpc not in REQUESTS:
            raise AssertionError(f"unexpected request: {req.path}")
        seen.append((rpc, REQUESTS[rpc].FromString(req.body)))
        if rpc == "ListTriggers":
            response = triggers.ListTriggersResponse(
                triggers=[triggers.Trigger(trigger_id=9, status=triggers.STATUS_ARMED)]
            )
        elif rpc == "PreviewOrder":
            response = orders.PreviewOrderResponse(evaluated_at={"seconds": 1})
        elif rpc == "CreateOrder":
            response = orders.CreateOrderResponse(order_id=9)
        else:
            response = orders.BatchCreateOrdersResponse()
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


# Public write helper -> the RPCs it sends, in order.
WRITE_HELPERS = {
    "orders.create": (
        lambda c, scope: c.orders.create(**order_input(), **scope), ["CreateOrder"]
    ),
    "orders.preview": (
        lambda c, scope: c.orders.preview(**order_input(), **scope), ["PreviewOrder"]
    ),
    "orders.batch_create": (
        lambda c, scope: c.orders.batch_create(items=[order_input()], **scope),
        ["BatchCreateOrders"],
    ),
    "orders.batch_cancel": (
        lambda c, scope: c.orders.batch_cancel(items=[key_item()], **scope),
        ["BatchCancelOrders"],
    ),
    "orders.batch_replace": (
        lambda c, scope: c.orders.batch_replace(
            items=[replace_item()], symbol="BTC-USDT", **scope
        ),
        ["BatchReplaceOrders"],
    ),
    "orders.modify": (
        lambda c, scope: c.orders.modify(
            key=OrderId(format_id(9)), symbol="BTC-USDT", new_price="100", **scope
        ),
        ["ModifyOrder"],
    ),
    "orders.cancel": (
        lambda c, scope: c.orders.cancel(key=OrderId(format_id(9)), **scope), ["CancelOrder"]
    ),
    "orders.cancel_all": (
        lambda c, scope: c.orders.cancel_all(dry_run=True, **scope), ["CancelAllOrders"]
    ),
    "orders.cancel_all_after": (
        lambda c, scope: c.orders.cancel_all_after(timeout_sec=15, **scope), ["CancelAllAfter"]
    ),
    "orders.stop_all_trading": (
        lambda c, scope: c.orders.stop_all_trading(**scope),
        ["ListTriggers", "CancelTrigger", "CancelAllOrders"],
    ),
    "triggers.create": (
        lambda c, scope: c.triggers.create(
            symbol="BTC-USDT", trigger_type="stop_loss", side="sell", qty="0.01",
            trigger_price="100", client_trigger_id="scope", **scope,
        ),
        ["CreateTrigger"],
    ),
    "triggers.modify": (
        lambda c, scope: c.triggers.modify(
            trigger_id=format_id(9), max_slippage_bps=100, **scope
        ),
        ["ModifyTrigger"],
    ),
    "triggers.cancel": (
        lambda c, scope: c.triggers.cancel(trigger_id=format_id(9), **scope), ["CancelTrigger"]
    ),
    "triggers.pause": (
        lambda c, scope: c.triggers.pause(trigger_id=format_id(9), **scope), ["PauseTrigger"]
    ),
    "triggers.resume": (
        lambda c, scope: c.triggers.resume(trigger_id=format_id(9), **scope), ["ResumeTrigger"]
    ),
}


@pytest.mark.parametrize("default", [42, 43])
@pytest.mark.parametrize("helper", sorted(WRITE_HELPERS))
@pytest.mark.parametrize("scope,expected", [
    ({}, "default"),
    ({"account": "main"}, "default"),
    ({"account": "active"}, "default"),
    ({"sub_account_id": ""}, None),
    ({"account": ""}, None),
    ({"sub_account_id": format_id(44)}, 44),
    ({"account": format_id(44)}, 44),
    ({"account": {"subaccountId": format_id(44)}}, 44),
])
async def test_write_helpers_send_the_resolved_scope(default, helper, scope, expected):
    call, rpcs = WRITE_HELPERS[helper]
    want = default if expected == "default" else expected
    async with scope_client(default) as (client, seen):
        # The capture is the assertion; the canned answer may not decode.
        with suppress(PolyesterError):
            await call(client, scope)
        assert [rpc for rpc, _ in seen] == rpcs, "public helper never reached transport"
        for rpc, request in seen:
            assert request.HasField("subaccount_id") == (want is not None), rpc
            assert request.subaccount_id == (want or 0), rpc


@pytest.mark.parametrize("helper", sorted(WRITE_HELPERS))
@pytest.mark.parametrize("scope", [
    {"account": "main", "sub_account_id": ""},
    {"account": "active", "sub_account_id": ""},
    {"account": "main", "sub_account_id": format_id(44)},
    {"account": "active", "sub_account_id": format_id(42)},
    {"account": {"subaccountId": format_id(44)}, "sub_account_id": format_id(42)},
])
async def test_write_helpers_refuse_selector_conflicts(helper, scope):
    call, _ = WRITE_HELPERS[helper]
    async with scope_client(42) as (client, seen):
        with pytest.raises(PolyesterValidationError, match="Pass account or sub_account_id"):
            await call(client, scope)
        assert seen == []


@pytest.mark.parametrize("helper", sorted(WRITE_HELPERS))
@pytest.mark.parametrize("scope", [{"sub_account_id": "  "}, {"account": "\t"}])
async def test_write_helpers_refuse_whitespace_scope(helper, scope):
    call, _ = WRITE_HELPERS[helper]
    async with scope_client(42) as (client, seen):
        with pytest.raises(PolyesterValidationError, match="base58 or decimal"):
            await call(client, scope)
        assert seen == []


@pytest.mark.parametrize("helper", ["create", "preview"])
@pytest.mark.parametrize("account", ["main", "active"])
@pytest.mark.parametrize("override", ["", format_id(44)])
async def test_typed_order_requests_refuse_selector_conflicts(helper, account, override):
    async with scope_client(42) as (client, seen):
        request = CreateOrderRequest(**order_input(), sub_account_id=override)
        with pytest.raises(PolyesterValidationError, match="Pass account or sub_account_id"):
            await getattr(client.orders, helper)(request, account=account)
        assert seen == []


@pytest.mark.parametrize("helper", ["create", "preview"])
@pytest.mark.parametrize("request_scope,account,want", [
    (None, None, 42),
    (None, "main", 42),
    (None, format_id(44), 44),
    ("", None, None),
    (format_id(44), None, 44),
])
async def test_typed_order_requests_send_the_resolved_scope(helper, request_scope, account, want):
    async with scope_client(42) as (client, seen):
        request = CreateOrderRequest(**order_input(), sub_account_id=request_scope)
        await getattr(client.orders, helper)(request, account=account)
        assert len(seen) == 1
        assert seen[0][1].HasField("subaccount_id") == (want is not None)
        assert seen[0][1].subaccount_id == (want or 0)


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


ITEM_SCOPES = [
    {"sub_account_id": ""},
    {"sub_account_id": format_id(44)},
    {"subaccount_id": format_id(44)},
    {"subaccountId": format_id(44)},
    {"account": "main"},
]


@pytest.mark.parametrize("item_scope", ITEM_SCOPES)
@pytest.mark.parametrize("top", [None, "", format_id(44)])
async def test_batch_cancel_refuses_item_scope(item_scope, top):
    async with scope_client(42) as (client, seen):
        with pytest.raises(PolyesterValidationError, match="batch-level sub_account_id"):
            await client.orders.batch_cancel(
                items=[key_item(), {**key_item(), **item_scope}], sub_account_id=top
            )
        assert seen == []


@pytest.mark.parametrize("item_scope", ITEM_SCOPES)
@pytest.mark.parametrize("top", [None, "", format_id(44)])
async def test_batch_replace_refuses_item_scope(item_scope, top):
    async with scope_client(42) as (client, seen):
        with pytest.raises(PolyesterValidationError, match="batch-level sub_account_id"):
            await client.orders.batch_replace(
                items=[replace_item(), {**replace_item(), **item_scope}],
                symbol="BTC-USDT",
                sub_account_id=top,
            )
        assert seen == []


@pytest.mark.parametrize("item_scope", ITEM_SCOPES)
@pytest.mark.parametrize("top", [None, "", format_id(44)])
async def test_batch_sign_refuses_action_scope(item_scope, top):
    async with scope_client(42) as (client, seen):
        with pytest.raises(PolyesterValidationError, match="batch-level sub_account_id"):
            await client.guard_signer.batch_sign_protected_actions(
                actions=[{"action": "funding_add_external_whitelist", **item_scope}],
                sub_account_id=top,
            )
        assert seen == []
