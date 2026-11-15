from __future__ import annotations

from polyester._wire import protobuf_to_public_dict
from polyester.codecs.decode.common import require_id
from polyester.codecs.proto_helpers import format_uint64_id, optional_timestamp
from polyester.gen.auth.v1 import auth_pb2, profile_pb2
from polyester.models.auth import (
    MeResult,
    UsernameHistoryEntry,
    UsernameHistoryList,
    UserProfile,
)


def me_from_proto(msg: auth_pb2.MeResponse) -> MeResult:
    require_id("Me", "account_id", msg.account_id)
    session = None
    if msg.HasField("session"):
        require_id("Me", "session.session_id", msg.session.session_id)
        session = protobuf_to_public_dict(msg.session)
    return MeResult(
        account_id=format_uint64_id(msg.account_id),
        api_key_id=(msg.api_key_id or "").strip(),
        username=msg.username,
        root_smart_account_address=msg.root_smart_account_address,
        session=session,
    )


def profile_from_proto(msg: profile_pb2.UserProfile) -> UserProfile:
    return UserProfile(
        username=msg.username,
        bio=msg.bio,
        website=msg.website,
        twitter=msg.twitter,
        twitter_verified=msg.twitter_verified,
        discord=msg.discord,
        discord_verified=msg.discord_verified,
        avatar_url=msg.avatar_url,
        created_at=optional_timestamp(msg, "created_at"),
        next_username_change_at=optional_timestamp(msg, "next_username_change_at"),
        vip_tier=msg.vip_tier,
        username_unlocked=msg.username_unlocked,
    )


def username_history_from_proto(
    msg: profile_pb2.GetUsernameHistoryResponse,
) -> UsernameHistoryList:
    return UsernameHistoryList(
        history=[
            UsernameHistoryEntry(
                username=entry.username,
                set_at=optional_timestamp(entry, "set_at"),
            )
            for entry in msg.history
        ]
    )
