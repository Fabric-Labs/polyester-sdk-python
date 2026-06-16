from __future__ import annotations

from typing import Any, TypeVar

from connectrpc.client import ConnectClient
from connectrpc.method import IdempotencyLevel, MethodInfo
from google.protobuf.message import Message

from polyester.services._generated import unary_auth

TRequest = TypeVar("TRequest", bound=Message)
TResponse = TypeVar("TResponse", bound=Message)


async def unary_ledger_write(
    transport,
    request: TRequest,
    *,
    method_name: str,
    response_type: type[TResponse],
) -> dict[str, Any]:
    """Call a LedgerWriteService RPC even when the generated client omits the method."""

    async def _call(client: ConnectClient, req: TRequest) -> TResponse:
        return await client.execute_unary(
            request=req,
            method=MethodInfo(
                name=method_name,
                service_name="ledger.write.v1.LedgerWriteService",
                input=type(req),
                output=response_type,
                idempotency_level=IdempotencyLevel.UNKNOWN,
            ),
        )

    # Use base ConnectClient — generated ledger_write_connect is out of sync with pb2.
    return await unary_auth(transport, ConnectClient, _call, request)
