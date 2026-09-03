from datetime import UTC, datetime

from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.decode.auth import (
    me_from_proto,
    profile_from_proto,
    username_history_from_proto,
)
from polyester.codecs.decode.sub_accounts import (
    subaccount_activity_event_from_proto,
    subaccount_from_proto,
)
from polyester.codecs.scalars import format_id
from polyester.gen.auth.v1 import auth_pb2, profile_pb2, subaccounts_pb2


def test_me_from_proto_formats_ids_and_session() -> None:
    msg = auth_pb2.MeResponse(
        account_id=123456,
        api_key_id="ak_0123456789abcdef0123456789abcdef",
        username="alice",
        root_smart_account_address="0xabc",
    )
    result = me_from_proto(msg)
    assert result.account_id == format_id(123456)
    assert result.api_key_id == "ak_0123456789abcdef0123456789abcdef"
    assert result.username == "alice"
    assert result.root_smart_account_address == "0xabc"
    assert result.session is None


def test_profile_from_proto_parses_timestamps() -> None:
    created = Timestamp(seconds=1_700_000_000)
    next_change = Timestamp(seconds=1_800_000_000)
    msg = profile_pb2.UserProfile(
        username="alice",
        bio="builder",
        twitter_verified=True,
        vip_tier=2,
        created_at=created,
        next_username_change_at=next_change,
    )
    result = profile_from_proto(msg)
    assert result.username == "alice"
    assert result.bio == "builder"
    assert result.twitter_verified is True
    assert result.vip_tier == 2
    assert result.created_at == datetime.fromtimestamp(1_700_000_000, tz=UTC)
    assert result.next_username_change_at == datetime.fromtimestamp(1_800_000_000, tz=UTC)


def test_username_history_from_proto_orders_entries() -> None:
    msg = profile_pb2.GetUsernameHistoryResponse(
        history=[
            profile_pb2.UsernameHistoryEntry(
                username="new",
                set_at=Timestamp(seconds=2),
            ),
            profile_pb2.UsernameHistoryEntry(
                username="old",
                set_at=Timestamp(seconds=1),
            ),
        ]
    )
    result = username_history_from_proto(msg)
    assert [entry.username for entry in result.history] == ["new", "old"]


def test_subaccount_freshness_and_activity_enums() -> None:
    subaccount = subaccount_from_proto(
        subaccounts_pb2.Subaccount(
            id=12,
            status=subaccounts_pb2.SUBACCOUNT_STATUS_ACTIVE,
            updated_at=Timestamp(seconds=3, nanos=123_456_000),
        )
    )
    assert subaccount.status == "active"
    assert subaccount.updated_at is not None
    assert subaccount.updated_at.microsecond == 123_456
    assert (
        subaccount_from_proto(
            subaccounts_pb2.Subaccount(status=subaccounts_pb2.SUBACCOUNT_STATUS_DISABLED)
        ).status
        == "disabled"
    )
    assert subaccount_from_proto(subaccounts_pb2.Subaccount()).status == ""

    event = subaccount_activity_event_from_proto(
        subaccounts_pb2.ActivityEvent(
            entity_kind=subaccounts_pb2.ACTIVITY_ENTITY_INVITE,
            event_action=subaccounts_pb2.ACTIVITY_ACTION_CREATED,
            source=subaccounts_pb2.ACTIVITY_SOURCE_API,
        )
    )
    assert event.entity_kind == "invite"
    assert event.event_action == "created"
    assert event.source == "api"
