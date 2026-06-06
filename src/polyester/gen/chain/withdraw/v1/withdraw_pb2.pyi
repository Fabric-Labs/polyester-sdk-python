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

class TradingWithdrawAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACTION_UNSPECIFIED: _ClassVar[TradingWithdrawAction]
    TO_FUNDING: _ClassVar[TradingWithdrawAction]
    TO_EXTERNAL_CHAIN: _ClassVar[TradingWithdrawAction]
ACTION_UNSPECIFIED: TradingWithdrawAction
TO_FUNDING: TradingWithdrawAction
TO_EXTERNAL_CHAIN: TradingWithdrawAction

class CreateTradingWithdrawResponse(_message.Message):
    __slots__ = ("intent_id",)
    INTENT_ID_FIELD_NUMBER: _ClassVar[int]
    intent_id: str
    def __init__(self, intent_id: _Optional[str] = ...) -> None: ...

class CreateWalletTradingWithdrawResponse(_message.Message):
    __slots__ = ("intent_id",)
    INTENT_ID_FIELD_NUMBER: _ClassVar[int]
    intent_id: str
    def __init__(self, intent_id: _Optional[str] = ...) -> None: ...

class TradingWithdrawIntentPayload(_message.Message):
    __slots__ = ("action", "asset_id", "destination_chain_id", "amount_q", "deadline_ts_sec", "nonce", "destination_address", "idempotency_key")
    ACTION_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CHAIN_ID_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_Q_FIELD_NUMBER: _ClassVar[int]
    DEADLINE_TS_SEC_FIELD_NUMBER: _ClassVar[int]
    NONCE_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_KEY_FIELD_NUMBER: _ClassVar[int]
    action: TradingWithdrawAction
    asset_id: int
    destination_chain_id: int
    amount_q: _u128_pb2.U128
    deadline_ts_sec: int
    nonce: _u128_pb2.U128
    destination_address: str
    idempotency_key: str
    def __init__(self, action: _Optional[_Union[TradingWithdrawAction, str]] = ..., asset_id: _Optional[int] = ..., destination_chain_id: _Optional[int] = ..., amount_q: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., deadline_ts_sec: _Optional[int] = ..., nonce: _Optional[_Union[_u128_pb2.U128, _Mapping]] = ..., destination_address: _Optional[str] = ..., idempotency_key: _Optional[str] = ...) -> None: ...

class CreateTradingWithdrawRequest(_message.Message):
    __slots__ = ("payload", "payload_signature")
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    payload: TradingWithdrawIntentPayload
    payload_signature: bytes
    def __init__(self, payload: _Optional[_Union[TradingWithdrawIntentPayload, _Mapping]] = ..., payload_signature: _Optional[bytes] = ...) -> None: ...

class CreateWalletTradingWithdrawRequest(_message.Message):
    __slots__ = ("payload", "subaccount_id", "signer_wallet", "payload_signature")
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SIGNER_WALLET_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    payload: TradingWithdrawIntentPayload
    subaccount_id: int
    signer_wallet: str
    payload_signature: bytes
    def __init__(self, payload: _Optional[_Union[TradingWithdrawIntentPayload, _Mapping]] = ..., subaccount_id: _Optional[int] = ..., signer_wallet: _Optional[str] = ..., payload_signature: _Optional[bytes] = ...) -> None: ...
