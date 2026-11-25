from __future__ import annotations

from collections.abc import Awaitable, Callable

from connectrpc.code import Code
from connectrpc.codec import Codec
from connectrpc.errors import ConnectError
from connectrpc.interceptor import UnaryInterceptor
from connectrpc.request import RequestContext
from google.protobuf.message import Message

from polyester.auth import ApiKeyCredentials, _sign_request_async
from polyester.user_agent import USER_AGENT, USER_AGENT_HEADER

# The request deadline the Connect protocol sends the server, in milliseconds.
_CONNECT_TIMEOUT_HEADER = "connect-timeout-ms"


def _deadline_exceeded() -> ConnectError:
    """The error connectrpc raises when a request's deadline passes in flight."""
    return ConnectError(Code.DEADLINE_EXCEEDED, "Request timed out")


class UserAgentUnaryInterceptor(UnaryInterceptor):
    """Attach the Polyester SDK User-Agent on every Connect unary call."""

    async def intercept_unary(
        self,
        call_next: Callable[[Message, RequestContext], Awaitable[Message]],
        request: Message,
        ctx: RequestContext,
    ) -> Message:
        ctx.request_headers()[USER_AGENT_HEADER] = USER_AGENT
        return await call_next(request, ctx)


class ApiKeyAuthUnaryInterceptor(UnaryInterceptor):
    """Attach Polyester API-key headers to generated Connect unary calls.

    The request's deadline starts before signing, so a wait for signing
    capacity (see ``_SigningTimestampAllocator``) spends its time: the wait
    ends at the deadline as the transport's own timeout does, before anything
    is sent, and the server is given only the time that is left.
    """

    def __init__(
        self,
        credentials: ApiKeyCredentials,
        *,
        base_url: str,
        codec: Codec,
        recv_window_ms: int | None = None,
    ) -> None:
        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._codec = codec
        self._recv_window_ms = recv_window_ms

    async def intercept_unary(
        self,
        call_next: Callable[[Message, RequestContext], Awaitable[Message]],
        request: Message,
        ctx: RequestContext,
    ) -> Message:
        info = ctx.method()
        url = f"{self._base_url}/{info.service_name}/{info.name}"
        body = self._codec.encode(request)
        remaining_ms = ctx.timeout_ms()
        try:
            headers = await _sign_request_async(
                self._credentials,
                method=ctx.http_method(),
                url=url,
                body=body,
                recv_window_ms=self._recv_window_ms,
                timeout=None if remaining_ms is None else remaining_ms / 1000,
            )
        except TimeoutError as exc:
            raise _deadline_exceeded() from exc
        request_headers = ctx.request_headers()
        request_headers.update(headers)
        remaining_ms = ctx.timeout_ms()
        if remaining_ms is not None:
            if remaining_ms <= 0:
                raise _deadline_exceeded()
            if _CONNECT_TIMEOUT_HEADER in request_headers:
                request_headers[_CONNECT_TIMEOUT_HEADER] = str(max(1, int(remaining_ms)))
        return await call_next(request, ctx)
