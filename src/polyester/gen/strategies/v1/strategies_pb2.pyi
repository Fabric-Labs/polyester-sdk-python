import datetime

from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ERROR_UNSPECIFIED: _ClassVar[ErrorCode]
    VERSION_NOT_FOUND: _ClassVar[ErrorCode]
    BACKTEST_NOT_FOUND: _ClassVar[ErrorCode]
    PROPOSAL_NOT_FOUND: _ClassVar[ErrorCode]
    BOT_NOT_FOUND: _ClassVar[ErrorCode]
    RUNTIME_VERSION_UNSUPPORTED: _ClassVar[ErrorCode]
    MANIFEST_TOO_LARGE: _ClassVar[ErrorCode]
    SETTINGS_INVALID: _ClassVar[ErrorCode]
    FUNDING_INVALID: _ClassVar[ErrorCode]
    VERSION_INVALID: _ClassVar[ErrorCode]
    SCENARIOS_FAILING: _ClassVar[ErrorCode]
    BACKTEST_MISSING: _ClassVar[ErrorCode]
    MARKET_NOT_ALLOWED: _ClassVar[ErrorCode]
    INSUFFICIENT_FUNDS: _ClassVar[ErrorCode]
    BOT_CAP_REACHED: _ClassVar[ErrorCode]
    WINDOW_HAS_NO_DATA: _ClassVar[ErrorCode]
    NOT_BACKTESTABLE: _ClassVar[ErrorCode]
    SCENARIO_RUN_LIMIT_REACHED: _ClassVar[ErrorCode]
    BACKTEST_LIMIT_REACHED: _ClassVar[ErrorCode]
    INDICATOR_SETTINGS_LIMIT_REACHED: _ClassVar[ErrorCode]
    IDEMPOTENCY_CONFLICT: _ClassVar[ErrorCode]
    SERVICE_UNAVAILABLE: _ClassVar[ErrorCode]
    FUNDING_SUBACCOUNT_NOT_FOUND: _ClassVar[ErrorCode]
    BOT_NOT_RUNNING: _ClassVar[ErrorCode]
    BOT_ALREADY_STOPPING: _ClassVar[ErrorCode]
    STRATEGY_NOT_FOUND: _ClassVar[ErrorCode]
    DRAFT_REVISION_CONFLICT: _ClassVar[ErrorCode]
    STRATEGY_CAP_REACHED: _ClassVar[ErrorCode]
    TEMPLATE_NOT_FOUND: _ClassVar[ErrorCode]
    STRATEGY_IN_USE: _ClassVar[ErrorCode]
    REVISION_NOT_FOUND: _ClassVar[ErrorCode]
    BACKTEST_NOT_DONE: _ClassVar[ErrorCode]
    MFA_ELEVATION_REQUIRED: _ClassVar[ErrorCode]
    PROPOSAL_EXPIRED: _ClassVar[ErrorCode]
    SUBACCOUNT_AUTHORIZATION_REQUIRED: _ClassVar[ErrorCode]
    NOTES_REVISION_CONFLICT: _ClassVar[ErrorCode]
    LISTING_NOT_FOUND: _ClassVar[ErrorCode]
    LISTING_CAP_REACHED: _ClassVar[ErrorCode]
    USERNAME_REQUIRED: _ClassVar[ErrorCode]
    PUBLISH_LIMIT_REACHED: _ClassVar[ErrorCode]

class NotBacktestableReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NOT_BACKTESTABLE_REASON_UNSPECIFIED: _ClassVar[NotBacktestableReason]
    REACTS_TO_TRADES_OR_QUOTES: _ClassVar[NotBacktestableReason]
    READS_SOCIAL_SIGNALS: _ClassVar[NotBacktestableReason]
    MIXED_QUOTE_ASSETS: _ClassVar[NotBacktestableReason]
    NO_REFERENCE_CANDLES: _ClassVar[NotBacktestableReason]
    PLACES_LIMIT_ORDERS: _ClassVar[NotBacktestableReason]
    READS_VOLUME: _ClassVar[NotBacktestableReason]

