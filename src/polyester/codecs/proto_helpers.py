from __future__ import annotations

from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from google.protobuf.message import Message

from polyester.codecs.scalars import format_id

_ENUM_PREFIXES = (
    "SIDE_",
    "ORDER_TYPE_",
    "ORDER_STATUS_",
    "TIF_",
    "FLOW_STEP_",
    "FLOW_KIND_",
    "KIND_",
    "MODIFY_ACTION_",
    "API_KEY_STATUS_",
)


def format_uint64_id(value: int) -> str:
    if value == 0:
        return "0"
    return format_id(value)


def u128_to_str(hi: int, lo: int) -> str:
    return str((int(hi) << 64) + int(lo))


def proto_enum_name(enum_type: EnumTypeWrapper, value: int) -> str:
    if value == 0:
        return ""
    try:
        name = enum_type.Name(value)
    except (ValueError, TypeError):
        return str(value)
    if isinstance(name, str):
        for prefix in _ENUM_PREFIXES:
            if name.startswith(prefix):
                return name[len(prefix) :].lower()
        return name.lower()
    return str(value)


def has_field(message: Message, field_name: str) -> bool:
    try:
        return message.HasField(field_name)
    except ValueError:
        return False
