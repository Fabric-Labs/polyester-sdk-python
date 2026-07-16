from polyester.gen.buf.validate import validate_pb2 as _validate_pb2
from polyester.gen.gnostic.openapi.v3 import annotations_pb2 as _annotations_pb2
from polyester.gen.google.api import annotations_pb2 as _annotations_pb2_1
from polyester.gen.polyester.type.v1 import u128_pb2 as _u128_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InternalTransferStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    INTERNAL_TRANSFER_STATUS_UNSPECIFIED: _ClassVar[InternalTransferStatus]
    INTERNAL_TRANSFER_STATUS_ACCEPTED: _ClassVar[InternalTransferStatus]
    INTERNAL_TRANSFER_STATUS_REJECTED: _ClassVar[InternalTransferStatus]
    INTERNAL_TRANSFER_STATUS_FAILED: _ClassVar[InternalTransferStatus]
INTERNAL_TRANSFER_STATUS_UNSPECIFIED: InternalTransferStatus
INTERNAL_TRANSFER_STATUS_ACCEPTED: InternalTransferStatus
INTERNAL_TRANSFER_STATUS_REJECTED: InternalTransferStatus
INTERNAL_TRANSFER_STATUS_FAILED: InternalTransferStatus

class CreateInternalTransferRequest(_message.Message):
    __slots__ = ("subaccount_id", "destination_account_id", "destination_subaccount_id", "destination_smart_account_address", "asset_id", "amount_e18", "idempotency_key")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_SMART_ACCOUNT_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    destination_account_id: int
    destination_subaccount_id: int
    destination_smart_account_address: str
    asset_id: int
    amount_e18: _u128_pb2.U128
    idempotency_key: str
    def __init__(self, subaccount_id: _Optional[int] = ..., destination_account_id: _Optional[int] = ..., destination_subaccount_id: _Optional[int] = ..., destination_smart_account_address: _Optional[str] = ..., asset_id: _Optional[int] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class ResolvedDestination(_message.Message):
    __slots__ = ("root_account_public_id", "subaccount_public_id", "smart_account_address")
    ROOT_ACCOUNT_PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_PUBLIC_ID_FIELD_NUMBER: _ClassVar[int]
    SMART_ACCOUNT_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    root_account_public_id: str
    subaccount_public_id: str
    smart_account_address: str
    def __init__(self, root_account_public_id: _Optional[str] = ..., subaccount_public_id: _Optional[str] = ..., smart_account_address: _Optional[str] = ...) -> None: ...

class CreateInternalTransferResponse(_message.Message):
    __slots__ = ("request_id", "transfer_id", "accepted_at_ts_ns", "asset_id", "asset_code", "u_asset_id", "amount_e18", "destination", "status")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSFER_ID_FIELD_NUMBER: _ClassVar[int]
    ACCEPTED_AT_TS_NS_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    ASSET_CODE_FIELD_NUMBER: _ClassVar[int]
    U_ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_E18_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    transfer_id: str
    accepted_at_ts_ns: int
    asset_id: int
    asset_code: str
    u_asset_id: str
    amount_e18: _u128_pb2.U128
    destination: ResolvedDestination
    status: InternalTransferStatus
    def __init__(self, request_id: _Optional[str] = ..., transfer_id: _Optional[str] = ..., accepted_at_ts_ns: _Optional[int] = ..., asset_id: _Optional[int] = ..., asset_code: _Optional[str] = ..., u_asset_id: _Optional[str] = ..., amount_e18: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., destination: _Optional[_Union[ResolvedDestination, _Mapping]] = ..., status: _Optional[_Union[InternalTransferStatus, str]] = ...) -> None: ...
