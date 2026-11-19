from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RequestErrorCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CODE_UNSPECIFIED: _ClassVar[RequestErrorCode]
    REQUEST_TOO_LARGE: _ClassVar[RequestErrorCode]
CODE_UNSPECIFIED: RequestErrorCode
REQUEST_TOO_LARGE: RequestErrorCode

class RequestErrorDetail(_message.Message):
    __slots__ = ("code", "limit_bytes")
    CODE_FIELD_NUMBER: _ClassVar[int]
    LIMIT_BYTES_FIELD_NUMBER: _ClassVar[int]
    code: RequestErrorCode
    limit_bytes: int
    def __init__(self, code: _Optional[_Union[RequestErrorCode, str]] = ..., limit_bytes: _Optional[int] = ...) -> None: ...
