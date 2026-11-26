from __future__ import annotations

from typing import Any

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from polyester.codecs.decode.api_keys import api_key_from_proto
from polyester.codecs.decode.balances import balances_list_from_proto
from polyester.codecs.decode.common import require_id
from polyester.codecs.decode.policies import subaccount_policy_from_proto
from polyester.codecs.proto_helpers import (
    format_optional_uint64_id,
    format_uint64_id,
    has_field,
    optional_timestamp,
    proto_enum_name,
)
from polyester.codecs.scalars import format_id
from polyester.errors import PolyesterResponseContractError
from polyester.gen.auth.v1 import subaccounts_pb2
from polyester.models.sub_accounts import (
    ActivityActor,
    ActivityItem,
    GetSubaccountResult,
    SubAccount,
    SubAccountActivityEvent,
    SubAccountActivityList,
    SubAccountInvite,
    SubAccountInvitesList,
    SubAccountMember,
    SubAccountMembersList,
    SubAccountsList,
)


def _subaccount_role_from_proto(value: int) -> str:
    """The role as sent; ``SUBACCOUNT_ROLE_UNSPECIFIED`` (a removed
    sub-account's role) reads as ``""``, never as a default role."""
    name = proto_enum_name(subaccounts_pb2.SubaccountRole, value)
    if name in {"", "subaccount_role_unspecified"}:
        return ""
    return name


def _invite_status_from_proto(value: int) -> str:
    name = proto_enum_name(subaccounts_pb2.SubaccountInviteStatus, value)
    if name.startswith("subaccount_invite_status_"):
        return name.removeprefix("subaccount_invite_status_")
    return name or "pending"


def _subaccount_status_from_proto(value: int) -> str:
    return proto_enum_name(subaccounts_pb2.SubaccountStatus, value)


def subaccount_from_proto(msg: subaccounts_pb2.Subaccount) -> SubAccount:
    return SubAccount(
        id=format_uint64_id(msg.id),
        role=_subaccount_role_from_proto(msg.role),
        label=msg.label,
        icon=msg.icon,
        color=msg.color,
        status=_subaccount_status_from_proto(msg.status),
        smart_account_address=msg.smart_account_address,
        owner_username=msg.owner_username,
        owner_avatar_url=msg.owner_avatar_url,
        owner_root_smart_account_address=msg.owner_root_smart_account_address,
        subaccount_policy_id=format_uint64_id(msg.subaccount_policy_id),
        require_member_mfa=bool(msg.require_member_mfa),
        smart_account_salt_nonce=int(msg.smart_account_salt_nonce),
        updated_at=optional_timestamp(msg, "updated_at"),
        revision=int(msg.revision),
        removed=bool(msg.removed),
        strategy_bot=bool(msg.strategy_bot),
    )


def subaccounts_list_from_proto(msg: subaccounts_pb2.ListSubaccountsResponse) -> SubAccountsList:
    for item in msg.subaccounts:
        require_id("ListSubaccounts", "subaccounts.id", item.id)
    return SubAccountsList(
        subaccounts=[subaccount_from_proto(item) for item in msg.subaccounts],
        total_created=int(msg.total_created),
    )


def subaccount_member_from_proto(msg: subaccounts_pb2.SubaccountMemberView) -> SubAccountMember:
    return SubAccountMember(
        account_id=format_uint64_id(msg.account_id),
        role=_subaccount_role_from_proto(msg.role),
        username=msg.username,
        smart_account_address=msg.smart_account_address,
        avatar_url=msg.avatar_url,
        mfa_enrolled=bool(msg.mfa_enrolled),
    )


def subaccount_members_list_from_proto(
    msg: subaccounts_pb2.ListSubaccountMembersResponse,
) -> SubAccountMembersList:
    for item in msg.members:
        require_id("ListSubaccountMembers", "member account_id", item.account_id)
    return SubAccountMembersList(
        members=[subaccount_member_from_proto(item) for item in msg.members]
    )


def subaccount_invite_from_proto(msg: subaccounts_pb2.SubaccountInvite) -> SubAccountInvite:
    return SubAccountInvite(
        id=format_uint64_id(msg.id),
        subaccount_id=format_uint64_id(msg.subaccount_id),
        grantee_account_id=format_uint64_id(msg.grantee_account_id),
        inviter_account_id=format_uint64_id(msg.inviter_account_id),
        role=_subaccount_role_from_proto(msg.role),
        status=_invite_status_from_proto(msg.status),
        created_at=optional_timestamp(msg, "created_at"),
        responded_at=optional_timestamp(msg, "responded_at"),
        grantee_username=msg.grantee_username,
        inviter_username=msg.inviter_username,
        subaccount_label=msg.subaccount_label,
        inviter_root_smart_account_address=msg.inviter_root_smart_account_address,
        grantee_root_smart_account_address=msg.grantee_root_smart_account_address,
        require_member_mfa=bool(msg.require_member_mfa),
    )


def _require_invite_ids(operation: str, msg: subaccounts_pb2.SubaccountInvite) -> None:
    require_id(operation, "invites.id", msg.id)
    require_id(operation, "invites.subaccount_id", msg.subaccount_id)


