"""Automatic signing timestamps stay within the server's future allowance.

The API refuses an API-key timestamp more than one second ahead of its clock
as ``TIMESTAMP_SKEW``.
"""

from __future__ import annotations

import time
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.auth import (
    MAX_SIGNING_FUTURE_SKEW_MS,
    ApiKeyCredentials,
    sign_request,
    sign_request_async,
)
from polyester.errors import PolyesterRateLimitError

SERVER_FUTURE_ALLOWANCE_MS = 1_000
URL = "https://api.example.test/v1/rt/token"


def _credentials() -> ApiKeyCredentials:
    return ApiKeyCredentials(
        key_id=f"key_future_allowance_{uuid.uuid4().hex}",
        private_key=Ed25519PrivateKey.generate().private_bytes_raw(),
    )


def test_ceiling_leaves_room_for_clock_skew_under_the_server_allowance() -> None:
    assert 0 < MAX_SIGNING_FUTURE_SKEW_MS < SERVER_FUTURE_ALLOWANCE_MS


def test_sync_burst_never_signs_beyond_the_server_allowance() -> None:
    credentials = _credentials()
    signed = 0
    for _ in range(2_000):
        try:
            headers = sign_request(credentials, method="GET", url=URL, body=b"")
        except PolyesterRateLimitError:
            # Capacity backpressure is the allowed outcome once the ceiling is reached.
            continue
        ahead = int(headers["X-API-TIMESTAMP"]) - time.time_ns() // 1_000_000
        assert ahead <= SERVER_FUTURE_ALLOWANCE_MS, f"signed {ahead} ms ahead"
        signed += 1
    assert signed > 0


async def test_async_burst_never_signs_beyond_the_server_allowance() -> None:
    credentials = _credentials()
    for _ in range(2_000):
        headers = await sign_request_async(credentials, method="GET", url=URL, body=b"")
        ahead = int(headers["X-API-TIMESTAMP"]) - time.time_ns() // 1_000_000
        assert ahead <= SERVER_FUTURE_ALLOWANCE_MS, f"signed {ahead} ms ahead"
