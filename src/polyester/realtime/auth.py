from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from urllib.parse import quote

import httpx

from polyester._answer import attach_answer
from polyester._problem import decode_http_problem, loads_bounded
from polyester._redact import url_for_error, url_without_userinfo
from polyester._redirects import redirect_refusal
from polyester.auth import ApiKeyCredentials, sign_request_async
from polyester.codecs.timestamp_window import timestamp_window_from_json
from polyester.errors import (
    TIMESTAMP_SKEW,
    PolyesterAuthError,
    PolyesterError,
    PolyesterRealtimeError,
    PolyesterTimestampSkewError,
    PolyesterTransportError,
)
from polyester.user_agent import cloudflare_1010_message, is_cloudflare_browser_ban

MAX_TOKEN_RESPONSE_BYTES = 64 * 1024
_MAX_ERROR_BODY_CHARS = 512
_DEFAULT_TIMEOUT_SECONDS = 10.0


def connection_token_url(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/v1/rt/token"


def subscription_token_url(api_url: str, channel: str) -> str:
    base = f"{api_url.rstrip('/')}/v1/rt/subscribe"
    return f"{base}?channel={quote(channel, safe='')}"


def _client_timeout_seconds(http: httpx.AsyncClient) -> float:
    """Resolve the SDK-configured timeout as one absolute wall-clock budget."""
    timeout = http.timeout
    if timeout is None:
        return _DEFAULT_TIMEOUT_SECONDS
    if isinstance(timeout, (int, float)):
        return float(timeout)
    for name in ("read", "write", "connect", "pool"):
        value = getattr(timeout, name, None)
        if isinstance(value, (int, float)):
            return float(value)
    return _DEFAULT_TIMEOUT_SECONDS


def _content_length_exceeds_limit(response: httpx.Response, max_bytes: int) -> bool:
    raw = response.headers.get("content-length")
    if raw is None:
        return False
    try:
        return int(raw) > max_bytes
    except ValueError:
        return False


def _truncate_body(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    if len(text) > _MAX_ERROR_BODY_CHARS:
        return text[:_MAX_ERROR_BODY_CHARS] + "…"
    return text


async def _read_limited(response: httpx.Response, max_bytes: int, *, label: str) -> bytes:
    if _content_length_exceeds_limit(response, max_bytes):
        raise PolyesterRealtimeError(f"{label}: response exceeds {max_bytes} bytes")
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise PolyesterRealtimeError(f"{label}: response exceeds {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _auth_http_error(
    *,
    status_code: int,
    label: str,
    endpoint: str,
    body: bytes,
) -> PolyesterAuthError | PolyesterTimestampSkewError:
    truncated = _truncate_body(body)
    code: str | None = None
    server_message: str | None = None
    problem = None
    payload: object = None
    try:
        payload = loads_bounded(body)
        problem = decode_http_problem(payload, status_code)
        if isinstance(payload, dict):
            raw_code = payload.get("code")
            raw_message = payload.get("message")
            if isinstance(raw_code, str) and raw_code.strip():
                code = raw_code.strip()
            if isinstance(raw_message, str) and raw_message.strip():
                server_message = raw_message.strip()
    except ValueError:
        # Not JSON, not UTF-8 or unreadable: the refusal reads by its status.
        pass
    if code == TIMESTAMP_SKEW:
        skew_error = PolyesterTimestampSkewError(
            f"{label}: {TIMESTAMP_SKEW}",
            status_code=status_code,
            timestamp_window=timestamp_window_from_json(
                payload.get("timestampWindow") if isinstance(payload, dict) else None
            ),
        )
        skew_error.problem = problem
        return skew_error
    code = code or ("permission_denied" if status_code == 403 else "unauthenticated")
    kind = "permission denied" if status_code == 403 else "authentication failed"
    detail = problem.detail if problem is not None else server_message or truncated
    message = f"{label}: {kind} (HTTP {status_code}, code {code})"
    if detail:
        message = f"{message}: {detail}"
    message = f"{message} [{endpoint}]"
    error = PolyesterAuthError(
        message,
        status_code=status_code,
        label=label,
        body=truncated or None,
        code=code,
        context=label,
        endpoint=endpoint,
    )
    error.problem = problem
    return error


# The answers a signed GET in this task received, recorded by a response hook:
# httpx runs it when an answer's headers arrive, before it reads the body or a
# redirect's Location, either of which can fail.
_answers: ContextVar[list[httpx.Response] | None] = ContextVar(
    "polyester_signed_answers", default=None
)


async def _record_answer(response: httpx.Response) -> None:
    answers = _answers.get()
    if answers is not None:
        answers.append(response)


def _capture_answers(http: httpx.AsyncClient) -> None:
    """Have ``http`` record each answer a signed GET receives (see ``_answers``).

    The hook records nothing outside a signed GET, so ``http`` is otherwise
    unchanged.
    """
    hooks = http.event_hooks
    if _record_answer not in hooks.get("response", []):
        http.event_hooks = {**hooks, "response": [*hooks.get("response", []), _record_answer]}


def _userinfo_auth(http: httpx.AsyncClient, url: str) -> httpx.Auth | None:
    """The Basic auth httpx would derive from ``url``'s userinfo, or ``None``.

    httpx logs a request's URL and keeps it on its errors, password included,
    so the SDK gives it the URL without userinfo and sends this auth instead.
    httpx prefers the client's own auth, and so does this.
    """
    if http.auth is not None:
        return None
    parsed = httpx.URL(url)
    if not (parsed.username or parsed.password):
        return None
    return httpx.BasicAuth(parsed.username, parsed.password)


async def signed_get(
    http: httpx.AsyncClient,
    credentials: ApiKeyCredentials,
    *,
    url: str,
    label: str,
    max_bytes: int,
) -> bytes:
    """One API-key-signed GET; 401 and 403 raise ``PolyesterAuthError``."""
    # Drop userinfo before anything can quote the URL: signing refuses a
    # malformed URL by naming it, and httpx logs the URL it requests. Only the
    # path and query are signed, so the signature is the same.
    target = url_without_userinfo(url)
    headers = await sign_request_async(credentials, method="GET", url=target, body=b"")
    auth = _userinfo_auth(http, url) if target != url else None
    # One absolute wall-clock deadline covers request headers + bounded body.
    # httpx per-phase timeouts alone are insufficient: slow-drip chunks can each
    # arrive within the read timeout while the total exceeds the SDK budget.
    timeout = _client_timeout_seconds(http)
    # Each answer is recorded when its headers arrive: whatever then cuts its
    # body off, or makes its Location unreadable, the deadline included, the
    # error made from a failed answer carries its status and delay.
    _capture_answers(http)
    answers: list[httpx.Response] = []
    recording = _answers.set(answers)
    try:
        async with asyncio.timeout(timeout):
            # Never follow a redirect, whatever the client's own setting: it
            # would carry the signed headers to the redirect target.
            stream = (
                http.stream("GET", target, headers=headers, follow_redirects=False)
                if auth is None
                else http.stream("GET", target, headers=headers, auth=auth, follow_redirects=False)
            )
            async with stream as response:
                try:
                    return await _read_signed_answer(
                        response, url=url, target=target, label=label, max_bytes=max_bytes
                    )
                except PolyesterError as error:
                    # Every error from a failed answer carries its status and delay.
                    if response.status_code >= 300:
                        attach_answer(error, response.status_code, response.headers)
                    raise
    except httpx.TransportError as exc:
        # The body was cut short or broken, or a redirect's Location could
        # not be read: a failed answer reads by its status alone.
        failed = _failed_answer(answers)
        if failed is not None:
            raise _unread_answer_error(failed, url=url, target=target, label=label) from exc
        if isinstance(exc, httpx.TimeoutException):
            raise PolyesterRealtimeError(f"{label}: timed out") from exc
        raise
    except TimeoutError as exc:
        failed = _failed_answer(answers)
        if failed is not None:
            raise _unread_answer_error(failed, url=url, target=target, label=label) from exc
        raise PolyesterRealtimeError(f"{label}: timed out") from exc
    finally:
        _answers.reset(recording)


def _failed_answer(answers: list[httpx.Response]) -> httpx.Response | None:
    """The failed answer the signed GET received, if it received one."""
    if answers and answers[-1].status_code >= 300:
        return answers[-1]
    return None


def _unread_answer_error(
    response: httpx.Response, *, url: str, target: str, label: str
) -> PolyesterError:
    """The error of a failed answer whose body or Location could not be read:
    a refused redirect, or else its status alone, carrying the answer's
    metadata."""
    status = response.status_code
    error: PolyesterError | None = redirect_refusal(
        status, response.headers.get("location"), target
    )
    if error is None:
        error = _answer_error(status, b"", url=url, label=label)
    attach_answer(error, status, response.headers)
    return error


async def _read_signed_answer(
    response: httpx.Response, *, url: str, target: str, label: str, max_bytes: int
) -> bytes:
    """A signed GET's answer: its body when it succeeded, else the error it maps to."""
    refusal = redirect_refusal(response.status_code, response.headers.get("location"), target)
    if refusal is not None:
        raise refusal
    try:
        raw = await _read_limited(response, max_bytes, label=label)
    except asyncio.CancelledError:
        # Ensure the streamed peer is aborted promptly on cancel (E6).
        await response.aclose()
        raise
    if response.status_code >= 300:
        raise _answer_error(response.status_code, raw, url=url, label=label)
    return raw


def _answer_error(status: int, raw: bytes, *, url: str, label: str) -> PolyesterError:
    """The error a failed answer with this body maps to."""
    if status == 403 and is_cloudflare_browser_ban(raw.decode("utf-8", errors="replace")):
        return PolyesterTransportError(cloudflare_1010_message())
    if status in (401, 403):
        return _auth_http_error(
            status_code=status,
            label=label,
            endpoint=url_for_error(url),
            body=raw,
        )
    truncated = _truncate_body(raw)
    detail = f": {truncated}" if truncated else ""
    return PolyesterRealtimeError(f"{label}: HTTP {status}{detail}")


async def fetch_rt_token(
    http: httpx.AsyncClient,
    credentials: ApiKeyCredentials,
    *,
    url: str,
    label: str,
) -> str:
    raw = await signed_get(
        http, credentials, url=url, label=label, max_bytes=MAX_TOKEN_RESPONSE_BYTES
    )
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        # Not JSON, not UTF-8, or an integer too long to convert.
        raise PolyesterRealtimeError(f"{label}: response is not valid JSON") from exc
    token = payload.get("token") if isinstance(payload, dict) else None
    if not token:
        raise PolyesterRealtimeError(f"{label}: response missing token")
    return str(token)


async def fetch_connection_token(
    http: httpx.AsyncClient,
    credentials: ApiKeyCredentials,
    *,
    api_url: str,
) -> str:
    return await fetch_rt_token(
        http,
        credentials,
        url=connection_token_url(api_url),
        label="realtime connection token",
    )


async def fetch_subscription_token(
    http: httpx.AsyncClient,
    credentials: ApiKeyCredentials,
    *,
    api_url: str,
    channel: str,
) -> str:
    return await fetch_rt_token(
        http,
        credentials,
        url=subscription_token_url(api_url, channel),
        label=f"realtime subscription token for {channel}",
    )
