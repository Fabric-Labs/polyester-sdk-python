from __future__ import annotations

from base64 import b64decode
from contextlib import suppress
from dataclasses import dataclass
from math import isfinite
from typing import Literal

import httpx
import pyqwest
from connectrpc.code import Code
from connectrpc.codec import proto_binary_codec
from connectrpc.errors import ConnectError
from connectrpc.interceptor import UnaryInterceptor
from google.protobuf.any_pb2 import Any as AnyMessage
from google.protobuf.json_format import MessageToJson, Parse
from google.protobuf.message import Message

from polyester._problem import decode_http_problem
from polyester.auth import ApiKeyCredentials
from polyester.auth_interceptor import ApiKeyAuthUnaryInterceptor, UserAgentUnaryInterceptor
from polyester.errors import PolyesterAuthError, PolyesterTransportError
from polyester.user_agent import USER_AGENT, USER_AGENT_HEADER

WireFormat = Literal["binary", "json"]
MAX_CONNECT_RESPONSE_BYTES = 4 * 1024 * 1024


class _ProtoJSONCodec:
    """Protobuf JSON codec that ignores fields and enum names this SDK does not
    know yet (the server adds them ahead of SDK releases); unknown enum names
    read as the unspecified value, unknown enum numbers stay numbers."""

    def name(self) -> str:
        return "json"

    def encode(self, message: Message) -> bytes:
        return MessageToJson(message).encode()

    def decode(self, data: bytes | bytearray, message: Message) -> Message:
        Parse(bytes(data), message, ignore_unknown_fields=True)
        return message


_PROTO_JSON_CODEC = _ProtoJSONCodec()


