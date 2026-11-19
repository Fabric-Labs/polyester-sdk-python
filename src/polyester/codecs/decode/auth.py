from __future__ import annotations

from polyester._wire import protobuf_to_public_dict
from polyester.codecs.decode.common import require_id
from polyester.codecs.proto_helpers import (
    format_optional_uint64_id,
    format_uint64_id,
    optional_timestamp,
    proto_enum_name,
)
from polyester.errors import PolyesterResponseContractError
from polyester.gen.auth.v1 import address_book_pb2, auth_pb2, profile_pb2
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
    scope = proto_enum_name(address_book_pb2.AccountScopeType, int(msg.api_key_scope))
    _check_key_scope(bool((msg.api_key_id or "").strip()), scope, int(msg.subaccount_id))
    return MeResult(
        account_id=format_uint64_id(msg.account_id),
        api_key_id=(msg.api_key_id or "").strip(),
        username=msg.username,
        root_smart_account_address=msg.root_smart_account_address,
        session=session,
        api_key_scope=scope,
        subaccount_id=format_optional_uint64_id(int(msg.subaccount_id)),
    )


def _check_key_scope(is_key: bool, scope: str, subaccount_id: int) -> None:
    """An API key names its scope, ``root`` or ``subaccount``, and only a
    sub-account key names its sub-account; a session names neither."""
    if not is_key:
        if scope or subaccount_id:
            raise PolyesterResponseContractError("Me", "a session names an API key scope")
        return
    if scope not in ("root", "subaccount"):
        raise PolyesterResponseContractError("Me", f"API key with no known scope ({scope!r})")
    if (scope == "subaccount") != bool(subaccount_id):
        raise PolyesterResponseContractError(
            "Me",
            "sub-account key without its subaccount_id"
            if scope == "subaccount"
            else "root key naming a subaccount_id",
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