class OrderSide(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIDE_UNSPECIFIED: _ClassVar[OrderSide]
    BUY: _ClassVar[OrderSide]
    SELL: _ClassVar[OrderSide]

class EvidenceGrade(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVIDENCE_GRADE_UNSPECIFIED: _ClassVar[EvidenceGrade]
    NOT_ENOUGH: _ClassVar[EvidenceGrade]
    LOW: _ClassVar[EvidenceGrade]
    MEDIUM: _ClassVar[EvidenceGrade]
    HIGH: _ClassVar[EvidenceGrade]

class StopMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STOP_UNSPECIFIED: _ClassVar[StopMode]
    KEEP_ORDERS: _ClassVar[StopMode]
    CANCEL_ORDERS: _ClassVar[StopMode]

class StrategyTag(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TAG_UNSPECIFIED: _ClassVar[StrategyTag]
    TREND: _ClassVar[StrategyTag]
    MEAN_REVERSION: _ClassVar[StrategyTag]
    GRID: _ClassVar[StrategyTag]
    DCA: _ClassVar[StrategyTag]
    MARKET_MAKING: _ClassVar[StrategyTag]
    ARBITRAGE: _ClassVar[StrategyTag]
    SIGNALS: _ClassVar[StrategyTag]
ERROR_UNSPECIFIED: ErrorCode
VERSION_NOT_FOUND: ErrorCode
BACKTEST_NOT_FOUND: ErrorCode
PROPOSAL_NOT_FOUND: ErrorCode
BOT_NOT_FOUND: ErrorCode
RUNTIME_VERSION_UNSUPPORTED: ErrorCode
MANIFEST_TOO_LARGE: ErrorCode
SETTINGS_INVALID: ErrorCode
FUNDING_INVALID: ErrorCode
VERSION_INVALID: ErrorCode
SCENARIOS_FAILING: ErrorCode
BACKTEST_MISSING: ErrorCode
MARKET_NOT_ALLOWED: ErrorCode
INSUFFICIENT_FUNDS: ErrorCode
BOT_CAP_REACHED: ErrorCode
WINDOW_HAS_NO_DATA: ErrorCode
NOT_BACKTESTABLE: ErrorCode
SCENARIO_RUN_LIMIT_REACHED: ErrorCode
BACKTEST_LIMIT_REACHED: ErrorCode
INDICATOR_SETTINGS_LIMIT_REACHED: ErrorCode
IDEMPOTENCY_CONFLICT: ErrorCode
SERVICE_UNAVAILABLE: ErrorCode
FUNDING_SUBACCOUNT_NOT_FOUND: ErrorCode
BOT_NOT_RUNNING: ErrorCode
BOT_ALREADY_STOPPING: ErrorCode
STRATEGY_NOT_FOUND: ErrorCode
DRAFT_REVISION_CONFLICT: ErrorCode
STRATEGY_CAP_REACHED: ErrorCode
TEMPLATE_NOT_FOUND: ErrorCode
STRATEGY_IN_USE: ErrorCode
REVISION_NOT_FOUND: ErrorCode
BACKTEST_NOT_DONE: ErrorCode
MFA_ELEVATION_REQUIRED: ErrorCode
PROPOSAL_EXPIRED: ErrorCode
SUBACCOUNT_AUTHORIZATION_REQUIRED: ErrorCode
NOTES_REVISION_CONFLICT: ErrorCode
LISTING_NOT_FOUND: ErrorCode
LISTING_CAP_REACHED: ErrorCode
USERNAME_REQUIRED: ErrorCode
PUBLISH_LIMIT_REACHED: ErrorCode
NOT_BACKTESTABLE_REASON_UNSPECIFIED: NotBacktestableReason
REACTS_TO_TRADES_OR_QUOTES: NotBacktestableReason
READS_SOCIAL_SIGNALS: NotBacktestableReason
MIXED_QUOTE_ASSETS: NotBacktestableReason
NO_REFERENCE_CANDLES: NotBacktestableReason
PLACES_LIMIT_ORDERS: NotBacktestableReason
READS_VOLUME: NotBacktestableReason
SIDE_UNSPECIFIED: OrderSide
BUY: OrderSide
SELL: OrderSide
EVIDENCE_GRADE_UNSPECIFIED: EvidenceGrade
NOT_ENOUGH: EvidenceGrade
LOW: EvidenceGrade
MEDIUM: EvidenceGrade
HIGH: EvidenceGrade
STOP_UNSPECIFIED: StopMode
KEEP_ORDERS: StopMode
CANCEL_ORDERS: StopMode
TAG_UNSPECIFIED: StrategyTag
TREND: StrategyTag
MEAN_REVERSION: StrategyTag
GRID: StrategyTag
DCA: StrategyTag
MARKET_MAKING: StrategyTag
ARBITRAGE: StrategyTag
SIGNALS: StrategyTag

class BotCapDetail(_message.Message):
    __slots__ = ("vip_tier", "bot_cap", "bots", "next_vip_tier", "next_bot_cap")
    VIP_TIER_FIELD_NUMBER: _ClassVar[int]
    BOT_CAP_FIELD_NUMBER: _ClassVar[int]
    BOTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_VIP_TIER_FIELD_NUMBER: _ClassVar[int]
    NEXT_BOT_CAP_FIELD_NUMBER: _ClassVar[int]
    vip_tier: int
    bot_cap: int
    bots: int
    next_vip_tier: int
    next_bot_cap: int
    def __init__(self, vip_tier: _Optional[int] = ..., bot_cap: _Optional[int] = ..., bots: _Optional[int] = ..., next_vip_tier: _Optional[int] = ..., next_bot_cap: _Optional[int] = ...) -> None: ...

class StrategyCapDetail(_message.Message):
    __slots__ = ("strategy_cap", "strategies")
    STRATEGY_CAP_FIELD_NUMBER: _ClassVar[int]
    STRATEGIES_FIELD_NUMBER: _ClassVar[int]
    strategy_cap: int
    strategies: int
    def __init__(self, strategy_cap: _Optional[int] = ..., strategies: _Optional[int] = ...) -> None: ...

class ListingCapDetail(_message.Message):
    __slots__ = ("listing_cap", "listings")
    LISTING_CAP_FIELD_NUMBER: _ClassVar[int]
    LISTINGS_FIELD_NUMBER: _ClassVar[int]
    listing_cap: int
    listings: int
    def __init__(self, listing_cap: _Optional[int] = ..., listings: _Optional[int] = ...) -> None: ...

class RevisionConflictDetail(_message.Message):
    __slots__ = ("revision", "head_version_id")
    REVISION_FIELD_NUMBER: _ClassVar[int]
    HEAD_VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    revision: int
    head_version_id: str
    def __init__(self, revision: _Optional[int] = ..., head_version_id: _Optional[str] = ...) -> None: ...

class ErrorDetail(_message.Message):
    __slots__ = ("code", "field_path", "retry_after", "bot_cap", "markets", "shortfall", "strategy_cap", "revision_conflict", "not_backtestable_reason", "backtest_limit", "notes_conflict", "listing_cap")
    CODE_FIELD_NUMBER: _ClassVar[int]
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    RETRY_AFTER_FIELD_NUMBER: _ClassVar[int]
    BOT_CAP_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    SHORTFALL_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_CAP_FIELD_NUMBER: _ClassVar[int]
    REVISION_CONFLICT_FIELD_NUMBER: _ClassVar[int]
    NOT_BACKTESTABLE_REASON_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_LIMIT_FIELD_NUMBER: _ClassVar[int]
    NOTES_CONFLICT_FIELD_NUMBER: _ClassVar[int]
    LISTING_CAP_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    field_path: str
    retry_after: _timestamp_pb2.Timestamp
    bot_cap: BotCapDetail
    markets: _containers.RepeatedScalarFieldContainer[str]
    shortfall: _containers.RepeatedCompositeFieldContainer[Money]
    strategy_cap: StrategyCapDetail
    revision_conflict: RevisionConflictDetail
    not_backtestable_reason: NotBacktestableReason
    backtest_limit: BacktestLimitDetail
    notes_conflict: NotesConflictDetail
    listing_cap: ListingCapDetail
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ..., field_path: _Optional[str] = ..., retry_after: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bot_cap: _Optional[_Union[BotCapDetail, _Mapping]] = ..., markets: _Optional[_Iterable[str]] = ..., shortfall: _Optional[_Iterable[_Union[Money, _Mapping]]] = ..., strategy_cap: _Optional[_Union[StrategyCapDetail, _Mapping]] = ..., revision_conflict: _Optional[_Union[RevisionConflictDetail, _Mapping]] = ..., not_backtestable_reason: _Optional[_Union[NotBacktestableReason, str]] = ..., backtest_limit: _Optional[_Union[BacktestLimitDetail, _Mapping]] = ..., notes_conflict: _Optional[_Union[NotesConflictDetail, _Mapping]] = ..., listing_cap: _Optional[_Union[ListingCapDetail, _Mapping]] = ...) -> None: ...

class NotesConflictDetail(_message.Message):
    __slots__ = ("notes_revision",)
    NOTES_REVISION_FIELD_NUMBER: _ClassVar[int]
    notes_revision: int
    def __init__(self, notes_revision: _Optional[int] = ...) -> None: ...

class BacktestLimitDetail(_message.Message):
    __slots__ = ("daily_limit", "daily_used", "active_limit", "active")
    DAILY_LIMIT_FIELD_NUMBER: _ClassVar[int]
    DAILY_USED_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_LIMIT_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    daily_limit: int
    daily_used: int
    active_limit: int
    active: int
    def __init__(self, daily_limit: _Optional[int] = ..., daily_used: _Optional[int] = ..., active_limit: _Optional[int] = ..., active: _Optional[int] = ...) -> None: ...

class Money(_message.Message):
    __slots__ = ("asset", "amount")
    ASSET_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    asset: str
    amount: str
    def __init__(self, asset: _Optional[str] = ..., amount: _Optional[str] = ...) -> None: ...

class TimeWindow(_message.Message):
    __slots__ = ("start_time", "end_time")
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    def __init__(self, start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class IndicatorLibrary(_message.Message):
    __slots__ = ("name", "version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    version: str
    def __init__(self, name: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class IndicatorParameter(_message.Message):
    __slots__ = ("name", "description", "minimum", "maximum", "default_value", "integer")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    MINIMUM_FIELD_NUMBER: _ClassVar[int]
    MAXIMUM_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_VALUE_FIELD_NUMBER: _ClassVar[int]
    INTEGER_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    minimum: str
    maximum: str
    default_value: str
    integer: bool
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., minimum: _Optional[str] = ..., maximum: _Optional[str] = ..., default_value: _Optional[str] = ..., integer: _Optional[bool] = ...) -> None: ...

class Indicator(_message.Message):
    __slots__ = ("name", "description", "parameters", "outputs", "warmup_bars")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    OUTPUTS_FIELD_NUMBER: _ClassVar[int]
    WARMUP_BARS_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    parameters: _containers.RepeatedCompositeFieldContainer[IndicatorParameter]
    outputs: _containers.RepeatedScalarFieldContainer[str]
    warmup_bars: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., parameters: _Optional[_Iterable[_Union[IndicatorParameter, _Mapping]]] = ..., outputs: _Optional[_Iterable[str]] = ..., warmup_bars: _Optional[str] = ...) -> None: ...

class StrategyLimits(_message.Message):
    __slots__ = ("cpu_ms_per_call", "memory_bytes_per_call", "state_bytes", "code_bytes", "manifest_bytes", "scenario_runs_per_minute")
    CPU_MS_PER_CALL_FIELD_NUMBER: _ClassVar[int]
    MEMORY_BYTES_PER_CALL_FIELD_NUMBER: _ClassVar[int]
    STATE_BYTES_FIELD_NUMBER: _ClassVar[int]
    CODE_BYTES_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_BYTES_FIELD_NUMBER: _ClassVar[int]
    SCENARIO_RUNS_PER_MINUTE_FIELD_NUMBER: _ClassVar[int]
    cpu_ms_per_call: int
    memory_bytes_per_call: int
    state_bytes: int
    code_bytes: int
    manifest_bytes: int
    scenario_runs_per_minute: int
    def __init__(self, cpu_ms_per_call: _Optional[int] = ..., memory_bytes_per_call: _Optional[int] = ..., state_bytes: _Optional[int] = ..., code_bytes: _Optional[int] = ..., manifest_bytes: _Optional[int] = ..., scenario_runs_per_minute: _Optional[int] = ...) -> None: ...

class GetStrategyReferenceRequest(_message.Message):
    __slots__ = ("runtime_version",)
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    runtime_version: str
    def __init__(self, runtime_version: _Optional[str] = ...) -> None: ...

class GetStrategyReferenceResponse(_message.Message):
    __slots__ = ("runtime_version", "indicator_library", "reference", "manifest_schema", "indicators", "limits", "skill_pack", "skill_pack_version")
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    INDICATOR_LIBRARY_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_SCHEMA_FIELD_NUMBER: _ClassVar[int]
    INDICATORS_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    SKILL_PACK_FIELD_NUMBER: _ClassVar[int]
    SKILL_PACK_VERSION_FIELD_NUMBER: _ClassVar[int]
    runtime_version: str
    indicator_library: IndicatorLibrary
    reference: str
    manifest_schema: _struct_pb2.Struct
    indicators: _containers.RepeatedCompositeFieldContainer[Indicator]
    limits: StrategyLimits
    skill_pack: _containers.RepeatedCompositeFieldContainer[SkillDocument]
    skill_pack_version: str
    def __init__(self, runtime_version: _Optional[str] = ..., indicator_library: _Optional[_Union[IndicatorLibrary, _Mapping]] = ..., reference: _Optional[str] = ..., manifest_schema: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., indicators: _Optional[_Iterable[_Union[Indicator, _Mapping]]] = ..., limits: _Optional[_Union[StrategyLimits, _Mapping]] = ..., skill_pack: _Optional[_Iterable[_Union[SkillDocument, _Mapping]]] = ..., skill_pack_version: _Optional[str] = ...) -> None: ...

class SkillDocument(_message.Message):
    __slots__ = ("name", "markdown")
    NAME_FIELD_NUMBER: _ClassVar[int]
    MARKDOWN_FIELD_NUMBER: _ClassVar[int]
    name: str
    markdown: str
    def __init__(self, name: _Optional[str] = ..., markdown: _Optional[str] = ...) -> None: ...

class StrategyTemplate(_message.Message):
    __slots__ = ("template_id", "name", "description", "manifest", "code", "runtime_version", "money_card")
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    template_id: str
    name: str
    description: str
    manifest: _struct_pb2.Struct
    code: str
    runtime_version: str
    money_card: MoneyCard
    def __init__(self, template_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., manifest: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., code: _Optional[str] = ..., runtime_version: _Optional[str] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ...) -> None: ...

class ListStrategyTemplatesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListStrategyTemplatesResponse(_message.Message):
    __slots__ = ("templates",)
    TEMPLATES_FIELD_NUMBER: _ClassVar[int]
    templates: _containers.RepeatedCompositeFieldContainer[StrategyTemplate]
    def __init__(self, templates: _Optional[_Iterable[_Union[StrategyTemplate, _Mapping]]] = ...) -> None: ...

class ValidationIssue(_message.Message):
    __slots__ = ("manifest_path", "line", "column", "rule", "message", "hint")
    MANIFEST_PATH_FIELD_NUMBER: _ClassVar[int]
    LINE_FIELD_NUMBER: _ClassVar[int]
    COLUMN_FIELD_NUMBER: _ClassVar[int]
    RULE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    HINT_FIELD_NUMBER: _ClassVar[int]
    manifest_path: str
    line: int
    column: int
    rule: str
    message: str
    hint: str
    def __init__(self, manifest_path: _Optional[str] = ..., line: _Optional[int] = ..., column: _Optional[int] = ..., rule: _Optional[str] = ..., message: _Optional[str] = ..., hint: _Optional[str] = ...) -> None: ...

class MoneyCard(_message.Message):
    __slots__ = ("budget", "max_order", "max_open_gtc_orders", "daily_loss_threshold", "markets", "events")
    BUDGET_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDER_FIELD_NUMBER: _ClassVar[int]
    MAX_OPEN_GTC_ORDERS_FIELD_NUMBER: _ClassVar[int]
    DAILY_LOSS_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    budget: Money
    max_order: Money
    max_open_gtc_orders: int
    daily_loss_threshold: Money
    markets: _containers.RepeatedScalarFieldContainer[str]
    events: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, budget: _Optional[_Union[Money, _Mapping]] = ..., max_order: _Optional[_Union[Money, _Mapping]] = ..., max_open_gtc_orders: _Optional[int] = ..., daily_loss_threshold: _Optional[_Union[Money, _Mapping]] = ..., markets: _Optional[_Iterable[str]] = ..., events: _Optional[_Iterable[str]] = ...) -> None: ...

class SettingField(_message.Message):
    __slots__ = ("name", "description", "kind", "asset", "default_value", "minimum", "maximum")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    ASSET_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_VALUE_FIELD_NUMBER: _ClassVar[int]
    MINIMUM_FIELD_NUMBER: _ClassVar[int]
    MAXIMUM_FIELD_NUMBER: _ClassVar[int]
    name: str
    description: str
    kind: str
    asset: str
    default_value: str
    minimum: str
    maximum: str
    def __init__(self, name: _Optional[str] = ..., description: _Optional[str] = ..., kind: _Optional[str] = ..., asset: _Optional[str] = ..., default_value: _Optional[str] = ..., minimum: _Optional[str] = ..., maximum: _Optional[str] = ...) -> None: ...

class VersionValidation(_message.Message):
    __slots__ = ("version_id", "runtime_version", "valid", "errors", "warnings", "money_card", "settings_form", "flow")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    VALID_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FORM_FIELD_NUMBER: _ClassVar[int]
    FLOW_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    runtime_version: str
    valid: bool
    errors: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    warnings: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    money_card: MoneyCard
    settings_form: _containers.RepeatedCompositeFieldContainer[SettingField]
    flow: StrategyFlow
    def __init__(self, version_id: _Optional[str] = ..., runtime_version: _Optional[str] = ..., valid: _Optional[bool] = ..., errors: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ..., warnings: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings_form: _Optional[_Iterable[_Union[SettingField, _Mapping]]] = ..., flow: _Optional[_Union[StrategyFlow, _Mapping]] = ...) -> None: ...

class RunScenariosRequest(_message.Message):
    __slots__ = ("version_id",)
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    def __init__(self, version_id: _Optional[str] = ...) -> None: ...

class ScenarioResult(_message.Message):
    __slots__ = ("name", "passed", "expected", "actual", "logs", "error")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_FIELD_NUMBER: _ClassVar[int]
    ACTUAL_FIELD_NUMBER: _ClassVar[int]
    LOGS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    name: str
    passed: bool
    expected: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    actual: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    logs: _containers.RepeatedScalarFieldContainer[str]
    error: str
    def __init__(self, name: _Optional[str] = ..., passed: _Optional[bool] = ..., expected: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., actual: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., logs: _Optional[_Iterable[str]] = ..., error: _Optional[str] = ...) -> None: ...

class RunScenariosResponse(_message.Message):
    __slots__ = ("version_id", "passed", "failed", "results")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    passed: int
    failed: int
    results: _containers.RepeatedCompositeFieldContainer[ScenarioResult]
    def __init__(self, version_id: _Optional[str] = ..., passed: _Optional[int] = ..., failed: _Optional[int] = ..., results: _Optional[_Iterable[_Union[ScenarioResult, _Mapping]]] = ...) -> None: ...

class BacktestMetrics(_message.Message):
    __slots__ = ("return_percent", "max_drawdown_percent", "trades", "win_rate_percent", "fees", "exposure_percent", "sharpe_ratio", "realized_pnl", "max_drawdown_start", "max_drawdown_end", "start_equity", "end_equity")
    RETURN_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PERCENT_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    EXPOSURE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    SHARPE_RATIO_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_START_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_END_FIELD_NUMBER: _ClassVar[int]
    START_EQUITY_FIELD_NUMBER: _ClassVar[int]
    END_EQUITY_FIELD_NUMBER: _ClassVar[int]
    return_percent: str
    max_drawdown_percent: str
    trades: int
    win_rate_percent: str
    fees: Money
    exposure_percent: str
    sharpe_ratio: str
    realized_pnl: str
    max_drawdown_start: _timestamp_pb2.Timestamp
    max_drawdown_end: _timestamp_pb2.Timestamp
    start_equity: str
    end_equity: str
    def __init__(self, return_percent: _Optional[str] = ..., max_drawdown_percent: _Optional[str] = ..., trades: _Optional[int] = ..., win_rate_percent: _Optional[str] = ..., fees: _Optional[_Union[Money, _Mapping]] = ..., exposure_percent: _Optional[str] = ..., sharpe_ratio: _Optional[str] = ..., realized_pnl: _Optional[str] = ..., max_drawdown_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., max_drawdown_end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., start_equity: _Optional[str] = ..., end_equity: _Optional[str] = ...) -> None: ...

class BacktestScenario(_message.Message):
    __slots__ = ("name", "slippage_bps", "metrics", "held_back_metrics")
    NAME_FIELD_NUMBER: _ClassVar[int]
    SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_METRICS_FIELD_NUMBER: _ClassVar[int]
    name: str
    slippage_bps: int
    metrics: BacktestMetrics
    held_back_metrics: BacktestMetrics
    def __init__(self, name: _Optional[str] = ..., slippage_bps: _Optional[int] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., held_back_metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ...) -> None: ...

class EquityPoint(_message.Message):
    __slots__ = ("time", "equity", "buy_and_hold_equity")
    TIME_FIELD_NUMBER: _ClassVar[int]
    EQUITY_FIELD_NUMBER: _ClassVar[int]
    BUY_AND_HOLD_EQUITY_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    equity: str
    buy_and_hold_equity: str
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., equity: _Optional[str] = ..., buy_and_hold_equity: _Optional[str] = ...) -> None: ...

class Baseline(_message.Message):
    __slots__ = ("name", "metrics")
    NAME_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    name: str
    metrics: BacktestMetrics
    def __init__(self, name: _Optional[str] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ...) -> None: ...

class BacktestTrade(_message.Message):
    __slots__ = ("time", "market", "side", "price", "quantity", "fee", "reason", "realized_pnl", "trade_index", "after_gap")
    TIME_FIELD_NUMBER: _ClassVar[int]
    MARKET_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FEE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_FIELD_NUMBER: _ClassVar[int]
    TRADE_INDEX_FIELD_NUMBER: _ClassVar[int]
    AFTER_GAP_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    market: str
    side: OrderSide
    price: str
    quantity: str
    fee: Money
    reason: str
    realized_pnl: str
    trade_index: int
    after_gap: bool
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., market: _Optional[str] = ..., side: _Optional[_Union[OrderSide, str]] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ..., fee: _Optional[_Union[Money, _Mapping]] = ..., reason: _Optional[str] = ..., realized_pnl: _Optional[str] = ..., trade_index: _Optional[int] = ..., after_gap: _Optional[bool] = ...) -> None: ...

