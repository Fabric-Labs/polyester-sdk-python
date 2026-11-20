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

class OrderSide(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SIDE_UNSPECIFIED: _ClassVar[OrderSide]
    BUY: _ClassVar[OrderSide]
    SELL: _ClassVar[OrderSide]
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
SIDE_UNSPECIFIED: OrderSide
BUY: OrderSide
SELL: OrderSide

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

class ErrorDetail(_message.Message):
    __slots__ = ("code", "field_path", "retry_after", "bot_cap", "markets", "shortfall")
    CODE_FIELD_NUMBER: _ClassVar[int]
    FIELD_PATH_FIELD_NUMBER: _ClassVar[int]
    RETRY_AFTER_FIELD_NUMBER: _ClassVar[int]
    BOT_CAP_FIELD_NUMBER: _ClassVar[int]
    MARKETS_FIELD_NUMBER: _ClassVar[int]
    SHORTFALL_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    field_path: str
    retry_after: _timestamp_pb2.Timestamp
    bot_cap: BotCapDetail
    markets: _containers.RepeatedScalarFieldContainer[str]
    shortfall: _containers.RepeatedCompositeFieldContainer[Money]
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ..., field_path: _Optional[str] = ..., retry_after: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., bot_cap: _Optional[_Union[BotCapDetail, _Mapping]] = ..., markets: _Optional[_Iterable[str]] = ..., shortfall: _Optional[_Iterable[_Union[Money, _Mapping]]] = ...) -> None: ...

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
    __slots__ = ("cpu_ms_per_call", "memory_bytes_per_call", "state_bytes", "code_bytes", "manifest_bytes", "unique_indicator_settings", "backtests_per_day", "scenario_runs_per_minute")
    CPU_MS_PER_CALL_FIELD_NUMBER: _ClassVar[int]
    MEMORY_BYTES_PER_CALL_FIELD_NUMBER: _ClassVar[int]
    STATE_BYTES_FIELD_NUMBER: _ClassVar[int]
    CODE_BYTES_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_BYTES_FIELD_NUMBER: _ClassVar[int]
    UNIQUE_INDICATOR_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    BACKTESTS_PER_DAY_FIELD_NUMBER: _ClassVar[int]
    SCENARIO_RUNS_PER_MINUTE_FIELD_NUMBER: _ClassVar[int]
    cpu_ms_per_call: int
    memory_bytes_per_call: int
    state_bytes: int
    code_bytes: int
    manifest_bytes: int
    unique_indicator_settings: int
    backtests_per_day: int
    scenario_runs_per_minute: int
    def __init__(self, cpu_ms_per_call: _Optional[int] = ..., memory_bytes_per_call: _Optional[int] = ..., state_bytes: _Optional[int] = ..., code_bytes: _Optional[int] = ..., manifest_bytes: _Optional[int] = ..., unique_indicator_settings: _Optional[int] = ..., backtests_per_day: _Optional[int] = ..., scenario_runs_per_minute: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("template_id", "name", "description", "manifest", "code", "runtime_version")
    TEMPLATE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    template_id: str
    name: str
    description: str
    manifest: _struct_pb2.Struct
    code: str
    runtime_version: str
    def __init__(self, template_id: _Optional[str] = ..., name: _Optional[str] = ..., description: _Optional[str] = ..., manifest: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., code: _Optional[str] = ..., runtime_version: _Optional[str] = ...) -> None: ...

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

class ValidateStrategyRequest(_message.Message):
    __slots__ = ("name", "manifest", "code", "runtime_version")
    NAME_FIELD_NUMBER: _ClassVar[int]
    MANIFEST_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    name: str
    manifest: _struct_pb2.Struct
    code: str
    runtime_version: str
    def __init__(self, name: _Optional[str] = ..., manifest: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., code: _Optional[str] = ..., runtime_version: _Optional[str] = ...) -> None: ...

class ValidateStrategyResponse(_message.Message):
    __slots__ = ("version_id", "runtime_version", "valid", "errors", "warnings", "money_card", "settings_form")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    RUNTIME_VERSION_FIELD_NUMBER: _ClassVar[int]
    VALID_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FORM_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    runtime_version: str
    valid: bool
    errors: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    warnings: _containers.RepeatedCompositeFieldContainer[ValidationIssue]
    money_card: MoneyCard
    settings_form: _containers.RepeatedCompositeFieldContainer[SettingField]
    def __init__(self, version_id: _Optional[str] = ..., runtime_version: _Optional[str] = ..., valid: _Optional[bool] = ..., errors: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ..., warnings: _Optional[_Iterable[_Union[ValidationIssue, _Mapping]]] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings_form: _Optional[_Iterable[_Union[SettingField, _Mapping]]] = ...) -> None: ...

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
    __slots__ = ("return_percent", "max_drawdown_percent", "trades", "win_rate_percent", "fees", "exposure_percent")
    RETURN_PERCENT_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_PERCENT_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    WIN_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    FEES_FIELD_NUMBER: _ClassVar[int]
    EXPOSURE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    return_percent: str
    max_drawdown_percent: str
    trades: int
    win_rate_percent: str
    fees: Money
    exposure_percent: str
    def __init__(self, return_percent: _Optional[str] = ..., max_drawdown_percent: _Optional[str] = ..., trades: _Optional[int] = ..., win_rate_percent: _Optional[str] = ..., fees: _Optional[_Union[Money, _Mapping]] = ..., exposure_percent: _Optional[str] = ...) -> None: ...

class Baseline(_message.Message):
    __slots__ = ("name", "metrics")
    NAME_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    name: str
    metrics: BacktestMetrics
    def __init__(self, name: _Optional[str] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ...) -> None: ...

class BacktestTrade(_message.Message):
    __slots__ = ("time", "market", "side", "price", "quantity", "fee", "reason")
    TIME_FIELD_NUMBER: _ClassVar[int]
    MARKET_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FEE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    time: _timestamp_pb2.Timestamp
    market: str
    side: OrderSide
    price: str
    quantity: str
    fee: Money
    reason: str
    def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., market: _Optional[str] = ..., side: _Optional[_Union[OrderSide, str]] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ..., fee: _Optional[_Union[Money, _Mapping]] = ..., reason: _Optional[str] = ...) -> None: ...