class GatewayProblemError(ConnectError):
    """A gateway answer that is not a Connect error, as a ``ConnectError``.

    ``message`` is the problem ``code`` (``TIMESTAMP_SKEW``), as before.
    ``problem_code``, ``detail``, ``http_status`` and ``violations`` keep the
    rest of the problem body for the error mapping.
    """

    def __init__(
        self,
        code: Code,
        problem_code: str,
        *,
        http_status: int,
        detail: str = "",
        violations: list[dict[str, object]] | None = None,
        problem=None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(code, problem_code)
        self.problem = problem
        self.retry_after = retry_after
        self.problem_code = problem_code
        self.http_status = http_status
        self.detail = detail
        self.violations = list(violations or [])


class _ConnectErrorWithRetryAfter(ConnectError):
    def __init__(self, message: str, details: list[AnyMessage], retry_after: float) -> None:
        super().__init__(Code.RESOURCE_EXHAUSTED, message, details)
        self.retry_after = retry_after


_CONNECT_CODES = frozenset(code.value for code in Code)
# HTTP status -> Connect code for a non-Connect error body (Connect protocol table).
_HTTP_STATUS_TO_CODE = {
    # A REST problem body at 400 is a refused request (VALIDATION_ERROR,
    # QTY_STEP_SIZE, ...), not a server failure.
    400: Code.INVALID_ARGUMENT,
    401: Code.UNAUTHENTICATED,
    403: Code.PERMISSION_DENIED,
    404: Code.UNIMPLEMENTED,
    # REST answers a precondition refusal (for example
    # AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED) with 412, Connect with failed_precondition.
    412: Code.FAILED_PRECONDITION,
    429: Code.UNAVAILABLE,
    502: Code.UNAVAILABLE,
    503: Code.UNAVAILABLE,
    504: Code.UNAVAILABLE,
}


def _raise_for_gateway_rejection(response: pyqwest.FullResponse) -> pyqwest.FullResponse:
    """Map an API-gateway rejection that is not a Connect error.

    The gateway answers API-key failures with a JSON body such as
    ``{"code": "TIMESTAMP_SKEW"}`` (``application/json`` or
    ``application/problem+json``). connectrpc would read that ``code`` as an
    unknown Connect code and report an ambiguous ``unavailable`` server error.
    Map it by HTTP status instead, keeping the gateway code as the message, so
    ``TIMESTAMP_SKEW`` and ``SIGNATURE_INVALID`` reach the error mapping.
    """
    if response.status == 200:
        return response
    content_type = response.headers.get("content-type", "").lower()
    body = None
    if "json" in content_type:
        with suppress(Exception):
            body = response.json()
    code = body.get("code") if isinstance(body, dict) else None
    retry_after = None
    for header, divisor in (
        ("retry-after", 1),
        ("retry-after-ms", 1000),
        ("grpc-retry-pushback-ms", 1000),
    ):
        with suppress(ValueError, TypeError):
            value = float(response.headers.get(header, "")) / divisor
            if isfinite(value) and value >= 0:
                retry_after = value
                break
    if isinstance(body, dict) and isinstance(code, str) and code in _CONNECT_CODES:
        if code == "resource_exhausted" and retry_after is not None:
            # Preserve valid Connect details while carrying response backoff
            # through a ConnectError, whose upstream type has no metadata.
            with suppress(ValueError, TypeError, KeyError):
                details = [
                    AnyMessage(
                        type_url="type.googleapis.com/" + d["type"],
                        value=b64decode(d["value"] + "==="),
                    )
                    for d in body.get("details", [])
                    if "type" in d and "value" in d
                ]
                error = _ConnectErrorWithRetryAfter(body.get("message", ""), details, retry_after)
                raise error
        return response
    # A non-Connect 504 cannot prove that a mutation was refused, even if
    # the gateway sent HTML, malformed JSON, or no structured code at all.
    if response.status != 504 and (
        not isinstance(body, dict) or not isinstance(code, str) or not code
    ):
        return response
    if not isinstance(body, dict):
        body = {}
    code = code if isinstance(code, str) else ""
    detail = body.get("detail")
    violations = body.get("violations")
    raise GatewayProblemError(
        _HTTP_STATUS_TO_CODE.get(response.status, Code.UNKNOWN),
        code,
        http_status=response.status,
        problem=decode_http_problem(body, response.status),
        retry_after=retry_after,
        detail=detail if isinstance(detail, str) else "",
        violations=(
            [item for item in violations if isinstance(item, dict)]
            if isinstance(violations, list)
            else None
        ),
    )


class _ConnectHTTPClient:
    """pyqwest client for generated Connect clients; see ``_raise_for_gateway_rejection``."""

    def __init__(self, inner: pyqwest.Client | None = None) -> None:
        self._inner = inner or pyqwest.Client()

    async def post(self, url: str, headers=None, content=None, **kwargs) -> pyqwest.FullResponse:
        response = await self._inner.post(url=url, headers=headers, content=content, **kwargs)
        return _raise_for_gateway_rejection(response)

    async def get(self, url: str, headers=None, **kwargs) -> pyqwest.FullResponse:
        response = await self._inner.get(url=url, headers=headers, **kwargs)
        return _raise_for_gateway_rejection(response)


def codec_for_config(config: TransportConfig):
    if config.wire_format == "json":
        return _PROTO_JSON_CODEC
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
        self.public_http = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=config.timeout,
            headers={USER_AGENT_HEADER: USER_AGENT},
        )
        self._codec = codec_for_config(config)
        self._connect_http = _ConnectHTTPClient()
        self._user_agent_interceptor = UserAgentUnaryInterceptor()
        self._auth_interceptors: list[UnaryInterceptor] = [self._user_agent_interceptor]
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

    def _client_kwargs(self) -> dict:
        return {
            "codec": self._codec,
            "timeout_ms": int(self.config.timeout * 1000),
            "read_max_bytes": MAX_CONNECT_RESPONSE_BYTES,
            # Signing hashes the protobuf/JSON body; gzip would break API-key auth.
            "send_compression": None,
            "http_client": self._connect_http,
        }

    def create_public_client(self, client_cls: type):
        return client_cls(
            self.config.api_url,
            interceptors=[self._user_agent_interceptor],
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
