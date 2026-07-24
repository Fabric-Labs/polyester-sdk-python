from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class MFARequirement(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MFA_UNSPECIFIED: _ClassVar[MFARequirement]
    MFA_RECENT: _ClassVar[MFARequirement]
    MFA_FRESH_STEP_UP: _ClassVar[MFARequirement]
    MFA_CONDITIONAL: _ClassVar[MFARequirement]
MFA_UNSPECIFIED: MFARequirement
MFA_RECENT: MFARequirement
MFA_FRESH_STEP_UP: MFARequirement
MFA_CONDITIONAL: MFARequirement
PUBLIC_FIELD_NUMBER: _ClassVar[int]
public: _descriptor.FieldDescriptor
HIDDEN_FIELD_NUMBER: _ClassVar[int]
hidden: _descriptor.FieldDescriptor
MFA_REQUIREMENT_FIELD_NUMBER: _ClassVar[int]
mfa_requirement: _descriptor.FieldDescriptor
