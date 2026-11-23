from __future__ import annotations

from datetime import datetime
from typing import Any

import msgspec

from polyester.models.policies import SubaccountPolicy
from polyester.models.trading import ApiKeySummary, BalancesList


class SubAccount(msgspec.Struct, kw_only=True, omit_defaults=True):
    id: str = ""
    # The caller's role: viewer, trader, leveraged_trader, treasury, admin or
    # owner. Empty when the server sends none, as on a removal.
    role: str = ""
    label: str = ""
    icon: str = ""
    color: str = ""
    status: str = ""
    smart_account_address: str = ""
    owner_username: str = ""
    owner_avatar_url: str = ""
    owner_root_smart_account_address: str = ""
    subaccount_policy_id: str = ""
    require_member_mfa: bool = False
    smart_account_salt_nonce: int = 0
    updated_at: datetime | None = None
    revision: int = 0
    # True on a realtime update when the caller no longer has access to this
    # sub-account (for example after its owner removed the caller as a
    # member): drop it from the caller's list. Its ``role`` is then empty.
    # A role or access change does not move ``revision`` or ``updated_at``:
    # apply each update as it arrives. Reads never set it.
    removed: bool = False


class SubAccountsList(msgspec.Struct, kw_only=True, omit_defaults=True):
    subaccounts: list[SubAccount]
    total_created: int = 0


class CreateSubaccountResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    subaccount_id: str = ""
    total_created: int = 0
    smart_account_salt_nonce: int = 0
    revision: int = 0


class SubAccountMember(msgspec.Struct, kw_only=True, omit_defaults=True):
    account_id: str = ""
    role: str = ""
    username: str = ""
    smart_account_address: str = ""
    avatar_url: str = ""
    mfa_enrolled: bool = False


class SubAccountMembersList(msgspec.Struct, kw_only=True, omit_defaults=True):
    members: list[SubAccountMember]


class SubAccountInvite(msgspec.Struct, kw_only=True, omit_defaults=True):
    id: str = ""
    subaccount_id: str = ""
    grantee_account_id: str = ""
    inviter_account_id: str = ""
    role: str = ""
    status: str = ""
    created_at: datetime | None = None
    responded_at: datetime | None = None
    grantee_username: str = ""
    inviter_username: str = ""
    subaccount_label: str = ""
    inviter_root_smart_account_address: str = ""
    grantee_root_smart_account_address: str = ""
    require_member_mfa: bool = False


class SubAccountInvitesList(msgspec.Struct, kw_only=True, omit_defaults=True):
    invites: list[SubAccountInvite]


class ActivityActor(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Who acted on an activity event.

    ``kind`` is ``"user"`` (a signed-in account), ``"api_key"`` (a request
    signed with an API key), ``"system"`` (Polyester acting by itself, see
    ``system_reason``) or ``"unauthenticated"`` (a request nobody
    authenticated, such as a refused sign-in); a value this SDK does not know
    reads as its number. ``account_id`` (a public ID) and ``username`` name
    the account for a user or an API key, "" otherwise. ``api_key_id`` is the
    key's ``ak_…`` ID, and ``api_key_kind`` (``"standard"``, ``"assistant"``,
    ``"admin"``, ``"strategy_bot"`` or ``"broker"``) and ``api_key_label`` are
    the key's when the event was recorded; all three are set for an API key
    actor only.
    """

    kind: str = ""
    account_id: str = ""
    username: str = ""
    api_key_id: str = ""
    api_key_kind: str = ""
    api_key_label: str = ""
    system_reason: str = ""


class ActivityItem(msgspec.Struct, kw_only=True, omit_defaults=True):
    """The item an activity event affected.

    ``kind`` names the ID that is set, which says what the item is:
    ``"account_id"``, ``"subaccount_id"``, ``"invite_id"``,
    ``"subaccount_policy_id"``, ``"api_policy_id"``,
    ``"address_book_entry_id"``, ``"broker_allowlist_change_id"`` or
    ``"connected_app_id"`` (``id`` is a public ID), or ``"api_key_id"`` or
    ``"mfa_factor_id"`` (``id`` is the string ID those APIs use). Both are ""
    for an item with no ID (a sign-in session, a failed sign-in, the recovery
    codes). ``name`` is the item's display name when the event was recorded.
    """

    kind: str = ""
    id: str = ""
    name: str = ""


class SubAccountActivityEvent(msgspec.Struct, kw_only=True, omit_defaults=True):
    """One account activity event.

    ``actor`` says who acted, ``item`` which item changed and ``details``
    what changed. ``details`` is the change in its REST JSON form: one key
    naming the kind of item (``"account"``, ``"session"``, ``"apiKey"``,
    ``"policy"``, ``"subaccount"``, ``"member"``, ``"invite"``,
    ``"destination"``, ``"brokerAllowlist"`` or ``"security"``) holding only
    the fields the event set: a ``{"from": ..., "to": ...}`` pair for a changed
    value, ``{"fromId": ..., "toId": ...}`` for a changed ID,
    ``{"added": [...], "removed": [...]}`` or
    ``{"addedIds": [...], "removedIds": [...]}`` for a changed list, or a
    plain value, with camelCase keys, enum names, RFC 3339 times and public
    IDs.
    It is ``None`` when the event carries no details.
    """

    created_at: datetime | None = None
    entity_kind: str = ""
    event_action: str = ""
    source: str = ""
    ip: str = ""
    user_agent: str = ""
    # The sub-account the event belongs to (a public ID), "" for the main
    # account's own events.
    subaccount_id: str = ""
    actor: ActivityActor | None = None
    item: ActivityItem | None = None
    details: dict[str, Any] | None = None


class SubAccountActivityList(msgspec.Struct, kw_only=True, omit_defaults=True):
    events: list[SubAccountActivityEvent]
    next_page_token: str = ""


class GetSubaccountResult(msgspec.Struct, kw_only=True, omit_defaults=True):
    """Aggregated sub-account view.

    ``balances`` is set only for ``include_balances=True``: the sub-account's
    current balances in the shape of ``balances.list`` (one ``AssetBalance``
    per asset). ``None`` otherwise.
    """

    subaccount: SubAccount | None = None
    api_keys: list[ApiKeySummary] = []
    members: list[SubAccountMember] = []
    invites: list[SubAccountInvite] = []
    policy: SubaccountPolicy | None = None
    balances: BalancesList | None = None