class DataGap(_message.Message):
    __slots__ = ("market", "timeframe", "window", "affected")
    MARKET_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    AFFECTED_FIELD_NUMBER: _ClassVar[int]
    market: str
    timeframe: str
    window: TimeWindow
    affected: bool
    def __init__(self, market: _Optional[str] = ..., timeframe: _Optional[str] = ..., window: _Optional[_Union[TimeWindow, _Mapping]] = ..., affected: _Optional[bool] = ...) -> None: ...

class BacktestReport(_message.Message):
    __slots__ = ("fidelity", "period", "held_back_period", "metrics", "held_back_metrics", "baselines", "trades", "data_gaps", "warnings", "evidence_grade", "held_back_baselines", "scenarios", "equity", "held_back_start", "window_max_drawdown_percent", "window_max_drawdown_start", "window_max_drawdown_end", "held_back_seen")
    FIDELITY_FIELD_NUMBER: _ClassVar[int]
    PERIOD_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_PERIOD_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_METRICS_FIELD_NUMBER: _ClassVar[int]
    BASELINES_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    DATA_GAPS_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_GRADE_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_BASELINES_FIELD_NUMBER: _ClassVar[int]
    SCENARIOS_FIELD_NUMBER: _ClassVar[int]
    EQUITY_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_START_FIELD_NUMBER: _ClassVar[int]
    WINDOW_MAX_DRAWDOWN_PERCENT_FIELD_NUMBER: _ClassVar[int]
    WINDOW_MAX_DRAWDOWN_START_FIELD_NUMBER: _ClassVar[int]
    WINDOW_MAX_DRAWDOWN_END_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_SEEN_FIELD_NUMBER: _ClassVar[int]
    fidelity: str
    period: TimeWindow
    held_back_period: TimeWindow
    metrics: BacktestMetrics
    held_back_metrics: BacktestMetrics
    baselines: _containers.RepeatedCompositeFieldContainer[Baseline]
    trades: _containers.RepeatedCompositeFieldContainer[BacktestTrade]
    data_gaps: _containers.RepeatedCompositeFieldContainer[DataGap]
    warnings: _containers.RepeatedScalarFieldContainer[str]
    evidence_grade: EvidenceGrade
    held_back_baselines: _containers.RepeatedCompositeFieldContainer[Baseline]
    scenarios: _containers.RepeatedCompositeFieldContainer[BacktestScenario]
    equity: _containers.RepeatedCompositeFieldContainer[EquityPoint]
    held_back_start: _timestamp_pb2.Timestamp
    window_max_drawdown_percent: str
    window_max_drawdown_start: _timestamp_pb2.Timestamp
    window_max_drawdown_end: _timestamp_pb2.Timestamp
    held_back_seen: bool
    def __init__(self, fidelity: _Optional[str] = ..., period: _Optional[_Union[TimeWindow, _Mapping]] = ..., held_back_period: _Optional[_Union[TimeWindow, _Mapping]] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., held_back_metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., baselines: _Optional[_Iterable[_Union[Baseline, _Mapping]]] = ..., trades: _Optional[_Iterable[_Union[BacktestTrade, _Mapping]]] = ..., data_gaps: _Optional[_Iterable[_Union[DataGap, _Mapping]]] = ..., warnings: _Optional[_Iterable[str]] = ..., evidence_grade: _Optional[_Union[EvidenceGrade, str]] = ..., held_back_baselines: _Optional[_Iterable[_Union[Baseline, _Mapping]]] = ..., scenarios: _Optional[_Iterable[_Union[BacktestScenario, _Mapping]]] = ..., equity: _Optional[_Iterable[_Union[EquityPoint, _Mapping]]] = ..., held_back_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., window_max_drawdown_percent: _Optional[str] = ..., window_max_drawdown_start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., window_max_drawdown_end: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., held_back_seen: _Optional[bool] = ...) -> None: ...

