import json
from pathlib import Path

import pytest

from polyester.auth import ApiKeyCredentials, canonical_query, sign_request, sign_request_async

# Identical fixtures live in Go, Python and Rust. Expected queries follow
# server shared/pkg/auth/apikeys.go: decoded key/value sort, then RFC 3986 escape.
# Golden signatures use the public test seed 00..1f, timestamp 123, GET, no body.
VECTORS = json.loads(
    (Path(__file__).parents[2] / "testdata/signing_query_vectors.json").read_text()
)


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
async def test_server_query_signing_vectors(vector: dict[str, str]) -> None:
    credentials = ApiKeyCredentials(key_id="test-key", private_key=bytes(range(32)))
    assert canonical_query(vector["url"]) == vector["canonical_query"]
    headers = sign_request(credentials, method="GET", url=vector["url"], timestamp_ms="123")
    assert headers["X-API-SIGNATURE"] == vector["signature_hex"]
    async_headers = await sign_request_async(
        credentials, method="GET", url=vector["url"], timestamp_ms="123"
    )
    assert async_headers == headers
