"""``triggers.create`` always sends the client trigger ID the contract requires."""

from __future__ import annotations

import re

import pytest
import pytest_asyncio

from polyester import AsyncPolyester
from polyester.errors import PolyesterValidationError
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

CREATE_PATH = "/triggers.v1.TriggersService/CreateTrigger"


@pytest_asyncio.fixture(loop_scope="function")
async def trigger_client():
    seen: list[triggers.CreateTriggerRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        if req.method != "POST" or req.path != CREATE_PATH:
            return HttpScript.not_found()
        request = triggers.CreateTriggerRequest.FromString(req.body)
        seen.append(request)
        response = triggers.CreateTriggerResponse(
            trigger_id=42, client_trigger_id=request.trigger.client_trigger_id
        )
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
                }
            ]
        }
    )
    yield client, seen
    await client.aclose()
    await http.aclose()


async def _create(client: AsyncPolyester, **kwargs):
    return await client.triggers.create(
        symbol="BTC-USDT",
        trigger_type="stop_loss",
        side="sell",
        qty="1",
        trigger_price="100",
        **kwargs,
    )


@pytest.mark.parametrize("kwargs", [{}, {"client_trigger_id": None}, {"client_trigger_id": ""}])
async def test_create_without_an_id_sends_a_generated_one(trigger_client, kwargs) -> None:
    client, seen = trigger_client
    await _create(client, **kwargs)
    await _create(client, **kwargs)
    assert len(seen) == 2
    ids = [request.trigger.client_trigger_id for request in seen]
    assert all(re.fullmatch(r"trg-[0-9a-f]{12}", value) for value in ids), ids
    assert ids[0] != ids[1]


async def test_create_keeps_a_given_id_control(trigger_client) -> None:
    client, seen = trigger_client
    await _create(client, client_trigger_id="my-trigger-1")
    assert [request.trigger.client_trigger_id for request in seen] == ["my-trigger-1"]


async def test_create_refuses_a_blank_id_before_sending(trigger_client) -> None:
    client, seen = trigger_client
    with pytest.raises(PolyesterValidationError, match="client_trigger_id"):
        await _create(client, client_trigger_id="   ")
    assert seen == []
