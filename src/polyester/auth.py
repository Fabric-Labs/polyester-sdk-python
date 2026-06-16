from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.errors import PolyesterAuthError

API_KEY_ID_ENV = "POLYESTER_API_KEY_ID"
API_PRIVATE_KEY_ENV = "POLYESTER_API_PRIVATE_KEY"
ACCOUNT_ID_ENV = "POLYESTER_ACCOUNT_ID"


@dataclass(frozen=True, slots=True)
class ApiKeyCredentials:
    key_id: str
    private_key: bytes


def load_api_key_credentials(
    *,
    api_key_id: str | None = None,
    api_private_key: str | bytes | None = None,
) -> ApiKeyCredentials | None:
    key_id = api_key_id or os.getenv(API_KEY_ID_ENV)
    private = api_private_key if api_private_key is not None else os.getenv(API_PRIVATE_KEY_ENV)
    if not key_id and not private:
        return None
    if not key_id or private is None:
        raise PolyesterAuthError(
            "Both POLYESTER_API_KEY_ID and POLYESTER_API_PRIVATE_KEY are required"
        )
    return ApiKeyCredentials(key_id=key_id, private_key=normalize_private_key(private))


def normalize_private_key(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        private = value
    else:
        try:
            private = bytes.fromhex(value.strip())
        except ValueError as exc:
            raise PolyesterAuthError(
                "API private key must be a valid hex string or raw bytes"
            ) from exc
    if len(private) != 32:
        raise PolyesterAuthError("Ed25519 API private key must be exactly 32 bytes")
    return private


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_query(url: str) -> str:
    pairs = []
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        pairs.append(f"{quote(key, safe='')}={quote(value, safe='')}")
    pairs.sort()
    return "&".join(pairs)


def canonical_signing_string(
    *,
    timestamp_ms: str,
    method: str,
    url: str,
    body: bytes,
) -> str:
    pathname = urlsplit(url).path or "/"
    return "\n".join(
        [timestamp_ms, method.upper(), pathname, canonical_query(url), sha256_hex(body)]
    )


def sign_request(
    credentials: ApiKeyCredentials,
    *,
    method: str,
    url: str,
    body: bytes = b"",
    timestamp_ms: str | None = None,
) -> dict[str, str]:
    timestamp = timestamp_ms or str(int(time.time() * 1000))
    canonical = canonical_signing_string(
        timestamp_ms=timestamp,
        method=method,
        url=url,
        body=body,
    )
    key = Ed25519PrivateKey.from_private_bytes(credentials.private_key)
    signature = key.sign(canonical.encode("utf-8")).hex()
    return {
        "X-API-KEY-ID": credentials.key_id,
        "X-API-TIMESTAMP": timestamp,
        "X-API-SIGNATURE": signature,
    }
