from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class U128(_message.Message):
    __slots__ = ("hi", "lo")
    HI_FIELD_NUMBER: _ClassVar[int]
    LO_FIELD_NUMBER: _ClassVar[int]
    hi: int
    lo: int
    def __init__(self, hi: _Optional[int] = ..., lo: _Optional[int] = ...) -> None: ...

class TransferTradingToTradingRequest(_message.Message):
    __slots__ = ("request_id", "from_account_id", "to_account_id", "ledger", "amount_units")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TO_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LEDGER_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_UNITS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    from_account_id: int
    to_account_id: int
    ledger: int
    amount_units: U128
    def __init__(self, request_id: _Optional[str] = ..., from_account_id: _Optional[int] = ..., to_account_id: _Optional[int] = ..., ledger: _Optional[int] = ..., amount_units: _Optional[_Union[U128, _Mapping]] = ...) -> None: ...

class TransferTradingToTradingResponse(_message.Message):
    __slots__ = ("transfer_id", "timestamp")
    TRANSFER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    transfer_id: str
    timestamp: int
    def __init__(self, transfer_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class CreateFundingUserTransferRequest(_message.Message):
    __slots__ = ("intent_id", "from_account_id", "to_account_id", "ledger", "amount_units")
    INTENT_ID_FIELD_NUMBER: _ClassVar[int]
    FROM_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TO_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LEDGER_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_UNITS_FIELD_NUMBER: _ClassVar[int]
    intent_id: str
    from_account_id: int
    to_account_id: int
    ledger: int
    amount_units: U128
    def __init__(self, intent_id: _Optional[str] = ..., from_account_id: _Optional[int] = ..., to_account_id: _Optional[int] = ..., ledger: _Optional[int] = ..., amount_units: _Optional[_Union[U128, _Mapping]] = ...) -> None: ...

class CreateFundingUserTransferResponse(_message.Message):
    __slots__ = ("transfer_id", "timestamp")
    TRANSFER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    transfer_id: str
    timestamp: int
    def __init__(self, transfer_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class ReserveTradingWithdrawRequest(_message.Message):
    __slots__ = ("intent_id", "account_id", "ledger", "amount_units")
    INTENT_ID_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LEDGER_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_UNITS_FIELD_NUMBER: _ClassVar[int]
    intent_id: str
    account_id: int
    ledger: int
    amount_units: U128
    def __init__(self, intent_id: _Optional[str] = ..., account_id: _Optional[int] = ..., ledger: _Optional[int] = ..., amount_units: _Optional[_Union[U128, _Mapping]] = ...) -> None: ...

class ReserveTradingWithdrawResponse(_message.Message):
    __slots__ = ("transfer_id", "timestamp")
    TRANSFER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    transfer_id: str
    timestamp: int
    def __init__(self, transfer_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class ReleaseTradingWithdrawReserveRequest(_message.Message):
    __slots__ = ("intent_id", "account_id", "ledger", "close_scope")
    INTENT_ID_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    LEDGER_FIELD_NUMBER: _ClassVar[int]
    CLOSE_SCOPE_FIELD_NUMBER: _ClassVar[int]
    intent_id: str
    account_id: int
    ledger: int
    close_scope: str
    def __init__(self, intent_id: _Optional[str] = ..., account_id: _Optional[int] = ..., ledger: _Optional[int] = ..., close_scope: _Optional[str] = ...) -> None: ...

class ReleaseTradingWithdrawReserveResponse(_message.Message):
    __slots__ = ("transfer_id", "timestamp")
    TRANSFER_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    transfer_id: str
    timestamp: int
    def __init__(self, transfer_id: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...
