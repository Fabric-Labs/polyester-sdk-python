import pytest

from polyester.auth import generate_ed25519_keypair
from polyester.codecs.enums import resolve_proto_enum
from polyester.codecs.proto_build import message_from_mapping
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.analytics.v1 import analytics_read_pb2
from polyester.services.api_keys import AsyncApiKeysService


def test_generate_ed25519_keypair_lengths() -> None:
    public_key, secret_key = generate_ed25519_keypair()
    assert len(public_key) == 32
    assert len(secret_key) == 32
    assert public_key != secret_key


def test_api_keys_generate_keypair_wrapper() -> None:
    service = AsyncApiKeysService(transport=None, default_sub_account_id=None)
    keypair = service.generate_keypair()
    assert len(keypair.public_key) == 32
    assert keypair.public_key_hex == keypair.public_key.hex()


def test_analytics_range_alias() -> None:
    assert resolve_proto_enum(
        analytics_read_pb2,
        "7d",
        aliases={"7d": analytics_read_pb2.DAY_7},
        field_name="range",
    ) == analytics_read_pb2.DAY_7


def test_message_from_mapping_builds_proto() -> None:
    msg = message_from_mapping(
        analytics_read_pb2.GetZippedAssetSupplyRequest,
        {"zippedAssetId": 42, "range": "DAY_7"},
    )
    assert msg.zipped_asset_id == 42


def test_resolve_proto_enum_rejects_unknown() -> None:
    with pytest.raises(PolyesterValidationError):
        resolve_proto_enum(analytics_read_pb2, "not-a-range", field_name="range")
