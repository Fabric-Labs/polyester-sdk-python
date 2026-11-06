import json
from pathlib import Path

import pytest

from polyester.auth import (
    ApiKeyCredentials,
    canonical_query,
    canonical_signing_string,
    sign_request,
    sign_request_async,
)

# Identical fixtures live in Go, Python and Rust. Expected queries follow
# the server's canonicalization: decoded key/value bytes sorted, then RFC 3986 escaped.
# The signed path is the decoded path: "canonical_path" names it where it is valid UTF-8.
# Golden signatures use the public test seed 00..1f, timestamp 123, GET, no body.
VECTORS = json.loads(
    (Path(__file__).parents[2] / "testdata/signing_query_vectors.json").read_text()
)


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
async def test_server_query_signing_vectors(vector: dict[str, str]) -> None:
    credentials = ApiKeyCredentials(key_id="test-key", private_key=bytes(range(32)))
    assert canonical_query(vector["url"]) == vector["canonical_query"]
    if "canonical_path" in vector:
        signed = canonical_signing_string(
            timestamp_ms="123", method="GET", url=vector["url"], body=b""
        )
        assert signed.split("\n")[2] == vector["canonical_path"]
    headers = sign_request(credentials, method="GET", url=vector["url"], timestamp_ms="123")
    assert headers["X-API-SIGNATURE"] == vector["signature_hex"]
    async_headers = await sign_request_async(
        credentials, method="GET", url=vector["url"], timestamp_ms="123"
    )
    assert async_headers == headers


def test_path_vectors_are_present_and_change_the_signature() -> None:
    """The path cases must exist, and escaping must not change what is signed."""
    by_name = {vector["name"]: vector for vector in VECTORS}
    assert sum(name.startswith("path-") for name in by_name) >= 10
    assert by_name["path-escaped-slash"]["signature_hex"] == (
        by_name["path-lowercase-hex"]["signature_hex"]
    )
    credentials = ApiKeyCredentials(key_id="test-key", private_key=bytes(range(32)))
    plain = sign_request(
        credentials,
        method="GET",
        url="https://api.example.test/v1/orders/open",
        timestamp_ms="123",
    )
    assert plain["X-API-SIGNATURE"] == by_name["path-unreserved-escape"]["signature_hex"]
