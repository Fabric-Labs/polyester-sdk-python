import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.polyester.type.v1 import u128_pb2 as _u128_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AutoWithdrawCadence(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CADENCE_UNSPECIFIED: _ClassVar[AutoWithdrawCadence]
    DAILY: _ClassVar[AutoWithdrawCadence]
    WEEKLY: _ClassVar[AutoWithdrawCadence]
    HOURLY: _ClassVar[AutoWithdrawCadence]
    BIWEEKLY: _ClassVar[AutoWithdrawCadence]
    MONTHLY: _ClassVar[AutoWithdrawCadence]

class AutoWithdrawWeekday(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WEEKDAY_UNSPECIFIED: _ClassVar[AutoWithdrawWeekday]
    MONDAY: _ClassVar[AutoWithdrawWeekday]
    TUESDAY: _ClassVar[AutoWithdrawWeekday]
    WEDNESDAY: _ClassVar[AutoWithdrawWeekday]
    THURSDAY: _ClassVar[AutoWithdrawWeekday]
    FRIDAY: _ClassVar[AutoWithdrawWeekday]
    SATURDAY: _ClassVar[AutoWithdrawWeekday]
    SUNDAY: _ClassVar[AutoWithdrawWeekday]

class AutoWithdrawRunState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RUN_STATE_UNSPECIFIED: _ClassVar[AutoWithdrawRunState]
    RUN_PLANNED: _ClassVar[AutoWithdrawRunState]
    RUN_PAYING: _ClassVar[AutoWithdrawRunState]
    RUN_COMPLETED: _ClassVar[AutoWithdrawRunState]
    RUN_PARTIALLY_FAILED: _ClassVar[AutoWithdrawRunState]
    RUN_FAILED: _ClassVar[AutoWithdrawRunState]
    RUN_SKIPPED: _ClassVar[AutoWithdrawRunState]

class AutoWithdrawStepState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STEP_STATE_UNSPECIFIED: _ClassVar[AutoWithdrawStepState]
    STEP_PENDING: _ClassVar[AutoWithdrawStepState]
    STEP_SUBMITTING: _ClassVar[AutoWithdrawStepState]
    STEP_SUBMITTED: _ClassVar[AutoWithdrawStepState]
    STEP_COMPLETED: _ClassVar[AutoWithdrawStepState]
    STEP_FAILED: _ClassVar[AutoWithdrawStepState]
    STEP_SKIPPED: _ClassVar[AutoWithdrawStepState]

class AutoWithdrawPreviewStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PREVIEW_STATUS_UNSPECIFIED: _ClassVar[AutoWithdrawPreviewStatus]
    WILL_PAY: _ClassVar[AutoWithdrawPreviewStatus]
    ROLLS_OVER: _ClassVar[AutoWithdrawPreviewStatus]
    NO_DESTINATION: _ClassVar[AutoWithdrawPreviewStatus]
    PAUSED: _ClassVar[AutoWithdrawPreviewStatus]
    NO_RULE: _ClassVar[AutoWithdrawPreviewStatus]
CADENCE_UNSPECIFIED: AutoWithdrawCadence
DAILY: AutoWithdrawCadence
WEEKLY: AutoWithdrawCadence
HOURLY: AutoWithdrawCadence
BIWEEKLY: AutoWithdrawCadence
MONTHLY: AutoWithdrawCadence
WEEKDAY_UNSPECIFIED: AutoWithdrawWeekday
MONDAY: AutoWithdrawWeekday
TUESDAY: AutoWithdrawWeekday
WEDNESDAY: AutoWithdrawWeekday
THURSDAY: AutoWithdrawWeekday
FRIDAY: AutoWithdrawWeekday
SATURDAY: AutoWithdrawWeekday
SUNDAY: AutoWithdrawWeekday
RUN_STATE_UNSPECIFIED: AutoWithdrawRunState
RUN_PLANNED: AutoWithdrawRunState
RUN_PAYING: AutoWithdrawRunState
RUN_COMPLETED: AutoWithdrawRunState
RUN_PARTIALLY_FAILED: AutoWithdrawRunState
RUN_FAILED: AutoWithdrawRunState
RUN_SKIPPED: AutoWithdrawRunState
STEP_STATE_UNSPECIFIED: AutoWithdrawStepState
STEP_PENDING: AutoWithdrawStepState
STEP_SUBMITTING: AutoWithdrawStepState
STEP_SUBMITTED: AutoWithdrawStepState
STEP_COMPLETED: AutoWithdrawStepState
STEP_FAILED: AutoWithdrawStepState
STEP_SKIPPED: AutoWithdrawStepState
PREVIEW_STATUS_UNSPECIFIED: AutoWithdrawPreviewStatus
WILL_PAY: AutoWithdrawPreviewStatus
ROLLS_OVER: AutoWithdrawPreviewStatus
NO_DESTINATION: AutoWithdrawPreviewStatus
PAUSED: AutoWithdrawPreviewStatus
NO_RULE: AutoWithdrawPreviewStatus

class AutoWithdrawSchedule(_message.Message):
    __slots__ = ("cadence", "weekday", "minute_of_day", "minute_of_hour", "day_of_month", "anchor_date")
    CADENCE_FIELD_NUMBER: _ClassVar[int]
    WEEKDAY_FIELD_NUMBER: _ClassVar[int]
    MINUTE_OF_DAY_FIELD_NUMBER: _ClassVar[int]
    MINUTE_OF_HOUR_FIELD_NUMBER: _ClassVar[int]
    DAY_OF_MONTH_FIELD_NUMBER: _ClassVar[int]
    ANCHOR_DATE_FIELD_NUMBER: _ClassVar[int]
    cadence: AutoWithdrawCadence
    weekday: AutoWithdrawWeekday
    minute_of_day: int
    minute_of_hour: int
    day_of_month: int
    anchor_date: str
    def __init__(self, cadence: _Optional[_Union[AutoWithdrawCadence, str]] = ..., weekday: _Optional[_Union[AutoWithdrawWeekday, str]] = ..., minute_of_day: _Optional[int] = ..., minute_of_hour: _Optional[int] = ..., day_of_month: _Optional[int] = ..., anchor_date: _Optional[str] = ...) -> None: ...

class AutoWithdrawDestination(_message.Message):
    __slots__ = ("asset_id", "destination_chain_id", "destination_address", "min_amount_e18", "max_amount_e18", "min_floor_e18")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    MAX_AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    MIN_FLOOR_E18_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    destination_chain_id: int
    destination_address: str
    min_amount_e18: _u128_pb2.U128
    max_amount_e18: _u128_pb2.U128
    min_floor_e18: _u128_pb2.U128
    def __init__(self, asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., min_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., max_amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., min_floor_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ...) -> None: ...

class AutoWithdrawPause(_message.Message):
    __slots__ = ("asset_id", "reason", "paused_at")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    PAUSED_AT_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    reason: str
    paused_at: _timestamp_pb2.Timestamp
    def __init__(self, asset_id: _Optional[int] = ..., reason: _Optional[str] = ..., paused_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AutoWithdrawRule(_message.Message):
    __slots__ = ("subaccount_id", "version", "enabled", "schedule", "destinations", "created_at", "pause", "min_usd_value_e18", "created_by_account_id")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    DESTINATIONS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    PAUSE_FIELD_NUMBER: _ClassVar[int]
    MIN_USD_VALUE_E18_FIELD_NUMBER: _ClassVar[int]
    CREATED_BY_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    version: int
    enabled: bool
    schedule: AutoWithdrawSchedule
    destinations: _containers.RepeatedCompositeFieldContainer[AutoWithdrawDestination]
    created_at: _timestamp_pb2.Timestamp
    pause: AutoWithdrawPause
    min_usd_value_e18: _u128_pb2.U128
    created_by_account_id: int
    def __init__(self, subaccount_id: _Optional[int] = ..., version: _Optional[int] = ..., enabled: _Optional[bool] = ..., schedule: _Optional[_Union[AutoWithdrawSchedule, _Mapping]] = ..., destinations: _Optional[_Iterable[_Union[AutoWithdrawDestination, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pause: _Optional[_Union[AutoWithdrawPause, _Mapping]] = ..., min_usd_value_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., created_by_account_id: _Optional[int] = ...) -> None: ...

class SetAutoWithdrawRuleRequest(_message.Message):
    __slots__ = ("subaccount_id", "expected_version", "schedule", "destinations", "min_usd_value_e18")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_VERSION_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    DESTINATIONS_FIELD_NUMBER: _ClassVar[int]
    MIN_USD_VALUE_E18_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    expected_version: int
    schedule: AutoWithdrawSchedule
    destinations: _containers.RepeatedCompositeFieldContainer[AutoWithdrawDestination]
    min_usd_value_e18: _u128_pb2.U128
    def __init__(self, subaccount_id: _Optional[int] = ..., expected_version: _Optional[int] = ..., schedule: _Optional[_Union[AutoWithdrawSchedule, _Mapping]] = ..., destinations: _Optional[_Iterable[_Union[AutoWithdrawDestination, _Mapping]]] = ..., min_usd_value_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ...) -> None: ...

class SetAutoWithdrawRuleResponse(_message.Message):
    __slots__ = ("rule",)
    RULE_FIELD_NUMBER: _ClassVar[int]
    rule: AutoWithdrawRule
    def __init__(self, rule: _Optional[_Union[AutoWithdrawRule, _Mapping]] = ...) -> None: ...

class SetAutoWithdrawRuleEnabledRequest(_message.Message):
    __slots__ = ("subaccount_id", "expected_version", "enabled")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_VERSION_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    expected_version: int
    enabled: bool
    def __init__(self, subaccount_id: _Optional[int] = ..., expected_version: _Optional[int] = ..., enabled: _Optional[bool] = ...) -> None: ...

class SetAutoWithdrawRuleEnabledResponse(_message.Message):
    __slots__ = ("rule",)
    RULE_FIELD_NUMBER: _ClassVar[int]
    rule: AutoWithdrawRule
    def __init__(self, rule: _Optional[_Union[AutoWithdrawRule, _Mapping]] = ...) -> None: ...

class GetAutoWithdrawRuleRequest(_message.Message):
    __slots__ = ("subaccount_id",)
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    def __init__(self, subaccount_id: _Optional[int] = ...) -> None: ...

class GetAutoWithdrawRuleResponse(_message.Message):
    __slots__ = ("rule",)
    RULE_FIELD_NUMBER: _ClassVar[int]
    rule: AutoWithdrawRule
    def __init__(self, rule: _Optional[_Union[AutoWithdrawRule, _Mapping]] = ...) -> None: ...

class AutoWithdrawStep(_message.Message):
    __slots__ = ("asset_id", "destination_chain_id", "destination_address", "available_e18", "amount_e18", "state", "reason", "intent_id", "tx_hash", "value_usd_e18", "network_fee_e18")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_E18_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    INTENT_ID_FIELD_NUMBER: _ClassVar[int]
    TX_HASH_FIELD_NUMBER: _ClassVar[int]
    VALUE_USD_E18_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FEE_E18_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    destination_chain_id: int
    destination_address: str
    available_e18: _u128_pb2.U128
    amount_e18: _u128_pb2.U128
    state: AutoWithdrawStepState
    reason: str
    intent_id: str
    tx_hash: str
    value_usd_e18: _u128_pb2.U128
    network_fee_e18: _u128_pb2.U128
    def __init__(self, asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., available_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., state: _Optional[_Union[AutoWithdrawStepState, str]] = ..., reason: _Optional[str] = ..., intent_id: _Optional[str] = ..., tx_hash: _Optional[str] = ..., value_usd_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., network_fee_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ...) -> None: ...

class AutoWithdrawRun(_message.Message):
    __slots__ = ("run_seq", "rule_version", "scheduled_for", "state", "reason", "steps", "created_at", "finished_at")
    RUN_SEQ_FIELD_NUMBER: _ClassVar[int]
    RULE_VERSION_FIELD_NUMBER: _ClassVar[int]
    SCHEDULED_FOR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    STEPS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    run_seq: int
    rule_version: int
    scheduled_for: _timestamp_pb2.Timestamp
    state: AutoWithdrawRunState
    reason: str
    steps: _containers.RepeatedCompositeFieldContainer[AutoWithdrawStep]
    created_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    def __init__(self, run_seq: _Optional[int] = ..., rule_version: _Optional[int] = ..., scheduled_for: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., state: _Optional[_Union[AutoWithdrawRunState, str]] = ..., reason: _Optional[str] = ..., steps: _Optional[_Iterable[_Union[AutoWithdrawStep, _Mapping]]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListAutoWithdrawRunsRequest(_message.Message):
    __slots__ = ("subaccount_id", "limit", "page_token")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    limit: int
    page_token: str
    def __init__(self, subaccount_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListAutoWithdrawRunsResponse(_message.Message):
    __slots__ = ("runs", "next_page_token")
    RUNS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    runs: _containers.RepeatedCompositeFieldContainer[AutoWithdrawRun]
    next_page_token: str
    def __init__(self, runs: _Optional[_Iterable[_Union[AutoWithdrawRun, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class PreviewAutoWithdrawRunRequest(_message.Message):
    __slots__ = ("subaccount_id",)
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    def __init__(self, subaccount_id: _Optional[int] = ...) -> None: ...

class AutoWithdrawPreviewAsset(_message.Message):
    __slots__ = ("asset_id", "destination_chain_id", "destination_address", "available_e18", "payable_e18", "held_back_e18", "hold_reason", "minimum_e18", "value_usd_e18", "priced_at", "network_fee_e18", "network_fee_sampled_at", "payable_from")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_E18_FIELD_NUMBER: _ClassVar[int]
    PAYABLE_E18_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_E18_FIELD_NUMBER: _ClassVar[int]
    HOLD_REASON_FIELD_NUMBER: _ClassVar[int]
    MINIMUM_E18_FIELD_NUMBER: _ClassVar[int]
    VALUE_USD_E18_FIELD_NUMBER: _ClassVar[int]
    PRICED_AT_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FEE_E18_FIELD_NUMBER: _ClassVar[int]
    NETWORK_FEE_SAMPLED_AT_FIELD_NUMBER: _ClassVar[int]
    PAYABLE_FROM_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    destination_chain_id: int
    destination_address: str
    available_e18: _u128_pb2.U128
    payable_e18: _u128_pb2.U128
    held_back_e18: _u128_pb2.U128
    hold_reason: str
    minimum_e18: _u128_pb2.U128
    value_usd_e18: _u128_pb2.U128
    priced_at: _timestamp_pb2.Timestamp
    network_fee_e18: _u128_pb2.U128
    network_fee_sampled_at: _timestamp_pb2.Timestamp
    payable_from: _timestamp_pb2.Timestamp
    def __init__(self, asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., destination_address: _Optional[str] = ..., available_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., payable_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., held_back_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., hold_reason: _Optional[str] = ..., minimum_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., value_usd_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., priced_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., network_fee_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., network_fee_sampled_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., payable_from: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class PreviewAutoWithdrawRunResponse(_message.Message):
    __slots__ = ("status", "next_run_at", "rule_version", "pause", "min_usd_value_e18", "assets", "computed_at")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    NEXT_RUN_AT_FIELD_NUMBER: _ClassVar[int]
    RULE_VERSION_FIELD_NUMBER: _ClassVar[int]
    PAUSE_FIELD_NUMBER: _ClassVar[int]
    MIN_USD_VALUE_E18_FIELD_NUMBER: _ClassVar[int]
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    COMPUTED_AT_FIELD_NUMBER: _ClassVar[int]
    status: AutoWithdrawPreviewStatus
    next_run_at: _timestamp_pb2.Timestamp
    rule_version: int
    pause: AutoWithdrawPause
    min_usd_value_e18: _u128_pb2.U128
    assets: _containers.RepeatedCompositeFieldContainer[AutoWithdrawPreviewAsset]
    computed_at: _timestamp_pb2.Timestamp
    def __init__(self, status: _Optional[_Union[AutoWithdrawPreviewStatus, str]] = ..., next_run_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., rule_version: _Optional[int] = ..., pause: _Optional[_Union[AutoWithdrawPause, _Mapping]] = ..., min_usd_value_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., assets: _Optional[_Iterable[_Union[AutoWithdrawPreviewAsset, _Mapping]]] = ..., computed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
