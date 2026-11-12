import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.chain.withdraw.v1 import auto_withdraw_pb2 as _auto_withdraw_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.swap.quickswap.v1 import quickswap_pb2 as _quickswap_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BrokerRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BROKER_ROLE_UNSPECIFIED: _ClassVar[BrokerRole]
    OWNER: _ClassVar[BrokerRole]
    ADMIN: _ClassVar[BrokerRole]
    FINANCE: _ClassVar[BrokerRole]
    AFFILIATE_MANAGER: _ClassVar[BrokerRole]
    VIEWER: _ClassVar[BrokerRole]

class VaultStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VAULT_STATUS_UNSPECIFIED: _ClassVar[VaultStatus]
    VAULT_ACTIVE: _ClassVar[VaultStatus]
    VAULT_DISABLED: _ClassVar[VaultStatus]

class FeeTotalsGrouping(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    GROUPING_UNSPECIFIED: _ClassVar[FeeTotalsGrouping]
    BY_VAULT: _ClassVar[FeeTotalsGrouping]
    BY_DAY: _ClassVar[FeeTotalsGrouping]
    BY_MONTH: _ClassVar[FeeTotalsGrouping]

class StatsPeriod(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PERIOD_UNSPECIFIED: _ClassVar[StatsPeriod]
    DAY: _ClassVar[StatsPeriod]
    MONTH: _ClassVar[StatsPeriod]

class PayoutStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PAYOUT_STATUS_UNSPECIFIED: _ClassVar[PayoutStatus]
    PAYOUT_PAID: _ClassVar[PayoutStatus]
    PAYOUT_PARTIALLY_PAID: _ClassVar[PayoutStatus]
    PAYOUT_IN_PROGRESS: _ClassVar[PayoutStatus]
    PAYOUT_ROLLED_OVER: _ClassVar[PayoutStatus]
    PAYOUT_HELD: _ClassVar[PayoutStatus]
    PAYOUT_FAILED: _ClassVar[PayoutStatus]

class PayoutStage(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PAYOUT_STAGE_UNSPECIFIED: _ClassVar[PayoutStage]
    STAGE_PLANNING: _ClassVar[PayoutStage]
    STAGE_REQUESTING: _ClassVar[PayoutStage]
    STAGE_PROCESSING: _ClassVar[PayoutStage]
    STAGE_BROADCAST: _ClassVar[PayoutStage]

class PayoutStepState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PAYOUT_STEP_STATE_UNSPECIFIED: _ClassVar[PayoutStepState]
    PAYOUT_STEP_PENDING: _ClassVar[PayoutStepState]
    PAYOUT_STEP_REQUESTING: _ClassVar[PayoutStepState]
    PAYOUT_STEP_SUBMITTED: _ClassVar[PayoutStepState]
    PAYOUT_STEP_COMPLETED: _ClassVar[PayoutStepState]
    PAYOUT_STEP_FAILED: _ClassVar[PayoutStepState]
    PAYOUT_STEP_SKIPPED: _ClassVar[PayoutStepState]

class VaultLedgerEntryKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LEDGER_ENTRY_KIND_UNSPECIFIED: _ClassVar[VaultLedgerEntryKind]
    FEE_CREDIT: _ClassVar[VaultLedgerEntryKind]
    PAYOUT_DEBIT: _ClassVar[VaultLedgerEntryKind]
    PAYOUT_REFUND: _ClassVar[VaultLedgerEntryKind]

class PayoutClose(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CLOSE_UNSPECIFIED: _ClassVar[PayoutClose]
    CLOSE_PAID: _ClassVar[PayoutClose]
    CLOSE_REFUNDED_TO_SMART_ACCOUNT: _ClassVar[PayoutClose]
    CLOSE_SENT_TO_RECOVERY: _ClassVar[PayoutClose]
    CLOSE_UNKNOWN: _ClassVar[PayoutClose]

class AllowlistAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ALLOWLIST_ACTION_UNSPECIFIED: _ClassVar[AllowlistAction]
    ADD_DESTINATION: _ClassVar[AllowlistAction]
    REMOVE_DESTINATION: _ClassVar[AllowlistAction]

class AllowlistChangeStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ALLOWLIST_CHANGE_STATUS_UNSPECIFIED: _ClassVar[AllowlistChangeStatus]
    PENDING: _ClassVar[AllowlistChangeStatus]
    APPLIED: _ClassVar[AllowlistChangeStatus]
    NOT_APPLIED: _ClassVar[AllowlistChangeStatus]

class AllowlistChangeFailure(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ALLOWLIST_CHANGE_FAILURE_UNSPECIFIED: _ClassVar[AllowlistChangeFailure]
    TIMED_OUT: _ClassVar[AllowlistChangeFailure]
    NOT_LISTED_ON_CHAIN: _ClassVar[AllowlistChangeFailure]
    LIMIT_REACHED: _ClassVar[AllowlistChangeFailure]
    REQUESTER_NO_LONGER_ALLOWED: _ClassVar[AllowlistChangeFailure]
    REFUSED: _ClassVar[AllowlistChangeFailure]
BROKER_ROLE_UNSPECIFIED: BrokerRole
OWNER: BrokerRole
ADMIN: BrokerRole
FINANCE: BrokerRole
AFFILIATE_MANAGER: BrokerRole
VIEWER: BrokerRole
VAULT_STATUS_UNSPECIFIED: VaultStatus
VAULT_ACTIVE: VaultStatus
VAULT_DISABLED: VaultStatus
GROUPING_UNSPECIFIED: FeeTotalsGrouping
BY_VAULT: FeeTotalsGrouping
BY_DAY: FeeTotalsGrouping
BY_MONTH: FeeTotalsGrouping
PERIOD_UNSPECIFIED: StatsPeriod
DAY: StatsPeriod
MONTH: StatsPeriod
PAYOUT_STATUS_UNSPECIFIED: PayoutStatus
PAYOUT_PAID: PayoutStatus
PAYOUT_PARTIALLY_PAID: PayoutStatus
PAYOUT_IN_PROGRESS: PayoutStatus
PAYOUT_ROLLED_OVER: PayoutStatus
PAYOUT_HELD: PayoutStatus
PAYOUT_FAILED: PayoutStatus
PAYOUT_STAGE_UNSPECIFIED: PayoutStage
STAGE_PLANNING: PayoutStage
STAGE_REQUESTING: PayoutStage
STAGE_PROCESSING: PayoutStage
STAGE_BROADCAST: PayoutStage
PAYOUT_STEP_STATE_UNSPECIFIED: PayoutStepState
PAYOUT_STEP_PENDING: PayoutStepState
PAYOUT_STEP_REQUESTING: PayoutStepState
PAYOUT_STEP_SUBMITTED: PayoutStepState
PAYOUT_STEP_COMPLETED: PayoutStepState
PAYOUT_STEP_FAILED: PayoutStepState
PAYOUT_STEP_SKIPPED: PayoutStepState
LEDGER_ENTRY_KIND_UNSPECIFIED: VaultLedgerEntryKind
FEE_CREDIT: VaultLedgerEntryKind
PAYOUT_DEBIT: VaultLedgerEntryKind
PAYOUT_REFUND: VaultLedgerEntryKind
CLOSE_UNSPECIFIED: PayoutClose
CLOSE_PAID: PayoutClose
CLOSE_REFUNDED_TO_SMART_ACCOUNT: PayoutClose
CLOSE_SENT_TO_RECOVERY: PayoutClose
CLOSE_UNKNOWN: PayoutClose
ALLOWLIST_ACTION_UNSPECIFIED: AllowlistAction
ADD_DESTINATION: AllowlistAction
REMOVE_DESTINATION: AllowlistAction
ALLOWLIST_CHANGE_STATUS_UNSPECIFIED: AllowlistChangeStatus
PENDING: AllowlistChangeStatus
APPLIED: AllowlistChangeStatus
NOT_APPLIED: AllowlistChangeStatus
ALLOWLIST_CHANGE_FAILURE_UNSPECIFIED: AllowlistChangeFailure
TIMED_OUT: AllowlistChangeFailure
NOT_LISTED_ON_CHAIN: AllowlistChangeFailure
LIMIT_REACHED: AllowlistChangeFailure
REQUESTER_NO_LONGER_ALLOWED: AllowlistChangeFailure
REFUSED: AllowlistChangeFailure

class Broker(_message.Message):
    __slots__ = ("name", "display_name", "enabled", "root_account_id", "default_vault_account_id", "max_affiliate_vaults", "role", "quote_rps", "create_rps", "read_rps", "max_unfunded_addresses", "max_creates_per_hour")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    ROOT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    MAX_AFFILIATE_VAULTS_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    QUOTE_RPS_FIELD_NUMBER: _ClassVar[int]
    CREATE_RPS_FIELD_NUMBER: _ClassVar[int]
    READ_RPS_FIELD_NUMBER: _ClassVar[int]
    MAX_UNFUNDED_ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    MAX_CREATES_PER_HOUR_FIELD_NUMBER: _ClassVar[int]
    name: str
    display_name: str
    enabled: bool
    root_account_id: int
    default_vault_account_id: int
    max_affiliate_vaults: int
    role: BrokerRole
    quote_rps: int
    create_rps: int
    read_rps: int
    max_unfunded_addresses: int
    max_creates_per_hour: int
    def __init__(self, name: _Optional[str] = ..., display_name: _Optional[str] = ..., enabled: _Optional[bool] = ..., root_account_id: _Optional[int] = ..., default_vault_account_id: _Optional[int] = ..., max_affiliate_vaults: _Optional[int] = ..., role: _Optional[_Union[BrokerRole, str]] = ..., quote_rps: _Optional[int] = ..., create_rps: _Optional[int] = ..., read_rps: _Optional[int] = ..., max_unfunded_addresses: _Optional[int] = ..., max_creates_per_hour: _Optional[int] = ...) -> None: ...

class BrokerUsage(_message.Message):
    __slots__ = ("unfunded_addresses", "creates_last_hour", "affiliate_vaults")
    UNFUNDED_ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    CREATES_LAST_HOUR_FIELD_NUMBER: _ClassVar[int]
    AFFILIATE_VAULTS_FIELD_NUMBER: _ClassVar[int]
    unfunded_addresses: int
    creates_last_hour: int
    affiliate_vaults: int
    def __init__(self, unfunded_addresses: _Optional[int] = ..., creates_last_hour: _Optional[int] = ..., affiliate_vaults: _Optional[int] = ...) -> None: ...

class AffiliateVault(_message.Message):
    __slots__ = ("account_id", "label", "status", "created_at", "updated_at")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    account_id: int
    label: str
    status: VaultStatus
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, account_id: _Optional[int] = ..., label: _Optional[str] = ..., status: _Optional[_Union[VaultStatus, str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class BrokerKey(_message.Message):
    __slots__ = ("key_id", "label", "created_at", "created_by_account_id", "rotated_from", "expires_at", "revoked_at", "active")
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    CREATED_BY_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ROTATED_FROM_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    REVOKED_AT_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    label: str
    created_at: _timestamp_pb2.Timestamp
    created_by_account_id: int
    rotated_from: str
    expires_at: _timestamp_pb2.Timestamp
    revoked_at: _timestamp_pb2.Timestamp
    active: bool
    def __init__(self, key_id: _Optional[str] = ..., label: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., created_by_account_id: _Optional[int] = ..., rotated_from: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., revoked_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., active: _Optional[bool] = ...) -> None: ...

class Member(_message.Message):
    __slots__ = ("account_id", "role", "since")
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    SINCE_FIELD_NUMBER: _ClassVar[int]
    account_id: int
    role: BrokerRole
    since: _timestamp_pb2.Timestamp
    def __init__(self, account_id: _Optional[int] = ..., role: _Optional[_Union[BrokerRole, str]] = ..., since: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Invite(_message.Message):
    __slots__ = ("invite_id", "broker", "broker_display_name", "account_id", "role", "invited_by_account_id", "created_at")
    INVITE_ID_FIELD_NUMBER: _ClassVar[int]
    BROKER_FIELD_NUMBER: _ClassVar[int]
    BROKER_DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    INVITED_BY_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    invite_id: int
    broker: str
    broker_display_name: str
    account_id: int
    role: BrokerRole
    invited_by_account_id: int
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, invite_id: _Optional[int] = ..., broker: _Optional[str] = ..., broker_display_name: _Optional[str] = ..., account_id: _Optional[int] = ..., role: _Optional[_Union[BrokerRole, str]] = ..., invited_by_account_id: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Membership(_message.Message):
    __slots__ = ("broker", "broker_display_name", "role")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    BROKER_DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    broker: str
    broker_display_name: str
    role: BrokerRole
    def __init__(self, broker: _Optional[str] = ..., broker_display_name: _Optional[str] = ..., role: _Optional[_Union[BrokerRole, str]] = ...) -> None: ...

class GetBrokerRequest(_message.Message):
    __slots__ = ("broker",)
    BROKER_FIELD_NUMBER: _ClassVar[int]
    broker: str
    def __init__(self, broker: _Optional[str] = ...) -> None: ...

class GetBrokerResponse(_message.Message):
    __slots__ = ("broker", "usage")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    broker: Broker
    usage: BrokerUsage
    def __init__(self, broker: _Optional[_Union[Broker, _Mapping]] = ..., usage: _Optional[_Union[BrokerUsage, _Mapping]] = ...) -> None: ...

class ListMyBrokersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListMyBrokersResponse(_message.Message):
    __slots__ = ("memberships", "invites")
    MEMBERSHIPS_FIELD_NUMBER: _ClassVar[int]
    INVITES_FIELD_NUMBER: _ClassVar[int]
    memberships: _containers.RepeatedCompositeFieldContainer[Membership]
    invites: _containers.RepeatedCompositeFieldContainer[Invite]
    def __init__(self, memberships: _Optional[_Iterable[_Union[Membership, _Mapping]]] = ..., invites: _Optional[_Iterable[_Union[Invite, _Mapping]]] = ...) -> None: ...

class RespondToInviteRequest(_message.Message):
    __slots__ = ("invite_id", "accept")
    INVITE_ID_FIELD_NUMBER: _ClassVar[int]
    ACCEPT_FIELD_NUMBER: _ClassVar[int]
    invite_id: int
    accept: bool
    def __init__(self, invite_id: _Optional[int] = ..., accept: _Optional[bool] = ...) -> None: ...

class RespondToInviteResponse(_message.Message):
    __slots__ = ("membership",)
    MEMBERSHIP_FIELD_NUMBER: _ClassVar[int]
    membership: Membership
    def __init__(self, membership: _Optional[_Union[Membership, _Mapping]] = ...) -> None: ...

class ListMembersRequest(_message.Message):
    __slots__ = ("broker",)
    BROKER_FIELD_NUMBER: _ClassVar[int]
    broker: str
    def __init__(self, broker: _Optional[str] = ...) -> None: ...

class ListMembersResponse(_message.Message):
    __slots__ = ("members", "invites")
    MEMBERS_FIELD_NUMBER: _ClassVar[int]
    INVITES_FIELD_NUMBER: _ClassVar[int]
    members: _containers.RepeatedCompositeFieldContainer[Member]
    invites: _containers.RepeatedCompositeFieldContainer[Invite]
    def __init__(self, members: _Optional[_Iterable[_Union[Member, _Mapping]]] = ..., invites: _Optional[_Iterable[_Union[Invite, _Mapping]]] = ...) -> None: ...

class InviteMemberRequest(_message.Message):
    __slots__ = ("broker", "account_id", "role")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    broker: str
    account_id: int
    role: BrokerRole
    def __init__(self, broker: _Optional[str] = ..., account_id: _Optional[int] = ..., role: _Optional[_Union[BrokerRole, str]] = ...) -> None: ...

class InviteMemberResponse(_message.Message):
    __slots__ = ("invite",)
    INVITE_FIELD_NUMBER: _ClassVar[int]
    invite: Invite
    def __init__(self, invite: _Optional[_Union[Invite, _Mapping]] = ...) -> None: ...

class SetMemberRoleRequest(_message.Message):
    __slots__ = ("broker", "account_id", "role")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    broker: str
    account_id: int
    role: BrokerRole
    def __init__(self, broker: _Optional[str] = ..., account_id: _Optional[int] = ..., role: _Optional[_Union[BrokerRole, str]] = ...) -> None: ...

class SetMemberRoleResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RemoveMemberRequest(_message.Message):
    __slots__ = ("broker", "account_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    account_id: int
    def __init__(self, broker: _Optional[str] = ..., account_id: _Optional[int] = ...) -> None: ...

class RemoveMemberResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class TransferOwnershipRequest(_message.Message):
    __slots__ = ("broker", "account_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    account_id: int
    def __init__(self, broker: _Optional[str] = ..., account_id: _Optional[int] = ...) -> None: ...

class TransferOwnershipResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListKeysRequest(_message.Message):
    __slots__ = ("broker", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListKeysResponse(_message.Message):
    __slots__ = ("keys", "next_page_token")
    KEYS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    keys: _containers.RepeatedCompositeFieldContainer[BrokerKey]
    next_page_token: str
    def __init__(self, keys: _Optional[_Iterable[_Union[BrokerKey, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateKeyRequest(_message.Message):
    __slots__ = ("broker", "label")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    broker: str
    label: str
    def __init__(self, broker: _Optional[str] = ..., label: _Optional[str] = ...) -> None: ...

class CreateKeyResponse(_message.Message):
    __slots__ = ("key", "token")
    KEY_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    key: BrokerKey
    token: str
    def __init__(self, key: _Optional[_Union[BrokerKey, _Mapping]] = ..., token: _Optional[str] = ...) -> None: ...

class RotateKeyRequest(_message.Message):
    __slots__ = ("broker", "key_id", "overlap_seconds")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    OVERLAP_SECONDS_FIELD_NUMBER: _ClassVar[int]
    broker: str
    key_id: str
    overlap_seconds: int
    def __init__(self, broker: _Optional[str] = ..., key_id: _Optional[str] = ..., overlap_seconds: _Optional[int] = ...) -> None: ...

class RotateKeyResponse(_message.Message):
    __slots__ = ("key", "token", "previous_key")
    KEY_FIELD_NUMBER: _ClassVar[int]
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    PREVIOUS_KEY_FIELD_NUMBER: _ClassVar[int]
    key: BrokerKey
    token: str
    previous_key: BrokerKey
    def __init__(self, key: _Optional[_Union[BrokerKey, _Mapping]] = ..., token: _Optional[str] = ..., previous_key: _Optional[_Union[BrokerKey, _Mapping]] = ...) -> None: ...

class RevokeKeyRequest(_message.Message):
    __slots__ = ("broker", "key_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    key_id: str
    def __init__(self, broker: _Optional[str] = ..., key_id: _Optional[str] = ...) -> None: ...

class RevokeKeyResponse(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: BrokerKey
    def __init__(self, key: _Optional[_Union[BrokerKey, _Mapping]] = ...) -> None: ...

class CreateAffiliateVaultRequest(_message.Message):
    __slots__ = ("broker", "label")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    broker: str
    label: str
    def __init__(self, broker: _Optional[str] = ..., label: _Optional[str] = ...) -> None: ...

class CreateAffiliateVaultResponse(_message.Message):
    __slots__ = ("vault", "created")
    VAULT_FIELD_NUMBER: _ClassVar[int]
    CREATED_FIELD_NUMBER: _ClassVar[int]
    vault: AffiliateVault
    created: bool
    def __init__(self, vault: _Optional[_Union[AffiliateVault, _Mapping]] = ..., created: _Optional[bool] = ...) -> None: ...

class ListVaultsRequest(_message.Message):
    __slots__ = ("broker", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListVaultsResponse(_message.Message):
    __slots__ = ("vaults", "next_page_token")
    VAULTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    vaults: _containers.RepeatedCompositeFieldContainer[AffiliateVault]
    next_page_token: str
    def __init__(self, vaults: _Optional[_Iterable[_Union[AffiliateVault, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetVaultRequest(_message.Message):
    __slots__ = ("broker", "account_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    account_id: int
    def __init__(self, broker: _Optional[str] = ..., account_id: _Optional[int] = ...) -> None: ...

class GetVaultResponse(_message.Message):
    __slots__ = ("vault",)
    VAULT_FIELD_NUMBER: _ClassVar[int]
    vault: AffiliateVault
    def __init__(self, vault: _Optional[_Union[AffiliateVault, _Mapping]] = ...) -> None: ...

class SetVaultStatusRequest(_message.Message):
    __slots__ = ("broker", "account_id", "status")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    broker: str
    account_id: int
    status: VaultStatus
    def __init__(self, broker: _Optional[str] = ..., account_id: _Optional[int] = ..., status: _Optional[_Union[VaultStatus, str]] = ...) -> None: ...

class SetVaultStatusResponse(_message.Message):
    __slots__ = ("vault",)
    VAULT_FIELD_NUMBER: _ClassVar[int]
    vault: AffiliateVault
    def __init__(self, vault: _Optional[_Union[AffiliateVault, _Mapping]] = ...) -> None: ...

class QuickSwapSummary(_message.Message):
    __slots__ = ("swap_id", "idempotency_key", "status", "reason", "is_terminal", "terms", "fees", "charged_fees", "created_at", "updated_at")
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    IS_TERMINAL_FIELD_NUMBER: _ClassVar[int]
    TERMS_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    CHARGED_FEES_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    swap_id: int
    idempotency_key: str
    status: _quickswap_pb2.QuickSwapStatus
    reason: _quickswap_pb2.QuickSwapReason
    is_terminal: bool
    terms: _quickswap_pb2.QuickSwapTerms
    fees: _quickswap_pb2.RequestedFees
    charged_fees: _containers.RepeatedCompositeFieldContainer[_quickswap_pb2.ChargedFee]
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, swap_id: _Optional[int] = ..., idempotency_key: _Optional[str] = ..., status: _Optional[_Union[_quickswap_pb2.QuickSwapStatus, str]] = ..., reason: _Optional[_Union[_quickswap_pb2.QuickSwapReason, str]] = ..., is_terminal: _Optional[bool] = ..., terms: _Optional[_Union[_quickswap_pb2.QuickSwapTerms, _Mapping]] = ..., fees: _Optional[_Union[_quickswap_pb2.RequestedFees, _Mapping]] = ..., charged_fees: _Optional[_Iterable[_Union[_quickswap_pb2.ChargedFee, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class QuickSwapBrokerServiceGetQuickSwapRequest(_message.Message):
    __slots__ = ("broker", "swap_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    swap_id: int
    def __init__(self, broker: _Optional[str] = ..., swap_id: _Optional[int] = ...) -> None: ...

class QuickSwapBrokerServiceGetQuickSwapResponse(_message.Message):
    __slots__ = ("quick_swap",)
    QUICK_SWAP_FIELD_NUMBER: _ClassVar[int]
    quick_swap: _quickswap_pb2.QuickSwap
    def __init__(self, quick_swap: _Optional[_Union[_quickswap_pb2.QuickSwap, _Mapping]] = ...) -> None: ...

class ListQuickSwapsRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "statuses", "start_time", "end_time", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    statuses: _containers.RepeatedScalarFieldContainer[_quickswap_pb2.QuickSwapStatus]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., statuses: _Optional[_Iterable[_Union[_quickswap_pb2.QuickSwapStatus, str]]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListQuickSwapsResponse(_message.Message):
    __slots__ = ("quick_swaps", "next_page_token")
    QUICK_SWAPS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    quick_swaps: _containers.RepeatedCompositeFieldContainer[QuickSwapSummary]
    next_page_token: str
    def __init__(self, quick_swaps: _Optional[_Iterable[_Union[QuickSwapSummary, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetFeeTotalsRequest(_message.Message):
    __slots__ = ("broker", "group_by", "start_time", "end_time", "vault_account_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    GROUP_BY_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    group_by: FeeTotalsGrouping
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    vault_account_id: int
    def __init__(self, broker: _Optional[str] = ..., group_by: _Optional[_Union[FeeTotalsGrouping, str]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., vault_account_id: _Optional[int] = ...) -> None: ...

class FeeTotal(_message.Message):
    __slots__ = ("vault_account_id", "period_start", "asset_id", "amount", "swap_count")
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    PERIOD_START_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    SWAP_COUNT_FIELD_NUMBER: _ClassVar[int]
    vault_account_id: int
    period_start: _timestamp_pb2.Timestamp
    asset_id: int
    amount: _quickswap_pb2.TokenAmount
    swap_count: int
    def __init__(self, vault_account_id: _Optional[int] = ..., period_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., asset_id: _Optional[int] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., swap_count: _Optional[int] = ...) -> None: ...

class GetFeeTotalsResponse(_message.Message):
    __slots__ = ("totals",)
    TOTALS_FIELD_NUMBER: _ClassVar[int]
    totals: _containers.RepeatedCompositeFieldContainer[FeeTotal]
    def __init__(self, totals: _Optional[_Iterable[_Union[FeeTotal, _Mapping]]] = ...) -> None: ...

class GetBrokerStatsRequest(_message.Message):
    __slots__ = ("broker", "group_by", "start_time", "end_time")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    GROUP_BY_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    broker: str
    group_by: StatsPeriod
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    def __init__(self, broker: _Optional[str] = ..., group_by: _Optional[_Union[StatsPeriod, str]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StatusCount(_message.Message):
    __slots__ = ("status", "count")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    status: _quickswap_pb2.QuickSwapStatus
    count: int
    def __init__(self, status: _Optional[_Union[_quickswap_pb2.QuickSwapStatus, str]] = ..., count: _Optional[int] = ...) -> None: ...

class AssetVolume(_message.Message):
    __slots__ = ("asset_id", "amount")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    amount: _quickswap_pb2.TokenAmount
    def __init__(self, asset_id: _Optional[int] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class FeeSplit(_message.Message):
    __slots__ = ("asset_id", "service_fee", "broker_fee", "affiliate_fee", "referral_fee")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FEE_FIELD_NUMBER: _ClassVar[int]
    BROKER_FEE_FIELD_NUMBER: _ClassVar[int]
    AFFILIATE_FEE_FIELD_NUMBER: _ClassVar[int]
    REFERRAL_FEE_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    service_fee: _quickswap_pb2.TokenAmount
    broker_fee: _quickswap_pb2.TokenAmount
    affiliate_fee: _quickswap_pb2.TokenAmount
    referral_fee: _quickswap_pb2.TokenAmount
    def __init__(self, asset_id: _Optional[int] = ..., service_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., broker_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., affiliate_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., referral_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class BrokerStatsPeriod(_message.Message):
    __slots__ = ("period_start", "created_count", "statuses", "deposited", "delivered", "fees")
    PERIOD_START_FIELD_NUMBER: _ClassVar[int]
    CREATED_COUNT_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    DEPOSITED_FIELD_NUMBER: _ClassVar[int]
    DELIVERED_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    period_start: _timestamp_pb2.Timestamp
    created_count: int
    statuses: _containers.RepeatedCompositeFieldContainer[StatusCount]
    deposited: _containers.RepeatedCompositeFieldContainer[AssetVolume]
    delivered: _containers.RepeatedCompositeFieldContainer[AssetVolume]
    fees: _containers.RepeatedCompositeFieldContainer[FeeSplit]
    def __init__(self, period_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., created_count: _Optional[int] = ..., statuses: _Optional[_Iterable[_Union[StatusCount, _Mapping]]] = ..., deposited: _Optional[_Iterable[_Union[AssetVolume, _Mapping]]] = ..., delivered: _Optional[_Iterable[_Union[AssetVolume, _Mapping]]] = ..., fees: _Optional[_Iterable[_Union[FeeSplit, _Mapping]]] = ...) -> None: ...

class GetBrokerStatsResponse(_message.Message):
    __slots__ = ("periods",)
    PERIODS_FIELD_NUMBER: _ClassVar[int]
    periods: _containers.RepeatedCompositeFieldContainer[BrokerStatsPeriod]
    def __init__(self, periods: _Optional[_Iterable[_Union[BrokerStatsPeriod, _Mapping]]] = ...) -> None: ...

class ListVaultBalancesRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class VaultAssetBalance(_message.Message):
    __slots__ = ("asset_id", "amount", "pending_outgoing")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    PENDING_OUTGOING_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    amount: _quickswap_pb2.TokenAmount
    pending_outgoing: _quickswap_pb2.TokenAmount
    def __init__(self, asset_id: _Optional[int] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., pending_outgoing: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class VaultBalance(_message.Message):
    __slots__ = ("vault_account_id", "assets", "as_of")
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    AS_OF_FIELD_NUMBER: _ClassVar[int]
    vault_account_id: int
    assets: _containers.RepeatedCompositeFieldContainer[VaultAssetBalance]
    as_of: _timestamp_pb2.Timestamp
    def __init__(self, vault_account_id: _Optional[int] = ..., assets: _Optional[_Iterable[_Union[VaultAssetBalance, _Mapping]]] = ..., as_of: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListVaultBalancesResponse(_message.Message):
    __slots__ = ("vaults", "next_page_token")
    VAULTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    vaults: _containers.RepeatedCompositeFieldContainer[VaultBalance]
    next_page_token: str
    def __init__(self, vaults: _Optional[_Iterable[_Union[VaultBalance, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class PayoutStep(_message.Message):
    __slots__ = ("asset_id", "destination_chain_id", "destination_address", "state", "reason", "available", "amount", "minimum", "value_usd", "tx_hash", "charged_network_fee", "close", "refunded_amount")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    MINIMUM_FIELD_NUMBER: _ClassVar[int]
    VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    TX_HASH_FIELD_NUMBER: _ClassVar[int]
    CHARGED_NETWORK_FEE_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    REFUNDED_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    destination_chain_id: int
    destination_address: str
    state: PayoutStepState
    reason: str
    available: _quickswap_pb2.TokenAmount
    amount: _quickswap_pb2.TokenAmount
    minimum: _quickswap_pb2.TokenAmount
    value_usd: _quickswap_pb2.TokenAmount
    tx_hash: str
    charged_network_fee: _quickswap_pb2.TokenAmount
    close: PayoutClose
    refunded_amount: _quickswap_pb2.TokenAmount
    def __init__(self, asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., state: _Optional[_Union[PayoutStepState, str]] = ..., reason: _Optional[str] = ..., available: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., minimum: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., value_usd: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., tx_hash: _Optional[str] = ..., charged_network_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., close: _Optional[_Union[PayoutClose, str]] = ..., refunded_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class Payout(_message.Message):
    __slots__ = ("run_id", "vault_account_id", "status", "reason", "stage", "rule_version", "scheduled_for", "started_at", "finished_at", "min_usd_value", "steps")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    RULE_VERSION_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_FOR_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    MIN_USD_VALUE_FIELD_NUMBER: _ClassVar[int]
    STEPS_FIELD_NUMBER: _ClassVar[int]
    run_id: int
    vault_account_id: int
    status: PayoutStatus
    reason: str
    stage: PayoutStage
    rule_version: int
    scheduled_for: _timestamp_pb2.Timestamp
    started_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    min_usd_value: _quickswap_pb2.TokenAmount
    steps: _containers.RepeatedCompositeFieldContainer[PayoutStep]
    def __init__(self, run_id: _Optional[int] = ..., vault_account_id: _Optional[int] = ..., status: _Optional[_Union[PayoutStatus, str]] = ..., reason: _Optional[str] = ..., stage: _Optional[_Union[PayoutStage, str]] = ..., rule_version: _Optional[int] = ..., scheduled_for: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., min_usd_value: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., steps: _Optional[_Iterable[_Union[PayoutStep, _Mapping]]] = ...) -> None: ...

class ListPayoutsRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "statuses", "start_time", "end_time", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUSES_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    statuses: _containers.RepeatedScalarFieldContainer[PayoutStatus]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., statuses: _Optional[_Iterable[_Union[PayoutStatus, str]]] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListPayoutsResponse(_message.Message):
    __slots__ = ("payouts", "next_page_token")
    PAYOUTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    payouts: _containers.RepeatedCompositeFieldContainer[Payout]
    next_page_token: str
    def __init__(self, payouts: _Optional[_Iterable[_Union[Payout, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetPayoutRequest(_message.Message):
    __slots__ = ("broker", "run_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    run_id: int
    def __init__(self, broker: _Optional[str] = ..., run_id: _Optional[int] = ...) -> None: ...

class GetPayoutResponse(_message.Message):
    __slots__ = ("payout",)
    PAYOUT_FIELD_NUMBER: _ClassVar[int]
    payout: Payout
    def __init__(self, payout: _Optional[_Union[Payout, _Mapping]] = ...) -> None: ...

class UpcomingPayoutAsset(_message.Message):
    __slots__ = ("asset_id", "destination_chain_id", "destination_address", "available", "payable", "held_back", "hold_reason", "minimum", "value_usd", "priced_at", "estimated_network_fee", "estimated_network_fee_sampled_at", "payable_from")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    PAYABLE_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_FIELD_NUMBER: _ClassVar[int]
    HOLD_REASON_FIELD_NUMBER: _ClassVar[int]
    MINIMUM_FIELD_NUMBER: _ClassVar[int]
    VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    PRICED_AT_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_NETWORK_FEE_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_NETWORK_FEE_SAMPLED_AT_FIELD_NUMBER: _ClassVar[int]
    PAYABLE_FROM_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    destination_chain_id: int
    destination_address: str
    available: _quickswap_pb2.TokenAmount
    payable: _quickswap_pb2.TokenAmount
    held_back: _quickswap_pb2.TokenAmount
    hold_reason: str
    minimum: _quickswap_pb2.TokenAmount
    value_usd: _quickswap_pb2.TokenAmount
    priced_at: _timestamp_pb2.Timestamp
    estimated_network_fee: _quickswap_pb2.TokenAmount
    estimated_network_fee_sampled_at: _timestamp_pb2.Timestamp
    payable_from: _timestamp_pb2.Timestamp
    def __init__(self, asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., available: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., payable: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., held_back: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., hold_reason: _Optional[str] = ..., minimum: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., value_usd: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., priced_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., estimated_network_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., estimated_network_fee_sampled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., payable_from: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class UpcomingPayout(_message.Message):
    __slots__ = ("vault_account_id", "status", "next_run_at", "rule_version", "pause", "min_usd_value", "assets", "computed_at")
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    NEXT_RUN_AT_FIELD_NUMBER: _ClassVar[int]
    RULE_VERSION_FIELD_NUMBER: _ClassVar[int]
    PAUSE_FIELD_NUMBER: _ClassVar[int]
    MIN_USD_VALUE_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    COMPUTED_AT_FIELD_NUMBER: _ClassVar[int]
    vault_account_id: int
    status: _auto_withdraw_pb2.AutoWithdrawPreviewStatus
    next_run_at: _timestamp_pb2.Timestamp
    rule_version: int
    pause: _auto_withdraw_pb2.AutoWithdrawPause
    min_usd_value: _quickswap_pb2.TokenAmount
    assets: _containers.RepeatedCompositeFieldContainer[UpcomingPayoutAsset]
    computed_at: _timestamp_pb2.Timestamp
    def __init__(self, vault_account_id: _Optional[int] = ..., status: _Optional[_Union[_auto_withdraw_pb2.AutoWithdrawPreviewStatus, str]] = ..., next_run_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., rule_version: _Optional[int] = ..., pause: _Optional[_Union[_auto_withdraw_pb2.AutoWithdrawPause, _Mapping]] = ..., min_usd_value: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., assets: _Optional[_Iterable[_Union[UpcomingPayoutAsset, _Mapping]]] = ..., computed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListUpcomingPayoutsRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListUpcomingPayoutsResponse(_message.Message):
    __slots__ = ("upcoming_payouts", "next_page_token")
    UPCOMING_PAYOUTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    upcoming_payouts: _containers.RepeatedCompositeFieldContainer[UpcomingPayout]
    next_page_token: str
    def __init__(self, upcoming_payouts: _Optional[_Iterable[_Union[UpcomingPayout, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class PayoutRuleDestination(_message.Message):
    __slots__ = ("asset_id", "destination_chain_id", "destination_address", "min_amount", "max_amount", "min_floor", "estimated_network_fee", "estimated_network_fee_sampled_at")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    MAX_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    MIN_FLOOR_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_NETWORK_FEE_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_NETWORK_FEE_SAMPLED_AT_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    destination_chain_id: int
    destination_address: str
    min_amount: _quickswap_pb2.TokenAmount
    max_amount: _quickswap_pb2.TokenAmount
    min_floor: _quickswap_pb2.TokenAmount
    estimated_network_fee: _quickswap_pb2.TokenAmount
    estimated_network_fee_sampled_at: _timestamp_pb2.Timestamp
    def __init__(self, asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., min_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., max_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., min_floor: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., estimated_network_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., estimated_network_fee_sampled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AssetWithoutDestination(_message.Message):
    __slots__ = ("asset_id", "balance")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    balance: _quickswap_pb2.TokenAmount
    def __init__(self, asset_id: _Optional[int] = ..., balance: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class VaultPayoutRule(_message.Message):
    __slots__ = ("vault_account_id", "rule_version", "enabled", "schedule", "destinations", "pause", "min_usd_value", "updated_at", "assets_without_destination")
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    RULE_VERSION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    DESTINATIONS_FIELD_NUMBER: _ClassVar[int]
    PAUSE_FIELD_NUMBER: _ClassVar[int]
    MIN_USD_VALUE_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    ASSETS_WITHOUT_DESTINATION_FIELD_NUMBER: _ClassVar[int]
    vault_account_id: int
    rule_version: int
    enabled: bool
    schedule: _auto_withdraw_pb2.AutoWithdrawSchedule
    destinations: _containers.RepeatedCompositeFieldContainer[PayoutRuleDestination]
    pause: _auto_withdraw_pb2.AutoWithdrawPause
    min_usd_value: _quickswap_pb2.TokenAmount
    updated_at: _timestamp_pb2.Timestamp
    assets_without_destination: _containers.RepeatedCompositeFieldContainer[AssetWithoutDestination]
    def __init__(self, vault_account_id: _Optional[int] = ..., rule_version: _Optional[int] = ..., enabled: _Optional[bool] = ..., schedule: _Optional[_Union[_auto_withdraw_pb2.AutoWithdrawSchedule, _Mapping]] = ..., destinations: _Optional[_Iterable[_Union[PayoutRuleDestination, _Mapping]]] = ..., pause: _Optional[_Union[_auto_withdraw_pb2.AutoWithdrawPause, _Mapping]] = ..., min_usd_value: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., assets_without_destination: _Optional[_Iterable[_Union[AssetWithoutDestination, _Mapping]]] = ...) -> None: ...

class ListVaultPayoutRulesRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListVaultPayoutRulesResponse(_message.Message):
    __slots__ = ("rules", "next_page_token")
    RULES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedCompositeFieldContainer[VaultPayoutRule]
    next_page_token: str
    def __init__(self, rules: _Optional[_Iterable[_Union[VaultPayoutRule, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class VaultLedgerFeeCredit(_message.Message):
    __slots__ = ("credit_id", "swap_id", "fee_kind", "fee_bps", "source_zipped_asset_id", "destination_zipped_asset_id", "quoted_source_amount", "quoted_destination_amount", "source_amount", "destination_amount")
    CREDIT_ID_FIELD_NUMBER: _ClassVar[int]
    SWAP_ID_FIELD_NUMBER: _ClassVar[int]
    FEE_KIND_FIELD_NUMBER: _ClassVar[int]
    FEE_BPS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    QUOTED_SOURCE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    QUOTED_DESTINATION_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    SOURCE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    credit_id: int
    swap_id: int
    fee_kind: _quickswap_pb2.FeeKind
    fee_bps: int
    source_zipped_asset_id: int
    destination_zipped_asset_id: int
    quoted_source_amount: _quickswap_pb2.TokenAmount
    quoted_destination_amount: _quickswap_pb2.TokenAmount
    source_amount: _quickswap_pb2.TokenAmount
    destination_amount: _quickswap_pb2.TokenAmount
    def __init__(self, credit_id: _Optional[int] = ..., swap_id: _Optional[int] = ..., fee_kind: _Optional[_Union[_quickswap_pb2.FeeKind, str]] = ..., fee_bps: _Optional[int] = ..., source_zipped_asset_id: _Optional[int] = ..., destination_zipped_asset_id: _Optional[int] = ..., quoted_source_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., quoted_destination_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., source_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., destination_amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class VaultLedgerPayoutDebit(_message.Message):
    __slots__ = ("run_id", "payout_status", "destination_chain_id", "destination_address", "tx_hash", "state", "reason", "close", "charged_network_fee")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    PAYOUT_STATUS_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    TX_HASH_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    CHARGED_NETWORK_FEE_FIELD_NUMBER: _ClassVar[int]
    run_id: int
    payout_status: PayoutStatus
    destination_chain_id: int
    destination_address: str
    tx_hash: str
    state: PayoutStepState
    reason: str
    close: PayoutClose
    charged_network_fee: _quickswap_pb2.TokenAmount
    def __init__(self, run_id: _Optional[int] = ..., payout_status: _Optional[_Union[PayoutStatus, str]] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., tx_hash: _Optional[str] = ..., state: _Optional[_Union[PayoutStepState, str]] = ..., reason: _Optional[str] = ..., close: _Optional[_Union[PayoutClose, str]] = ..., charged_network_fee: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ...) -> None: ...

class VaultLedgerPayoutRefund(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: int
    def __init__(self, run_id: _Optional[int] = ...) -> None: ...

class VaultLedgerEntry(_message.Message):
    __slots__ = ("kind", "occurred_at", "vault_account_id", "asset_id", "amount", "fee_credit", "payout_debit", "payout_refund")
    KIND_FIELD_NUMBER: _ClassVar[int]
    OCCURRED_AT_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    FEE_CREDIT_FIELD_NUMBER: _ClassVar[int]
    PAYOUT_DEBIT_FIELD_NUMBER: _ClassVar[int]
    PAYOUT_REFUND_FIELD_NUMBER: _ClassVar[int]
    kind: VaultLedgerEntryKind
    occurred_at: _timestamp_pb2.Timestamp
    vault_account_id: int
    asset_id: int
    amount: _quickswap_pb2.TokenAmount
    fee_credit: VaultLedgerFeeCredit
    payout_debit: VaultLedgerPayoutDebit
    payout_refund: VaultLedgerPayoutRefund
    def __init__(self, kind: _Optional[_Union[VaultLedgerEntryKind, str]] = ..., occurred_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., vault_account_id: _Optional[int] = ..., asset_id: _Optional[int] = ..., amount: _Optional[_Union[_quickswap_pb2.TokenAmount, _Mapping]] = ..., fee_credit: _Optional[_Union[VaultLedgerFeeCredit, _Mapping]] = ..., payout_debit: _Optional[_Union[VaultLedgerPayoutDebit, _Mapping]] = ..., payout_refund: _Optional[_Union[VaultLedgerPayoutRefund, _Mapping]] = ...) -> None: ...

class ListVaultLedgerRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "start_time", "end_time", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListVaultLedgerResponse(_message.Message):
    __slots__ = ("entries", "next_page_token")
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[VaultLedgerEntry]
    next_page_token: str
    def __init__(self, entries: _Optional[_Iterable[_Union[VaultLedgerEntry, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class VaultAllowlistEntry(_message.Message):
    __slots__ = ("destination_chain_id", "destination_address", "label", "created_by_account_id", "listed_at", "payable_from", "cooling_down", "used_by_payout_rule")
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    CREATED_BY_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LISTED_AT_FIELD_NUMBER: _ClassVar[int]
    PAYABLE_FROM_FIELD_NUMBER: _ClassVar[int]
    COOLING_DOWN_FIELD_NUMBER: _ClassVar[int]
    USED_BY_PAYOUT_RULE_FIELD_NUMBER: _ClassVar[int]
    destination_chain_id: int
    destination_address: str
    label: str
    created_by_account_id: int
    listed_at: _timestamp_pb2.Timestamp
    payable_from: _timestamp_pb2.Timestamp
    cooling_down: bool
    used_by_payout_rule: bool
    def __init__(self, destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., label: _Optional[str] = ..., created_by_account_id: _Optional[int] = ..., listed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., payable_from: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., cooling_down: _Optional[bool] = ..., used_by_payout_rule: _Optional[bool] = ...) -> None: ...

class VaultAllowlistChange(_message.Message):
    __slots__ = ("change_id", "vault_account_id", "action", "destination_chain_id", "destination_address", "label", "requested_by_account_id", "requested_at", "expires_at", "status", "failure", "closed_at")
    CHANGE_ID_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_BY_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUESTED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    CLOSED_AT_FIELD_NUMBER: _ClassVar[int]
    change_id: int
    vault_account_id: int
    action: AllowlistAction
    destination_chain_id: int
    destination_address: str
    label: str
    requested_by_account_id: int
    requested_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    status: AllowlistChangeStatus
    failure: AllowlistChangeFailure
    closed_at: _timestamp_pb2.Timestamp
    def __init__(self, change_id: _Optional[int] = ..., vault_account_id: _Optional[int] = ..., action: _Optional[_Union[AllowlistAction, str]] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., label: _Optional[str] = ..., requested_by_account_id: _Optional[int] = ..., requested_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., status: _Optional[_Union[AllowlistChangeStatus, str]] = ..., failure: _Optional[_Union[AllowlistChangeFailure, str]] = ..., closed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListVaultAllowlistRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "destination_chain_id")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    destination_chain_id: int
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ...) -> None: ...

class ListVaultAllowlistResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[VaultAllowlistEntry]
    def __init__(self, entries: _Optional[_Iterable[_Union[VaultAllowlistEntry, _Mapping]]] = ...) -> None: ...

class ListVaultAllowlistChangesRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "limit", "page_token")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    limit: int
    page_token: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListVaultAllowlistChangesResponse(_message.Message):
    __slots__ = ("changes", "next_page_token")
    CHANGES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    changes: _containers.RepeatedCompositeFieldContainer[VaultAllowlistChange]
    next_page_token: str
    def __init__(self, changes: _Optional[_Iterable[_Union[VaultAllowlistChange, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class RequestVaultAllowlistChangeRequest(_message.Message):
    __slots__ = ("broker", "vault_account_id", "action", "destination_chain_id", "destination_address", "label")
    BROKER_FIELD_NUMBER: _ClassVar[int]
    VAULT_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    broker: str
    vault_account_id: int
    action: AllowlistAction
    destination_chain_id: int
    destination_address: str
    label: str
    def __init__(self, broker: _Optional[str] = ..., vault_account_id: _Optional[int] = ..., action: _Optional[_Union[AllowlistAction, str]] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., label: _Optional[str] = ...) -> None: ...

class RequestVaultAllowlistChangeResponse(_message.Message):
    __slots__ = ("change",)
    CHANGE_FIELD_NUMBER: _ClassVar[int]
    change: VaultAllowlistChange
    def __init__(self, change: _Optional[_Union[VaultAllowlistChange, _Mapping]] = ...) -> None: ...
