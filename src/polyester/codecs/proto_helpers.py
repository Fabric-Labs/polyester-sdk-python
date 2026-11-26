from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from polyester.codecs.scalars import (
    aware_datetime,
    datetime_to_timestamp_dict,
    format_id,
    timestamp_parts_to_datetime,
)

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
    "TRIGGER_TYPE_",
    "TRIGGER_STATUS_",
    "TRIGGER_EVENT_TYPE_",
    "TRIGGER_CANCEL_REASON_",
    "TRIGGER_FAILURE_REASON_",
    "STATUS_",
    "EVENT_",
    "TIME_IN_FORCE_",
    "SELF_TRADE_PREVENTION_MODE_",
    "BALANCE_RANGE_",
    "PROTECTED_ACTION_",
    "SCOPE_",
    "ENTRY_KIND_",
    "DESTINATION_",
    "INTERNAL_WHITELIST_",
    "TRANSFER_COUNTERPARTY_",
    "SUBACCOUNT_STATUS_",
)


def format_uint64_id(value: int) -> str:
    if value == 0:
        return "0"
    return format_id(value)


def format_optional_uint64_id(value: int) -> str:
    """Public ID of ``value``, or "" for 0, the contract's "none"."""
    if value == 0:
        return ""
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


def error_code_name(enum_type: EnumTypeWrapper, value: int) -> str:
    """Name of a server error code, or ``UNKNOWN_ERROR_CODE(n)`` for a number
    this SDK's generated enum does not define yet."""
    try:
        return enum_type.Name(value)
    except (ValueError, TypeError):
        return f"UNKNOWN_ERROR_CODE({value})"


def has_field(message: Message, field_name: str) -> bool:
    try:
        return message.HasField(field_name)
    except ValueError:
        return False


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_RFC3339 = re.compile(
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})",
    re.IGNORECASE,
)


def _ceil_microseconds(nanos: int) -> int:
    """``nanos`` in microseconds, rounded up: a ``datetime`` holds
    microseconds, and rounding down would read an instant before the one
    sent."""
    return -(-nanos // 1000)


def optional_timestamp_ceil(message: Message, field_name: str) -> datetime | None:
    """The ``Timestamp`` field ``field_name`` as an aware UTC datetime rounded
    up to the microsecond, or ``None`` when the server left it unset.

    For a lower bound, such as the earliest acceptable start of a period: a
    time with sub-microsecond digits reads as the next microsecond, never one
    before it, so passing it back is accepted. Without such digits it is
    exact, as :func:`optional_timestamp` reads it. ``None`` too when no
    ``datetime`` represents it: rounded up, it is past the year 9999.
    """
    if not has_field(message, field_name):
        return None
    value = getattr(message, field_name)
    try:
        return _EPOCH + timedelta(
            seconds=int(value.seconds), microseconds=_ceil_microseconds(int(value.nanos))
        )
    except OverflowError:
        return None


def rfc3339_ceil(text: object) -> datetime | None:
    """An RFC 3339 time with up to nine fractional digits as an aware UTC
    datetime rounded up to the microsecond, as :func:`optional_timestamp_ceil`
    rounds; ``None`` for anything else, and for an instant no ``datetime``
    represents once in UTC and rounded up."""
    if not isinstance(text, str):
        return None
    match = _RFC3339.fullmatch(text.strip())
    if match is None:
        return None
    whole, fraction, offset = match.groups()
    offset = "+00:00" if offset.upper() == "Z" else offset
    try:
        base = datetime.fromisoformat(whole + offset)
    except ValueError:
        return None
    nanos = int((fraction or "").ljust(9, "0"))
    try:
        return base.astimezone(UTC) + timedelta(microseconds=_ceil_microseconds(nanos))
    except OverflowError:
        return None


def optional_timestamp(message: Message, field_name: str) -> datetime | None:
    """The ``Timestamp`` field ``field_name`` as an aware UTC datetime, or
    ``None`` when the server left it unset.

    Field presence decides: an unset field reads from the message as a
    default ``Timestamp``, the Unix epoch, so its value cannot tell unset
    from sent. A sent time, even the epoch itself, is kept. Integer
    arithmetic: the exact time to the microsecond.
    """
    if not has_field(message, field_name):
        return None
    value = getattr(message, field_name)
    result: datetime = value.ToDatetime(tzinfo=UTC)
    return result


def datetime_to_timestamp(value: object, field_name: str) -> Timestamp:
    """The protobuf ``Timestamp`` of a caller's time parameter ``field_name``.

    Every public time parameter is converted here: ``value`` must be a
    timezone-aware :class:`~datetime.datetime`, and anything else raises
    :class:`~polyester.errors.PolyesterValidationError` naming the parameter
    (see :func:`~polyester.codecs.scalars.aware_datetime`). Exact to the
    microsecond.
    """
    return Timestamp(**datetime_to_timestamp_dict(aware_datetime(value, field_name), field_name))


def optional_datetime_to_timestamp(value: object, field_name: str) -> Timestamp | None:
    """:func:`datetime_to_timestamp`, or ``None`` (not sent) for ``None``."""
    return None if value is None else datetime_to_timestamp(value, field_name)


def timestamp_to_ms(msg: Message | None) -> int:
    if msg is None:
        return 0
    seconds = int(getattr(msg, "seconds", 0) or 0)
    nanos = int(getattr(msg, "nanos", 0) or 0)
    if seconds == 0 and nanos == 0:
        return 0
    return seconds * 1000 + nanos // 1_000_000


def timestamp_to_datetime(msg: Message | None) -> datetime | None:
    """A proto ``Timestamp`` as an aware UTC datetime exact to the microsecond,
    or ``None`` when it is missing or zero."""
    if msg is None:
        return None
    seconds = int(getattr(msg, "seconds", 0) or 0)
    nanos = int(getattr(msg, "nanos", 0) or 0)
    if seconds == 0 and nanos == 0:
        return None
    return timestamp_parts_to_datetime(seconds, nanos)


def timestamp_to_rfc3339(msg: Message | None) -> str | None:
    """Encode a proto Timestamp as RFC3339 UTC, or None when unset/zero."""
    if msg is None:
        return None
    seconds = int(getattr(msg, "seconds", 0) or 0)
    nanos = int(getattr(msg, "nanos", 0) or 0)
    if seconds == 0 and nanos == 0:
        return None
    # isoformat, not strftime: RFC 3339's four-digit year on every platform
    # (glibc's %Y writes the year 1 as "1").
    text = timestamp_parts_to_datetime(seconds, nanos).replace(tzinfo=None, microsecond=0)
    if nanos == 0:
        return f"{text.isoformat()}Z"
    return f"{text.isoformat()}.{nanos:09d}Z"


def bytes_to_hex(value: bytes | None) -> str:
    if not value:
        return ""
    return f"0x{value.hex()}"
