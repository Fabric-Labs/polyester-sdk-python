"""orders.cancel_all refuses a filter that would widen the cancel to every pair.

A blank symbol, or a blank entry in symbols, used to be dropped and so read
as "every pair". Like triggers.cancel_all, each is refused before anything
is sent; leaving the filters out is still the intentional cancel of every pair.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from google.protobuf import json_format

from polyester import AsyncPolyester
from polyester.codecs.orders import cancel_all_orders_to_proto
from polyester.errors import PolyesterCatalogHydrationError, PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()


@asynccontextmanager
async def _client(answer: Callable[[ParsedRequest], HttpScript]):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return answer(req)

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


def _cancel_all_reply(req: ParsedRequest) -> HttpScript:
    reply = orders_pb2.CancelAllOrdersResponse(status=orders_pb2.CancelAllOrdersResponse.DRY_RUN)
    if req.body.lstrip().startswith(b"{"):
        return HttpScript.json(200, json_format.MessageToJson(reply))
    return connect_proto_response(reply.SerializeToString())


def _sent(req: ParsedRequest) -> orders_pb2.CancelAllOrdersRequest:
    message = orders_pb2.CancelAllOrdersRequest()
    if req.body.lstrip().startswith(b"{"):
        json_format.Parse(req.body, message)
    else:
        message.ParseFromString(req.body)
    return message


_REFUSED: list[dict[str, Any]] = [
    {"symbol": ""},
    {"symbol": "   "},
    {"symbol": " \t"},
    {"symbol": b"BTC-USDT"},
    {"symbol": bytearray(b"BTC-USDT")},
    {"symbol": memoryview(b"BTC-USDT")},
    {"symbol": 1},
    {"symbols": [""]},
    {"symbols": ["   "]},
    {"symbols": ["BTC-USDT", " "]},
    {"symbols": [None]},
    {"symbols": [1]},
    {"symbols": [b"BTC-USDT"]},
    {"symbols": [bytearray(b"BTC-USDT")]},
    {"symbols": [memoryview(b"BTC-USDT")]},
    {"symbols": ""},
    {"symbols": "BTC-USDT"},
    {"symbols": b""},
    {"symbols": bytearray(b"")},
    {"symbols": memoryview(b"")},
    {"symbols": memoryview(b"BTC")},
    {"symbols": {"BTC-USDT": 1}},
    {"symbols": 7},
    {"symbol_ids": b""},
    {"symbol_ids": b"\x01"},
    {"symbol_ids": memoryview(b"")},
    {"symbol_ids": memoryview(b"\x01")},
    {"symbol_ids": "12"},
    {"symbol_ids": {1: 1}},
    {"symbol_ids": 1},
    {"symbol_ids": [True]},
    {"symbol": "   ", "symbol_ids": [1]},
    {"symbol": "BTC-USDT", "symbol_ids": [1]},
    {"symbols": ["BTC-USDT"], "symbol_ids": [1]},
    {"symbol": "BTC-USDT", "symbols": ["BTC-USDT"]},
    {"symbol": "BTC-USDT", "request_id": "bad!key"},
    {"request_id": ""},
    {"request_id": "   "},
    {"request_id": " retry-1"},
    {"request_id": "retry-1 "},
    {"request_id": "has space"},
    {"request_id": "x" * 65},
    {"request_id": 7},
]


def _catalog_wait(outcome: str, waits: list[str]) -> Callable[[], Awaitable[None]]:
    """A catalog wait that records each call, then fails or never ends."""

    async def wait() -> None:
        waits.append(outcome)
        if outcome == "failed":
            raise PolyesterCatalogHydrationError("spot config unavailable")
        await asyncio.Event().wait()

    return wait


@pytest.mark.parametrize("catalogs", ["failed", "pending"])
@pytest.mark.parametrize("kwargs", _REFUSED, ids=repr)
async def test_orders_cancel_all_refuses_a_blank_or_malformed_filter_before_sending(
    kwargs: dict[str, Any], catalogs: str
) -> None:
    # A malformed filter must never reach the server as an account-wide cancel,
    # and is refused before the catalogs are awaited: a failed or pending
    # catalog load never decides the answer.
    waits: list[str] = []
    async with _client(_cancel_all_reply) as (client, requests):
        client.orders._wait_for_catalogs = _catalog_wait(catalogs, waits)
        with pytest.raises(PolyesterValidationError):
            await asyncio.wait_for(client.orders.cancel_all(dry_run=True, **kwargs), 5)
    assert waits == []
    assert requests == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"symbol": ""},
        {"symbol": "  "},
        {"request_id": " stop-1"},
        {"request_id": ""},
        {"request_id": "bad!key"},
        {"request_id": "r" * 65},
    ],
    ids=repr,
)
async def test_stop_all_trading_refuses_a_blank_filter_before_canceling_triggers(
    kwargs: dict[str, Any],
) -> None:
    # Refused up front: no catalog wait, and no trigger is listed or canceled
    # before the cancel-all would have been refused.
    waits: list[str] = []
    async with _client(_cancel_all_reply) as (client, requests):
        client.orders._wait_for_catalogs = _catalog_wait("failed", waits)
        with pytest.raises(PolyesterValidationError):
            await client.orders.stop_all_trading(**kwargs)
    assert waits == []
    assert requests == []


async def test_orders_cancel_all_without_filters_still_cancels_every_pair() -> None:
    async with _client(_cancel_all_reply) as (client, requests):
        await client.orders.cancel_all(dry_run=True)
        await client.orders.cancel_all(dry_run=True, symbols=[], request_id="all-1")
        await client.orders.cancel_all(dry_run=True, symbol_ids=(), request_id="ui/all:2")
    sent = [_sent(req) for req in requests]
    assert [list(r.symbol_ids) for r in sent] == [[], [], []]
    assert sent[0].request_id.startswith("cancel-all-")
    # A supplied request ID is sent exactly as given.
    assert [r.request_id for r in sent[1:]] == ["all-1", "ui/all:2"]


@pytest.mark.parametrize("request_id", ["", "  ", " pad", "pad ", 7])
def test_cancel_all_orders_to_proto_never_trims_or_replaces_a_request_id(request_id) -> None:
    with pytest.raises(PolyesterValidationError, match="request_id"):
        cancel_all_orders_to_proto(request_id=request_id)
    assert cancel_all_orders_to_proto(request_id="keep-1").request_id == "keep-1"
