from __future__ import annotations

import pytest
from connectrpc.codec import proto_binary_codec, proto_json_codec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from polyester.auth import ApiKeyCredentials, canonical_signing_string
from polyester.gen.auth.v1.auth_connect import AuthServiceClient
from polyester.gen.auth.v1.auth_pb2 import GetNonceRequest, GetNonceResponse
from polyester.transport import TransportConfig, TransportFactory, codec_for_config

_ADDRESS = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_PROCEDURE = "/auth.v1.AuthService/GetNonce"


def _media_type(value: str | None) -> str:
    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()


def test_unary_codecs_use_connect_unary_media_types() -> None:
    binary = proto_binary_codec()
    json_codec = proto_json_codec()
    assert binary.name() == "proto"
    assert json_codec.name() == "json"
    assert f"application/{binary.name()}" == "application/proto"
    assert f"application/{json_codec.name()}" == "application/json"


def test_codec_for_config_encodes_the_active_wire_format() -> None:
    request = GetNonceRequest(smart_account_address=_ADDRESS)
    binary = codec_for_config(TransportConfig(api_url="https://example.test"))
    json_codec = codec_for_config(
        TransportConfig(api_url="https://example.test", wire_format="json")
    )
    encoded_binary = binary.encode(request)
    encoded_json = json_codec.encode(request)
    assert encoded_binary != encoded_json
    assert encoded_json.startswith(b"{")
    assert b"smartAccountAddress" in encoded_json or b"smart_account_address" in encoded_json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("wire_format", "content_type"),
    [
        ("binary", "application/proto"),
        ("json", "application/json"),
    ],
)
async def test_authenticated_unary_signs_transmitted_codec_bytes(
    httpserver,
    wire_format: str,
    content_type: str,
) -> None:
    private = Ed25519PrivateKey.generate()
    credentials = ApiKeyCredentials(key_id="ak_test", private_key=private.private_bytes_raw())
    request = GetNonceRequest(smart_account_address=_ADDRESS)
    api_url = httpserver.url_for("/").rstrip("/")
    codec = codec_for_config(TransportConfig(api_url=api_url, wire_format=wire_format))
    response_body = b"{}" if wire_format == "json" else GetNonceResponse().SerializeToString()
    httpserver.expect_request(_PROCEDURE, method="POST").respond_with_data(
        response_body,
        content_type=content_type,
        headers={"Connect-Protocol-Version": "1"},
    )
    factory = TransportFactory(
        TransportConfig(api_url=api_url, wire_format=wire_format),
        credentials=credentials,
    )
    try:
        client = factory.create_auth_client(AuthServiceClient)
        await client.get_nonce(request)
    finally:
        await factory.aclose()

    assert len(httpserver.log) == 1
    captured, _ = httpserver.log[0]
    body = captured.data
    assert _media_type(captured.headers.get("Content-Type")) == content_type
    assert "connect+" not in _media_type(captured.headers.get("Content-Type"))
    assert captured.headers.get("Connect-Protocol-Version") == "1"
    assert captured.headers.get("X-API-KEY-ID") == "ak_test"
    assert body == codec.encode(request)

    timestamp = captured.headers["X-API-TIMESTAMP"]
    signature = bytes.fromhex(captured.headers["X-API-SIGNATURE"])
    canonical = canonical_signing_string(
        timestamp_ms=timestamp,
        method="POST",
        url=f"{api_url}{_PROCEDURE}",
        body=body,
    )
    private.public_key().verify(signature, canonical.encode("utf-8"))
