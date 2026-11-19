from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class DepthTier(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DEPTH_UNSPECIFIED: _ClassVar[DepthTier]
    DEPTH_1: _ClassVar[DepthTier]
    DEPTH_5: _ClassVar[DepthTier]
    DEPTH_10: _ClassVar[DepthTier]
    DEPTH_20: _ClassVar[DepthTier]
    DEPTH_50: _ClassVar[DepthTier]
    DEPTH_100: _ClassVar[DepthTier]
    DEPTH_200: _ClassVar[DepthTier]
    DEPTH_500: _ClassVar[DepthTier]
    DEPTH_1000: _ClassVar[DepthTier]
    DEPTH_5000: _ClassVar[DepthTier]
DEPTH_UNSPECIFIED: DepthTier
DEPTH_1: DepthTier
DEPTH_5: DepthTier
DEPTH_10: DepthTier
DEPTH_20: DepthTier
DEPTH_50: DepthTier
DEPTH_100: DepthTier
DEPTH_200: DepthTier
DEPTH_500: DepthTier
DEPTH_1000: DepthTier
DEPTH_5000: DepthTier