class DataGap(_message.Message):
    __slots__ = ("market", "timeframe", "window")
    MARKET_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    market: str
    timeframe: str
    window: TimeWindow
    def __init__(self, market: _Optional[str] = ..., timeframe: _Optional[str] = ..., window: _Optional[_Union[TimeWindow, _Mapping]] = ...) -> None: ...

class BacktestReport(_message.Message):
    __slots__ = ("fidelity", "evidence_grade", "period", "held_back_period", "metrics", "held_back_metrics", "baselines", "attempts", "trades", "data_gaps", "warnings", "report_url")
    FIDELITY_FIELD_NUMBER: _ClassVar[int]
    EVIDENCE_GRADE_FIELD_NUMBER: _ClassVar[int]
    PERIOD_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_PERIOD_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_METRICS_FIELD_NUMBER: _ClassVar[int]
    BASELINES_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    DATA_GAPS_FIELD_NUMBER: _ClassVar[int]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    REPORT_URL_FIELD_NUMBER: _ClassVar[int]
    fidelity: str
    evidence_grade: str
    period: TimeWindow
    held_back_period: TimeWindow
    metrics: BacktestMetrics
    held_back_metrics: BacktestMetrics
    baselines: _containers.RepeatedCompositeFieldContainer[Baseline]
    attempts: int
    trades: _containers.RepeatedCompositeFieldContainer[BacktestTrade]
    data_gaps: _containers.RepeatedCompositeFieldContainer[DataGap]
    warnings: _containers.RepeatedScalarFieldContainer[str]
    report_url: str
    def __init__(self, fidelity: _Optional[str] = ..., evidence_grade: _Optional[str] = ..., period: _Optional[_Union[TimeWindow, _Mapping]] = ..., held_back_period: _Optional[_Union[TimeWindow, _Mapping]] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., held_back_metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., baselines: _Optional[_Iterable[_Union[Baseline, _Mapping]]] = ..., attempts: _Optional[int] = ..., trades: _Optional[_Iterable[_Union[BacktestTrade, _Mapping]]] = ..., data_gaps: _Optional[_Iterable[_Union[DataGap, _Mapping]]] = ..., warnings: _Optional[_Iterable[str]] = ..., report_url: _Optional[str] = ...) -> None: ...

