from polyester.gen.polyester.type.v1 import u128_pb2 as _u128_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RequestFeeStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    REQUEST_FEE_STATUS_UNSPECIFIED: _ClassVar[RequestFeeStatus]
    REQUEST_FEE_STATUS_LOCKED: _ClassVar[RequestFeeStatus]
    REQUEST_FEE_STATUS_SETTLED: _ClassVar[RequestFeeStatus]

class FlowReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    FLOW_REASON_UNSPECIFIED: _ClassVar[FlowReason]
    FLOW_REASON_ZIPPER_VALIDATION_REJECTED: _ClassVar[FlowReason]
    FLOW_REASON_ZIPPER_EXECUTION_REJECTED: _ClassVar[FlowReason]
    FLOW_REASON_ZIPPER_WITHDRAW_EXECUTION_FAILED: _ClassVar[FlowReason]
    FLOW_REASON_ZIPPER_DEPOSIT_REFUND_FAILED: _ClassVar[FlowReason]
    FLOW_REASON_LEDGER_MIRROR_REJECTED: _ClassVar[FlowReason]
    FLOW_REASON_LEDGER_MIRROR_TRANSFER_EXCEEDS_CREDITS: _ClassVar[FlowReason]
    FLOW_REASON_LEDGER_MIRROR_TRANSFER_EXISTS: _ClassVar[FlowReason]
    FLOW_REASON_LEDGER_MIRROR_PENDING_TRANSFER_NOT_FOUND: _ClassVar[FlowReason]
    FLOW_REASON_LEDGER_MIRROR_TRANSFER_ID_ALREADY_FAILED: _ClassVar[FlowReason]

class FlowKind(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    KIND_UNSPECIFIED: _ClassVar[FlowKind]
    KIND_DEPOSIT: _ClassVar[FlowKind]
    KIND_WITHDRAW: _ClassVar[FlowKind]
    KIND_TRANSFER: _ClassVar[FlowKind]

class FlowDomain(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DOMAIN_UNSPECIFIED: _ClassVar[FlowDomain]
    DOMAIN_EXTERNAL_CHAIN: _ClassVar[FlowDomain]
    DOMAIN_ZIPPER: _ClassVar[FlowDomain]
    DOMAIN_FUNDING: _ClassVar[FlowDomain]
    DOMAIN_TRADING: _ClassVar[FlowDomain]
    DOMAIN_LENDING: _ClassVar[FlowDomain]

class LifecycleSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SOURCE_UNSPECIFIED: _ClassVar[LifecycleSource]
    SOURCE_RELAYER: _ClassVar[LifecycleSource]
    SOURCE_POLYESTER_CHAIN: _ClassVar[LifecycleSource]
    SOURCE_EXECUTOR: _ClassVar[LifecycleSource]
    SOURCE_LEDGER: _ClassVar[LifecycleSource]

class FlowState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATE_UNSPECIFIED: _ClassVar[FlowState]
    STATE_PENDING_SOURCE: _ClassVar[FlowState]
    STATE_PENDING_POLYESTER_CHAIN: _ClassVar[FlowState]
    STATE_PENDING_LEDGER: _ClassVar[FlowState]
    STATE_COMPLETED: _ClassVar[FlowState]
    STATE_FAILED: _ClassVar[FlowState]
    STATE_DROPPED: _ClassVar[FlowState]
    STATE_REFUNDED: _ClassVar[FlowState]
REQUEST_FEE_STATUS_UNSPECIFIED: RequestFeeStatus
REQUEST_FEE_STATUS_LOCKED: RequestFeeStatus
REQUEST_FEE_STATUS_SETTLED: RequestFeeStatus
FLOW_REASON_UNSPECIFIED: FlowReason
FLOW_REASON_ZIPPER_VALIDATION_REJECTED: FlowReason
FLOW_REASON_ZIPPER_EXECUTION_REJECTED: FlowReason
FLOW_REASON_ZIPPER_WITHDRAW_EXECUTION_FAILED: FlowReason
FLOW_REASON_ZIPPER_DEPOSIT_REFUND_FAILED: FlowReason
FLOW_REASON_LEDGER_MIRROR_REJECTED: FlowReason
FLOW_REASON_LEDGER_MIRROR_TRANSFER_EXCEEDS_CREDITS: FlowReason
FLOW_REASON_LEDGER_MIRROR_TRANSFER_EXISTS: FlowReason
FLOW_REASON_LEDGER_MIRROR_PENDING_TRANSFER_NOT_FOUND: FlowReason
FLOW_REASON_LEDGER_MIRROR_TRANSFER_ID_ALREADY_FAILED: FlowReason
KIND_UNSPECIFIED: FlowKind
KIND_DEPOSIT: FlowKind
KIND_WITHDRAW: FlowKind
KIND_TRANSFER: FlowKind
DOMAIN_UNSPECIFIED: FlowDomain
DOMAIN_EXTERNAL_CHAIN: FlowDomain
DOMAIN_ZIPPER: FlowDomain
DOMAIN_FUNDING: FlowDomain
DOMAIN_TRADING: FlowDomain
DOMAIN_LENDING: FlowDomain
SOURCE_UNSPECIFIED: LifecycleSource
SOURCE_RELAYER: LifecycleSource
SOURCE_POLYESTER_CHAIN: LifecycleSource
SOURCE_EXECUTOR: LifecycleSource
SOURCE_LEDGER: LifecycleSource
STATE_UNSPECIFIED: FlowState
STATE_PENDING_SOURCE: FlowState
STATE_PENDING_POLYESTER_CHAIN: FlowState
STATE_PENDING_LEDGER: FlowState
STATE_COMPLETED: FlowState
STATE_FAILED: FlowState
STATE_DROPPED: FlowState
STATE_REFUNDED: FlowState

class AssetIds(_message.Message):
    __slots__ = ("zipped_asset_id", "unified_asset_id")
    ZIPPED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    UNIFIED_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    zipped_asset_id: int
    unified_asset_id: int
    def __init__(self, zipped_asset_id: _Optional[int] = ..., unified_asset_id: _Optional[int] = ...) -> None: ...

class RequestFee(_message.Message):
    __slots__ = ("asset_ids", "amount_e18", "recipient_address", "status")
    ASSET_IDS_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    RECIPIENT_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    asset_ids: AssetIds
    amount_e18: _u128_pb2.U128
    recipient_address: str
    status: RequestFeeStatus
    def __init__(self, asset_ids: _Optional[_Union[AssetIds, _Mapping]] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., recipient_address: _Optional[str] = ..., status: _Optional[_Union[RequestFeeStatus, str]] = ...) -> None: ...
