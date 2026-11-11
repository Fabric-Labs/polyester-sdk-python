"""A market order executes immediate-or-cancel; no other time in force is sent.

The public contract offers one market execution, ``market_ioc`` ("Market orders
always execute as immediate-or-cancel"). A market order asking for ``fok``,
``gtc`` or ``gtd`` is refused before anything is sent, never turned into IOC.
The same holds for a trigger's market child and for a trailing stop, whose
child is always IOC.
"""

from __future__ import annotations

import json

import pytest
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.timestamp_pb2 import Timestamp

from polyester import AsyncPolyester
from polyester.codecs.triggers import create_trigger_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2 as orders
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

METHODS = ("create", "preview", "batch_create")
RESPONSES = {
    "CreateOrder": orders.CreateOrderResponse(order_id=42),
    "PreviewOrder": orders.PreviewOrderResponse(
        admissible=True, evaluated_at=Timestamp(seconds=1_700_000_000)
    ),
    "BatchCreateOrders": orders.BatchCreateOrdersResponse(),
}
REQUESTS = {
    "CreateOrder": orders.CreateOrderRequest,
    "PreviewOrder": orders.PreviewOrderRequest,
    "BatchCreateOrders": orders.BatchCreateOrdersRequest,
}


async def _client(json_wire: bool, seen: list[object]) -> tuple[AsyncPolyester, MockHttpServer]:
    async def handler(req: ParsedRequest) -> HttpScript:
        rpc = req.path.rsplit("/", 1)[-1]
        request = (
            ParseDict(json.loads(req.body), REQUESTS[rpc]())
            if json_wire
            else REQUESTS[rpc].FromString(req.body)
        )
        seen.append(request)
        response = RESPONSES[rpc]
        if json_wire:
            return HttpScript.json(200, MessageToDict(response))
        return connect_proto_response(response.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
        wire_format="json" if json_wire else "binary",
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
    return client, http


async def _send(client: AsyncPolyester, method: str, order: dict[str, object]) -> None:
    if method == "batch_create":
        await client.orders.batch_create(items=[order])  # type: ignore[list-item]
    else:
        await getattr(client.orders, method)(**order)


def _market(side: str, tif: str | None) -> dict[str, object]:
    order: dict[str, object] = {
        "symbol": "BTC-USDT",
        "side": side,
        "order_type": "market",
        "qty": "0.00008",
    }
    if tif is not None:
        order["tif"] = tif
    return order


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("tif", ["fok", "gtc", "gtd"])
async def test_market_order_refuses_non_ioc_tif_before_sending(
    json_wire: bool, method: str, side: str, tif: str
) -> None:
    seen: list[object] = []
    client, http = await _client(json_wire, seen)
    try:
        with pytest.raises(
            PolyesterValidationError, match=f"^tif='{tif}' is only valid for limit orders$"
        ):
            await _send(client, method, _market(side, tif))
        assert seen == []
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("json_wire", [False, True])
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("tif", [None, "ioc"])
async def test_market_order_with_ioc_or_no_tif_is_sent_as_market_ioc(
    json_wire: bool, method: str, side: str, tif: str | None
) -> None:
    seen: list[object] = []
    client, http = await _client(json_wire, seen)
    try:
        await _send(client, method, _market(side, tif))
        assert len(seen) == 1
        request = seen[0]
        intent = request.items[0] if method == "batch_create" else request.order  # type: ignore[attr-defined]
        assert intent.WhichOneof("execution") == "market_ioc"
    finally:
        await client.aclose()
        await http.aclose()


def _trigger(**overrides: object):
    kwargs: dict[str, object] = {
        "symbol": "BTC-USDT",
        "symbol_id": 1,
        "trigger_type": "stop_loss",
        "trigger_price": "83589",
        "side": "sell",
        "qty": "0.01",
        "quantity_scale": 8,
        "order_type": "market",
    }
    kwargs.update(overrides)
    return create_trigger_to_proto(**kwargs)  # type: ignore[arg-type]


IOC_ONLY_CHILDREN = {
    "stop_loss": {"trigger_type": "stop_loss"},
    "take_profit": {"trigger_type": "take_profit"},
    "twap": {
        "trigger_type": "twap",
        "trigger_price": None,
        "twap_duration_ms": 60_000,
        "twap_slice_interval_ms": 1_000,
    },
    "trailing_stop": {
        "trigger_type": "trailing_stop",
        "trigger_price": None,
        "trailing_distance_bps": 50,
    },
}


@pytest.mark.parametrize("child", sorted(IOC_ONLY_CHILDREN))
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("tif", ["gtc", "fok"])
def test_trigger_market_or_trailing_child_refuses_non_ioc_tif(
    child: str, side: str, tif: str
) -> None:
    overrides = dict(IOC_ONLY_CHILDREN[child], side=side, tif=tif)
    if child == "trailing_stop" and side == "buy":
        overrides["limit_price"] = "90000"
    with pytest.raises(PolyesterValidationError, match=f"^tif={tif} applies only to limit"):
        _trigger(**overrides)


@pytest.mark.parametrize("child", sorted(IOC_ONLY_CHILDREN))
@pytest.mark.parametrize("tif", [None, "ioc"])
def test_trigger_market_or_trailing_child_accepts_ioc_or_no_tif(
    child: str, tif: str | None
) -> None:
    overrides: dict[str, object] = dict(IOC_ONLY_CHILDREN[child])
    if tif is not None:
        overrides["tif"] = tif
    proto = _trigger(**overrides)
    assert proto.trigger.WhichOneof("strategy") == child


@pytest.mark.parametrize("trigger_type", ["stop_loss", "take_profit"])
def test_trigger_limit_child_without_tif_rests_gtc(trigger_type: str) -> None:
    proto = _trigger(trigger_type=trigger_type, order_type="limit", limit_price="83500")
    child = getattr(proto.trigger, trigger_type).child
    assert child.WhichOneof("execution") == "limit_gtc"
