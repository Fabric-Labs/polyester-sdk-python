from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class AccountCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ACCOUNT_CODE_UNSPECIFIED: _ClassVar[AccountCode]
    FUNDING: _ClassVar[AccountCode]
    TRADING: _ClassVar[AccountCode]

class TransferCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRANSFER_CODE_UNSPECIFIED: _ClassVar[TransferCode]
    DEPOSIT: _ClassVar[TransferCode]
    WITHDRAW: _ClassVar[TransferCode]
    MAKER_FEE: _ClassVar[TransferCode]
    TAKER_FEE: _ClassVar[TransferCode]
    INTERNAL_TRANSFER: _ClassVar[TransferCode]
    TRADE_BASE: _ClassVar[TransferCode]
    TRADE_QUOTE: _ClassVar[TransferCode]
    REBATE: _ClassVar[TransferCode]
    FUNDING_TO_TRADING: _ClassVar[TransferCode]
    TRADING_TO_FUNDING: _ClassVar[TransferCode]
    TRADING_WITHDRAW_RESERVE: _ClassVar[TransferCode]
    FUNDING_USER_TRANSFER: _ClassVar[TransferCode]
    TRADING_WITHDRAW_REQUEST_FEE: _ClassVar[TransferCode]
    TRADING_WITHDRAW_FEE_LEG: _ClassVar[TransferCode]
    QUICKSWAP_POLYESTER_FEE: _ClassVar[TransferCode]
    QUICKSWAP_BROKER_FEE: _ClassVar[TransferCode]
    QUICKSWAP_AFFILIATE_FEE: _ClassVar[TransferCode]
    FEE_SWEEP: _ClassVar[TransferCode]
    FEE_REFILL: _ClassVar[TransferCode]
    SYSTEM_ADJUSTMENT: _ClassVar[TransferCode]
ACCOUNT_CODE_UNSPECIFIED: AccountCode
FUNDING: AccountCode
TRADING: AccountCode
TRANSFER_CODE_UNSPECIFIED: TransferCode
DEPOSIT: TransferCode
WITHDRAW: TransferCode
MAKER_FEE: TransferCode
TAKER_FEE: TransferCode
INTERNAL_TRANSFER: TransferCode
TRADE_BASE: TransferCode
TRADE_QUOTE: TransferCode
REBATE: TransferCode
FUNDING_TO_TRADING: TransferCode
TRADING_TO_FUNDING: TransferCode
TRADING_WITHDRAW_RESERVE: TransferCode
FUNDING_USER_TRANSFER: TransferCode
TRADING_WITHDRAW_REQUEST_FEE: TransferCode
TRADING_WITHDRAW_FEE_LEG: TransferCode
QUICKSWAP_POLYESTER_FEE: TransferCode
QUICKSWAP_BROKER_FEE: TransferCode
QUICKSWAP_AFFILIATE_FEE: TransferCode
FEE_SWEEP: TransferCode
FEE_REFILL: TransferCode
SYSTEM_ADJUSTMENT: TransferCode
