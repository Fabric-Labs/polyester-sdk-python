import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from polyester.gen.google.api import field_behavior_pb2 as _field_behavior_pb2
from google.protobuf import field_mask_pb2 as _field_mask_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PolicyAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNSPECIFIED: _ClassVar[PolicyAction]
    TRADE_SPOT: _ClassVar[PolicyAction]
    TRADE_PERP: _ClassVar[PolicyAction]
    INTERNAL_TRANSFER: _ClassVar[PolicyAction]
    EXTERNAL_WITHDRAW: _ClassVar[PolicyAction]
    READ_BALANCES: _ClassVar[PolicyAction]
    READ_SPOT: _ClassVar[PolicyAction]
    READ_PERP: _ClassVar[PolicyAction]
    READ_INTERNAL_TRANSFERS: _ClassVar[PolicyAction]
    READ_EXTERNAL_WITHDRAWALS: _ClassVar[PolicyAction]
    READ_TRANSFER_CONTROLS: _ClassVar[PolicyAction]
    MANAGE_ADDRESS_BOOK: _ClassVar[PolicyAction]
    MANAGE_TRANSFER_WHITELISTS: _ClassVar[PolicyAction]
UNSPECIFIED: PolicyAction
TRADE_SPOT: PolicyAction
TRADE_PERP: PolicyAction
INTERNAL_TRANSFER: PolicyAction
EXTERNAL_WITHDRAW: PolicyAction
READ_BALANCES: PolicyAction
READ_SPOT: PolicyAction
READ_PERP: PolicyAction
READ_INTERNAL_TRANSFERS: PolicyAction
READ_EXTERNAL_WITHDRAWALS: PolicyAction
READ_TRANSFER_CONTROLS: PolicyAction
MANAGE_ADDRESS_BOOK: PolicyAction
MANAGE_TRANSFER_WHITELISTS: PolicyAction

