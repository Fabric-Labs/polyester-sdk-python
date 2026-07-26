import pytest

from polyester.codecs.enums import resolve_proto_enum
from polyester.codecs.proto_build import message_from_mapping, repeated_messages_from_mappings
from polyester.errors import PolyesterValidationError
from polyester.gen.auth.v1 import social_verification_pb2 as sv_pb2
from polyester.gen.chain.analytics.v1 import analytics_read_pb2
from polyester.gen.collab.v1 import whiteboard_pb2 as wb_pb2
from polyester.gen.layout.v1 import layout_pb2
from polyester.gen.polychart.v1 import polychart_pb2
from polyester.services.whiteboard import _board_audience, _board_role


def test_social_provider_and_method_enums() -> None:
    twitter = resolve_proto_enum(sv_pb2, "twitter", aliases={"twitter": sv_pb2.TWITTER})
    assert twitter == sv_pb2.TWITTER
    assert resolve_proto_enum(sv_pb2, "profile", aliases={"profile": sv_pb2.METHOD_PROFILE}) == (
        sv_pb2.METHOD_PROFILE
    )


def test_whiteboard_audience_and_role_aliases() -> None:
    assert _board_audience("private") == wb_pb2.PRIVATE
    assert _board_role("editor") == wb_pb2.EDITOR


def test_polychart_layer_ref_from_mapping() -> None:
    ref = message_from_mapping(polychart_pb2.LayerRef, {"ownerId": 1, "layerId": 42})
    assert ref.owner_id == 1
    assert ref.layer_id == 42


def test_layout_upsert_request_wraps_layout_message() -> None:
    request = layout_pb2.UpsertLayoutRequest(
        layout=message_from_mapping(layout_pb2.Layout, {"layoutId": 7, "name": "main"}),
    )
    assert request.layout.layout_id == 7
    assert request.layout.name == "main"


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


def test_repeated_acl_entries_from_mappings() -> None:
    entries = repeated_messages_from_mappings(
        wb_pb2.BoardAclEntry,
        [{"subjectType": "USER_SUBJECT", "subjectId": 1, "role": "VIEWER"}],
    )
    assert len(entries) == 1
    assert entries[0].subject_id == 1


def test_resolve_proto_enum_rejects_garbage() -> None:
    with pytest.raises(PolyesterValidationError):
        resolve_proto_enum(wb_pb2, "not-a-role", field_name="role")
