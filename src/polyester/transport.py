from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
from connectrpc.codec import proto_binary_codec, proto_json_codec
from connectrpc.interceptor import UnaryInterceptor

from polyester.auth import ApiKeyCredentials
from polyester.auth_interceptor import ApiKeyAuthUnaryInterceptor
from polyester.connect_transport import connect_headers as build_connect_headers
from polyester.errors import PolyesterAuthError, PolyesterTransportError

WireFormat = Literal["binary", "json"]
MAX_CONNECT_RESPONSE_BYTES = 4 * 1024 * 1024


def codec_for_config(config: TransportConfig):
    if config.wire_format == "json":
        return proto_json_codec()
    return proto_binary_codec()


@dataclass(frozen=True, slots=True)
class TransportConfig:
    api_url: str
    timeout: float = 10.0
    wire_format: WireFormat = "binary"

    def __repr__(self) -> str:
        return (
            f"TransportConfig(api_url={self.api_url!r}, timeout={self.timeout!r}, "
            f"wire_format={self.wire_format!r})"
        )


class TransportFactory:
    """Owns SDK HTTP clients and generated Connect-client construction."""

    def __init__(
        self,
        config: TransportConfig,
        *,
        credentials: ApiKeyCredentials | None = None,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.public_http = httpx.AsyncClient(base_url=config.api_url, timeout=config.timeout)
        self._codec = codec_for_config(config)
        self._auth_interceptors: list[UnaryInterceptor] = []
        if credentials is not None:
            self._auth_interceptors.append(
                ApiKeyAuthUnaryInterceptor(
                    credentials,
                    base_url=config.api_url,
                    codec=self._codec,
                )
            )

    def __repr__(self) -> str:
        creds = "[REDACTED]" if self.credentials is not None else None
        return f"TransportFactory(config={self.config!r}, credentials={creds})"

    def connect_headers(self) -> dict[str, str]:
        return build_connect_headers(wire_format=self.config.wire_format)

    def _client_kwargs(self) -> dict:
        return {
            "codec": self._codec,
            "timeout_ms": int(self.config.timeout * 1000),
            "read_max_bytes": MAX_CONNECT_RESPONSE_BYTES,
            # Signing hashes the protobuf/JSON body; gzip would break API-key auth.
            "send_compression": None,
        }

    def create_public_client(self, client_cls: type):
        return client_cls(
            self.config.api_url,
            interceptors=[],
            **self._client_kwargs(),
        )

    def create_auth_client(self, client_cls: type):
        if self.credentials is None:
            raise PolyesterAuthError("This endpoint requires Polyester API-key credentials")
        return client_cls(
            self.config.api_url,
            interceptors=self._auth_interceptors,
            **self._client_kwargs(),
        )

    async def aclose(self) -> None:
        await self.public_http.aclose()


def map_transport_error(exc: Exception) -> PolyesterTransportError:
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return PolyesterTransportError(str(exc))
    return PolyesterTransportError(str(exc))
