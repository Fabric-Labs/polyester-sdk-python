from __future__ import annotations

from urllib.parse import quote

import httpx

from polyester.auth import ApiKeyCredentials, sign_request
from polyester.errors import PolyesterAuthError, PolyesterRealtimeError


def connection_token_url(api_url: str) -> str:
    return f"{api_url.rstrip('/')}/v1/rt/token"


def subscription_token_url(api_url: str, channel: str) -> str:
    base = f"{api_url.rstrip('/')}/v1/rt/subscribe"
    return f"{base}?channel={quote(channel, safe='')}"


async def fetch_rt_token(
    http: httpx.AsyncClient,
    credentials: ApiKeyCredentials,
    *,
    url: str,
    label: str,
) -> str:
    headers = sign_request(credentials, method="GET", url=url, body=b"")
    response = await http.get(url, headers=headers)
    if response.status_code == 401:
        raise PolyesterAuthError(f"{label}: authentication failed")
    if response.status_code >= 400:
        raise PolyesterRealtimeError(f"{label}: HTTP {response.status_code}")
    payload = response.json()
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
