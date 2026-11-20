from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class AccountScopeType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SCOPE_UNSPECIFIED: _ClassVar[AccountScopeType]
    SCOPE_ROOT: _ClassVar[AccountScopeType]
    SCOPE_SUBACCOUNT: _ClassVar[AccountScopeType]
SCOPE_UNSPECIFIED: AccountScopeType
SCOPE_ROOT: AccountScopeType
SCOPE_SUBACCOUNT: AccountScopeType
