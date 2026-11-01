import pytest

from polyester.codecs.enums import resolve_proto_enum
from polyester.codecs.proto_build import repeated_messages_from_mappings
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import social_verification_pb2 as sv_pb2
from polyester.gen.chain.analytics.v1 import analytics_read_pb2
from polyester.gen.polyester.type.v1 import u128_pb2


def test_social_provider_and_method_enums() -> None:
    twitter = resolve_proto_enum(sv_pb2, "twitter", aliases={"twitter": sv_pb2.TWITTER})
    assert twitter == sv_pb2.TWITTER
    assert resolve_proto_enum(sv_pb2, "profile", aliases={"profile": sv_pb2.METHOD_PROFILE}) == (
        sv_pb2.METHOD_PROFILE
    )


def test_chain_analytics_range_aliases_cover_common_windows() -> None:
    aliases = {
        "1d": analytics_read_pb2.DAY_1,
        "7d": analytics_read_pb2.DAY_7,
        "30d": analytics_read_pb2.DAY_30,
        "90d": analytics_read_pb2.DAY_90,
        "180d": analytics_read_pb2.DAY_180,
        "365d": analytics_read_pb2.DAY_365,
    }
    for label in aliases:
        assert (
            resolve_proto_enum(
                analytics_read_pb2,
                label,
                aliases=aliases,
                field_name="range",
            )
            == aliases[label]
        )


def test_repeated_messages_from_mappings() -> None:
    entries = repeated_messages_from_mappings(u128_pb2.U128, [{"hi": 0, "lo": 1}])
    assert len(entries) == 1
    assert entries[0].lo == 1


def test_resolve_proto_enum_rejects_garbage() -> None:
    with pytest.raises(PolyesterValidationError):
        resolve_proto_enum(sv_pb2, "not-a-provider", field_name="provider")