def subaccount_invites_list_from_proto(
    msg: subaccounts_pb2.ListSubaccountInvitesResponse,
) -> SubAccountInvitesList:
    for item in msg.invites:
        _require_invite_ids("ListSubaccountInvites", item)
    return SubAccountInvitesList(
        invites=[subaccount_invite_from_proto(item) for item in msg.invites]
    )


def subaccount_activity_event_from_proto(
    msg: subaccounts_pb2.ActivityEvent,
) -> SubAccountActivityEvent:
    return SubAccountActivityEvent(
        created_at=optional_timestamp(msg, "created_at"),
        entity_kind=proto_enum_name(
            subaccounts_pb2.ActivityEntityKind, msg.entity_kind
        ).removeprefix("activity_entity_"),
        event_action=proto_enum_name(
            subaccounts_pb2.ActivityEventAction, msg.event_action
        ).removeprefix("activity_action_"),
        source=proto_enum_name(subaccounts_pb2.ActivityEventSource, msg.source).removeprefix(
            "activity_source_"
        ),
        ip=msg.ip,
        user_agent=msg.user_agent,
        subaccount_id=format_optional_uint64_id(int(msg.subaccount_id)),
        actor=_activity_actor(msg.actor) if has_field(msg, "actor") else None,
        item=_activity_item(msg.item) if has_field(msg, "item") else None,
        details=_activity_details(msg.details) if has_field(msg, "details") else None,
    )


def _activity_actor(msg: subaccounts_pb2.ActivityActor) -> ActivityActor:
    return ActivityActor(
        kind=proto_enum_name(subaccounts_pb2.ActivityActorKind, msg.kind).removeprefix(
            "activity_actor_"
        ),
        account_id=format_optional_uint64_id(int(msg.account_id)),
        username=msg.username,
        api_key_id=msg.api_key_id,
        api_key_kind=proto_enum_name(
            subaccounts_pb2.ActivityApiKeyKind, msg.api_key_kind
        ).removeprefix("activity_key_"),
        api_key_label=msg.api_key_label,
        system_reason=proto_enum_name(
            subaccounts_pb2.ActivitySystemReason, msg.system_reason
        ).removeprefix("activity_system_"),
    )


def _activity_item(msg: subaccounts_pb2.ActivityItem) -> ActivityItem:
    kind = msg.WhichOneof("id") or ""
    if not kind:
        item_id = ""
    elif msg.DESCRIPTOR.fields_by_name[kind].type == FieldDescriptor.TYPE_FIXED64:
        item_id = format_uint64_id(int(getattr(msg, kind)))
    else:
        item_id = str(getattr(msg, kind))
    return ActivityItem(kind=kind, id=item_id, name=msg.name)


def _activity_details(msg: subaccounts_pb2.ActivityDetails) -> dict[str, Any]:
    """``details`` as REST JSON shows it: camelCase keys, enum names, RFC 3339
    times, and every fixed64 field (an opaque ID) as its public ID rather than
    protobuf JSON's decimal string."""
    rendered = MessageToDict(msg)
    _public_ids(msg, rendered)
    return rendered


def _public_ids(msg: Message, rendered: dict[str, Any]) -> None:
    for field, value in msg.ListFields():
        if field.json_name not in rendered:
            continue
        if field.type == FieldDescriptor.TYPE_FIXED64:
            if field.is_repeated:
                rendered[field.json_name] = [format_id(int(item)) for item in value]
            else:
                rendered[field.json_name] = format_id(int(value))
        elif (
            field.type == FieldDescriptor.TYPE_MESSAGE
            and not field.message_type.GetOptions().map_entry
        ):
            if field.is_repeated:
                for item, item_rendered in zip(value, rendered[field.json_name], strict=True):
                    _public_ids(item, item_rendered)
            elif isinstance(rendered[field.json_name], dict):
                _public_ids(value, rendered[field.json_name])


def subaccount_activity_list_from_proto(
    msg: subaccounts_pb2.ListSubaccountEventsResponse,
) -> SubAccountActivityList:
    return SubAccountActivityList(
        events=[subaccount_activity_event_from_proto(item) for item in msg.events],
        next_page_token=msg.next_page_token,
    )


def get_subaccount_from_proto(msg: subaccounts_pb2.GetSubaccountResponse) -> GetSubaccountResult:
    if not has_field(msg, "subaccount"):
        raise PolyesterResponseContractError("GetSubaccount", "missing subaccount")
    require_id("GetSubaccount", "subaccount.id", msg.subaccount.id)
    for member in msg.members:
        require_id("GetSubaccount", "member account_id", member.account_id)
    for key in msg.api_keys:
        require_id("GetSubaccount", "key_id", key.key_id)
    for invite in msg.invites:
        _require_invite_ids("GetSubaccount", invite)
    if has_field(msg, "policy"):
        require_id("GetSubaccount", "policy.id", msg.policy.id)
    subaccount = subaccount_from_proto(msg.subaccount) if has_field(msg, "subaccount") else None
    policy = subaccount_policy_from_proto(msg.policy) if has_field(msg, "policy") else None
    return GetSubaccountResult(
        subaccount=subaccount,
        api_keys=[api_key_from_proto(item) for item in msg.api_keys],
        members=[subaccount_member_from_proto(item) for item in msg.members],
        invites=[subaccount_invite_from_proto(item) for item in msg.invites],
        policy=policy,
        balances=balances_list_from_proto(msg.balances) if has_field(msg, "balances") else None,
    )