class Backtest(_message.Message):
    __slots__ = ("backtest_id", "version_id", "status", "window", "created_at", "finished_at", "report", "failure")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[Backtest.Status]
        QUEUED: _ClassVar[Backtest.Status]
        RUNNING: _ClassVar[Backtest.Status]
        DONE: _ClassVar[Backtest.Status]
        FAILED: _ClassVar[Backtest.Status]
    STATUS_UNSPECIFIED: Backtest.Status
    QUEUED: Backtest.Status
    RUNNING: Backtest.Status
    DONE: Backtest.Status
    FAILED: Backtest.Status
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    WINDOW_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    FINISHED_AT_FIELD_NUMBER: _ClassVar[int]
    REPORT_FIELD_NUMBER: _ClassVar[int]
    FAILURE_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    version_id: str
    status: Backtest.Status
    window: TimeWindow
    created_at: _timestamp_pb2.Timestamp
    finished_at: _timestamp_pb2.Timestamp
    report: BacktestReport
    failure: str
    def __init__(self, backtest_id: _Optional[int] = ..., version_id: _Optional[str] = ..., status: _Optional[_Union[Backtest.Status, str]] = ..., window: _Optional[_Union[TimeWindow, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., finished_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., report: _Optional[_Union[BacktestReport, _Mapping]] = ..., failure: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("backtest_id", "status", "metrics", "held_back_metrics", "attempts", "report_url")
    BACKTEST_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    METRICS_FIELD_NUMBER: _ClassVar[int]
    HELD_BACK_METRICS_FIELD_NUMBER: _ClassVar[int]
    ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    REPORT_URL_FIELD_NUMBER: _ClassVar[int]
    backtest_id: int
    status: Backtest.Status
    metrics: BacktestMetrics
    held_back_metrics: BacktestMetrics
    attempts: int
    report_url: str
    def __init__(self, backtest_id: _Optional[int] = ..., status: _Optional[_Union[Backtest.Status, str]] = ..., metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., held_back_metrics: _Optional[_Union[BacktestMetrics, _Mapping]] = ..., attempts: _Optional[int] = ..., report_url: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("name", "value")
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: str
    def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class DeployProposalSummary(_message.Message):
    __slots__ = ("version_id", "bot_name", "money_card", "settings", "funding_subaccount_id", "funding", "scenarios_passed", "backtest")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    BOT_NAME_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    FUNDING_FIELD_NUMBER: _ClassVar[int]
    SCENARIOS_PASSED_FIELD_NUMBER: _ClassVar[int]
    BACKTEST_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    bot_name: str
    money_card: MoneyCard
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    funding_subaccount_id: int
    funding: _containers.RepeatedCompositeFieldContainer[Money]
    scenarios_passed: int
    backtest: BacktestSummary
    def __init__(self, version_id: _Optional[str] = ..., bot_name: _Optional[str] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., funding_subaccount_id: _Optional[int] = ..., funding: _Optional[_Iterable[_Union[Money, _Mapping]]] = ..., scenarios_passed: _Optional[int] = ..., backtest: _Optional[_Union[BacktestSummary, _Mapping]] = ...) -> None: ...

class ProposeDeployRequest(_message.Message):
    __slots__ = ("version_id", "bot_name", "settings", "funding", "idempotency_key", "funding_subaccount_id")
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    BOT_NAME_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    FUNDING_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    FUNDING_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    bot_name: str
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    funding: _containers.RepeatedCompositeFieldContainer[Money]
    idempotency_key: str
    funding_subaccount_id: int
    def __init__(self, version_id: _Optional[str] = ..., bot_name: _Optional[str] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., funding: _Optional[_Iterable[_Union[Money, _Mapping]]] = ..., idempotency_key: _Optional[str] = ..., funding_subaccount_id: _Optional[int] = ...) -> None: ...

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
    __slots__ = ("proposal_id", "state", "step", "bot_id", "subaccount_id", "failure", "expires_at", "updated_at")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATE_UNSPECIFIED: _ClassVar[DeployStatus.State]
        PROPOSED: _ClassVar[DeployStatus.State]
        VALIDATING: _ClassVar[DeployStatus.State]
        CREATING_SUBACCOUNT: _ClassVar[DeployStatus.State]
        FUNDING: _ClassVar[DeployStatus.State]
        DEPLOYING: _ClassVar[DeployStatus.State]
        LIVE: _ClassVar[DeployStatus.State]
        FAILED: _ClassVar[DeployStatus.State]
        EXPIRED: _ClassVar[DeployStatus.State]
    STATE_UNSPECIFIED: DeployStatus.State
    PROPOSED: DeployStatus.State
    VALIDATING: DeployStatus.State
    CREATING_SUBACCOUNT: DeployStatus.State
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
    proposal_id: int
    state: DeployStatus.State
    step: str
    bot_id: int
    subaccount_id: int
    failure: str
    expires_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, proposal_id: _Optional[int] = ..., state: _Optional[_Union[DeployStatus.State, str]] = ..., step: _Optional[str] = ..., bot_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., failure: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

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

class Bot(_message.Message):
    __slots__ = ("bot_id", "name", "subaccount_id", "status", "status_reason", "version_id", "profit_and_loss", "last_decision_at", "created_at", "quote_asset")
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[Bot.Status]
        DEPLOYING: _ClassVar[Bot.Status]
        RUNNING: _ClassVar[Bot.Status]
        STOPPING: _ClassVar[Bot.Status]
        STOPPED: _ClassVar[Bot.Status]
        PAUSED: _ClassVar[Bot.Status]
        QUARANTINED: _ClassVar[Bot.Status]
    STATUS_UNSPECIFIED: Bot.Status
    DEPLOYING: Bot.Status
    RUNNING: Bot.Status
    STOPPING: Bot.Status
    STOPPED: Bot.Status
    PAUSED: Bot.Status
    QUARANTINED: Bot.Status
    BOT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATUS_REASON_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    PROFIT_AND_LOSS_FIELD_NUMBER: _ClassVar[int]
    LAST_DECISION_AT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    bot_id: int
    name: str
    subaccount_id: int
    status: Bot.Status
    status_reason: str
    version_id: str
    profit_and_loss: str
    last_decision_at: _timestamp_pb2.Timestamp
    created_at: _timestamp_pb2.Timestamp
    quote_asset: str
    def __init__(self, bot_id: _Optional[int] = ..., name: _Optional[str] = ..., subaccount_id: _Optional[int] = ..., status: _Optional[_Union[Bot.Status, str]] = ..., status_reason: _Optional[str] = ..., version_id: _Optional[str] = ..., profit_and_loss: _Optional[str] = ..., last_decision_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., quote_asset: _Optional[str] = ...) -> None: ...

class ListBotsRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListBotsResponse(_message.Message):
    __slots__ = ("bots", "next_page_token")
    BOTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    bots: _containers.RepeatedCompositeFieldContainer[Bot]
    next_page_token: str
    def __init__(self, bots: _Optional[_Iterable[_Union[Bot, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class BotBalance(_message.Message):
    __slots__ = ("asset", "free", "locked")
    ASSET_FIELD_NUMBER: _ClassVar[int]
    FREE_FIELD_NUMBER: _ClassVar[int]
    LOCKED_FIELD_NUMBER: _ClassVar[int]
    asset: str
    free: str
    locked: str
    def __init__(self, asset: _Optional[str] = ..., free: _Optional[str] = ..., locked: _Optional[str] = ...) -> None: ...

class BotOrder(_message.Message):
    __slots__ = ("order_id", "market", "side", "type", "price", "quantity", "filled_quantity", "created_at")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    MARKET_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FILLED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    market: str
    side: OrderSide
    type: str
    price: str
    quantity: str
    filled_quantity: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, order_id: _Optional[int] = ..., market: _Optional[str] = ..., side: _Optional[_Union[OrderSide, str]] = ..., type: _Optional[str] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ..., filled_quantity: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class BotDecision(_message.Message):
    __slots__ = ("decided_at", "event", "orders", "logs", "snapshot")
    DECIDED_AT_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    LOGS_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    decided_at: _timestamp_pb2.Timestamp
    event: str
    orders: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    logs: _containers.RepeatedScalarFieldContainer[str]
    snapshot: _struct_pb2.Struct
    def __init__(self, decided_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., event: _Optional[str] = ..., orders: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., logs: _Optional[_Iterable[str]] = ..., snapshot: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

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

class GetBotResponse(_message.Message):
    __slots__ = ("bot", "money_card", "settings", "balances", "open_orders", "decisions", "errors")
    BOT_FIELD_NUMBER: _ClassVar[int]
    MONEY_CARD_FIELD_NUMBER: _ClassVar[int]
    SETTINGS_FIELD_NUMBER: _ClassVar[int]
    BALANCES_FIELD_NUMBER: _ClassVar[int]
    OPEN_ORDERS_FIELD_NUMBER: _ClassVar[int]
    DECISIONS_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    bot: Bot
    money_card: MoneyCard
    settings: _containers.RepeatedCompositeFieldContainer[SettingValue]
    balances: _containers.RepeatedCompositeFieldContainer[BotBalance]
    open_orders: _containers.RepeatedCompositeFieldContainer[BotOrder]
    decisions: _containers.RepeatedCompositeFieldContainer[BotDecision]
    errors: _containers.RepeatedCompositeFieldContainer[BotError]
    def __init__(self, bot: _Optional[_Union[Bot, _Mapping]] = ..., money_card: _Optional[_Union[MoneyCard, _Mapping]] = ..., settings: _Optional[_Iterable[_Union[SettingValue, _Mapping]]] = ..., balances: _Optional[_Iterable[_Union[BotBalance, _Mapping]]] = ..., open_orders: _Optional[_Iterable[_Union[BotOrder, _Mapping]]] = ..., decisions: _Optional[_Iterable[_Union[BotDecision, _Mapping]]] = ..., errors: _Optional[_Iterable[_Union[BotError, _Mapping]]] = ...) -> None: ...

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
    __slots__ = ("entries", "next_page_token")
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[BotLogEntry]
    next_page_token: str
    def __init__(self, entries: _Optional[_Iterable[_Union[BotLogEntry, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