class Backtest(_message.Message):
    __slots__ = ("backtest_id", "version_id", "status", "window", "created_at", "finished_at", "report", "failure", "attempts", "not_backtestable_reason")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[Backtest.Status]
        QUEUED: _ClassVar[Backtest.Status]
        RUNNING: _ClassVar[Backtest.Status]
        DONE: _ClassVar[Backtest.Status]
        FAILED: _ClassVar[Backtest.Status]
        NOT_BACKTESTABLE: _ClassVar[Backtest.Status]
    STATUS_UNSPECIFIED: Backtest.Status
    QUEUED: Backtest.Status
    RUNNING: Backtest.Status
    DONE: Backtest.Status
    FAILED: Backtest.Status
    NOT_BACKTESTABLE: Backtest.Status
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    REPORT_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    NOT_BACKTESTABLE_REASON_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    version_id: str
    status: Backtest.Status
    window: TimeWindow
    created_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    report: BacktestReport
    failure: str
    attempts: int
    not_backtestable_reason: NotBacktestableReason
    def __init__(self, backtest_id: _Optional[int] = ..., version_id: _Optional[str] = ..., status: _Optional[_Union[Backtest.Status, str]] = ..., window: _Optional[_Union[TimeWindow, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., report: _Optional[_Union[BacktestReport, _Mapping]] = ..., failure: _Optional[str] = ..., attempts: _Optional[int] = ..., not_backtestable_reason: _Optional[_Union[NotBacktestableReason, str]] = ...) -> None: ...

class StartBacktestRequest(_message.Message):
    __slots__ = ("version_id", "start_time", "end_time", "settings", "initial_balances", "idempotency_key")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    INITIAL_BALANCES_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    initial_balances: _containers.RepeatedCompositeFieldContainer[Money]
    idempotency_key: str
    def __init__(self, version_id: _Optional[str] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., initial_balances: _Optional[_Iterable[_Union[Money, _Mapping]]] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class StartBacktestResponse(_message.Message):
    __slots__ = ("backtest_id", "status", "estimated_seconds")
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_SECONDS_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    status: Backtest.Status
    estimated_seconds: int
    def __init__(self, backtest_id: _Optional[int] = ..., status: _Optional[_Union[Backtest.Status, str]] = ..., estimated_seconds: _Optional[int] = ...) -> None: ...

class GetBacktestRequest(_message.Message):
    __slots__ = ("backtest_id",)
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    def __init__(self, backtest_id: _Optional[int] = ...) -> None: ...

class GetBacktestResponse(_message.Message):
    __slots__ = ("backtest",)
    BACKTEST_FIELD_NUMBER: _ClassVar[int]
    backtest: Backtest
    def __init__(self, backtest: _Optional[_Union[Backtest, _Mapping]] = ...) -> None: ...

class ListBacktestTradesRequest(_message.Message):
    __slots__ = ("backtest_id", "page_token", "limit")
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    page_token: str
    limit: int
    def __init__(self, backtest_id: _Optional[int] = ..., page_token: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListBacktestTradesResponse(_message.Message):
    __slots__ = ("trades", "next_page_token")
    TRADES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[BacktestTrade]
    next_page_token: str
    def __init__(self, trades: _Optional[_Iterable[_Union[BacktestTrade, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ScenarioSummary(_message.Message):
    __slots__ = ("name", "outcome")
    class Outcome(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OUTCOME_UNSPECIFIED: _ClassVar[ScenarioSummary.Outcome]
        NOT_RUN: _ClassVar[ScenarioSummary.Outcome]
        PASSED: _ClassVar[ScenarioSummary.Outcome]
        FAILED: _ClassVar[ScenarioSummary.Outcome]
    OUTCOME_UNSPECIFIED: ScenarioSummary.Outcome
    NOT_RUN: ScenarioSummary.Outcome
    PASSED: ScenarioSummary.Outcome
    FAILED: ScenarioSummary.Outcome
    NAME_FIELD_NUMBER: _ClassVar[int]
    OUTCOME_FIELD_NUMBER: _ClassVar[int]
    name: str
    outcome: ScenarioSummary.Outcome
    def __init__(self, name: _Optional[str] = ..., outcome: _Optional[_Union[ScenarioSummary.Outcome, str]] = ...) -> None: ...

class BacktestSummary(_message.Message):
    __slots__ = ("backtest_id", "status", "metrics", "held_back_metrics", "attempts")
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_METRICS_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    status: Backtest.Status
    metrics: BacktestMetrics
    held_back_metrics: BacktestMetrics
    attempts: int
    def __init__(self, backtest_id: _Optional[int] = ..., status: _Optional[_Union[Backtest.Status, str]] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., held_back_metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., attempts: _Optional[int] = ...) -> None: ...

class ExplainStrategyRequest(_message.Message):
    __slots__ = ("version_id",)
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    def __init__(self, version_id: _Optional[str] = ...) -> None: ...

class ExplainStrategyResponse(_message.Message):
    __slots__ = ("version_id", "money_card", "settings", "scenarios", "backtest", "backtest_absent_reason", "warnings", "limitations")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    SCENARIOS_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_ABSENT_REASON_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    LIMITATIONS_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    money_card: MoneyCard
    settings: _containers.RepeatedCompositeFieldContainer[SettingField]
    scenarios: _containers.RepeatedCompositeFieldContainer[ScenarioSummary]
    backtest: BacktestSummary
    backtest_absent_reason: str
    warnings: _containers.RepeatedScalarFieldContainer[str]
    limitations: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, version_id: _Optional[str] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings: _Optional[_Iterable[_Union[SettingField, _Mapping]]] = ..., scenarios: _Optional[_Iterable[_Union[ScenarioSummary, _Mapping]]] = ..., backtest: _Optional[_Union[BacktestSummary, _Mapping]] = ..., backtest_absent_reason: _Optional[str] = ..., warnings: _Optional[_Iterable[str]] = ..., limitations: _Optional[_Iterable[str]] = ...) -> None: ...

class SettingValue(_message.Message):
    __slots__ = ("name", "value", "description", "kind", "asset")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    ASSET_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: str
    description: str
    kind: str
    asset: str
    def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ..., description: _Optional[str] = ..., kind: _Optional[str] = ..., asset: _Optional[str] = ...) -> None: ...

class DeployProposalSummary(_message.Message):
    __slots__ = ("version_id", "bot_name", "money_card", "settings", "funding_subaccount_id", "funding", "scenarios_passed", "backtest", "strategy_id", "revision", "not_backtestable_reason")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    BOT_NAME_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FUNDING_FIELD_NUMBER: _ClassVar[int]
    SCENARIOS_PASSED_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    NOT_BACKTESTABLE_REASON_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    bot_name: str
    money_card: MoneyCard
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    funding_subaccount_id: int
    funding: _containers.RepeatedCompositeFieldContainer[Money]
    scenarios_passed: int
    backtest: BacktestSummary
    strategy_id: int
    revision: int
    not_backtestable_reason: NotBacktestableReason
    def __init__(self, version_id: _Optional[str] = ..., bot_name: _Optional[str] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., funding_subaccount_id: _Optional[int] = ..., funding: _Optional[_Iterable[_Union[Money, _Mapping]]] = ..., scenarios_passed: _Optional[int] = ..., backtest: _Optional[_Union[BacktestSummary, _Mapping]] = ..., strategy_id: _Optional[int] = ..., revision: _Optional[int] = ..., not_backtestable_reason: _Optional[_Union[NotBacktestableReason, str]] = ...) -> None: ...

class ProposeDeployRequest(_message.Message):
    __slots__ = ("strategy_id", "revision", "bot_name", "settings", "funding", "idempotency_key", "funding_subaccount_id")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    BOT_NAME_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    FUNDING_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    revision: int
    bot_name: str
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    funding: _containers.RepeatedCompositeFieldContainer[Money]
    idempotency_key: str
    funding_subaccount_id: int
    def __init__(self, strategy_id: _Optional[int] = ..., revision: _Optional[int] = ..., bot_name: _Optional[str] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., funding: _Optional[_Iterable[_Union[Money, _Mapping]]] = ..., idempotency_key: _Optional[str] = ..., funding_subaccount_id: _Optional[int] = ...) -> None: ...

class ProposeDeployResponse(_message.Message):
    __slots__ = ("proposal_id", "deploy_url", "summary", "expires_at")
    PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    DEPLOY_URL_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    proposal_id: int
    deploy_url: str
    summary: DeployProposalSummary
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, proposal_id: _Optional[int] = ..., deploy_url: _Optional[str] = ..., summary: _Optional[_Union[DeployProposalSummary, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DeployStatus(_message.Message):
    __slots__ = ("proposal_id", "state", "step", "bot_id", "subaccount_id", "failure", "expires_at", "updated_at", "failed_at", "wait")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATE_UNSPECIFIED: _ClassVar[DeployStatus.State]
        PROPOSED: _ClassVar[DeployStatus.State]
        VALIDATING: _ClassVar[DeployStatus.State]
        CREATING_SUBACCOUNT: _ClassVar[DeployStatus.State]
        SETTING_ACCESS: _ClassVar[DeployStatus.State]
        FUNDING: _ClassVar[DeployStatus.State]
        DEPLOYING: _ClassVar[DeployStatus.State]
        LIVE: _ClassVar[DeployStatus.State]
        FAILED: _ClassVar[DeployStatus.State]
        EXPIRED: _ClassVar[DeployStatus.State]
    STATE_UNSPECIFIED: DeployStatus.State
    PROPOSED: DeployStatus.State
    VALIDATING: DeployStatus.State
    CREATING_SUBACCOUNT: DeployStatus.State
    SETTING_ACCESS: DeployStatus.State
    FUNDING: DeployStatus.State
    DEPLOYING: DeployStatus.State
    LIVE: DeployStatus.State
    FAILED: DeployStatus.State
    EXPIRED: DeployStatus.State
    PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    FAILED_AT_FIELD_NUMBER: _ClassVar[int]
    WAIT_FIELD_NUMBER: _ClassVar[int]
    proposal_id: int
    state: DeployStatus.State
    step: str
    bot_id: int
    subaccount_id: int
    failure: str
    expires_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    failed_at: DeployStatus.State
    wait: DeployWait
    def __init__(self, proposal_id: _Optional[int] = ..., state: _Optional[_Union[DeployStatus.State, str]] = ..., step: _Optional[str] = ..., bot_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., failure: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., failed_at: _Optional[_Union[DeployStatus.State, str]] = ..., wait: _Optional[_Union[DeployWait, _Mapping]] = ...) -> None: ...

class DeployWait(_message.Message):
    __slots__ = ("reason", "address")
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        REASON_UNSPECIFIED: _ClassVar[DeployWait.Reason]
        WHITELIST_REQUIRED: _ClassVar[DeployWait.Reason]
    REASON_UNSPECIFIED: DeployWait.Reason
    WHITELIST_REQUIRED: DeployWait.Reason
    REASON_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    reason: DeployWait.Reason
    address: str
    def __init__(self, reason: _Optional[_Union[DeployWait.Reason, str]] = ..., address: _Optional[str] = ...) -> None: ...

class GetDeployStatusRequest(_message.Message):
    __slots__ = ("proposal_id",)
    PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    proposal_id: int
    def __init__(self, proposal_id: _Optional[int] = ...) -> None: ...

class GetDeployStatusResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DeployStatus
    def __init__(self, status: _Optional[_Union[DeployStatus, _Mapping]] = ...) -> None: ...

class SubaccountAuthorization(_message.Message):
    __slots__ = ("smart_account_address", "message", "signature")
    SMART_ACCOUNT_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    smart_account_address: str
    message: str
    signature: str
    def __init__(self, smart_account_address: _Optional[str] = ..., message: _Optional[str] = ..., signature: _Optional[str] = ...) -> None: ...

class DeployBotRequest(_message.Message):
    __slots__ = ("proposal_id", "subaccount_authorization")
    PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_AUTHORIZATION_FIELD_NUMBER: _ClassVar[int]
    proposal_id: int
    subaccount_authorization: SubaccountAuthorization
    def __init__(self, proposal_id: _Optional[int] = ..., subaccount_authorization: _Optional[_Union[SubaccountAuthorization, _Mapping]] = ...) -> None: ...

class DeployBotResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: DeployStatus
    def __init__(self, status: _Optional[_Union[DeployStatus, _Mapping]] = ...) -> None: ...

class GetDeployProposalRequest(_message.Message):
    __slots__ = ("proposal_id",)
    PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    proposal_id: int
    def __init__(self, proposal_id: _Optional[int] = ...) -> None: ...

class GetDeployProposalResponse(_message.Message):
    __slots__ = ("proposal_id", "summary", "status", "created_at", "funding_subaccount_label")
    PROPOSAL_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FUNDING_SUBACCOUNT_LABEL_FIELD_NUMBER: _ClassVar[int]
    proposal_id: int
    summary: DeployProposalSummary
    status: DeployStatus
    created_at: _timestamp_pb2.Timestamp
    funding_subaccount_label: str
    def __init__(self, proposal_id: _Optional[int] = ..., summary: _Optional[_Union[DeployProposalSummary, _Mapping]] = ..., status: _Optional[_Union[DeployStatus, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., funding_subaccount_label: _Optional[str] = ...) -> None: ...

class Bot(_message.Message):
    __slots__ = ("bot_id", "name", "subaccount_id", "status", "status_reason", "version_id", "last_decision_at", "created_at", "quote_asset", "markets", "funding", "uptime_ratio", "running_since", "pause_reason", "activity")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[Bot.Status]
        DEPLOYING: _ClassVar[Bot.Status]
        RUNNING: _ClassVar[Bot.Status]
        STOPPING: _ClassVar[Bot.Status]
        STOPPED: _ClassVar[Bot.Status]
        PAUSED: _ClassVar[Bot.Status]
    STATUS_UNSPECIFIED: Bot.Status
    DEPLOYING: Bot.Status
    RUNNING: Bot.Status
    STOPPING: Bot.Status
    STOPPED: Bot.Status
    PAUSED: Bot.Status
    class PauseReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PAUSE_REASON_UNSPECIFIED: _ClassVar[Bot.PauseReason]
        BOT_DECIDED: _ClassVar[Bot.PauseReason]
        FAILURES_IN_A_ROW: _ClassVar[Bot.PauseReason]
        ENVIRONMENT_RESET: _ClassVar[Bot.PauseReason]
        UNRECORDED_ORDER: _ClassVar[Bot.PauseReason]
    PAUSE_REASON_UNSPECIFIED: Bot.PauseReason
    BOT_DECIDED: Bot.PauseReason
    FAILURES_IN_A_ROW: Bot.PauseReason
    ENVIRONMENT_RESET: Bot.PauseReason
    UNRECORDED_ORDER: Bot.PauseReason
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_REASON_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    LAST_DECISION_AT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_FIELD_NUMBER: _ClassVar[int]
    UPTIME_RATIO_FIELD_NUMBER: _ClassVar[int]
    RUNNING_SINCE_FIELD_NUMBER: _ClassVar[int]
    PAUSE_REASON_FIELD_NUMBER: _ClassVar[int]
    ACTIVITY_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    name: str
    subaccount_id: int
    status: Bot.Status
    status_reason: str
    version_id: str
    last_decision_at: _timestamp_pb2.Timestamp
    created_at: _timestamp_pb2.Timestamp
    quote_asset: str
    markets: _containers.RepeatedScalarFieldContainer[str]
    funding: BotFunding
    uptime_ratio: str
    running_since: _timestamp_pb2.Timestamp
    pause_reason: Bot.PauseReason
    activity: _containers.RepeatedCompositeFieldContainer[BotActivityHour]
    def __init__(self, bot_id: _Optional[int] = ..., name: _Optional[str] = ..., subaccount_id: _Optional[int] = ..., status: _Optional[_Union[Bot.Status, str]] = ..., status_reason: _Optional[str] = ..., version_id: _Optional[str] = ..., last_decision_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., quote_asset: _Optional[str] = ..., markets: _Optional[_Iterable[str]] = ..., funding: _Optional[_Union[BotFunding, _Mapping]] = ..., uptime_ratio: _Optional[str] = ..., running_since: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pause_reason: _Optional[_Union[Bot.PauseReason, str]] = ..., activity: _Optional[_Iterable[_Union[BotActivityHour, _Mapping]]] = ...) -> None: ...

class BotActivityHour(_message.Message):
    __slots__ = ("start", "decisions", "fills", "expired")
    START_FIELD_NUMBER: _ClassVar[int]
    DECISIONS_FIELD_NUMBER: _ClassVar[int]
    FILLS_FIELD_NUMBER: _ClassVar[int]
    EXPIRED_FIELD_NUMBER: _ClassVar[int]
    start: _timestamp_pb2.Timestamp
    decisions: int
    fills: int
    expired: int
    def __init__(self, start: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., decisions: _Optional[int] = ..., fills: _Optional[int] = ..., expired: _Optional[int] = ...) -> None: ...

class BotFunding(_message.Message):
    __slots__ = ("subaccount_id", "subaccount_label", "initial_funding")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_LABEL_FIELD_NUMBER: _ClassVar[int]
    INITIAL_FUNDING_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    subaccount_label: str
    initial_funding: _containers.RepeatedCompositeFieldContainer[Money]
    def __init__(self, subaccount_id: _Optional[int] = ..., subaccount_label: _Optional[str] = ..., initial_funding: _Optional[_Iterable[_Union[Money, _Mapping]]] = ...) -> None: ...

class BotStatusCount(_message.Message):
    __slots__ = ("status", "count")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    status: Bot.Status
    count: int
    def __init__(self, status: _Optional[_Union[Bot.Status, str]] = ..., count: _Optional[int] = ...) -> None: ...

class ListBotsRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListBotsResponse(_message.Message):
    __slots__ = ("bots", "next_page_token", "status_counts")
    BOTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    STATUS_COUNTS_FIELD_NUMBER: _ClassVar[int]
    bots: _containers.RepeatedCompositeFieldContainer[Bot]
    next_page_token: str
    status_counts: _containers.RepeatedCompositeFieldContainer[BotStatusCount]
    def __init__(self, bots: _Optional[_Iterable[_Union[Bot, _Mapping]]] = ..., next_page_token: _Optional[str] = ..., status_counts: _Optional[_Iterable[_Union[BotStatusCount, _Mapping]]] = ...) -> None: ...

class BotDecision(_message.Message):
    __slots__ = ("decided_at", "event", "orders", "logs")
    DECIDED_AT_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    LOGS_FIELD_NUMBER: _ClassVar[int]
    decided_at: _timestamp_pb2.Timestamp
    event: str
    orders: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    logs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, decided_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., event: _Optional[str] = ..., orders: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., logs: _Optional[_Iterable[str]] = ...) -> None: ...

class BotError(_message.Message):
    __slots__ = ("time", "event", "message")
    TIME_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    event: str
    message: str
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., event: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class GetBotRequest(_message.Message):
    __slots__ = ("bot_id",)
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    def __init__(self, bot_id: _Optional[int] = ...) -> None: ...

class StopBotRequest(_message.Message):
    __slots__ = ("bot_id", "mode", "idempotency_key")
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    mode: StopMode
    idempotency_key: str
    def __init__(self, bot_id: _Optional[int] = ..., mode: _Optional[_Union[StopMode, str]] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class StopBotResponse(_message.Message):
    __slots__ = ("bot", "mode")
    BOT_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    bot: Bot
    mode: StopMode
    def __init__(self, bot: _Optional[_Union[Bot, _Mapping]] = ..., mode: _Optional[_Union[StopMode, str]] = ...) -> None: ...

class GetBotResponse(_message.Message):
    __slots__ = ("bot", "money_card", "settings", "decisions", "errors")
    BOT_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    DECISIONS_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    bot: Bot
    money_card: MoneyCard
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    decisions: _containers.RepeatedCompositeFieldContainer[BotDecision]
    errors: _containers.RepeatedCompositeFieldContainer[BotError]
    def __init__(self, bot: _Optional[_Union[Bot, _Mapping]] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., decisions: _Optional[_Iterable[_Union[BotDecision, _Mapping]]] = ..., errors: _Optional[_Iterable[_Union[BotError, _Mapping]]] = ...) -> None: ...

class ListBotVersionsRequest(_message.Message):
    __slots__ = ("bot_id", "limit", "page_token")
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    limit: int
    page_token: str
    def __init__(self, bot_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class BotVersion(_message.Message):
    __slots__ = ("version_id", "name", "runtime_version", "started_at", "stopped_at")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    STOPPED_AT_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    name: str
    runtime_version: str
    started_at: _timestamp_pb2.Timestamp
    stopped_at: _timestamp_pb2.Timestamp
    def __init__(self, version_id: _Optional[str] = ..., name: _Optional[str] = ..., runtime_version: _Optional[str] = ..., started_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., stopped_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListBotVersionsResponse(_message.Message):
    __slots__ = ("versions", "next_page_token")
    VERSIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    versions: _containers.RepeatedCompositeFieldContainer[BotVersion]
    next_page_token: str
    def __init__(self, versions: _Optional[_Iterable[_Union[BotVersion, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetStrategyVersionRequest(_message.Message):
    __slots__ = ("version_id",)
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    def __init__(self, version_id: _Optional[str] = ...) -> None: ...

class GetStrategyVersionResponse(_message.Message):
    __slots__ = ("version_id", "name", "runtime_version", "manifest", "code", "settings_form", "valid", "created_at", "flow", "validation")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FORM_FIELD_NUMBER: _ClassVar[int]
    VALID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FLOW_FIELD_NUMBER: _ClassVar[int]
    VALIDATION_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    name: str
    runtime_version: str
    manifest: _struct_pb2.Struct
    code: str
    settings_form: _containers.RepeatedCompositeFieldContainer[SettingField]
    valid: bool
    created_at: _timestamp_pb2.Timestamp
    flow: StrategyFlow
    validation: VersionValidation
    def __init__(self, version_id: _Optional[str] = ..., name: _Optional[str] = ..., runtime_version: _Optional[str] = ..., manifest: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., code: _Optional[str] = ..., settings_form: _Optional[_Iterable[_Union[SettingField, _Mapping]]] = ..., valid: _Optional[bool] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., flow: _Optional[_Union[StrategyFlow, _Mapping]] = ..., validation: _Optional[_Union[VersionValidation, _Mapping]] = ...) -> None: ...

class StrategyFlow(_message.Message):
    __slots__ = ("nodes", "edges", "notes", "complete")
    NODES_FIELD_NUMBER: _ClassVar[int]
    EDGES_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    COMPLETE_FIELD_NUMBER: _ClassVar[int]
    nodes: _containers.RepeatedCompositeFieldContainer[FlowNode]
    edges: _containers.RepeatedCompositeFieldContainer[FlowEdge]
    notes: _containers.RepeatedScalarFieldContainer[str]
    complete: bool
    def __init__(self, nodes: _Optional[_Iterable[_Union[FlowNode, _Mapping]]] = ..., edges: _Optional[_Iterable[_Union[FlowEdge, _Mapping]]] = ..., notes: _Optional[_Iterable[str]] = ..., complete: _Optional[bool] = ...) -> None: ...

class FlowNode(_message.Message):
    __slots__ = ("node_id", "kind", "label", "span", "event", "action", "settings")
    class Kind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        KIND_UNSPECIFIED: _ClassVar[FlowNode.Kind]
        TRIGGER: _ClassVar[FlowNode.Kind]
        CONDITION: _ClassVar[FlowNode.Kind]
        ACTION: _ClassVar[FlowNode.Kind]
    KIND_UNSPECIFIED: FlowNode.Kind
    TRIGGER: FlowNode.Kind
    CONDITION: FlowNode.Kind
    ACTION: FlowNode.Kind
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    LABEL_FIELD_NUMBER: _ClassVar[int]
    SPAN_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    kind: FlowNode.Kind
    label: str
    span: SourceSpan
    event: str
    action: str
    settings: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, node_id: _Optional[str] = ..., kind: _Optional[_Union[FlowNode.Kind, str]] = ..., label: _Optional[str] = ..., span: _Optional[_Union[SourceSpan, _Mapping]] = ..., event: _Optional[str] = ..., action: _Optional[str] = ..., settings: _Optional[_Iterable[str]] = ...) -> None: ...

class FlowEdge(_message.Message):
    __slots__ = ("from_node_id", "to_node_id", "branch")
    FROM_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    TO_NODE_ID_FIELD_NUMBER: _ClassVar[int]
    BRANCH_FIELD_NUMBER: _ClassVar[int]
    from_node_id: str
    to_node_id: str
    branch: str
    def __init__(self, from_node_id: _Optional[str] = ..., to_node_id: _Optional[str] = ..., branch: _Optional[str] = ...) -> None: ...

class SourceSpan(_message.Message):
    __slots__ = ("start_line", "end_line")
    START_LINE_FIELD_NUMBER: _ClassVar[int]
    END_LINE_FIELD_NUMBER: _ClassVar[int]
    start_line: int
    end_line: int
    def __init__(self, start_line: _Optional[int] = ..., end_line: _Optional[int] = ...) -> None: ...

class Strategy(_message.Message):
    __slots__ = ("strategy_id", "name", "revision", "head_version_id", "valid", "origin", "created_at", "updated_at", "bot", "markets", "summary", "listing")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    HEAD_VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    VALID_FIELD_NUMBER: _ClassVar[int]
    ORIGIN_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    BOT_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    LISTING_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    name: str
    revision: int
    head_version_id: str
    valid: bool
    origin: StrategyOrigin
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    bot: StrategyBot
    markets: _containers.RepeatedScalarFieldContainer[str]
    summary: str
    listing: StrategyListing
    def __init__(self, strategy_id: _Optional[int] = ..., name: _Optional[str] = ..., revision: _Optional[int] = ..., head_version_id: _Optional[str] = ..., valid: _Optional[bool] = ..., origin: _Optional[_Union[StrategyOrigin, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bot: _Optional[_Union[StrategyBot, _Mapping]] = ..., markets: _Optional[_Iterable[str]] = ..., summary: _Optional[str] = ..., listing: _Optional[_Union[StrategyListing, _Mapping]] = ...) -> None: ...

class StrategyListing(_message.Message):
    __slots__ = ("listing_id", "state", "version_id", "published_at")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LISTING_STATE_UNSPECIFIED: _ClassVar[StrategyListing.State]
        PUBLIC: _ClassVar[StrategyListing.State]
        HIDDEN: _ClassVar[StrategyListing.State]
    LISTING_STATE_UNSPECIFIED: StrategyListing.State
    PUBLIC: StrategyListing.State
    HIDDEN: StrategyListing.State
    LISTING_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_FIELD_NUMBER: _ClassVar[int]
    listing_id: int
    state: StrategyListing.State
    version_id: str
    published_at: _timestamp_pb2.Timestamp
    def __init__(self, listing_id: _Optional[int] = ..., state: _Optional[_Union[StrategyListing.State, str]] = ..., version_id: _Optional[str] = ..., published_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StrategyBot(_message.Message):
    __slots__ = ("bot_id", "status")
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    status: Bot.Status
    def __init__(self, bot_id: _Optional[int] = ..., status: _Optional[_Union[Bot.Status, str]] = ...) -> None: ...

class StrategyOrigin(_message.Message):
    __slots__ = ("template_id", "duplicate")
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    DUPLICATE_FIELD_NUMBER: _ClassVar[int]
    template_id: str
    duplicate: StrategyDuplicateOrigin
    def __init__(self, template_id: _Optional[str] = ..., duplicate: _Optional[_Union[StrategyDuplicateOrigin, _Mapping]] = ...) -> None: ...

class StrategyDuplicateOrigin(_message.Message):
    __slots__ = ("source_version_id",)
    SOURCE_VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    source_version_id: str
    def __init__(self, source_version_id: _Optional[str] = ...) -> None: ...

class StrategyRevision(_message.Message):
    __slots__ = ("revision", "version_id", "valid", "saved_at", "saved_by")
    class SavedBy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SAVED_BY_UNSPECIFIED: _ClassVar[StrategyRevision.SavedBy]
        SESSION: _ClassVar[StrategyRevision.SavedBy]
        API_KEY: _ClassVar[StrategyRevision.SavedBy]
        CONNECTED_APP: _ClassVar[StrategyRevision.SavedBy]
    SAVED_BY_UNSPECIFIED: StrategyRevision.SavedBy
    SESSION: StrategyRevision.SavedBy
    API_KEY: StrategyRevision.SavedBy
    CONNECTED_APP: StrategyRevision.SavedBy
    REVISION_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    VALID_FIELD_NUMBER: _ClassVar[int]
    SAVED_AT_FIELD_NUMBER: _ClassVar[int]
    SAVED_BY_FIELD_NUMBER: _ClassVar[int]
    revision: int
    version_id: str
    valid: bool
    saved_at: _timestamp_pb2.Timestamp
    saved_by: StrategyRevision.SavedBy
    def __init__(self, revision: _Optional[int] = ..., version_id: _Optional[str] = ..., valid: _Optional[bool] = ..., saved_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., saved_by: _Optional[_Union[StrategyRevision.SavedBy, str]] = ...) -> None: ...

class CreateStrategyRequest(_message.Message):
    __slots__ = ("name", "template_id", "version_id", "idempotency_key")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    name: str
    template_id: str
    version_id: str
    idempotency_key: str
    def __init__(self, name: _Optional[str] = ..., template_id: _Optional[str] = ..., version_id: _Optional[str] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class CreateStrategyResponse(_message.Message):
    __slots__ = ("strategy", "version")
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    version: VersionValidation
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ..., version: _Optional[_Union[VersionValidation, _Mapping]] = ...) -> None: ...

class SaveDraftVersionRequest(_message.Message):
    __slots__ = ("strategy_id", "expected_revision", "name", "manifest", "code", "runtime_version", "idempotency_key", "expected_notes_revision")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_NOTES_REVISION_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    expected_revision: int
    name: str
    manifest: _struct_pb2.Struct
    code: str
    runtime_version: str
    idempotency_key: str
    expected_notes_revision: int
    def __init__(self, strategy_id: _Optional[int] = ..., expected_revision: _Optional[int] = ..., name: _Optional[str] = ..., manifest: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., code: _Optional[str] = ..., runtime_version: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., expected_notes_revision: _Optional[int] = ...) -> None: ...

class SaveDraftVersionResponse(_message.Message):
    __slots__ = ("revision", "version")
    REVISION_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    revision: int
    version: VersionValidation
    def __init__(self, revision: _Optional[int] = ..., version: _Optional[_Union[VersionValidation, _Mapping]] = ...) -> None: ...

class GetStrategyRequest(_message.Message):
    __slots__ = ("strategy_id",)
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    def __init__(self, strategy_id: _Optional[int] = ...) -> None: ...

class GetStrategyResponse(_message.Message):
    __slots__ = ("strategy", "head", "notes")
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    HEAD_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    head: GetStrategyVersionResponse
    notes: StrategyNotes
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ..., head: _Optional[_Union[GetStrategyVersionResponse, _Mapping]] = ..., notes: _Optional[_Union[StrategyNotes, _Mapping]] = ...) -> None: ...

class ListStrategiesRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListStrategiesResponse(_message.Message):
    __slots__ = ("strategies", "next_page_token")
    STRATEGIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    strategies: _containers.RepeatedCompositeFieldContainer[Strategy]
    next_page_token: str
    def __init__(self, strategies: _Optional[_Iterable[_Union[Strategy, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListStrategyRevisionsRequest(_message.Message):
    __slots__ = ("strategy_id", "limit", "page_token")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    limit: int
    page_token: str
    def __init__(self, strategy_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListStrategyRevisionsResponse(_message.Message):
    __slots__ = ("revisions", "next_page_token")
    REVISIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    revisions: _containers.RepeatedCompositeFieldContainer[StrategyRevision]
    next_page_token: str
    def __init__(self, revisions: _Optional[_Iterable[_Union[StrategyRevision, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class RenameStrategyRequest(_message.Message):
    __slots__ = ("strategy_id", "name")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    name: str
    def __init__(self, strategy_id: _Optional[int] = ..., name: _Optional[str] = ...) -> None: ...

class RenameStrategyResponse(_message.Message):
    __slots__ = ("strategy",)
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    strategy: Strategy
    def __init__(self, strategy: _Optional[_Union[Strategy, _Mapping]] = ...) -> None: ...

class DeleteStrategyRequest(_message.Message):
    __slots__ = ("strategy_id",)
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    def __init__(self, strategy_id: _Optional[int] = ...) -> None: ...

class DeleteStrategyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StrategyNotes(_message.Message):
    __slots__ = ("strategy_id", "notes_revision", "summary", "body", "saved_at", "saved_by")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    NOTES_REVISION_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    SAVED_AT_FIELD_NUMBER: _ClassVar[int]
    SAVED_BY_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    notes_revision: int
    summary: str
    body: str
    saved_at: _timestamp_pb2.Timestamp
    saved_by: StrategyRevision.SavedBy
    def __init__(self, strategy_id: _Optional[int] = ..., notes_revision: _Optional[int] = ..., summary: _Optional[str] = ..., body: _Optional[str] = ..., saved_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., saved_by: _Optional[_Union[StrategyRevision.SavedBy, str]] = ...) -> None: ...

class GetStrategyNotesRequest(_message.Message):
    __slots__ = ("strategy_id",)
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    def __init__(self, strategy_id: _Optional[int] = ...) -> None: ...

class GetStrategyNotesResponse(_message.Message):
    __slots__ = ("notes",)
    NOTES_FIELD_NUMBER: _ClassVar[int]
    notes: StrategyNotes
    def __init__(self, notes: _Optional[_Union[StrategyNotes, _Mapping]] = ...) -> None: ...

class SaveStrategyNotesRequest(_message.Message):
    __slots__ = ("strategy_id", "expected_notes_revision", "summary", "body", "idempotency_key", "expected_revision")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_NOTES_REVISION_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_REVISION_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    expected_notes_revision: int
    summary: str
    body: str
    idempotency_key: str
    expected_revision: int
    def __init__(self, strategy_id: _Optional[int] = ..., expected_notes_revision: _Optional[int] = ..., summary: _Optional[str] = ..., body: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., expected_revision: _Optional[int] = ...) -> None: ...

class SaveStrategyNotesResponse(_message.Message):
    __slots__ = ("notes",)
    NOTES_FIELD_NUMBER: _ClassVar[int]
    notes: StrategyNotes
    def __init__(self, notes: _Optional[_Union[StrategyNotes, _Mapping]] = ...) -> None: ...

class ListStrategyNotesRevisionsRequest(_message.Message):
    __slots__ = ("strategy_id", "limit", "page_token")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    limit: int
    page_token: str
    def __init__(self, strategy_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListStrategyNotesRevisionsResponse(_message.Message):
    __slots__ = ("revisions", "next_page_token")
    REVISIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    revisions: _containers.RepeatedCompositeFieldContainer[StrategyNotes]
    next_page_token: str
    def __init__(self, revisions: _Optional[_Iterable[_Union[StrategyNotes, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListBacktestsRequest(_message.Message):
    __slots__ = ("strategy_id", "limit", "page_token")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    limit: int
    page_token: str
    def __init__(self, strategy_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class StrategyBacktest(_message.Message):
    __slots__ = ("summary", "version_id", "revision", "window", "created_at", "finished_at")
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    REVISION_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    summary: BacktestSummary
    version_id: str
    revision: int
    window: TimeWindow
    created_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    def __init__(self, summary: _Optional[_Union[BacktestSummary, _Mapping]] = ..., version_id: _Optional[str] = ..., revision: _Optional[int] = ..., window: _Optional[_Union[TimeWindow, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListBacktestsResponse(_message.Message):
    __slots__ = ("backtests", "next_page_token")
    BACKTESTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    backtests: _containers.RepeatedCompositeFieldContainer[StrategyBacktest]
    next_page_token: str
    def __init__(self, backtests: _Optional[_Iterable[_Union[StrategyBacktest, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class BotLogEntry(_message.Message):
    __slots__ = ("sequence", "time", "kind", "message")
    class Kind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        KIND_UNSPECIFIED: _ClassVar[BotLogEntry.Kind]
        LOG: _ClassVar[BotLogEntry.Kind]
        DECISION: _ClassVar[BotLogEntry.Kind]
        ERROR: _ClassVar[BotLogEntry.Kind]
    KIND_UNSPECIFIED: BotLogEntry.Kind
    LOG: BotLogEntry.Kind
    DECISION: BotLogEntry.Kind
    ERROR: BotLogEntry.Kind
    SEQUENCE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    sequence: int
    time: _timestamp_pb2.Timestamp
    kind: BotLogEntry.Kind
    message: str
    def __init__(self, sequence: _Optional[int] = ..., time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., kind: _Optional[_Union[BotLogEntry.Kind, str]] = ..., message: _Optional[str] = ...) -> None: ...

class ListBotLogsRequest(_message.Message):
    __slots__ = ("bot_id", "start_time", "limit", "page_token")
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    start_time: _timestamp_pb2.Timestamp
    limit: int
    page_token: str
    def __init__(self, bot_id: _Optional[int] = ..., start_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListBotLogsResponse(_message.Message):
    __slots__ = ("entries", "next_page_token", "follow_token", "deployed_again")
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    FOLLOW_TOKEN_FIELD_NUMBER: _ClassVar[int]
    DEPLOYED_AGAIN_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[BotLogEntry]
    next_page_token: str
    follow_token: str
    deployed_again: bool
    def __init__(self, entries: _Optional[_Iterable[_Union[BotLogEntry, _Mapping]]] = ..., next_page_token: _Optional[str] = ..., follow_token: _Optional[str] = ..., deployed_again: _Optional[bool] = ...) -> None: ...

class CommunityBacktest(_message.Message):
    __slots__ = ("status", "not_backtestable_reason", "window", "metrics", "report", "failure")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    NOT_BACKTESTABLE_REASON_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    REPORT_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    status: Backtest.Status
    not_backtestable_reason: NotBacktestableReason
    window: TimeWindow
    metrics: BacktestMetrics
    report: BacktestReport
    failure: str
    def __init__(self, status: _Optional[_Union[Backtest.Status, str]] = ..., not_backtestable_reason: _Optional[_Union[NotBacktestableReason, str]] = ..., window: _Optional[_Union[TimeWindow, _Mapping]] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., report: _Optional[_Union[BacktestReport, _Mapping]] = ..., failure: _Optional[str] = ...) -> None: ...

class CommunityStrategySummary(_message.Message):
    __slots__ = ("listing_id", "title", "tags", "markets", "author_username", "backtest", "published_at")
    LISTING_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_USERNAME_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_FIELD_NUMBER: _ClassVar[int]
    listing_id: int
    title: str
    tags: _containers.RepeatedScalarFieldContainer[StrategyTag]
    markets: _containers.RepeatedScalarFieldContainer[str]
    author_username: str
    backtest: CommunityBacktest
    published_at: _timestamp_pb2.Timestamp
    def __init__(self, listing_id: _Optional[int] = ..., title: _Optional[str] = ..., tags: _Optional[_Iterable[_Union[StrategyTag, str]]] = ..., markets: _Optional[_Iterable[str]] = ..., author_username: _Optional[str] = ..., backtest: _Optional[_Union[CommunityBacktest, _Mapping]] = ..., published_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CommunityStrategy(_message.Message):
    __slots__ = ("listing_id", "title", "description", "tags", "markets", "author_username", "published_at", "version_id", "runtime_version", "manifest", "code", "settings_form", "money_card", "flow", "backtest")
    LISTING_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_USERNAME_FIELD_NUMBER: _ClassVar[int]
    PUBLISHED_AT_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FORM_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    FLOW_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_FIELD_NUMBER: _ClassVar[int]
    listing_id: int
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[StrategyTag]
    markets: _containers.RepeatedScalarFieldContainer[str]
    author_username: str
    published_at: _timestamp_pb2.Timestamp
    version_id: str
    runtime_version: str
    manifest: _struct_pb2.Struct
    code: str
    settings_form: _containers.RepeatedCompositeFieldContainer[SettingField]
    money_card: MoneyCard
    flow: StrategyFlow
    backtest: CommunityBacktest
    def __init__(self, listing_id: _Optional[int] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[_Union[StrategyTag, str]]] = ..., markets: _Optional[_Iterable[str]] = ..., author_username: _Optional[str] = ..., published_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., version_id: _Optional[str] = ..., runtime_version: _Optional[str] = ..., manifest: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., code: _Optional[str] = ..., settings_form: _Optional[_Iterable[_Union[SettingField, _Mapping]]] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., flow: _Optional[_Union[StrategyFlow, _Mapping]] = ..., backtest: _Optional[_Union[CommunityBacktest, _Mapping]] = ...) -> None: ...

class PublishStrategyVersionRequest(_message.Message):
    __slots__ = ("strategy_id", "version_id", "title", "description", "tags", "idempotency_key")
    STRATEGY_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    strategy_id: int
    version_id: str
    title: str
    description: str
    tags: _containers.RepeatedScalarFieldContainer[StrategyTag]
    idempotency_key: str
    def __init__(self, strategy_id: _Optional[int] = ..., version_id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., tags: _Optional[_Iterable[_Union[StrategyTag, str]]] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class PublishStrategyVersionResponse(_message.Message):
    __slots__ = ("listing",)
    LISTING_FIELD_NUMBER: _ClassVar[int]
    listing: StrategyListing
    def __init__(self, listing: _Optional[_Union[StrategyListing, _Mapping]] = ...) -> None: ...

class UnpublishStrategyRequest(_message.Message):
    __slots__ = ("listing_id",)
    LISTING_ID_FIELD_NUMBER: _ClassVar[int]
    listing_id: int
    def __init__(self, listing_id: _Optional[int] = ...) -> None: ...

class UnpublishStrategyResponse(_message.Message):
    __slots__ = ("listing",)
    LISTING_FIELD_NUMBER: _ClassVar[int]
    listing: StrategyListing
    def __init__(self, listing: _Optional[_Union[StrategyListing, _Mapping]] = ...) -> None: ...

class ListCommunityStrategiesRequest(_message.Message):
    __slots__ = ("tags", "markets", "limit", "page_token")
    TAGS_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    tags: _containers.RepeatedScalarFieldContainer[StrategyTag]
    markets: _containers.RepeatedScalarFieldContainer[str]
    limit: int
    page_token: str
    def __init__(self, tags: _Optional[_Iterable[_Union[StrategyTag, str]]] = ..., markets: _Optional[_Iterable[str]] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListCommunityStrategiesResponse(_message.Message):
    __slots__ = ("strategies", "next_page_token")
    STRATEGIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    strategies: _containers.RepeatedCompositeFieldContainer[CommunityStrategySummary]
    next_page_token: str
    def __init__(self, strategies: _Optional[_Iterable[_Union[CommunityStrategySummary, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class GetCommunityStrategyRequest(_message.Message):
    __slots__ = ("listing_id",)
    LISTING_ID_FIELD_NUMBER: _ClassVar[int]
    listing_id: int
    def __init__(self, listing_id: _Optional[int] = ...) -> None: ...

class GetCommunityStrategyResponse(_message.Message):
    __slots__ = ("strategy",)
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    strategy: CommunityStrategy
    def __init__(self, strategy: _Optional[_Union[CommunityStrategy, _Mapping]] = ...) -> None: ...
