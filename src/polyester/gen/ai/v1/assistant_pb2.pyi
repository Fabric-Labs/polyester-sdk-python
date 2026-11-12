import datetime

from polyester.gen.alerts.v1 import price_alerts_pb2 as _price_alerts_pb2
from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.chain.deposit.v1 import deposit_pb2 as _deposit_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2 as _ledger_read_pb2
from polyester.gen.marketdata.v1 import marketdata_pb2 as _marketdata_pb2
from polyester.gen.orders.v1 import orders_pb2 as _orders_pb2
from polyester.gen.orders.v1 import orders_read_pb2 as _orders_read_pb2
from polyester.gen.polyester.api import options_pb2 as _options_pb2
from polyester.gen.triggers.v1 import triggers_pb2 as _triggers_pb2
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
    CONVERSATION_NOT_FOUND: _ClassVar[ErrorCode]
    RUN_NOT_FOUND: _ClassVar[ErrorCode]
    APPROVAL_NOT_FOUND: _ClassVar[ErrorCode]
    MEMORY_NOT_FOUND: _ClassVar[ErrorCode]
    RUN_ACTIVE: _ClassVar[ErrorCode]
    IDEMPOTENCY_CONFLICT: _ClassVar[ErrorCode]
    APPROVAL_ALREADY_DECIDED: _ClassVar[ErrorCode]
    APPROVAL_EXPIRED: _ClassVar[ErrorCode]
    USAGE_LIMIT_REACHED: _ClassVar[ErrorCode]
    SERVICE_UNAVAILABLE: _ClassVar[ErrorCode]
    KEY_SETUP_NOT_FOUND: _ClassVar[ErrorCode]
    KEY_SETUP_NOT_REGISTERED: _ClassVar[ErrorCode]

