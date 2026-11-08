from __future__ import annotations

import asyncio
import json
from urllib.parse import quote

import httpx

from polyester._problem import decode_http_problem
from polyester._redact import url_without_userinfo
from polyester.auth import ApiKeyCredentials, sign_request_async
from polyester.errors import (
    TIMESTAMP_SKEW,
    PolyesterAuthError,
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
    try:
        payload = json.loads(body)
        problem = decode_http_problem(payload, status_code)
        if isinstance(payload, dict):
            raw_code = payload.get("code")
            raw_message = payload.get("message")
            if isinstance(raw_code, str) and raw_code.strip():
                code = raw_code.strip()
            if isinstance(raw_message, str) and raw_message.strip():
                server_message = raw_message.strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    if code == TIMESTAMP_SKEW:
        skew_error = PolyesterTimestampSkewError(
            f"{label}: {TIMESTAMP_SKEW}", status_code=status_code
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


def _without_userinfo(http: httpx.AsyncClient, url: str) -> tuple[httpx.URL, httpx.Auth | None]:
    """``url`` without userinfo, and the Basic auth httpx would derive from it.

    httpx logs a request's URL and keeps it on its errors, password included.
    It turns URL userinfo into Basic auth unless the client has its own auth,
    so send that Basic auth explicitly and leave the userinfo out of the URL.
    ``None`` means keep the client's default.
    """
    target = httpx.URL(url)
    if not (target.username or target.password):
        return target, None
    auth = httpx.BasicAuth(target.username, target.password) if http.auth is None else None
    return target.copy_with(userinfo=b""), auth


async def signed_get(
    http: httpx.AsyncClient,
    credentials: ApiKeyCredentials,
    *,
    url: str,
    label: str,
    max_bytes: int,
) -> bytes:
    """One API-key-signed GET; 401 and 403 raise ``PolyesterAuthError``."""
    headers = await sign_request_async(credentials, method="GET", url=url, body=b"")
    # One absolute wall-clock deadline covers request headers + bounded body.
    # httpx per-phase timeouts alone are insufficient: slow-drip chunks can each
    # arrive within the read timeout while the total exceeds the SDK budget.
    timeout = _client_timeout_seconds(http)
    try:
        async with asyncio.timeout(timeout):
            target, auth = _without_userinfo(http, url)
            stream = (
                http.stream("GET", target, headers=headers)
                if auth is None
                else http.stream("GET", target, headers=headers, auth=auth)
            )
            async with stream as response:
                try:
                    raw = await _read_limited(response, max_bytes, label=label)
                except asyncio.CancelledError:
                    # Ensure the streamed peer is aborted promptly on cancel (E6).
                    await response.aclose()
                    raise
                if response.status_code == 403 and is_cloudflare_browser_ban(
                    raw.decode("utf-8", errors="replace")
                ):
                    raise PolyesterTransportError(cloudflare_1010_message())
                if response.status_code in (401, 403):
                    raise _auth_http_error(
                        status_code=response.status_code,
                        label=label,
                        endpoint=url_without_userinfo(url),
                        body=raw,
                    )
                if response.status_code >= 400:
                    truncated = _truncate_body(raw)
                    detail = f": {truncated}" if truncated else ""
                    raise PolyesterRealtimeError(f"{label}: HTTP {response.status_code}{detail}")
    except TimeoutError as exc:
        raise PolyesterRealtimeError(f"{label}: timed out") from exc
    except httpx.TimeoutException as exc:
        raise PolyesterRealtimeError(f"{label}: timed out") from exc
    return raw


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
    except json.JSONDecodeError as exc:
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
