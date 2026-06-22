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
        canonical_query("https://api.example.test/path?b=2&a=hello world")
        == "a=hello%20world&b=2"
    )


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


def test_load_credentials_from_private_key_env(monkeypatch) -> None:
    generated = Ed25519PrivateKey.generate()
    hex_private = generated.private_bytes_raw().hex()
    monkeypatch.setenv("POLYESTER_API_KEY_ID", "ak_test")
    monkeypatch.setenv(API_PRIVATE_KEY_ENV, hex_private)
    creds = load_api_key_credentials()
    assert creds is not None
    assert creds.private_key == generated.private_bytes_raw()