class MessageRole(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ROLE_UNSPECIFIED: _ClassVar[MessageRole]
    USER: _ClassVar[MessageRole]
    ASSISTANT: _ClassVar[MessageRole]

class FailureCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FAILURE_UNSPECIFIED: _ClassVar[FailureCategory]
    CANCELLED: _ClassVar[FailureCategory]
    BUDGET_EXCEEDED: _ClassVar[FailureCategory]
    PERMISSION_DENIED: _ClassVar[FailureCategory]
    MODEL_UNAVAILABLE: _ClassVar[FailureCategory]
    UNEXPECTED_ERROR: _ClassVar[FailureCategory]

class ApprovalDecision(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DECISION_UNSPECIFIED: _ClassVar[ApprovalDecision]
    APPROVE: _ClassVar[ApprovalDecision]
    REJECT: _ClassVar[ApprovalDecision]

class ApprovalStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    APPROVAL_UNSPECIFIED: _ClassVar[ApprovalStatus]
    PENDING: _ClassVar[ApprovalStatus]
    APPROVED: _ClassVar[ApprovalStatus]
    REJECTED: _ClassVar[ApprovalStatus]
    EXPIRED: _ClassVar[ApprovalStatus]

class MemoryKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KIND_UNSPECIFIED: _ClassVar[MemoryKind]
    FACT: _ClassVar[MemoryKind]
    PLANNING_FIGURE: _ClassVar[MemoryKind]
    PROFILE: _ClassVar[MemoryKind]

class AssistantKeyState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KEY_STATE_UNSPECIFIED: _ClassVar[AssistantKeyState]
    ACTIVE: _ClassVar[AssistantKeyState]
    DISABLED: _ClassVar[AssistantKeyState]

class ReferencePriceSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRICE_SOURCE_UNSPECIFIED: _ClassVar[ReferencePriceSource]
    BEST_BID: _ClassVar[ReferencePriceSource]
    BEST_ASK: _ClassVar[ReferencePriceSource]
    LAST_PRICE: _ClassVar[ReferencePriceSource]
    INDEX_PRICE: _ClassVar[ReferencePriceSource]

class TriggerDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DIRECTION_UNSPECIFIED: _ClassVar[TriggerDirection]
    AT_OR_ABOVE: _ClassVar[TriggerDirection]
    AT_OR_BELOW: _ClassVar[TriggerDirection]

class OrderPriceField(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PRICE_FIELD_UNSPECIFIED: _ClassVar[OrderPriceField]
    LIMIT_PRICE: _ClassVar[OrderPriceField]
    TRIGGER_PRICE: _ClassVar[OrderPriceField]
    ACTIVATION_PRICE: _ClassVar[OrderPriceField]
    LADDER_LOW_PRICE: _ClassVar[OrderPriceField]
    LADDER_HIGH_PRICE: _ClassVar[OrderPriceField]
    TAKE_PROFIT_TRIGGER_PRICE: _ClassVar[OrderPriceField]
    TAKE_PROFIT_LIMIT_PRICE: _ClassVar[OrderPriceField]
    STOP_LOSS_TRIGGER_PRICE: _ClassVar[OrderPriceField]
    STOP_LOSS_LIMIT_PRICE: _ClassVar[OrderPriceField]
    TRAILING_STOP_ACTIVATION_PRICE: _ClassVar[OrderPriceField]
    TRAILING_STOP_LIMIT_PRICE: _ClassVar[OrderPriceField]

class PriceOffsetDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OFFSET_DIRECTION_UNSPECIFIED: _ClassVar[PriceOffsetDirection]
    ABOVE: _ClassVar[PriceOffsetDirection]
    BELOW: _ClassVar[PriceOffsetDirection]

class PriceRounding(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ROUNDING_UNSPECIFIED: _ClassVar[PriceRounding]
    DOWN: _ClassVar[PriceRounding]
    UP: _ClassVar[PriceRounding]

class UnfilledSlicePolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    UNFILLED_SLICE_UNSPECIFIED: _ClassVar[UnfilledSlicePolicy]
    CANCEL_BEFORE_NEXT: _ClassVar[UnfilledSlicePolicy]

class TriggerChangeAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRIGGER_CHANGE_UNSPECIFIED: _ClassVar[TriggerChangeAction]
    MODIFY: _ClassVar[TriggerChangeAction]
    PAUSE: _ClassVar[TriggerChangeAction]
    RESUME: _ClassVar[TriggerChangeAction]
ERROR_UNSPECIFIED: ErrorCode
CONVERSATION_NOT_FOUND: ErrorCode
RUN_NOT_FOUND: ErrorCode
APPROVAL_NOT_FOUND: ErrorCode
MEMORY_NOT_FOUND: ErrorCode
RUN_ACTIVE: ErrorCode
IDEMPOTENCY_CONFLICT: ErrorCode
APPROVAL_ALREADY_DECIDED: ErrorCode
APPROVAL_EXPIRED: ErrorCode
USAGE_LIMIT_REACHED: ErrorCode
SERVICE_UNAVAILABLE: ErrorCode
KEY_SETUP_NOT_FOUND: ErrorCode
KEY_SETUP_NOT_REGISTERED: ErrorCode
ROLE_UNSPECIFIED: MessageRole
USER: MessageRole
ASSISTANT: MessageRole
FAILURE_UNSPECIFIED: FailureCategory
CANCELLED: FailureCategory
BUDGET_EXCEEDED: FailureCategory
PERMISSION_DENIED: FailureCategory
MODEL_UNAVAILABLE: FailureCategory
UNEXPECTED_ERROR: FailureCategory
DECISION_UNSPECIFIED: ApprovalDecision
APPROVE: ApprovalDecision
REJECT: ApprovalDecision
APPROVAL_UNSPECIFIED: ApprovalStatus
PENDING: ApprovalStatus
APPROVED: ApprovalStatus
REJECTED: ApprovalStatus
EXPIRED: ApprovalStatus
KIND_UNSPECIFIED: MemoryKind
FACT: MemoryKind
PLANNING_FIGURE: MemoryKind
PROFILE: MemoryKind
KEY_STATE_UNSPECIFIED: AssistantKeyState
ACTIVE: AssistantKeyState
DISABLED: AssistantKeyState
PRICE_SOURCE_UNSPECIFIED: ReferencePriceSource
BEST_BID: ReferencePriceSource
BEST_ASK: ReferencePriceSource
LAST_PRICE: ReferencePriceSource
INDEX_PRICE: ReferencePriceSource
DIRECTION_UNSPECIFIED: TriggerDirection
AT_OR_ABOVE: TriggerDirection
AT_OR_BELOW: TriggerDirection
PRICE_FIELD_UNSPECIFIED: OrderPriceField
LIMIT_PRICE: OrderPriceField
TRIGGER_PRICE: OrderPriceField
ACTIVATION_PRICE: OrderPriceField
LADDER_LOW_PRICE: OrderPriceField
LADDER_HIGH_PRICE: OrderPriceField
TAKE_PROFIT_TRIGGER_PRICE: OrderPriceField
TAKE_PROFIT_LIMIT_PRICE: OrderPriceField
STOP_LOSS_TRIGGER_PRICE: OrderPriceField
STOP_LOSS_LIMIT_PRICE: OrderPriceField
TRAILING_STOP_ACTIVATION_PRICE: OrderPriceField
TRAILING_STOP_LIMIT_PRICE: OrderPriceField
OFFSET_DIRECTION_UNSPECIFIED: PriceOffsetDirection
ABOVE: PriceOffsetDirection
BELOW: PriceOffsetDirection
ROUNDING_UNSPECIFIED: PriceRounding
DOWN: PriceRounding
UP: PriceRounding
UNFILLED_SLICE_UNSPECIFIED: UnfilledSlicePolicy
CANCEL_BEFORE_NEXT: UnfilledSlicePolicy
TRIGGER_CHANGE_UNSPECIFIED: TriggerChangeAction
MODIFY: TriggerChangeAction
PAUSE: TriggerChangeAction
RESUME: TriggerChangeAction

class ErrorDetail(_message.Message):
    __slots__ = ("code",)
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: ErrorCode
    def __init__(self, code: _Optional[_Union[ErrorCode, str]] = ...) -> None: ...

class Conversation(_message.Message):
    __slots__ = ("conversation_id", "title", "created_at", "updated_at")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    conversation_id: int
    title: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, conversation_id: _Optional[int] = ..., title: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Message(_message.Message):
    __slots__ = ("message_id", "role", "text", "created_at", "run_id")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: int
    role: MessageRole
    text: str
    created_at: _timestamp_pb2.Timestamp
    run_id: int
    def __init__(self, message_id: _Optional[int] = ..., role: _Optional[_Union[MessageRole, str]] = ..., text: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., run_id: _Optional[int] = ...) -> None: ...

class Memory(_message.Message):
    __slots__ = ("memory_id", "text", "created_at", "conversation_id", "kind")
    MEMORY_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    memory_id: int
    text: str
    created_at: _timestamp_pb2.Timestamp
    conversation_id: int
    kind: MemoryKind
    def __init__(self, memory_id: _Optional[int] = ..., text: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., conversation_id: _Optional[int] = ..., kind: _Optional[_Union[MemoryKind, str]] = ...) -> None: ...

class Usage(_message.Message):
    __slots__ = ("input_tokens", "output_tokens", "cached_input_tokens")
    INPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    CACHED_INPUT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    def __init__(self, input_tokens: _Optional[int] = ..., output_tokens: _Optional[int] = ..., cached_input_tokens: _Optional[int] = ...) -> None: ...

class OrdersTable(_message.Message):
    __slots__ = ("orders", "truncated", "account_id")
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[_orders_read_pb2.Order]
    truncated: bool
    account_id: int
    def __init__(self, orders: _Optional[_Iterable[_Union[_orders_read_pb2.Order, _Mapping]]] = ..., truncated: _Optional[bool] = ..., account_id: _Optional[int] = ...) -> None: ...

class TriggersTable(_message.Message):
    __slots__ = ("triggers", "truncated", "account_id")
    TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    triggers: _containers.RepeatedCompositeFieldContainer[_triggers_pb2.Trigger]
    truncated: bool
    account_id: int
    def __init__(self, triggers: _Optional[_Iterable[_Union[_triggers_pb2.Trigger, _Mapping]]] = ..., truncated: _Optional[bool] = ..., account_id: _Optional[int] = ...) -> None: ...

class BalancesTable(_message.Message):
    __slots__ = ("balances", "account_id")
    BALANCES_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    balances: _containers.RepeatedCompositeFieldContainer[_ledger_read_pb2.AssetBalance]
    account_id: int
    def __init__(self, balances: _Optional[_Iterable[_Union[_ledger_read_pb2.AssetBalance, _Mapping]]] = ..., account_id: _Optional[int] = ...) -> None: ...

class PriceChart(_message.Message):
    __slots__ = ("symbol_id", "timeframe", "candles")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    TIMEFRAME_FIELD_NUMBER: _ClassVar[int]
    CANDLES_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    timeframe: _marketdata_pb2.Timeframe
    candles: _containers.RepeatedCompositeFieldContainer[_marketdata_pb2.Candle]
    def __init__(self, symbol_id: _Optional[int] = ..., timeframe: _Optional[_Union[_marketdata_pb2.Timeframe, str]] = ..., candles: _Optional[_Iterable[_Union[_marketdata_pb2.Candle, _Mapping]]] = ...) -> None: ...

class MarkdownTableRow(_message.Message):
    __slots__ = ("cells",)
    CELLS_FIELD_NUMBER: _ClassVar[int]
    cells: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, cells: _Optional[_Iterable[str]] = ...) -> None: ...

class MarkdownTable(_message.Message):
    __slots__ = ("columns", "rows", "truncated")
    COLUMNS_FIELD_NUMBER: _ClassVar[int]
    ROWS_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    columns: _containers.RepeatedScalarFieldContainer[str]
    rows: _containers.RepeatedCompositeFieldContainer[MarkdownTableRow]
    truncated: bool
    def __init__(self, columns: _Optional[_Iterable[str]] = ..., rows: _Optional[_Iterable[_Union[MarkdownTableRow, _Mapping]]] = ..., truncated: _Optional[bool] = ...) -> None: ...

class DepositAddressCard(_message.Message):
    __slots__ = ("deposit_address", "asset_id", "account_id")
    DEPOSIT_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    deposit_address: _deposit_pb2.DepositAddress
    asset_id: int
    account_id: int
    def __init__(self, deposit_address: _Optional[_Union[_deposit_pb2.DepositAddress, _Mapping]] = ..., asset_id: _Optional[int] = ..., account_id: _Optional[int] = ...) -> None: ...

class BalanceHistoryChart(_message.Message):
    __slots__ = ("history", "account_id")
    HISTORY_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    history: _ledger_read_pb2.GetBalanceHistoryResponse
    account_id: int
    def __init__(self, history: _Optional[_Union[_ledger_read_pb2.GetBalanceHistoryResponse, _Mapping]] = ..., account_id: _Optional[int] = ...) -> None: ...

class EquityHistoryChart(_message.Message):
    __slots__ = ("history", "account_id")
    HISTORY_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    history: _ledger_read_pb2.GetEquityHistorySeriesResponse
    account_id: int
    def __init__(self, history: _Optional[_Union[_ledger_read_pb2.GetEquityHistorySeriesResponse, _Mapping]] = ..., account_id: _Optional[int] = ...) -> None: ...

class TransfersTable(_message.Message):
    __slots__ = ("transfers", "truncated", "account_id")
    TRANSFERS_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    transfers: _containers.RepeatedCompositeFieldContainer[_ledger_read_pb2.TransferRow]
    truncated: bool
    account_id: int
    def __init__(self, transfers: _Optional[_Iterable[_Union[_ledger_read_pb2.TransferRow, _Mapping]]] = ..., truncated: _Optional[bool] = ..., account_id: _Optional[int] = ...) -> None: ...

class View(_message.Message):
    __slots__ = ("orders_table", "balances_table", "price_chart", "markdown_table", "price_alert", "triggers_table", "deposit_address", "balance_history_chart", "equity_history_chart", "transfers_table")
    ORDERS_TABLE_FIELD_NUMBER: _ClassVar[int]
    BALANCES_TABLE_FIELD_NUMBER: _ClassVar[int]
    PRICE_CHART_FIELD_NUMBER: _ClassVar[int]
    MARKDOWN_TABLE_FIELD_NUMBER: _ClassVar[int]
    PRICE_ALERT_FIELD_NUMBER: _ClassVar[int]
    TRIGGERS_TABLE_FIELD_NUMBER: _ClassVar[int]
    DEPOSIT_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    BALANCE_HISTORY_CHART_FIELD_NUMBER: _ClassVar[int]
    EQUITY_HISTORY_CHART_FIELD_NUMBER: _ClassVar[int]
    TRANSFERS_TABLE_FIELD_NUMBER: _ClassVar[int]
    orders_table: OrdersTable
    balances_table: BalancesTable
    price_chart: PriceChart
    markdown_table: MarkdownTable
    price_alert: _price_alerts_pb2.PriceAlert
    triggers_table: TriggersTable
    deposit_address: DepositAddressCard
    balance_history_chart: BalanceHistoryChart
    equity_history_chart: EquityHistoryChart
    transfers_table: TransfersTable
    def __init__(self, orders_table: _Optional[_Union[OrdersTable, _Mapping]] = ..., balances_table: _Optional[_Union[BalancesTable, _Mapping]] = ..., price_chart: _Optional[_Union[PriceChart, _Mapping]] = ..., markdown_table: _Optional[_Union[MarkdownTable, _Mapping]] = ..., price_alert: _Optional[_Union[_price_alerts_pb2.PriceAlert, _Mapping]] = ..., triggers_table: _Optional[_Union[TriggersTable, _Mapping]] = ..., deposit_address: _Optional[_Union[DepositAddressCard, _Mapping]] = ..., balance_history_chart: _Optional[_Union[BalanceHistoryChart, _Mapping]] = ..., equity_history_chart: _Optional[_Union[EquityHistoryChart, _Mapping]] = ..., transfers_table: _Optional[_Union[TransfersTable, _Mapping]] = ...) -> None: ...

class TextDelta(_message.Message):
    __slots__ = ("text",)
    TEXT_FIELD_NUMBER: _ClassVar[int]
    text: str
    def __init__(self, text: _Optional[str] = ...) -> None: ...

class DiscardPartial(_message.Message):
    __slots__ = ("from_seq",)
    FROM_SEQ_FIELD_NUMBER: _ClassVar[int]
    from_seq: int
    def __init__(self, from_seq: _Optional[int] = ...) -> None: ...

class ToolStarted(_message.Message):
    __slots__ = ("tool_call_id", "name", "input")
    TOOL_CALL_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    tool_call_id: str
    name: str
    input: _struct_pb2.Struct
    def __init__(self, tool_call_id: _Optional[str] = ..., name: _Optional[str] = ..., input: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class ToolFinished(_message.Message):
    __slots__ = ("tool_call_id", "name", "ok", "error_message")
    TOOL_CALL_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    OK_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    tool_call_id: str
    name: str
    ok: bool
    error_message: str
    def __init__(self, tool_call_id: _Optional[str] = ..., name: _Optional[str] = ..., ok: _Optional[bool] = ..., error_message: _Optional[str] = ...) -> None: ...

class RecalledMemory(_message.Message):
    __slots__ = ("memory_id", "text", "kind")
    MEMORY_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    KIND_FIELD_NUMBER: _ClassVar[int]
    memory_id: int
    text: str
    kind: MemoryKind
    def __init__(self, memory_id: _Optional[int] = ..., text: _Optional[str] = ..., kind: _Optional[_Union[MemoryKind, str]] = ...) -> None: ...

class MemoriesRecalled(_message.Message):
    __slots__ = ("tool_call_id", "memories")
    TOOL_CALL_ID_FIELD_NUMBER: _ClassVar[int]
    MEMORIES_FIELD_NUMBER: _ClassVar[int]
    tool_call_id: str
    memories: _containers.RepeatedCompositeFieldContainer[RecalledMemory]
    def __init__(self, tool_call_id: _Optional[str] = ..., memories: _Optional[_Iterable[_Union[RecalledMemory, _Mapping]]] = ...) -> None: ...

class DestinationsSuggested(_message.Message):
    __slots__ = ("tool_call_id", "destination_ids")
    TOOL_CALL_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_IDS_FIELD_NUMBER: _ClassVar[int]
    tool_call_id: str
    destination_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, tool_call_id: _Optional[str] = ..., destination_ids: _Optional[_Iterable[str]] = ...) -> None: ...

class SkillLoaded(_message.Message):
    __slots__ = ("name",)
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class SubagentStarted(_message.Message):
    __slots__ = ("subagent_id", "name")
    SUBAGENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    subagent_id: str
    name: str
    def __init__(self, subagent_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class SubagentFinished(_message.Message):
    __slots__ = ("subagent_id", "name", "ok", "summary")
    SUBAGENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    OK_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    subagent_id: str
    name: str
    ok: bool
    summary: str
    def __init__(self, subagent_id: _Optional[str] = ..., name: _Optional[str] = ..., ok: _Optional[bool] = ..., summary: _Optional[str] = ...) -> None: ...

class ApprovalParameter(_message.Message):
    __slots__ = ("label", "value")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    label: str
    value: str
    def __init__(self, label: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class ReferencePrice(_message.Message):
    __slots__ = ("price", "source", "observed_at")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    OBSERVED_AT_FIELD_NUMBER: _ClassVar[int]
    price: str
    source: ReferencePriceSource
    observed_at: _timestamp_pb2.Timestamp
    def __init__(self, price: _Optional[str] = ..., source: _Optional[_Union[ReferencePriceSource, str]] = ..., observed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class RelativePrice(_message.Message):
    __slots__ = ("field", "price", "direction", "offset_bps", "market", "limit_price", "rounding", "tick_size")
    FIELD_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    OFFSET_BPS_FIELD_NUMBER: _ClassVar[int]
    MARKET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    ROUNDING_FIELD_NUMBER: _ClassVar[int]
    TICK_SIZE_FIELD_NUMBER: _ClassVar[int]
    field: OrderPriceField
    price: str
    direction: PriceOffsetDirection
    offset_bps: int
    market: ReferencePrice
    limit_price: str
    rounding: PriceRounding
    tick_size: str
    def __init__(self, field: _Optional[_Union[OrderPriceField, str]] = ..., price: _Optional[str] = ..., direction: _Optional[_Union[PriceOffsetDirection, str]] = ..., offset_bps: _Optional[int] = ..., market: _Optional[_Union[ReferencePrice, _Mapping]] = ..., limit_price: _Optional[str] = ..., rounding: _Optional[_Union[PriceRounding, str]] = ..., tick_size: _Optional[str] = ...) -> None: ...

class AttachedExit(_message.Message):
    __slots__ = ("trigger_price", "limit_price")
    TRIGGER_PRICE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    trigger_price: str
    limit_price: str
    def __init__(self, trigger_price: _Optional[str] = ..., limit_price: _Optional[str] = ...) -> None: ...

class AttachedTrailingStop(_message.Message):
    __slots__ = ("distance", "distance_bps", "activation_price", "limit_price")
    DISTANCE_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    distance: str
    distance_bps: int
    activation_price: str
    limit_price: str
    def __init__(self, distance: _Optional[str] = ..., distance_bps: _Optional[int] = ..., activation_price: _Optional[str] = ..., limit_price: _Optional[str] = ...) -> None: ...

class AttachedExits(_message.Message):
    __slots__ = ("take_profit", "stop_loss", "trailing_stop", "oco")
    TAKE_PROFIT_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_FIELD_NUMBER: _ClassVar[int]
    OCO_FIELD_NUMBER: _ClassVar[int]
    take_profit: AttachedExit
    stop_loss: AttachedExit
    trailing_stop: AttachedTrailingStop
    oco: bool
    def __init__(self, take_profit: _Optional[_Union[AttachedExit, _Mapping]] = ..., stop_loss: _Optional[_Union[AttachedExit, _Mapping]] = ..., trailing_stop: _Optional[_Union[AttachedTrailingStop, _Mapping]] = ..., oco: _Optional[bool] = ...) -> None: ...

class MarketOrderPreview(_message.Message):
    __slots__ = ("max_slippage_bps", "attached")
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    ATTACHED_FIELD_NUMBER: _ClassVar[int]
    max_slippage_bps: int
    attached: AttachedExits
    def __init__(self, max_slippage_bps: _Optional[int] = ..., attached: _Optional[_Union[AttachedExits, _Mapping]] = ...) -> None: ...

class LimitOrderPreview(_message.Message):
    __slots__ = ("price", "time_in_force", "expire_at", "post_only", "attached")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    EXPIRE_AT_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    ATTACHED_FIELD_NUMBER: _ClassVar[int]
    price: str
    time_in_force: _orders_pb2.TimeInForce
    expire_at: _timestamp_pb2.Timestamp
    post_only: bool
    attached: AttachedExits
    def __init__(self, price: _Optional[str] = ..., time_in_force: _Optional[_Union[_orders_pb2.TimeInForce, str]] = ..., expire_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., post_only: _Optional[bool] = ..., attached: _Optional[_Union[AttachedExits, _Mapping]] = ...) -> None: ...

class StopOrderPreview(_message.Message):
    __slots__ = ("trigger_price", "trigger_price_source", "direction", "limit_price", "time_in_force", "post_only", "max_slippage_bps", "funds_reserved")
    TRIGGER_PRICE_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    FUNDS_RESERVED_FIELD_NUMBER: _ClassVar[int]
    trigger_price: str
    trigger_price_source: _orders_pb2.TriggerPriceSource
    direction: TriggerDirection
    limit_price: str
    time_in_force: _orders_pb2.TimeInForce
    post_only: bool
    max_slippage_bps: int
    funds_reserved: bool
    def __init__(self, trigger_price: _Optional[str] = ..., trigger_price_source: _Optional[_Union[_orders_pb2.TriggerPriceSource, str]] = ..., direction: _Optional[_Union[TriggerDirection, str]] = ..., limit_price: _Optional[str] = ..., time_in_force: _Optional[_Union[_orders_pb2.TimeInForce, str]] = ..., post_only: _Optional[bool] = ..., max_slippage_bps: _Optional[int] = ..., funds_reserved: _Optional[bool] = ...) -> None: ...

class TrailingStopPreview(_message.Message):
    __slots__ = ("distance", "distance_bps", "activation_price", "trigger_price_source", "limit_price", "max_slippage_bps", "funds_reserved")
    DISTANCE_FIELD_NUMBER: _ClassVar[int]
    DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_SOURCE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    FUNDS_RESERVED_FIELD_NUMBER: _ClassVar[int]
    distance: str
    distance_bps: int
    activation_price: str
    trigger_price_source: _orders_pb2.TriggerPriceSource
    limit_price: str
    max_slippage_bps: int
    funds_reserved: bool
    def __init__(self, distance: _Optional[str] = ..., distance_bps: _Optional[int] = ..., activation_price: _Optional[str] = ..., trigger_price_source: _Optional[_Union[_orders_pb2.TriggerPriceSource, str]] = ..., limit_price: _Optional[str] = ..., max_slippage_bps: _Optional[int] = ..., funds_reserved: _Optional[bool] = ...) -> None: ...

class TwapPreview(_message.Message):
    __slots__ = ("duration_ms", "slice_interval_ms", "slice_count", "slice_quantity", "limit_price", "max_slippage_bps", "unfilled_slice_policy", "first_slice_immediate")
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    SLICE_INTERVAL_MS_FIELD_NUMBER: _ClassVar[int]
    SLICE_COUNT_FIELD_NUMBER: _ClassVar[int]
    SLICE_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    UNFILLED_SLICE_POLICY_FIELD_NUMBER: _ClassVar[int]
    FIRST_SLICE_IMMEDIATE_FIELD_NUMBER: _ClassVar[int]
    duration_ms: int
    slice_interval_ms: int
    slice_count: int
    slice_quantity: str
    limit_price: str
    max_slippage_bps: int
    unfilled_slice_policy: UnfilledSlicePolicy
    first_slice_immediate: bool
    def __init__(self, duration_ms: _Optional[int] = ..., slice_interval_ms: _Optional[int] = ..., slice_count: _Optional[int] = ..., slice_quantity: _Optional[str] = ..., limit_price: _Optional[str] = ..., max_slippage_bps: _Optional[int] = ..., unfilled_slice_policy: _Optional[_Union[UnfilledSlicePolicy, str]] = ..., first_slice_immediate: _Optional[bool] = ...) -> None: ...

class LadderLevel(_message.Message):
    __slots__ = ("price", "quantity")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    price: str
    quantity: str
    def __init__(self, price: _Optional[str] = ..., quantity: _Optional[str] = ...) -> None: ...

class LadderPreview(_message.Message):
    __slots__ = ("low_price", "high_price", "levels", "post_only", "time_in_force", "all_levels_at_once")
    LOW_PRICE_FIELD_NUMBER: _ClassVar[int]
    HIGH_PRICE_FIELD_NUMBER: _ClassVar[int]
    LEVELS_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    ALL_LEVELS_AT_ONCE_FIELD_NUMBER: _ClassVar[int]
    low_price: str
    high_price: str
    levels: _containers.RepeatedCompositeFieldContainer[LadderLevel]
    post_only: bool
    time_in_force: _orders_pb2.TimeInForce
    all_levels_at_once: bool
    def __init__(self, low_price: _Optional[str] = ..., high_price: _Optional[str] = ..., levels: _Optional[_Iterable[_Union[LadderLevel, _Mapping]]] = ..., post_only: _Optional[bool] = ..., time_in_force: _Optional[_Union[_orders_pb2.TimeInForce, str]] = ..., all_levels_at_once: _Optional[bool] = ...) -> None: ...

class OrderPreview(_message.Message):
    __slots__ = ("symbol_id", "symbol", "base_asset", "quote_asset", "side", "quantity", "quote_amount", "estimated_value", "reserved_amount", "reference_price", "market", "limit", "stop_loss", "take_profit", "trailing_stop", "twap", "ladder", "relative_prices")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    BASE_ASSET_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    QUOTE_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    ESTIMATED_VALUE_FIELD_NUMBER: _ClassVar[int]
    RESERVED_AMOUNT_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_PRICE_FIELD_NUMBER: _ClassVar[int]
    MARKET_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    STOP_LOSS_FIELD_NUMBER: _ClassVar[int]
    TAKE_PROFIT_FIELD_NUMBER: _ClassVar[int]
    TRAILING_STOP_FIELD_NUMBER: _ClassVar[int]
    TWAP_FIELD_NUMBER: _ClassVar[int]
    LADDER_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_PRICES_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    symbol: str
    base_asset: str
    quote_asset: str
    side: _orders_pb2.Side
    quantity: str
    quote_amount: str
    estimated_value: str
    reserved_amount: str
    reference_price: ReferencePrice
    market: MarketOrderPreview
    limit: LimitOrderPreview
    stop_loss: StopOrderPreview
    take_profit: StopOrderPreview
    trailing_stop: TrailingStopPreview
    twap: TwapPreview
    ladder: LadderPreview
    relative_prices: _containers.RepeatedCompositeFieldContainer[RelativePrice]
    def __init__(self, symbol_id: _Optional[int] = ..., symbol: _Optional[str] = ..., base_asset: _Optional[str] = ..., quote_asset: _Optional[str] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., quantity: _Optional[str] = ..., quote_amount: _Optional[str] = ..., estimated_value: _Optional[str] = ..., reserved_amount: _Optional[str] = ..., reference_price: _Optional[_Union[ReferencePrice, _Mapping]] = ..., market: _Optional[_Union[MarketOrderPreview, _Mapping]] = ..., limit: _Optional[_Union[LimitOrderPreview, _Mapping]] = ..., stop_loss: _Optional[_Union[StopOrderPreview, _Mapping]] = ..., take_profit: _Optional[_Union[StopOrderPreview, _Mapping]] = ..., trailing_stop: _Optional[_Union[TrailingStopPreview, _Mapping]] = ..., twap: _Optional[_Union[TwapPreview, _Mapping]] = ..., ladder: _Optional[_Union[LadderPreview, _Mapping]] = ..., relative_prices: _Optional[_Iterable[_Union[RelativePrice, _Mapping]]] = ...) -> None: ...

class QuoteValue(_message.Message):
    __slots__ = ("quote_asset", "value")
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    quote_asset: str
    value: str
    def __init__(self, quote_asset: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class PlaceOrdersPreview(_message.Message):
    __slots__ = ("orders", "total_values")
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_VALUES_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[OrderPreview]
    total_values: _containers.RepeatedCompositeFieldContainer[QuoteValue]
    def __init__(self, orders: _Optional[_Iterable[_Union[OrderPreview, _Mapping]]] = ..., total_values: _Optional[_Iterable[_Union[QuoteValue, _Mapping]]] = ...) -> None: ...

class SwapLegPreview(_message.Message):
    __slots__ = ("symbol", "side", "average_price", "price_impact_bps", "taker_fee_rate_percent", "fee", "fee_asset")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_PRICE_FIELD_NUMBER: _ClassVar[int]
    PRICE_IMPACT_BPS_FIELD_NUMBER: _ClassVar[int]
    TAKER_FEE_RATE_PERCENT_FIELD_NUMBER: _ClassVar[int]
    FEE_FIELD_NUMBER: _ClassVar[int]
    FEE_ASSET_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    side: _orders_pb2.Side
    average_price: str
    price_impact_bps: int
    taker_fee_rate_percent: str
    fee: str
    fee_asset: str
    def __init__(self, symbol: _Optional[str] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., average_price: _Optional[str] = ..., price_impact_bps: _Optional[int] = ..., taker_fee_rate_percent: _Optional[str] = ..., fee: _Optional[str] = ..., fee_asset: _Optional[str] = ...) -> None: ...

class SwapPreview(_message.Message):
    __slots__ = ("source_asset", "destination_asset", "amount", "expected_amount_out", "min_amount_out", "max_slippage_bps", "legs", "quoted_at", "expires_at")
    SOURCE_ASSET_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ASSET_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_AMOUNT_OUT_FIELD_NUMBER: _ClassVar[int]
    MIN_AMOUNT_OUT_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    LEGS_FIELD_NUMBER: _ClassVar[int]
    QUOTED_AT_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    source_asset: str
    destination_asset: str
    amount: str
    expected_amount_out: str
    min_amount_out: str
    max_slippage_bps: int
    legs: _containers.RepeatedCompositeFieldContainer[SwapLegPreview]
    quoted_at: _timestamp_pb2.Timestamp
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, source_asset: _Optional[str] = ..., destination_asset: _Optional[str] = ..., amount: _Optional[str] = ..., expected_amount_out: _Optional[str] = ..., min_amount_out: _Optional[str] = ..., max_slippage_bps: _Optional[int] = ..., legs: _Optional[_Iterable[_Union[SwapLegPreview, _Mapping]]] = ..., quoted_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class OrderToCancel(_message.Message):
    __slots__ = ("order_id", "symbol", "side", "price", "quantity", "filled_quantity")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FILLED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    symbol: str
    side: _orders_pb2.Side
    price: str
    quantity: str
    filled_quantity: str
    def __init__(self, order_id: _Optional[int] = ..., symbol: _Optional[str] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ..., filled_quantity: _Optional[str] = ...) -> None: ...

class CancelOrdersPreview(_message.Message):
    __slots__ = ("orders", "cancel_all", "symbols", "side", "live_triggers_kept", "live_triggers_kept_lower_bound")
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ALL_FIELD_NUMBER: _ClassVar[int]
    SYMBOLS_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    LIVE_TRIGGERS_KEPT_FIELD_NUMBER: _ClassVar[int]
    LIVE_TRIGGERS_KEPT_LOWER_BOUND_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[OrderToCancel]
    cancel_all: bool
    symbols: _containers.RepeatedScalarFieldContainer[str]
    side: _orders_pb2.Side
    live_triggers_kept: int
    live_triggers_kept_lower_bound: bool
    def __init__(self, orders: _Optional[_Iterable[_Union[OrderToCancel, _Mapping]]] = ..., cancel_all: _Optional[bool] = ..., symbols: _Optional[_Iterable[str]] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., live_triggers_kept: _Optional[int] = ..., live_triggers_kept_lower_bound: _Optional[bool] = ...) -> None: ...

class CancelTriggerPreview(_message.Message):
    __slots__ = ("trigger_id", "symbol_id", "symbol", "type", "side", "quantity", "trigger_price", "filled_quantity", "slices_done", "slice_count", "levels_filled", "level_count", "cancels_open_orders")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_FIELD_NUMBER: _ClassVar[int]
    FILLED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SLICES_DONE_FIELD_NUMBER: _ClassVar[int]
    SLICE_COUNT_FIELD_NUMBER: _ClassVar[int]
    LEVELS_FILLED_FIELD_NUMBER: _ClassVar[int]
    LEVEL_COUNT_FIELD_NUMBER: _ClassVar[int]
    CANCELS_OPEN_ORDERS_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    symbol_id: int
    symbol: str
    type: _triggers_pb2.TriggerType
    side: _orders_pb2.Side
    quantity: str
    trigger_price: str
    filled_quantity: str
    slices_done: int
    slice_count: int
    levels_filled: int
    level_count: int
    cancels_open_orders: bool
    def __init__(self, trigger_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., symbol: _Optional[str] = ..., type: _Optional[_Union[_triggers_pb2.TriggerType, str]] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., quantity: _Optional[str] = ..., trigger_price: _Optional[str] = ..., filled_quantity: _Optional[str] = ..., slices_done: _Optional[int] = ..., slice_count: _Optional[int] = ..., levels_filled: _Optional[int] = ..., level_count: _Optional[int] = ..., cancels_open_orders: _Optional[bool] = ...) -> None: ...

class OrderChange(_message.Message):
    __slots__ = ("order_id", "side", "price", "new_price", "quantity", "new_quantity", "filled_quantity", "replaced")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    NEW_PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    NEW_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FILLED_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    REPLACED_FIELD_NUMBER: _ClassVar[int]
    order_id: int
    side: _orders_pb2.Side
    price: str
    new_price: str
    quantity: str
    new_quantity: str
    filled_quantity: str
    replaced: bool
    def __init__(self, order_id: _Optional[int] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., price: _Optional[str] = ..., new_price: _Optional[str] = ..., quantity: _Optional[str] = ..., new_quantity: _Optional[str] = ..., filled_quantity: _Optional[str] = ..., replaced: _Optional[bool] = ...) -> None: ...

class OrderChangePreview(_message.Message):
    __slots__ = ("symbol_id", "symbol", "base_asset", "quote_asset", "orders")
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    BASE_ASSET_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    symbol_id: int
    symbol: str
    base_asset: str
    quote_asset: str
    orders: _containers.RepeatedCompositeFieldContainer[OrderChange]
    def __init__(self, symbol_id: _Optional[int] = ..., symbol: _Optional[str] = ..., base_asset: _Optional[str] = ..., quote_asset: _Optional[str] = ..., orders: _Optional[_Iterable[_Union[OrderChange, _Mapping]]] = ...) -> None: ...

class TriggerSettings(_message.Message):
    __slots__ = ("status", "trigger_price", "trailing_distance_price", "trailing_distance_bps", "activation_price", "max_slippage_bps", "max_slippage_price", "limit_price")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_PRICE_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_PRICE_FIELD_NUMBER: _ClassVar[int]
    TRAILING_DISTANCE_BPS_FIELD_NUMBER: _ClassVar[int]
    ACTIVATION_PRICE_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_BPS_FIELD_NUMBER: _ClassVar[int]
    MAX_SLIPPAGE_PRICE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_PRICE_FIELD_NUMBER: _ClassVar[int]
    status: _triggers_pb2.TriggerStatus
    trigger_price: str
    trailing_distance_price: str
    trailing_distance_bps: int
    activation_price: str
    max_slippage_bps: int
    max_slippage_price: str
    limit_price: str
    def __init__(self, status: _Optional[_Union[_triggers_pb2.TriggerStatus, str]] = ..., trigger_price: _Optional[str] = ..., trailing_distance_price: _Optional[str] = ..., trailing_distance_bps: _Optional[int] = ..., activation_price: _Optional[str] = ..., max_slippage_bps: _Optional[int] = ..., max_slippage_price: _Optional[str] = ..., limit_price: _Optional[str] = ...) -> None: ...

class TriggerChangePreview(_message.Message):
    __slots__ = ("trigger_id", "symbol_id", "symbol", "base_asset", "quote_asset", "type", "side", "quantity", "action", "before", "after", "reference_price", "direction", "reserve_increase", "reserve_release", "fires_on_resume")
    TRIGGER_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_ID_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    BASE_ASSET_FIELD_NUMBER: _ClassVar[int]
    QUOTE_ASSET_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    BEFORE_FIELD_NUMBER: _ClassVar[int]
    AFTER_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_PRICE_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    RESERVE_INCREASE_FIELD_NUMBER: _ClassVar[int]
    RESERVE_RELEASE_FIELD_NUMBER: _ClassVar[int]
    FIRES_ON_RESUME_FIELD_NUMBER: _ClassVar[int]
    trigger_id: int
    symbol_id: int
    symbol: str
    base_asset: str
    quote_asset: str
    type: _triggers_pb2.TriggerType
    side: _orders_pb2.Side
    quantity: str
    action: TriggerChangeAction
    before: TriggerSettings
    after: TriggerSettings
    reference_price: ReferencePrice
    direction: TriggerDirection
    reserve_increase: str
    reserve_release: str
    fires_on_resume: bool
    def __init__(self, trigger_id: _Optional[int] = ..., symbol_id: _Optional[int] = ..., symbol: _Optional[str] = ..., base_asset: _Optional[str] = ..., quote_asset: _Optional[str] = ..., type: _Optional[_Union[_triggers_pb2.TriggerType, str]] = ..., side: _Optional[_Union[_orders_pb2.Side, str]] = ..., quantity: _Optional[str] = ..., action: _Optional[_Union[TriggerChangeAction, str]] = ..., before: _Optional[_Union[TriggerSettings, _Mapping]] = ..., after: _Optional[_Union[TriggerSettings, _Mapping]] = ..., reference_price: _Optional[_Union[ReferencePrice, _Mapping]] = ..., direction: _Optional[_Union[TriggerDirection, str]] = ..., reserve_increase: _Optional[str] = ..., reserve_release: _Optional[str] = ..., fires_on_resume: _Optional[bool] = ...) -> None: ...

class ApprovalRequested(_message.Message):
    __slots__ = ("approval_id", "summary", "expires_at", "parameters", "account_id", "order_preview", "cancel_orders", "order_change", "trigger_change", "place_orders", "swap", "cancel_trigger")
    APPROVAL_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_PREVIEW_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ORDERS_FIELD_NUMBER: _ClassVar[int]
    ORDER_CHANGE_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_CHANGE_FIELD_NUMBER: _ClassVar[int]
    PLACE_ORDERS_FIELD_NUMBER: _ClassVar[int]
    SWAP_FIELD_NUMBER: _ClassVar[int]
    CANCEL_TRIGGER_FIELD_NUMBER: _ClassVar[int]
    approval_id: int
    summary: str
    expires_at: _timestamp_pb2.Timestamp
    parameters: _containers.RepeatedCompositeFieldContainer[ApprovalParameter]
    account_id: int
    order_preview: OrderPreview
    cancel_orders: CancelOrdersPreview
    order_change: OrderChangePreview
    trigger_change: TriggerChangePreview
    place_orders: PlaceOrdersPreview
    swap: SwapPreview
    cancel_trigger: CancelTriggerPreview
    def __init__(self, approval_id: _Optional[int] = ..., summary: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., parameters: _Optional[_Iterable[_Union[ApprovalParameter, _Mapping]]] = ..., account_id: _Optional[int] = ..., order_preview: _Optional[_Union[OrderPreview, _Mapping]] = ..., cancel_orders: _Optional[_Union[CancelOrdersPreview, _Mapping]] = ..., order_change: _Optional[_Union[OrderChangePreview, _Mapping]] = ..., trigger_change: _Optional[_Union[TriggerChangePreview, _Mapping]] = ..., place_orders: _Optional[_Union[PlaceOrdersPreview, _Mapping]] = ..., swap: _Optional[_Union[SwapPreview, _Mapping]] = ..., cancel_trigger: _Optional[_Union[CancelTriggerPreview, _Mapping]] = ...) -> None: ...

class ApprovalResolved(_message.Message):
    __slots__ = ("approval_id", "status")
    APPROVAL_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    approval_id: int
    status: ApprovalStatus
    def __init__(self, approval_id: _Optional[int] = ..., status: _Optional[_Union[ApprovalStatus, str]] = ...) -> None: ...

class RunCompleted(_message.Message):
    __slots__ = ("usage",)
    USAGE_FIELD_NUMBER: _ClassVar[int]
    usage: Usage
    def __init__(self, usage: _Optional[_Union[Usage, _Mapping]] = ...) -> None: ...

class RunFailed(_message.Message):
    __slots__ = ("category", "message", "usage")
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    USAGE_FIELD_NUMBER: _ClassVar[int]
    category: FailureCategory
    message: str
    usage: Usage
    def __init__(self, category: _Optional[_Union[FailureCategory, str]] = ..., message: _Optional[str] = ..., usage: _Optional[_Union[Usage, _Mapping]] = ...) -> None: ...

class RunEvent(_message.Message):
    __slots__ = ("seq", "created_at", "text_delta", "discard_partial", "tool_started", "tool_finished", "skill_loaded", "subagent_started", "subagent_finished", "approval_requested", "approval_resolved", "view", "run_completed", "run_failed", "memories_recalled", "destinations_suggested")
    SEQ_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    TEXT_DELTA_FIELD_NUMBER: _ClassVar[int]
    DISCARD_PARTIAL_FIELD_NUMBER: _ClassVar[int]
    TOOL_STARTED_FIELD_NUMBER: _ClassVar[int]
    TOOL_FINISHED_FIELD_NUMBER: _ClassVar[int]
    SKILL_LOADED_FIELD_NUMBER: _ClassVar[int]
    SUBAGENT_STARTED_FIELD_NUMBER: _ClassVar[int]
    SUBAGENT_FINISHED_FIELD_NUMBER: _ClassVar[int]
    APPROVAL_REQUESTED_FIELD_NUMBER: _ClassVar[int]
    APPROVAL_RESOLVED_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    RUN_COMPLETED_FIELD_NUMBER: _ClassVar[int]
    RUN_FAILED_FIELD_NUMBER: _ClassVar[int]
    MEMORIES_RECALLED_FIELD_NUMBER: _ClassVar[int]
    DESTINATIONS_SUGGESTED_FIELD_NUMBER: _ClassVar[int]
    seq: int
    created_at: _timestamp_pb2.Timestamp
    text_delta: TextDelta
    discard_partial: DiscardPartial
    tool_started: ToolStarted
    tool_finished: ToolFinished
    skill_loaded: SkillLoaded
    subagent_started: SubagentStarted
    subagent_finished: SubagentFinished
    approval_requested: ApprovalRequested
    approval_resolved: ApprovalResolved
    view: View
    run_completed: RunCompleted
    run_failed: RunFailed
    memories_recalled: MemoriesRecalled
    destinations_suggested: DestinationsSuggested
    def __init__(self, seq: _Optional[int] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., text_delta: _Optional[_Union[TextDelta, _Mapping]] = ..., discard_partial: _Optional[_Union[DiscardPartial, _Mapping]] = ..., tool_started: _Optional[_Union[ToolStarted, _Mapping]] = ..., tool_finished: _Optional[_Union[ToolFinished, _Mapping]] = ..., skill_loaded: _Optional[_Union[SkillLoaded, _Mapping]] = ..., subagent_started: _Optional[_Union[SubagentStarted, _Mapping]] = ..., subagent_finished: _Optional[_Union[SubagentFinished, _Mapping]] = ..., approval_requested: _Optional[_Union[ApprovalRequested, _Mapping]] = ..., approval_resolved: _Optional[_Union[ApprovalResolved, _Mapping]] = ..., view: _Optional[_Union[View, _Mapping]] = ..., run_completed: _Optional[_Union[RunCompleted, _Mapping]] = ..., run_failed: _Optional[_Union[RunFailed, _Mapping]] = ..., memories_recalled: _Optional[_Union[MemoriesRecalled, _Mapping]] = ..., destinations_suggested: _Optional[_Union[DestinationsSuggested, _Mapping]] = ...) -> None: ...

class AssistantKey(_message.Message):
    __slots__ = ("subaccount_id", "key_id", "public_key_ed25519", "state")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_KEY_ED25519_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    key_id: str
    public_key_ed25519: bytes
    state: AssistantKeyState
    def __init__(self, subaccount_id: _Optional[int] = ..., key_id: _Optional[str] = ..., public_key_ed25519: _Optional[bytes] = ..., state: _Optional[_Union[AssistantKeyState, str]] = ...) -> None: ...

class AssistantKeyAccount(_message.Message):
    __slots__ = ("subaccount_id",)
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    def __init__(self, subaccount_id: _Optional[int] = ...) -> None: ...

class PreparedAssistantKey(_message.Message):
    __slots__ = ("subaccount_id", "public_key_ed25519", "registration_proof", "registration_deadline")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_KEY_ED25519_FIELD_NUMBER: _ClassVar[int]
    REGISTRATION_PROOF_FIELD_NUMBER: _ClassVar[int]
    REGISTRATION_DEADLINE_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    public_key_ed25519: bytes
    registration_proof: bytes
    registration_deadline: _timestamp_pb2.Timestamp
    def __init__(self, subaccount_id: _Optional[int] = ..., public_key_ed25519: _Optional[bytes] = ..., registration_proof: _Optional[bytes] = ..., registration_deadline: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Destination(_message.Message):
    __slots__ = ("id", "title", "description")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    description: str
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class SendMessageRequest(_message.Message):
    __slots__ = ("conversation_id", "text", "idempotency_key", "subaccount_id", "destinations")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATIONS_FIELD_NUMBER: _ClassVar[int]
    conversation_id: int
    text: str
    idempotency_key: str
    subaccount_id: int
    destinations: _containers.RepeatedCompositeFieldContainer[Destination]
    def __init__(self, conversation_id: _Optional[int] = ..., text: _Optional[str] = ..., idempotency_key: _Optional[str] = ..., subaccount_id: _Optional[int] = ..., destinations: _Optional[_Iterable[_Union[Destination, _Mapping]]] = ...) -> None: ...

class SendMessageResponse(_message.Message):
    __slots__ = ("run_id", "conversation_id")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: int
    conversation_id: int
    def __init__(self, run_id: _Optional[int] = ..., conversation_id: _Optional[int] = ...) -> None: ...

class WatchRunRequest(_message.Message):
    __slots__ = ("run_id", "after_seq")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    AFTER_SEQ_FIELD_NUMBER: _ClassVar[int]
    run_id: int
    after_seq: int
    def __init__(self, run_id: _Optional[int] = ..., after_seq: _Optional[int] = ...) -> None: ...

class WatchRunResponse(_message.Message):
    __slots__ = ("event",)
    EVENT_FIELD_NUMBER: _ClassVar[int]
    event: RunEvent
    def __init__(self, event: _Optional[_Union[RunEvent, _Mapping]] = ...) -> None: ...

class CancelRunRequest(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: int
    def __init__(self, run_id: _Optional[int] = ...) -> None: ...

class CancelRunResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DecideApprovalRequest(_message.Message):
    __slots__ = ("approval_id", "decision")
    APPROVAL_ID_FIELD_NUMBER: _ClassVar[int]
    DECISION_FIELD_NUMBER: _ClassVar[int]
    approval_id: int
    decision: ApprovalDecision
    def __init__(self, approval_id: _Optional[int] = ..., decision: _Optional[_Union[ApprovalDecision, str]] = ...) -> None: ...

class DecideApprovalResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: ApprovalStatus
    def __init__(self, status: _Optional[_Union[ApprovalStatus, str]] = ...) -> None: ...

class ListConversationsRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListConversationsResponse(_message.Message):
    __slots__ = ("conversations", "next_page_token")
    CONVERSATIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    conversations: _containers.RepeatedCompositeFieldContainer[Conversation]
    next_page_token: str
    def __init__(self, conversations: _Optional[_Iterable[_Union[Conversation, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListMessagesRequest(_message.Message):
    __slots__ = ("conversation_id", "limit", "page_token")
    CONVERSATION_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    conversation_id: int
    limit: int
    page_token: str
    def __init__(self, conversation_id: _Optional[int] = ..., limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListMessagesResponse(_message.Message):
    __slots__ = ("messages", "next_page_token")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[Message]
    next_page_token: str
    def __init__(self, messages: _Optional[_Iterable[_Union[Message, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListMemoriesRequest(_message.Message):
    __slots__ = ("limit", "page_token")
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    limit: int
    page_token: str
    def __init__(self, limit: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListMemoriesResponse(_message.Message):
    __slots__ = ("memories", "next_page_token")
    MEMORIES_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    memories: _containers.RepeatedCompositeFieldContainer[Memory]
    next_page_token: str
    def __init__(self, memories: _Optional[_Iterable[_Union[Memory, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class DeleteMemoryRequest(_message.Message):
    __slots__ = ("memory_id",)
    MEMORY_ID_FIELD_NUMBER: _ClassVar[int]
    memory_id: int
    def __init__(self, memory_id: _Optional[int] = ...) -> None: ...

class DeleteMemoryResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PrepareAssistantKeysRequest(_message.Message):
    __slots__ = ("accounts",)
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.RepeatedCompositeFieldContainer[AssistantKeyAccount]
    def __init__(self, accounts: _Optional[_Iterable[_Union[AssistantKeyAccount, _Mapping]]] = ...) -> None: ...

class PrepareAssistantKeysResponse(_message.Message):
    __slots__ = ("setup_id", "keys", "expires_at")
    SETUP_ID_FIELD_NUMBER: _ClassVar[int]
    KEYS_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    setup_id: int
    keys: _containers.RepeatedCompositeFieldContainer[PreparedAssistantKey]
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, setup_id: _Optional[int] = ..., keys: _Optional[_Iterable[_Union[PreparedAssistantKey, _Mapping]]] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CompleteAssistantKeysRequest(_message.Message):
    __slots__ = ("setup_id",)
    SETUP_ID_FIELD_NUMBER: _ClassVar[int]
    setup_id: int
    def __init__(self, setup_id: _Optional[int] = ...) -> None: ...

class CompleteAssistantKeysResponse(_message.Message):
    __slots__ = ("keys",)
    KEYS_FIELD_NUMBER: _ClassVar[int]
    keys: _containers.RepeatedCompositeFieldContainer[AssistantKey]
    def __init__(self, keys: _Optional[_Iterable[_Union[AssistantKey, _Mapping]]] = ...) -> None: ...

class ListAssistantKeysRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListAssistantKeysResponse(_message.Message):
    __slots__ = ("keys",)
    KEYS_FIELD_NUMBER: _ClassVar[int]
    keys: _containers.RepeatedCompositeFieldContainer[AssistantKey]
    def __init__(self, keys: _Optional[_Iterable[_Union[AssistantKey, _Mapping]]] = ...) -> None: ...

class TelegramApprovalLimits(_message.Message):
    __slots__ = ("per_approval_usd", "daily_usd")
    PER_APPROVAL_USD_FIELD_NUMBER: _ClassVar[int]
    DAILY_USD_FIELD_NUMBER: _ClassVar[int]
    per_approval_usd: str
    daily_usd: str
    def __init__(self, per_approval_usd: _Optional[str] = ..., daily_usd: _Optional[str] = ...) -> None: ...

class GetTelegramApprovalLimitsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetTelegramApprovalLimitsResponse(_message.Message):
    __slots__ = ("limits", "approved_last_24h_usd")
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    APPROVED_LAST_24H_USD_FIELD_NUMBER: _ClassVar[int]
    limits: TelegramApprovalLimits
    approved_last_24h_usd: str
    def __init__(self, limits: _Optional[_Union[TelegramApprovalLimits, _Mapping]] = ..., approved_last_24h_usd: _Optional[str] = ...) -> None: ...

class SetTelegramApprovalLimitsRequest(_message.Message):
    __slots__ = ("limits",)
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    limits: TelegramApprovalLimits
    def __init__(self, limits: _Optional[_Union[TelegramApprovalLimits, _Mapping]] = ...) -> None: ...

class SetTelegramApprovalLimitsResponse(_message.Message):
    __slots__ = ("limits",)
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    limits: TelegramApprovalLimits
    def __init__(self, limits: _Optional[_Union[TelegramApprovalLimits, _Mapping]] = ...) -> None: ...
