import httpx
import pytest

from polyester.auth import ApiKeyCredentials, canonical_signing_string, sign_request
from polyester.errors import PolyesterRealtimeError
from polyester.realtime.auth import (
    MAX_TOKEN_RESPONSE_BYTES,
    _content_length_exceeds_limit,
    connection_token_url,
    fetch_rt_token,
    subscription_token_url,
)


def test_connection_token_url() -> None:
    assert (
        connection_token_url("https://api-devnet.polyester.ai")
        == "https://api-devnet.polyester.ai/v1/rt/token"
    )


def test_subscription_token_url_encodes_channel() -> None:
    channel = "private:spot:orders:acct_test:proto"
    url = subscription_token_url("https://api-devnet.polyester.ai", channel)
    assert url.endswith("channel=private%3Aspot%3Aorders%3Aacct_test%3Aproto")


def test_realtime_token_signing_uses_get_with_empty_body_hash() -> None:
    channel = "private:spot:orders:acct-1:proto"
    url = subscription_token_url("https://api-devnet.polyester.ai", channel)
    canonical = canonical_signing_string(
        timestamp_ms="1234567890",
        method="GET",
        url=url,
        body=b"",
    )
    assert canonical.splitlines()[1] == "GET"
    assert "channel=private%3Aspot%3Aorders%3Aacct-1%3Aproto" in canonical
    empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert canonical.endswith(empty_hash)


def test_sign_request_headers_for_rt_subscribe() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate().private_bytes_raw()
    creds = ApiKeyCredentials(key_id="ak_test", private_key=private)
    url = subscription_token_url(
        "https://api-devnet.polyester.ai",
        "private:spot:orders:acct-1:proto",
    )
    headers = sign_request(creds, method="GET", url=url, body=b"", timestamp_ms="1")
    assert headers["X-API-KEY-ID"] == "ak_test"
    assert headers["X-API-TIMESTAMP"] == "1"
    assert len(headers["X-API-SIGNATURE"]) == 128


def test_content_length_above_cap_is_rejected() -> None:
    response = httpx.Response(200, headers={"content-length": str(MAX_TOKEN_RESPONSE_BYTES + 1)})
    assert _content_length_exceeds_limit(response, MAX_TOKEN_RESPONSE_BYTES)
    response = httpx.Response(200, headers={"content-length": "1024"})
    assert not _content_length_exceeds_limit(response, MAX_TOKEN_RESPONSE_BYTES)


@pytest.mark.asyncio
async def test_fetch_rt_token_rejects_oversized_body() -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate().private_bytes_raw()
    creds = ApiKeyCredentials(key_id="ak_test", private_key=private)
    oversized = b"x" * (MAX_TOKEN_RESPONSE_BYTES + 1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=oversized)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(PolyesterRealtimeError, match="exceeds"):
            await fetch_rt_token(
                http,
                creds,
                url="https://api.example.test/v1/rt/token",
                label="realtime connection token",
            )
