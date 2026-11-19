from __future__ import annotations

import asyncio
import dataclasses
import re
from base64 import b64decode
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Literal, NoReturn

import httpx
import pyqwest
from connectrpc.code import Code
from connectrpc.codec import proto_binary_codec
from connectrpc.errors import ConnectError
from connectrpc.interceptor import UnaryInterceptor
from connectrpc.request import RequestContext
from google.protobuf.any_pb2 import Any as AnyMessage
from google.protobuf.json_format import MessageToJson, Parse
from google.protobuf.message import Message

from polyester._answer import retry_after_from_headers
from polyester._contract_codes import (
    carries_contract_code,
    decode_coded_detail,
    future_code_label,
    has_future_code,
    is_placeholder_code,
    is_recognised_rest_code,
    outcome_unknown_code,
)
from polyester._problem import decode_http_problem, loads_bounded, media_type_of
from polyester._redact import (
    redact_exception_chain,
    register,
    url_secrets,
    url_without_userinfo,
)
from polyester._redirects import carries_api_key, redirect_refusal
from polyester.auth import ApiKeyCredentials, validate_recv_window_ms
from polyester.auth_interceptor import ApiKeyAuthUnaryInterceptor, UserAgentUnaryInterceptor
from polyester.errors import PolyesterAuthError, PolyesterRedirectError, PolyesterTransportError
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
    ``problem_code``, ``detail``, ``http_status``, ``violations`` and
    ``rate_limit`` keep the rest of the problem body for the error mapping.
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
        rate_limit: object | None = None,
        cause_code: str = "",
        level_index: int | None = None,
        timestamp_window: object | None = None,
    ) -> None:
        super().__init__(code, problem_code)
        # A TIMESTAMP_SKEW problem's ``timestampWindow`` object, as sent.
        self.timestamp_window = timestamp_window
        # A refused ladder's ``causeCode`` and ``levelIndex``, when sent.
        self.cause_code = cause_code
        self.level_index = level_index
        self.problem = problem
        self.retry_after = retry_after
        # The problem's ``rate_limit`` object, as sent.
        self.rate_limit = rate_limit
        self.problem_code = problem_code
        self.http_status = http_status
        self.detail = detail
        self.violations = list(violations or [])


class _AnswerError(ConnectError):
    """A ConnectRPC error this SDK decoded from an answer itself, so the
    answer's metadata rides along: the upstream ``ConnectError`` carries no
    response status or headers. ``_raise_for_gateway_rejection`` records them."""

    http_status: int | None = None
    retry_after: float | None = None


def _retry_after_header(response: pyqwest.FullResponse) -> float | None:
    """The delay in seconds an answer asks for: ``Retry-After``, then
    ``Retry-After-Ms``, then ``Grpc-Retry-Pushback-Ms``; ``None`` without one."""
    return retry_after_from_headers(response.headers)


_CONNECT_CODES = frozenset(code.value for code in Code)
# HTTP status -> Connect code for a REST problem whose code the contract defines.
_HTTP_STATUS_TO_CODE = {
    # A REST problem body at 400 is a refused request (VALIDATION_ERROR,
    # QTY_STEP_SIZE, ...), not a server failure.
    400: Code.INVALID_ARGUMENT,
    401: Code.UNAUTHENTICATED,
    403: Code.PERMISSION_DENIED,
    404: Code.UNIMPLEMENTED,
    409: Code.ABORTED,
    # REST answers a precondition refusal (for example
    # AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED) with 412, Connect with failed_precondition.
    412: Code.FAILED_PRECONDITION,
    413: Code.INVALID_ARGUMENT,
    429: Code.UNAVAILABLE,
    501: Code.UNIMPLEMENTED,
    502: Code.UNAVAILABLE,
    503: Code.UNAVAILABLE,
    504: Code.UNAVAILABLE,
}


