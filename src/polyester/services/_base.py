from __future__ import annotations

from typing import Any

from polyester.connect_transport import (
    encode_connect_body,
    normalize_procedure,
    parse_connect_json_response,
)
from polyester.transport import TransportFactory


class BaseService:
    def __init__(self, transport: TransportFactory) -> None:
        self._transport = transport

    async def _public_connect_unary(
        self,
        procedure: str,
        request: dict[str, Any] | None = None,
    ) -> Any:
        return await self._connect_unary(procedure, request, authenticated=False)

    async def _auth_connect_unary(
        self,
        procedure: str,
        request: dict[str, Any] | None = None,
    ) -> Any:
        return await self._connect_unary(procedure, request, authenticated=True)

    async def _connect_unary(
        self,
        procedure: str,
        request: dict[str, Any] | None,
        *,
        authenticated: bool,
    ) -> Any:
        path = normalize_procedure(procedure)
        body = encode_connect_body(request, wire_format=self._transport.config.wire_format)
        headers = self._transport.connect_headers()
        client = (
            self._transport.require_auth_http()
            if authenticated
            else self._transport.public_http
        )
        response = await client.post(path, content=body, headers=headers)
        return parse_connect_json_response(response)
