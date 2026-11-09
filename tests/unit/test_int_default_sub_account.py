"""A default sub-account given as an int is the numeric ID, and 0 is refused.

On the wire a sub-account ID of 0 means unset, the main account. A falsy int
default must not silently turn into "no scope": like ``"1"`` or ``"0"``, it is
refused before anything is sent.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio

from polyester import AsyncPolyester, Polyester
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
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
ANSWERS: dict[str, tuple[Any, Any]] = {
    "/ledger.read.v1.LedgerReadService/GetBalances": (
        ledger_read_pb2.GetBalancesRequest,
        ledger_read_pb2.GetBalancesResponse(),
    ),
    "/orders.v1.OrdersService/ModifyOrder": (
        orders_pb2.ModifyOrderRequest,
        orders_pb2.ModifyOrderResponse(old_order_id=42, final_order_id=42, action_taken=1),
    ),
    "/triggers.v1.TriggersService/CreateTrigger": (
        triggers_pb2.CreateTriggerRequest,
        triggers_pb2.CreateTriggerResponse(trigger_id=42),
    ),
}


def _scope(request: Any) -> int | None:
    return request.subaccount_id if request.HasField("subaccount_id") else None


@pytest_asyncio.fixture(loop_scope="function")
async def serve():
    seen: list[Any] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        seen.append(req.path)
        if req.path not in ANSWERS:
            return HttpScript.not_found()
        request_type, response = ANSWERS[req.path]
        seen[-1] = request_type.FromString(req.body)
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    clients: list[AsyncPolyester] = []

    def make(default: Any) -> AsyncPolyester:
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

    yield make, seen, http.base_url
    for client in clients:
        await client.aclose()
    await http.aclose()


async def _balances(client: AsyncPolyester) -> None:
    await client.balances.list()


async def _modify(client: AsyncPolyester) -> None:
    await client.orders.modify(symbol="BTC-USDT", key=OrderId(42), new_qty="1", new_price="100")


async def _trigger(client: AsyncPolyester) -> None:
    await client.triggers.create(
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="1",
        trigger_price="100",
        client_trigger_id="trg-int-default",
    )


PATHS: list[Callable[[AsyncPolyester], Awaitable[None]]] = [_balances, _modify, _trigger]
FALSY = [0, False, 0.0]


@pytest.mark.parametrize("default", FALSY, ids=repr)
@pytest.mark.parametrize("call", PATHS, ids=lambda call: call.__name__)
async def test_falsy_non_string_default_is_refused_and_sends_nothing(serve, call, default) -> None:
    make, seen, _ = serve
    with pytest.raises(PolyesterValidationError, match="default_sub_account_id"):
        await call(make(default))
    assert seen == []


@pytest.mark.parametrize("call", PATHS, ids=lambda call: call.__name__)
async def test_int_default_scopes_to_its_numeric_id(serve, call) -> None:
    make, seen, _ = serve
    client = make(SUB_ACCOUNT)
    await call(client)
    assert len(seen) == 1
    assert _scope(seen[0]) == SUB_ACCOUNT


@pytest.mark.parametrize("default", [2**64, -1, 4.2, b"77"], ids=repr)
async def test_other_invalid_defaults_are_refused_control(serve, default) -> None:
    make, seen, _ = serve
    with pytest.raises(PolyesterValidationError):
        await _balances(make(default))
    assert seen == []


def test_sync_client_refuses_an_int_zero_default() -> None:
    creds = make_test_credentials()
    with pytest.raises(PolyesterValidationError, match="default_sub_account_id"):
        # The refusal comes before any request: the URL has nothing listening.
        Polyester(
            api_url="http://127.0.0.1:9",
            api_key_id=creds.key_id,
            api_private_key=creds.private_key,
            default_sub_account_id=0,
            hydrate_catalogs=False,
        ).balances.list()
