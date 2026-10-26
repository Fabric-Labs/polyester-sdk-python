from __future__ import annotations

from typing import Any

from google.protobuf.json_format import ParseDict, ParseError
from google.protobuf.message import Message

from polyester.errors import PolyesterValidationError


def message_from_mapping(
    proto_cls: type[Message],
    value: dict[str, Any] | Message | None,
) -> Message:
    if value is None:
        return proto_cls()
    if isinstance(value, Message):
        return value
    msg = proto_cls()
    try:
        ParseDict(value, msg, ignore_unknown_fields=True)
    except ParseError as exc:
        # Out-of-range integers and wrong field types are caller input errors.
        raise PolyesterValidationError(f"invalid {proto_cls.DESCRIPTOR.name}: {exc}") from exc
    return msg


def repeated_messages_from_mappings(
    proto_cls: type[Message],
    values: list[dict[str, Any] | Message] | None,
) -> list[Message]:
    if not values:
        return []
    return [message_from_mapping(proto_cls, item) for item in values]