# HTTP status -> Connect code for an answer with no recognised code. Only a 401
# or 403 is a refusal on its status alone. The rest prove nothing about a
# mutation, so they stay ambiguous; these unavailable statuses also let reads
# retry. Every other status is Code.INTERNAL.
_NO_RECOGNISED_CODE_STATUS_TO_CODE = {
    401: Code.UNAUTHENTICATED,
    403: Code.PERMISSION_DENIED,
    429: Code.UNAVAILABLE,
    502: Code.UNAVAILABLE,
    503: Code.UNAVAILABLE,
    504: Code.UNAVAILABLE,
}

# Statuses that refuse a request whatever their code says.
_REFUSAL_STATUSES = frozenset({401, 403})
# A REST problem code in the contract's form. A new one at 429 is a refusal this
# SDK version can't name yet; anything else there isn't a code at all.
_REST_CODE_FORM = re.compile(r"[A-Z][A-Z0-9_]*")
_TYPE_URL_PREFIX = "type.googleapis.com/"

# Connect codes the contract never uses. None of them says a request was refused.
AMBIGUOUS_CONNECT_CODES = frozenset({"unknown", "data_loss", "canceled"})

# A router's own answer for a path it doesn't know.
ROUTE_NOT_FOUND_MESSAGES = frozenset({"not found", "404 page not found", "404 not found"})


def _connect_error_details(value: object) -> list[AnyMessage] | None:
    """Decode a Connect error's ``details``; ``None`` when they are malformed.

    A detail with no type or value is skipped, as the Connect client skips it.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        return None
    details = []
    for item in value:
        if not isinstance(item, dict):
            return None
        type_name = item.get("type")
        data = item.get("value")
        if type_name is None or data is None:
            continue
        if not isinstance(type_name, str) or not isinstance(data, str):
            return None
        try:
            raw = b64decode(data + "===")
        except ValueError:
            return None
        details.append(AnyMessage(type_url=_TYPE_URL_PREFIX + type_name, value=raw))
    return details


def _status_line(status: int) -> str:
    try:
        phrase = HTTPStatus(status).phrase
    except ValueError:
        phrase = ""
    return f"{status} {phrase}".strip()


def _unreadable_connect_error(status: int) -> ConnectError:
    """Report a Connect body that can't be read by its HTTP status alone."""
    return ConnectError(
        _NO_RECOGNISED_CODE_STATUS_TO_CODE.get(status, Code.INTERNAL), _status_line(status)
    )