class MarketScope(_message.Message):
    __slots__ = ()
    class Value(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNSPECIFIED: _ClassVar[MarketScope.Value]
        ALL: _ClassVar[MarketScope.Value]
        ALLOWLIST: _ClassVar[MarketScope.Value]
    UNSPECIFIED: MarketScope.Value
    ALL: MarketScope.Value
    ALLOWLIST: MarketScope.Value
    def __init__(self) -> None: ...

class SpotMarketRule(_message.Message):
    __slots__ = ("symbol",)
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    def __init__(self, symbol: _Optional[str] = ...) -> None: ...

class PerpMarketRule(_message.Message):
    __slots__ = ("symbol", "max_leverage_x")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    MAX_LEVERAGE_X_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    max_leverage_x: int
    def __init__(self, symbol: _Optional[str] = ..., max_leverage_x: _Optional[int] = ...) -> None: ...

class SubaccountPolicyView(_message.Message):
    __slots__ = ("id", "name", "description", "spot_markets", "perp_markets", "spot_market_scope", "perp_market_scope", "actions", "is_template", "source_template_id", "global_notional_cap", "max_order_notional", "max_open_orders", "max_open_positions", "global_perp_leverage_x", "daily_internal_transfer_out_limit", "daily_withdraw_limit", "internal_transfers_own_only", "enforce_withdraw_whitelist", "trading_halted", "liquidation_only", "daily_loss_limit", "intraday_drawdown_limit_bps", "locked", "review_at", "expires_at", "created_at", "updated_at", "revision")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKETS_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKETS_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    IS_TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_NOTIONAL_CAP_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDER_NOTIONAL_FIELD_NUMBER: _ClassVar[int]
    MAX_OPEN_ORDERS_FIELD_NUMBER: _ClassVar[int]
    MAX_OPEN_POSITIONS_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_PERP_LEVERAGE_X_FIELD_NUMBER: _ClassVar[int]
    DAILY_INTERNAL_TRANSFER_OUT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DAILY_WITHDRAW_LIMIT_FIELD_NUMBER: _ClassVar[int]
    INTERNAL_TRANSFERS_OWN_ONLY_FIELD_NUMBER: _ClassVar[int]
    ENFORCE_WITHDRAW_WHITELIST_FIELD_NUMBER: _ClassVar[int]
    TRADING_HALTED_FIELD_NUMBER: _ClassVar[int]
    LIQUIDATION_ONLY_FIELD_NUMBER: _ClassVar[int]
    DAILY_LOSS_LIMIT_FIELD_NUMBER: _ClassVar[int]
    INTRADAY_DRAWDOWN_LIMIT_BPS_FIELD_NUMBER: _ClassVar[int]
    LOCKED_FIELD_NUMBER: _ClassVar[int]
    REVIEW_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    description: str
    spot_markets: _containers.RepeatedCompositeFieldContainer[SpotMarketRule]
    perp_markets: _containers.RepeatedCompositeFieldContainer[PerpMarketRule]
    spot_market_scope: MarketScope.Value
    perp_market_scope: MarketScope.Value
    actions: _containers.RepeatedScalarFieldContainer[PolicyAction]
    is_template: bool
    source_template_id: int
    global_notional_cap: int
    max_order_notional: int
    max_open_orders: int
    max_open_positions: int
    global_perp_leverage_x: int
    daily_internal_transfer_out_limit: int
    daily_withdraw_limit: int
    internal_transfers_own_only: bool
    enforce_withdraw_whitelist: bool
    trading_halted: bool
    liquidation_only: bool
    daily_loss_limit: int
    intraday_drawdown_limit_bps: int
    locked: bool
    review_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    revision: int
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., spot_markets: _Optional[_Iterable[_Union[SpotMarketRule, _Mapping]]] = ..., perp_markets: _Optional[_Iterable[_Union[PerpMarketRule, _Mapping]]] = ..., spot_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., perp_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., actions: _Optional[_Iterable[_Union[PolicyAction, str]]] = ..., is_template: _Optional[bool] = ..., source_template_id: _Optional[int] = ..., global_notional_cap: _Optional[int] = ..., max_order_notional: _Optional[int] = ..., max_open_orders: _Optional[int] = ..., max_open_positions: _Optional[int] = ..., global_perp_leverage_x: _Optional[int] = ..., daily_internal_transfer_out_limit: _Optional[int] = ..., daily_withdraw_limit: _Optional[int] = ..., internal_transfers_own_only: _Optional[bool] = ..., enforce_withdraw_whitelist: _Optional[bool] = ..., trading_halted: _Optional[bool] = ..., liquidation_only: _Optional[bool] = ..., daily_loss_limit: _Optional[int] = ..., intraday_drawdown_limit_bps: _Optional[int] = ..., locked: _Optional[bool] = ..., review_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., revision: _Optional[int] = ...) -> None: ...

class ListSubaccountPoliciesRequest(_message.Message):
    __slots__ = ("subaccount_id",)
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    def __init__(self, subaccount_id: _Optional[int] = ...) -> None: ...

class ListSubaccountPoliciesResponse(_message.Message):
    __slots__ = ("policies",)
    POLICIES_FIELD_NUMBER: _ClassVar[int]
    policies: _containers.RepeatedCompositeFieldContainer[SubaccountPolicyView]
    def __init__(self, policies: _Optional[_Iterable[_Union[SubaccountPolicyView, _Mapping]]] = ...) -> None: ...

