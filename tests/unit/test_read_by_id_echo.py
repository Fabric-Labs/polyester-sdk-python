"""A read by ID must answer the object it asked for: a reply that names
another one breaks the contract, however well formed it is, and raises
``PolyesterResponseContractError``; the reply that names the requested object
decodes. Each read goes through its public service against a local server."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
from polyester.gen.auth.v1 import api_keys_pb2, subaccounts_pb2
from polyester.gen.chain.lifecycle.v1 import lifecycle_read_pb2
from polyester.gen.changelog.v1 import changelog_pb2
from polyester.gen.ledger.read.v1 import statement_export_pb2
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.transfer.v1 import dust_conversion_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models import ClientOrderId, OrderId
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()
_KEY_ID = "ak_0123456789abcdef0123456789abcdef"


@asynccontextmanager
async def _client(*replies: Message):
    """A client whose server answers each call with the next of ``replies``."""
    queue = list(replies)

    async def handler(_req: ParsedRequest) -> HttpScript:
        if not queue:
            return HttpScript.json(404, {"code": "not_found", "message": "no reply"})
        return connect_proto_response(queue.pop(0).SerializeToString())

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    try:
        yield client
    finally:
        await client.aclose()
        await http.aclose()


def _flow(flow_id: str) -> dict[str, Any]:
    return {
        "summary": {
            "flow_id": flow_id,
            "participation": lifecycle_read_pb2.PARTICIPATION_OWNER,
        }
    }


def _export(export_id: int) -> dict[str, Any]:
    return {"export_id": export_id, "status": statement_export_pb2.STATEMENT_EXPORT_STATUS_QUEUED}


Read = Callable[[AsyncPolyester], Awaitable[Any]]

# (name, reply for another object, reply for the requested one, read)
_CASES: list[tuple[str, Message, Message, Read]] = [
    (
        "GetBatchReplaceStatus",
        orders_read_pb2.GetBatchReplaceStatusResponse(batch_request_id=8, admission_status=1),
        orders_read_pb2.GetBatchReplaceStatusResponse(batch_request_id=7, admission_status=1),
        lambda c: c.orders.get_batch_replace_status(batch_request_id=format_id(7)),
    ),
    (
        "GetOrder by order ID",
        orders_read_pb2.GetOrderResponse(order={"order_id": 43, "client_order_id": "cid-1"}),
        orders_read_pb2.GetOrderResponse(order={"order_id": 42, "client_order_id": "cid-1"}),
        lambda c: c.orders.get(key=OrderId(format_id(42))),
    ),
    (
        "GetOrder by client order ID",
        orders_read_pb2.GetOrderResponse(order={"order_id": 42, "client_order_id": "cid-2"}),
        orders_read_pb2.GetOrderResponse(order={"order_id": 42, "client_order_id": "cid-1"}),
        lambda c: c.orders.get(key=ClientOrderId("cid-1")),
    ),
    (
        "GetTrigger",
        triggers_pb2.GetTriggerResponse(trigger={"trigger_id": 6}),
        triggers_pb2.GetTriggerResponse(trigger={"trigger_id": 5}),
        lambda c: c.triggers.get(trigger_id=format_id(5)),
    ),
    (
        "GetDustConversion",
        dust_conversion_pb2.GetDustConversionResponse(conversion={"conversion_id": "124"}),
        dust_conversion_pb2.GetDustConversionResponse(conversion={"conversion_id": "123"}),
        lambda c: c.dust_conversions.get(conversion_id="123"),
    ),
    (
        "GetFlowById",
        lifecycle_read_pb2.GetFlowResponse(flow=_flow("flow_b")),
        lifecycle_read_pb2.GetFlowResponse(flow=_flow("flow_a")),
        lambda c: c.lifecycle.get_flow(flow_id="flow_a"),
    ),
    (
        "GetAccountFlow",
        lifecycle_read_pb2.GetAccountFlowResponse(flow=_flow("flow_b")),
        lifecycle_read_pb2.GetAccountFlowResponse(flow=_flow("flow_a")),
        lambda c: c.lifecycle.get_account_flow(flow_id="flow_a"),
    ),
    (
        "GetSubaccount",
        subaccounts_pb2.GetSubaccountResponse(subaccount={"id": 10}),
        subaccounts_pb2.GetSubaccountResponse(subaccount={"id": 9}),
        lambda c: c.sub_accounts.get(sub_account_id=format_id(9)),
    ),
    (
        "GetApiKey",
        api_keys_pb2.GetApiKeyResponse(api_key={"key_id": "ak_fedcba9876543210fedcba9876543210"}),
        api_keys_pb2.GetApiKeyResponse(api_key={"key_id": _KEY_ID}),
        lambda c: c.api_keys.get(key_id=_KEY_ID),
    ),
    (
        "GetPost",
        changelog_pb2.GetPostResponse(post={"summary": {"slug": "2026-09-25"}}),
        changelog_pb2.GetPostResponse(post={"summary": {"slug": "2026-09-24"}}),
        lambda c: c.changelog.get_post("2026-09-24"),
    ),
    (
        "GetDeploymentGroup",
        changelog_pb2.GetDeploymentGroupResponse(group={"summary": {"slug": "testnet-v0.92.8"}}),
        changelog_pb2.GetDeploymentGroupResponse(group={"summary": {"slug": "testnet-v0.92.9"}}),
        lambda c: c.changelog.get_deployment_group("testnet-v0.92.9"),
    ),
    (
        "GetStatementExport",
        statement_export_pb2.GetStatementExportResponse(export=_export(78)),
        statement_export_pb2.GetStatementExportResponse(export=_export(77)),
        lambda c: c.statements.get_export(export_id=format_id(77)),
    ),
    (
        "CancelStatementExport",
        statement_export_pb2.CancelStatementExportResponse(export=_export(78)),
        statement_export_pb2.CancelStatementExportResponse(export=_export(77)),
        lambda c: c.statements.cancel_export(export_id=format_id(77)),
    ),
]


@pytest.mark.parametrize(("name", "wrong", "right", "read"), _CASES, ids=[c[0] for c in _CASES])
async def test_a_read_by_id_refuses_a_reply_for_another_object(
    name: str, wrong: Message, right: Message, read: Read
) -> None:
    async with _client(wrong, right) as client:
        with pytest.raises(PolyesterResponseContractError) as raised:
            await read(client)
        assert raised.value.context == name.split(" ")[0]
        assert await read(client) is not None


async def test_get_api_key_accepts_the_trimmed_key() -> None:
    # The server reads the key ID with surrounding whitespace trimmed.
    async with _client(api_keys_pb2.GetApiKeyResponse(api_key={"key_id": _KEY_ID})) as client:
        key = await client.api_keys.get(key_id=f" {_KEY_ID}\n")
    assert key is not None and key.key_id == _KEY_ID