def _body_text(body: object, status: int) -> str:
    """The body's own words for an error, or its status line."""
    if isinstance(body, dict):
        for key in ("message", "detail", "title"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return _status_line(status)


def _is_bare_404(response: pyqwest.FullResponse, body: object, is_json: bool) -> bool:
    """A 404 no service wrote: not JSON, empty, or a router's own message."""
    if not is_json or not response.content:
        return True
    message = body.get("message") if isinstance(body, dict) else None
    return isinstance(message, str) and message.strip().lower() in ROUTE_NOT_FOUND_MESSAGES


def _no_recognised_code_error(
    response: pyqwest.FullResponse, body: object, *, code: str = ""
) -> ConnectError:
    """Report an answer with no recognised code by its HTTP status.

    A gateway or an edge can send any of these, so none of them proves that a
    mutation was refused. ``code`` is kept for diagnosis only.
    """
    status = response.status
    known = _NO_RECOGNISED_CODE_STATUS_TO_CODE.get(status)
    message = _body_text(body, status)
    retry_after = _retry_after_header(response)
    if known is None or (code and status != 429):
        return GatewayProblemError(
            known or Code.INTERNAL,
            code,
            http_status=status,
            detail=message,
            problem=decode_http_problem(body, status),
            retry_after=retry_after,
        )
    return _AnswerError(known, message)


def _connect_code_for_status(status: int) -> Code:
    """The code Connect reads an answer with no readable code as, by status."""
    return {
        400: Code.INTERNAL,
        401: Code.UNAUTHENTICATED,
        403: Code.PERMISSION_DENIED,
        404: Code.UNIMPLEMENTED,
        429: Code.UNAVAILABLE,
        502: Code.UNAVAILABLE,
        503: Code.UNAVAILABLE,
        504: Code.UNAVAILABLE,
    }.get(status, Code.UNKNOWN)


def _raise_for_gateway_rejection(response: pyqwest.FullResponse) -> pyqwest.FullResponse:
    """Classify a failed answer; whatever error it raises carries the answer's
    metadata, its HTTP status and the delay it asked for, captured here once."""
    try:
        return _classify_failed_answer(response)
    except ConnectError as exc:
        if getattr(exc, "http_status", None) is None:
            exc.http_status = response.status  # type: ignore[attr-defined]
        if getattr(exc, "retry_after", None) is None:
            exc.retry_after = _retry_after_header(response)  # type: ignore[attr-defined]
        raise


def _classify_failed_answer(response: pyqwest.FullResponse) -> pyqwest.FullResponse:
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
    is_json = "json" in response.headers.get("content-type", "").lower()
    body = None
    if is_json:
        with suppress(Exception):
            body = response.json()
        if body is None:
            # A body the default parser refuses, such as one with an integer
            # too long to convert, may still name its code.
            with suppress(Exception):
                body = loads_bounded(bytes(response.content))
    code = body.get("code") if isinstance(body, dict) else None
    retry_after = _retry_after_header(response)
    status = response.status
    has_connect_code = isinstance(code, str) and code in _CONNECT_CODES
    has_no_code = not isinstance(code, str) or not code or is_placeholder_code(code)
    details: list[AnyMessage] = []
    if isinstance(body, dict) and (has_connect_code or has_no_code):
        # The Connect client decodes both of these bodies, and neither its
        # decoder nor the error mapping tolerates a malformed one.
        decoded = _connect_error_details(body.get("details"))
        message = body.get("message")
        if decoded is None or not isinstance(message, str | None):
            raise _unreadable_connect_error(status)
        details = decoded
    if status == 504:
        # The HTTP status decides outcome certainty first. A 504 never proves
        # a refusal: the API answers it only where a write's outcome is
        # unknown, and an edge answers it for a request that may have reached
        # the API. So before any code, message or typed detail is read for a
        # refusal, it is an unknown outcome that safe reads retry: the
        # outcome-unknown code the answer names, else a server error. No
        # body, a ConnectRPC code, a retryable rate-limit, admission or
        # authentication code, or a typed detail included, changes that.
        rest_code = code if isinstance(code, str) and code not in _CONNECT_CODES else ""
        outcome = _outcome_unknown_name(code, body, details)
        # ConnectRPC answers its own deadline_exceeded with 504: the request's
        # deadline passed, read as the deadline it is, whatever its message
        # or detail says. Still an unknown outcome that reads retry.
        deadline = not outcome and code == "deadline_exceeded"
        _raise_problem(
            response,
            body,
            outcome or rest_code or _future_code(details),
            Code.DEADLINE_EXCEEDED if deadline else Code.UNAVAILABLE,
            retry_after,
        )
    if has_connect_code:
        # These say nothing a 401 or 403 doesn't already say better.
        if (
            code in AMBIGUOUS_CONNECT_CODES
            and status in _REFUSAL_STATUSES
            and not _has_service_detail(details)
        ):
            raise _no_recognised_code_error(response, body)
        # Decoded here, as Connect would, so the answer's metadata rides along.
        raise _AnswerError(
            Code(code),
            str((body.get("message") if isinstance(body, dict) else None) or ""),
            details,
        )
    if has_no_code:
        return _answer_without_a_code(response, body, is_json, code, details)
    assert isinstance(code, str)
    if is_recognised_rest_code(code) or (status == 429 and _REST_CODE_FORM.fullmatch(code)):
        fallback = Code.INTERNAL if status >= 500 else Code.FAILED_PRECONDITION
        _raise_problem(
            response, body, code, _HTTP_STATUS_TO_CODE.get(status, fallback), retry_after
        )
    if status in _REFUSAL_STATUSES:
        _raise_problem(
            response, body, code, _NO_RECOGNISED_CODE_STATUS_TO_CODE[status], retry_after
        )
    raise _no_recognised_code_error(response, body, code=code)


def _outcome_unknown_name(code: object, body: object, details: list[AnyMessage]) -> str:
    """The outcome-unknown code an answer names, or ``""``: a REST problem's
    code, a ConnectRPC error's code-only message, or an order detail's code."""
    if isinstance(code, str) and code.endswith("_OUTCOME_UNKNOWN"):
        return code
    message = body.get("message") if isinstance(body, dict) else None
    if isinstance(message, str) and message.strip().endswith("_OUTCOME_UNKNOWN"):
        return message.strip()
    for d in details:
        name = outcome_unknown_code(d.type_url.removeprefix(_TYPE_URL_PREFIX), d.value)
        if name:
            return name
    return ""


def _has_service_detail(details: list[AnyMessage]) -> bool:
    return any(
        carries_contract_code(d.type_url.removeprefix(_TYPE_URL_PREFIX), d.value) for d in details
    )


def _answer_without_a_code(
    response: pyqwest.FullResponse,
    body: object,
    is_json: bool,
    code: object,
    details: list[AnyMessage],
) -> pyqwest.FullResponse:
    """Report an answer with no code by its status, as Connect reads it."""
    status = response.status
    if status < 400:
        return response
    message = body.get("message") if isinstance(body, dict) else None
    message = message if isinstance(message, str) else ""
    if _has_service_detail(details) or (
        status in _NO_RECOGNISED_CODE_STATUS_TO_CODE and code in (None, "")
    ):
        # What Connect reads by status, decoded here so the answer's metadata
        # rides along. A body that is not JSON, or JSON that does not parse,
        # reads by its status alone.
        raise _AnswerError(
            _connect_code_for_status(status), message or _status_line(status), details
        )
    # Connect reads this as unimplemented, which the error mapping names a
    # missing route.
    if status == 404 and _is_bare_404(response, body, is_json):
        raise _AnswerError(Code.UNIMPLEMENTED, "not found", [])
    raise _no_recognised_code_error(response, body, code=_future_code(details))


def _future_code(details: list[AnyMessage]) -> str:
    """The label of a typed code this SDK can't name, kept for diagnosis only."""
    for item in details:
        detail = decode_coded_detail(item.type_url.removeprefix(_TYPE_URL_PREFIX), item.value)
        if detail is not None and has_future_code(detail):
            return future_code_label(detail)
    return ""


def _problem_with_media_type(problem, content_type: str | None):
    if problem is None:
        return None
    return dataclasses.replace(problem, media_type=media_type_of(content_type))


def _raise_problem(
    response: pyqwest.FullResponse,
    body: object,
    code: str,
    connect_code: Code,
    retry_after: float | None,
) -> NoReturn:
    if not isinstance(body, dict):
        body = {}
    detail = body.get("detail")
    violations = body.get("violations")
    cause_code = body.get("causeCode")
    level_index = body.get("levelIndex")
    raise GatewayProblemError(
        connect_code,
        code,
        http_status=response.status,
        problem=_problem_with_media_type(
            decode_http_problem(body, response.status), response.headers.get("content-type")
        ),
        retry_after=retry_after,
        rate_limit=body.get("rateLimit"),
        timestamp_window=body.get("timestampWindow"),
        cause_code=cause_code if isinstance(cause_code, str) else "",
        level_index=(
            level_index
            if isinstance(level_index, int)
            and not isinstance(level_index, bool)
            and 0 <= level_index < 2**32
            else None
        ),
        detail=detail if isinstance(detail, str) else "",
        violations=(
            [item for item in violations if isinstance(item, dict)]
            if isinstance(violations, list)
            else None
        ),
    )


class SignedRedirectRefused(ConnectError):
    """A redirect answering a signed request, as a ``ConnectError``.

    connectrpc passes a ``ConnectError`` from the HTTP client through, so the
    error mapping turns ``refusal`` into the :class:`PolyesterRedirectError`.
    """

    http_status: int | None = None
    retry_after: float | None = None

    def __init__(self, refusal: PolyesterRedirectError) -> None:
        super().__init__(Code.FAILED_PRECONDITION, str(refusal))
        self.refusal = refusal


_no_redirect_transport: pyqwest.HTTPTransport | None = None


def _new_http_transport(*, follow_redirects: bool = True) -> pyqwest.HTTPTransport:
    """A transport with pyqwest's default settings and a connection pool of its own."""
    return pyqwest.HTTPTransport(
        tls_include_system_certs=True,
        connect_timeout=30.0,
        pool_idle_timeout=90.0,
        tcp_keepalive_interval=30.0,
        follow_redirects=follow_redirects,
    )


def _signed_transport() -> pyqwest.HTTPTransport:
    """pyqwest's default transport settings, but never following a redirect.

    One per process, as pyqwest's default transport is.
    """
    global _no_redirect_transport
    if _no_redirect_transport is None:
        _no_redirect_transport = _new_http_transport(follow_redirects=False)
    return _no_redirect_transport


# Response headers that name a response at the edge, most specific first.
_RESPONSE_REF_HEADERS = ("cf-ray", "x-request-id")
_response_refs: ContextVar[list[str] | None] = ContextVar("polyester_response_refs", default=None)


@contextmanager
def capture_response_refs() -> Iterator[list[str]]:
    """Collect the edge reference of every response the calls made inside receive."""
    refs: list[str] = []
    token = _response_refs.set(refs)
    try:
        yield refs
    finally:
        _response_refs.reset(token)


def _record_response_ref(response: pyqwest.FullResponse | pyqwest.Response) -> None:
    refs = _response_refs.get()
    if refs is None:
        return
    for header in _RESPONSE_REF_HEADERS:
        value = response.headers.get(header)
        if value:
            refs.append(value.strip())
            return


class _ConnectHTTPClient:
    """pyqwest client for generated Connect clients; see ``_raise_for_gateway_rejection``.

    It drops URL userinfo before sending. pyqwest never sends it, and its
    connection errors would quote it, password included.

    A request carrying API-key headers goes through ``signed``, a client that
    never follows a redirect, and a redirect answering it raises
    :class:`SignedRedirectRefused`. Unsigned requests go through ``inner``,
    pyqwest's default client, which follows redirects as before.

    An answer's metadata, its status and the delay it asked for, is read when
    its headers arrive, before its body and before any redirect is refused, so
    every error made from that answer carries it: one whose body is cut short,
    is too large to inspect or does not arrive before the deadline included.
    """

    def __init__(
        self, inner: pyqwest.Client | None = None, *, signed: pyqwest.Client | None = None
    ) -> None:
        self._inner = inner or pyqwest.Client()
        self._signed = signed or pyqwest.Client(_signed_transport())

    async def post(self, url: str, headers=None, content=None, **kwargs) -> pyqwest.FullResponse:
        return await self._send("POST", url, headers, content, **kwargs)

    async def get(self, url: str, headers=None, **kwargs) -> pyqwest.FullResponse:
        return await self._send("GET", url, headers, None, **kwargs)

    async def _send(
        self, method: str, url: str, headers: Any, content: Any, **kwargs: Any
    ) -> pyqwest.FullResponse:
        target = url_without_userinfo(url)
        signed = carries_api_key(headers)
        client = self._signed if signed else self._inner
        async with client.stream(method, target, headers, content, **kwargs) as response:
            return await _full_answer(response, target, signed=signed)


# The most of a failed answer's body read to classify it. A longer one is read
# by its status alone, as one that cannot be read is.
MAX_FAILED_ANSWER_BYTES = 64 * 1024
# The attribute that hands a failed answer whose body the deadline cut off to
# the error mapping, on the cancellation the deadline raised.
UNREAD_ANSWER_ATTR = "_polyester_unread_answer"


async def _full_answer(
    response: pyqwest.Response, target: str, *, signed: bool
) -> pyqwest.FullResponse:
    """Read ``response`` whole, or raise the error its answer maps to.

    The answer's metadata is taken from its headers before anything else is
    read or decided.
    """
    status = response.status
    headers = response.headers
    _record_response_ref(response)
    if signed:
        _refuse_redirect(status, headers, target)
    if status == 200:
        content = b"".join([bytes(chunk) async for chunk in response.content])
        return pyqwest.FullResponse(status, headers, content, response.trailers)
    try:
        failed_body = await _failed_answer_body(response)
    except asyncio.CancelledError as exc:
        # The deadline (or the caller) ended the call while the body was
        # read: the answer still decides the error, should the deadline be
        # why (see map_connect_error).
        setattr(exc, UNREAD_ANSWER_ATTR, unread_answer_error(status, headers))
        raise
    if failed_body is None:
        raise unread_answer_error(status, headers)
    return _raise_for_gateway_rejection(
        pyqwest.FullResponse(status, headers, failed_body, response.trailers)
    )


async def _failed_answer_body(response: pyqwest.Response) -> bytes | None:
    """A failed answer's body, or ``None`` when it cannot be read whole: cut
    short, broken, or longer than ``MAX_FAILED_ANSWER_BYTES``."""
    with suppress(ValueError, TypeError):
        if int(response.headers.get("content-length", "")) > MAX_FAILED_ANSWER_BYTES:
            return None
    chunks: list[bytes] = []
    total = 0
    try:
        async for chunk in response.content:
            total += len(chunk)
            if total > MAX_FAILED_ANSWER_BYTES:
                return None
            chunks.append(bytes(chunk))
    except Exception:
        return None
    return b"".join(chunks)


def unread_answer_error(status: int, headers: pyqwest.Headers) -> ConnectError:
    """The error of a failed answer whose body cannot be read: read by its
    status alone, with the answer's metadata."""
    try:
        _raise_for_gateway_rejection(pyqwest.FullResponse(status, headers, b"", pyqwest.Headers()))
    except ConnectError as exc:
        return exc
    # An answer below 400 that is no redirect: Connect reads it by status.
    error = _AnswerError(_connect_code_for_status(status), _status_line(status))
    error.http_status = status
    error.retry_after = retry_after_from_headers(headers)
    return error


def _refuse_redirect(status: int, headers: pyqwest.Headers, url: str) -> None:
    refusal = redirect_refusal(status, headers.get("location"), url)
    if refusal is not None:
        refusal.retry_after = retry_after_from_headers(headers)
        error = SignedRedirectRefused(refusal)
        error.http_status = status
        error.retry_after = refusal.retry_after
        raise error


class _CancellationUnaryInterceptor(UnaryInterceptor):
    """End a call the caller cancelled with ``CancelledError``, never an SDK error.

    connectrpc reports a call cancelled in flight as ``ConnectError`` with code
    ``canceled``, raised from the ``CancelledError``. On Python 3.11 its
    ``asyncio.wait_for`` can also drop a cancellation that lands as the answer
    arrives. Either way the task's ``cancelling()`` count shows the request, so
    the call ends cancelled: ``asyncio.timeout`` then raises ``TimeoutError``
    and a cancelled task stops. A ``canceled`` answer from the server, with no
    cancellation of the caller, stays an error.
    """

    async def intercept_unary(
        self,
        call_next: Callable[[Message, RequestContext], Awaitable[Message]],
        request: Message,
        ctx: RequestContext,
    ) -> Message:
        task = asyncio.current_task()
        cancelling = task.cancelling() if task is not None else 0
        try:
            response = await call_next(request, ctx)
        except ConnectError as exc:
            cancelled = exc.__cause__
            if exc.code is Code.CANCELED and isinstance(cancelled, asyncio.CancelledError):
                raise cancelled from None
            if task is not None and task.cancelling() > cancelling:
                raise asyncio.CancelledError() from exc
            raise
        if task is not None and task.cancelling() > cancelling:
            raise asyncio.CancelledError()
        return response


def codec_for_config(config: TransportConfig):
    if config.wire_format == "json":
        return _PROTO_JSON_CODEC
    return proto_binary_codec()


@dataclass(frozen=True, slots=True)
class TransportConfig:
    api_url: str
    timeout: float = 10.0
    wire_format: WireFormat = "binary"
    # Receive window of every signed ConnectRPC request, in milliseconds (1 to
    # 60000), sent as the signed X-API-RECV-WINDOW header. None sends none, and
    # the server applies 5000.
    recv_window_ms: int | None = None

    def __post_init__(self) -> None:
        validate_recv_window_ms(self.recv_window_ms)

    def __repr__(self) -> str:
        return (
            f"TransportConfig(api_url={url_without_userinfo(self.api_url)!r}, "
            f"timeout={self.timeout!r}, "
            f"wire_format={self.wire_format!r}, recv_window_ms={self.recv_window_ms!r})"
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
        # Client-held secrets never reach an error's text (see _redact), until
        # aclose forgets them.
        secrets = url_secrets(config.api_url)
        if credentials is not None:
            secrets += [credentials.private_key.hex(), credentials.private_key[:32].hex()]
        self._release_secrets = register(*secrets)
        self.public_http = httpx.AsyncClient(
            base_url=config.api_url,
            timeout=config.timeout,
            headers={USER_AGENT_HEADER: USER_AGENT},
        )
        self._codec = codec_for_config(config)
        self._connect_http = _ConnectHTTPClient()
        # Builds the transport of a fresh connection; see fresh_public_client.
        self._new_http_transport: Callable[[], pyqwest.HTTPTransport] = _new_http_transport
        # Outermost, so no other interceptor sees a cancellation as an error.
        self._public_interceptors: list[UnaryInterceptor] = [
            _CancellationUnaryInterceptor(),
            UserAgentUnaryInterceptor(),
        ]
        self._auth_interceptors: list[UnaryInterceptor] = list(self._public_interceptors)
        if credentials is not None:
            self._auth_interceptors.append(
                ApiKeyAuthUnaryInterceptor(
                    credentials,
                    base_url=config.api_url,
                    codec=self._codec,
                    recv_window_ms=config.recv_window_ms,
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
            interceptors=self._public_interceptors,
            **self._client_kwargs(),
        )

    @asynccontextmanager
    async def fresh_public_client(self, client_cls: type) -> AsyncIterator[Any]:
        """A public client on a connection pool of its own, closed on exit.

        Requests through it open a new connection, so a read retried through
        it can't queue behind a connection that dropped or stalled: an HTTP/2
        connection carries every request to the host, a stalled one included.
        """
        transport = self._new_http_transport()
        try:
            http = pyqwest.Client(transport)
            yield client_cls(
                self.config.api_url,
                interceptors=self._public_interceptors,
                **{**self._client_kwargs(), "http_client": _ConnectHTTPClient(http, signed=http)},
            )
        finally:
            await transport.aclose()

    def create_auth_client(self, client_cls: type):
        if self.credentials is None:
            raise PolyesterAuthError("This endpoint requires Polyester API-key credentials")
        return client_cls(
            self.config.api_url,
            interceptors=self._auth_interceptors,
            **self._client_kwargs(),
        )

    async def aclose(self) -> None:
        self._release_secrets()
        await self.public_http.aclose()


def map_transport_error(exc: Exception) -> PolyesterTransportError:
    redact_exception_chain(exc)
    return PolyesterTransportError(str(exc))