class GetSubaccountPolicyRequest(_message.Message):
    __slots__ = ("policy_id", "subaccount_id")
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    policy_id: int
    subaccount_id: int
    def __init__(self, policy_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class GetSubaccountPolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: SubaccountPolicyView
    def __init__(self, policy: _Optional[_Union[SubaccountPolicyView, _Mapping]] = ...) -> None: ...

class SubaccountPolicySpec(_message.Message):
    __slots__ = ("name", "description", "spot_markets", "perp_markets", "spot_market_scope", "perp_market_scope", "actions", "global_notional_cap", "max_order_notional", "max_open_orders", "max_open_positions", "global_perp_leverage_x", "daily_internal_transfer_out_limit", "daily_withdraw_limit", "internal_transfers_own_only", "enforce_withdraw_whitelist", "trading_halted", "liquidation_only", "daily_loss_limit", "intraday_drawdown_limit_bps", "locked", "review_at", "expires_at")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKETS_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKETS_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_NOTIONAL_CAP_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDER_NOTIONAL_FIELD_NUMBER: _ClassVar[int]
    MAX_OPEN_ORDERS_FIELD_NUMBER: _ClassVar[int]
    MAX_OPEN_POSITIONS_FIELD_NUMBER: _ClassVar[int]
    GLOBAL_PERP_LEVERAGE_X_FIELD_NUMBER: _ClassVar[int]
    DAILY_INTERNAL_TRANSFER_OUT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DAILY_WITHDRAW_LIMIT_FIELD_NUMBER: _ClassVar[int]
    INTERNAL_TRANSFERS_OWN_ONLY_FIELD_NUMBER: _ClassVar[int]
    ENFORCE_WITHDRAW_WHITELIST_FIELD_NUMBER: _ClassVar[int]
    TRADING_HALTED_FIELD_NUMBER: _ClassVar[int]
    LIQUIDATION_ONLY_FIELD_NUMBER: _ClassVar[int]
    DAILY_LOSS_LIMIT_FIELD_NUMBER: _ClassVar[int]
    INTRADAY_DRAWDOWN_LIMIT_BPS_FIELD_NUMBER: _ClassVar[int]
    LOCKED_FIELD_NUMBER: _ClassVar[int]
    REVIEW_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    spot_markets: _containers.RepeatedCompositeFieldContainer[SpotMarketRule]
    perp_markets: _containers.RepeatedCompositeFieldContainer[PerpMarketRule]
    spot_market_scope: MarketScope.Value
    perp_market_scope: MarketScope.Value
    actions: _containers.RepeatedScalarFieldContainer[PolicyAction]
    global_notional_cap: int
    max_order_notional: int
    max_open_orders: int
    max_open_positions: int
    global_perp_leverage_x: int
    daily_internal_transfer_out_limit: int
    daily_withdraw_limit: int
    internal_transfers_own_only: bool
    enforce_withdraw_whitelist: bool
    trading_halted: bool
    liquidation_only: bool
    daily_loss_limit: int
    intraday_drawdown_limit_bps: int
    locked: bool
    review_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., spot_markets: _Optional[_Iterable[_Union[SpotMarketRule, _Mapping]]] = ..., perp_markets: _Optional[_Iterable[_Union[PerpMarketRule, _Mapping]]] = ..., spot_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., perp_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., actions: _Optional[_Iterable[_Union[PolicyAction, str]]] = ..., global_notional_cap: _Optional[int] = ..., max_order_notional: _Optional[int] = ..., max_open_orders: _Optional[int] = ..., max_open_positions: _Optional[int] = ..., global_perp_leverage_x: _Optional[int] = ..., daily_internal_transfer_out_limit: _Optional[int] = ..., daily_withdraw_limit: _Optional[int] = ..., internal_transfers_own_only: _Optional[bool] = ..., enforce_withdraw_whitelist: _Optional[bool] = ..., trading_halted: _Optional[bool] = ..., liquidation_only: _Optional[bool] = ..., daily_loss_limit: _Optional[int] = ..., intraday_drawdown_limit_bps: _Optional[int] = ..., locked: _Optional[bool] = ..., review_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateSubaccountPolicyRequest(_message.Message):
    __slots__ = ("policy", "subaccount_id")
    POLICY_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    policy: SubaccountPolicySpec
    subaccount_id: int
    def __init__(self, policy: _Optional[_Union[SubaccountPolicySpec, _Mapping]] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class CreateSubaccountPolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: SubaccountPolicyView
    def __init__(self, policy: _Optional[_Union[SubaccountPolicyView, _Mapping]] = ...) -> None: ...

class UpdateSubaccountPolicyRequest(_message.Message):
    __slots__ = ("policy_id", "policy", "update_mask", "expected_revision")
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_FIELD_NUMBER: _ClassVar[int]
    UPDATE_MASK_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    policy_id: int
    policy: SubaccountPolicySpec
    update_mask: _field_mask_pb2.FieldMask
    expected_revision: int
    def __init__(self, policy_id: _Optional[int] = ..., policy: _Optional[_Union[SubaccountPolicySpec, _Mapping]] = ..., update_mask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., expected_revision: _Optional[int] = ...) -> None: ...

class UpdateSubaccountPolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: SubaccountPolicyView
    def __init__(self, policy: _Optional[_Union[SubaccountPolicyView, _Mapping]] = ...) -> None: ...

class DeleteSubaccountPolicyRequest(_message.Message):
    __slots__ = ("policy_id",)
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    policy_id: int
    def __init__(self, policy_id: _Optional[int] = ...) -> None: ...

class DeleteSubaccountPolicyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetSubaccountPolicyRequest(_message.Message):
    __slots__ = ("subaccount_id", "policy_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    policy_id: int
    def __init__(self, subaccount_id: _Optional[int] = ..., policy_id: _Optional[int] = ...) -> None: ...

class SetSubaccountPolicyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ApiPolicyView(_message.Message):
    __slots__ = ("id", "name", "description", "spot_markets", "perp_markets", "actions", "spot_market_scope", "perp_market_scope", "max_order_notional", "daily_internal_transfer_out_limit", "daily_withdraw_limit", "is_template", "source_template_id", "created_at", "updated_at", "revision")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKETS_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKETS_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDER_NOTIONAL_FIELD_NUMBER: _ClassVar[int]
    DAILY_INTERNAL_TRANSFER_OUT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DAILY_WITHDRAW_LIMIT_FIELD_NUMBER: _ClassVar[int]
    IS_TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    id: int
    name: str
    description: str
    spot_markets: _containers.RepeatedCompositeFieldContainer[SpotMarketRule]
    perp_markets: _containers.RepeatedCompositeFieldContainer[PerpMarketRule]
    actions: _containers.RepeatedScalarFieldContainer[PolicyAction]
    spot_market_scope: MarketScope.Value
    perp_market_scope: MarketScope.Value
    max_order_notional: int
    daily_internal_transfer_out_limit: int
    daily_withdraw_limit: int
    is_template: bool
    source_template_id: int
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    revision: int
    def __init__(self, id: _Optional[int] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., spot_markets: _Optional[_Iterable[_Union[SpotMarketRule, _Mapping]]] = ..., perp_markets: _Optional[_Iterable[_Union[PerpMarketRule, _Mapping]]] = ..., actions: _Optional[_Iterable[_Union[PolicyAction, str]]] = ..., spot_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., perp_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., max_order_notional: _Optional[int] = ..., daily_internal_transfer_out_limit: _Optional[int] = ..., daily_withdraw_limit: _Optional[int] = ..., is_template: _Optional[bool] = ..., source_template_id: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., revision: _Optional[int] = ...) -> None: ...

class ListApiPoliciesRequest(_message.Message):
    __slots__ = ("key_id",)
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    def __init__(self, key_id: _Optional[str] = ...) -> None: ...

class ListApiPoliciesResponse(_message.Message):
    __slots__ = ("policies",)
    POLICIES_FIELD_NUMBER: _ClassVar[int]
    policies: _containers.RepeatedCompositeFieldContainer[ApiPolicyView]
    def __init__(self, policies: _Optional[_Iterable[_Union[ApiPolicyView, _Mapping]]] = ...) -> None: ...

class GetApiPolicyRequest(_message.Message):
    __slots__ = ("policy_id", "key_id")
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    policy_id: int
    key_id: str
    def __init__(self, policy_id: _Optional[int] = ..., key_id: _Optional[str] = ...) -> None: ...

class GetApiPolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: ApiPolicyView
    def __init__(self, policy: _Optional[_Union[ApiPolicyView, _Mapping]] = ...) -> None: ...

class ApiPolicySpec(_message.Message):
    __slots__ = ("name", "description", "spot_markets", "perp_markets", "spot_market_scope", "perp_market_scope", "actions", "max_order_notional", "daily_internal_transfer_out_limit", "daily_withdraw_limit", "is_template")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKETS_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKETS_FIELD_NUMBER: _ClassVar[int]
    SPOT_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    PERP_MARKET_SCOPE_FIELD_NUMBER: _ClassVar[int]
    ACTIONS_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDER_NOTIONAL_FIELD_NUMBER: _ClassVar[int]
    DAILY_INTERNAL_TRANSFER_OUT_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DAILY_WITHDRAW_LIMIT_FIELD_NUMBER: _ClassVar[int]
    IS_TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    spot_markets: _containers.RepeatedCompositeFieldContainer[SpotMarketRule]
    perp_markets: _containers.RepeatedCompositeFieldContainer[PerpMarketRule]
    spot_market_scope: MarketScope.Value
    perp_market_scope: MarketScope.Value
    actions: _containers.RepeatedScalarFieldContainer[PolicyAction]
    max_order_notional: int
    daily_internal_transfer_out_limit: int
    daily_withdraw_limit: int
    is_template: bool
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., spot_markets: _Optional[_Iterable[_Union[SpotMarketRule, _Mapping]]] = ..., perp_markets: _Optional[_Iterable[_Union[PerpMarketRule, _Mapping]]] = ..., spot_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., perp_market_scope: _Optional[_Union[MarketScope.Value, str]] = ..., actions: _Optional[_Iterable[_Union[PolicyAction, str]]] = ..., max_order_notional: _Optional[int] = ..., daily_internal_transfer_out_limit: _Optional[int] = ..., daily_withdraw_limit: _Optional[int] = ..., is_template: _Optional[bool] = ...) -> None: ...

class CreateApiPolicyRequest(_message.Message):
    __slots__ = ("policy", "assign_to_key_id")
    POLICY_FIELD_NUMBER: _ClassVar[int]
    ASSIGN_TO_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    policy: ApiPolicySpec
    assign_to_key_id: str
    def __init__(self, policy: _Optional[_Union[ApiPolicySpec, _Mapping]] = ..., assign_to_key_id: _Optional[str] = ...) -> None: ...

class CreateApiPolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: ApiPolicyView
    def __init__(self, policy: _Optional[_Union[ApiPolicyView, _Mapping]] = ...) -> None: ...

class UpdateApiPolicyRequest(_message.Message):
    __slots__ = ("policy_id", "policy", "update_mask", "expected_revision")
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_FIELD_NUMBER: _ClassVar[int]
    UPDATE_MASK_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    policy_id: int
    policy: ApiPolicySpec
    update_mask: _field_mask_pb2.FieldMask
    expected_revision: int
    def __init__(self, policy_id: _Optional[int] = ..., policy: _Optional[_Union[ApiPolicySpec, _Mapping]] = ..., update_mask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., expected_revision: _Optional[int] = ...) -> None: ...

class UpdateApiPolicyResponse(_message.Message):
    __slots__ = ("policy",)
    POLICY_FIELD_NUMBER: _ClassVar[int]
    policy: ApiPolicyView
    def __init__(self, policy: _Optional[_Union[ApiPolicyView, _Mapping]] = ...) -> None: ...

class DeleteApiPolicyRequest(_message.Message):
    __slots__ = ("policy_id",)
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    policy_id: int
    def __init__(self, policy_id: _Optional[int] = ...) -> None: ...

class DeleteApiPolicyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SetApiKeyPolicyRequest(_message.Message):
    __slots__ = ("key_id", "policy_id")
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    POLICY_ID_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    policy_id: int
    def __init__(self, key_id: _Optional[str] = ..., policy_id: _Optional[int] = ...) -> None: ...

class SetApiKeyPolicyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
