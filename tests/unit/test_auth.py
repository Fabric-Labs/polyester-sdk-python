import time
from concurrent.futures import ThreadPoolExecutor

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.auth import (
    API_PRIVATE_KEY_ENV,
    ApiKeyCredentials,
    canonical_query,
    canonical_signing_string,
    load_api_key_credentials,
    sign_request,
)


def test_canonical_query_sorts_and_encodes_values() -> None:
    assert (
        canonical_query("https://api.example.test/path?b=2&a=hello world") == "a=hello%20world&b=2"
    )


def test_canonical_query_preserves_hyphens_in_channel_param() -> None:
    assert (
        canonical_query(
            "https://api.example.test/v1/rt/subscribe?channel=private:auth:api-keys:account:proto"
        )
        == "channel=private%3Aauth%3Aapi-keys%3Aaccount%3Aproto"
    )


def test_canonical_query_shared_vectors() -> None:
    cases = [
        (
            "https://api.example.test/x?z=1&a=hello world&m=a+b",
            "a=hello%20world&m=a%20b&z=1",
        ),
        (
            "https://api.example.test/x?z=1&a=hello%20world&m=a%2Bb",
            "a=hello%20world&m=a%2Bb&z=1",
        ),
        ("https://api.example.test/x?b=&a=1", "a=1&b="),
        ("https://api.example.test/x?a=1&a=2&b=0", "a=1&a=2&b=0"),
        (
            "https://api.example.test/x?path=foo/bar&name=a_b.c~d-e",
            "name=a_b.c~d-e&path=foo%2Fbar",
        ),
        (
            "https://api.example.test/x?msg=%E2%9C%93&plain=ok",
            "msg=%E2%9C%93&plain=ok",
        ),
    ]
    for url, want in cases:
        assert canonical_query(url) == want, url


def test_canonical_signing_string_matches_contract() -> None:
    canonical = canonical_signing_string(
        timestamp_ms="123",
        method="post",
        url="https://api.example.test/foo/bar?b=2&a=1",
        body=b"{}",
    )
    assert canonical == "\n".join(
        [
            "123",
            "POST",
            "/foo/bar",
            "a=1&b=2",
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        ]
    )


def test_sign_request_returns_polyester_headers() -> None:
    private_key = Ed25519PrivateKey.generate()
    private = private_key.private_bytes_raw()
    headers = sign_request(
        ApiKeyCredentials(key_id="key_123", private_key=private),
        method="POST",
        url="https://api.example.test/foo",
        body=b"{}",
        timestamp_ms="123",
    )
    assert headers["X-API-KEY-ID"] == "key_123"
    assert headers["X-API-TIMESTAMP"] == "123"
    assert len(headers["X-API-SIGNATURE"]) == 128


def test_api_key_credentials_repr_redacts_private_key() -> None:
    private = Ed25519PrivateKey.generate().private_bytes_raw()
    credentials = ApiKeyCredentials(key_id="key_123", private_key=private)
    rendered = repr(credentials)
    assert "key_123" in rendered
    assert "[REDACTED]" in rendered
    assert private.hex() not in rendered
    assert str(private) not in rendered


def test_transport_factory_repr_redacts_credentials() -> None:
    import asyncio

    from polyester.transport import TransportConfig, TransportFactory

    private = Ed25519PrivateKey.generate().private_bytes_raw()
    credentials = ApiKeyCredentials(key_id="key_123", private_key=private)
    factory = TransportFactory(
        TransportConfig(api_url="https://api.example.test"),
        credentials=credentials,
    )
    try:
        rendered = repr(factory)
        assert "[REDACTED]" in rendered
        assert private.hex() not in rendered
        assert "credentials=[REDACTED]" in rendered
        assert "api_url=" in repr(factory.config)
    finally:
        asyncio.run(factory.aclose())


def test_ed25519_keypair_repr_redacts_secret() -> None:
    from polyester.models.auth import Ed25519Keypair

    secret = b"\x01" * 32
    keypair = Ed25519Keypair(
        public_key_hex="aa",
        public_key=b"\x02" * 32,
        secret_key_hex=secret.hex(),
        secret_key=secret,
    )
    rendered = repr(keypair)
    assert "[REDACTED]" in rendered
    assert secret.hex() not in rendered


def test_automatic_timestamps_track_wall_clock_under_concurrency() -> None:
    credentials = ApiKeyCredentials(
        key_id="key_123",
        private_key=Ed25519PrivateKey.generate().private_bytes_raw(),
    )

    def sign(_: int) -> dict[str, str]:
        return sign_request(
            credentials,
            method="POST",
            url="https://api.example.test/foo",
            body=b"{}",
        )

    before = int(time.time() * 1000)
    with ThreadPoolExecutor(max_workers=32) as executor:
        headers = list(executor.map(sign, range(100_000)))
    after = int(time.time() * 1000)
    timestamps = [int(item["X-API-TIMESTAMP"]) for item in headers]
    assert min(timestamps) >= before
    assert max(timestamps) <= after


def test_signing_rejects_malformed_absolute_url() -> None:
    credentials = ApiKeyCredentials(
        key_id="key_123",
        private_key=Ed25519PrivateKey.generate().private_bytes_raw(),
    )
    try:
        sign_request(credentials, method="POST", url="://not-a-url", body=b"{}")
    except Exception as exc:
        assert "malformed absolute HTTP URL" in str(exc)
    else:
        raise AssertionError("malformed URL must fail closed")


def test_load_credentials_from_private_key_env(monkeypatch) -> None:
    generated = Ed25519PrivateKey.generate()
    hex_private = generated.private_bytes_raw().hex()
    monkeypatch.setenv("POLYESTER_API_KEY_ID", "ak_test")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, hex_private)
    creds = load_api_key_credentials()
    assert creds is not None
    assert creds.private_key == generated.private_bytes_raw()
