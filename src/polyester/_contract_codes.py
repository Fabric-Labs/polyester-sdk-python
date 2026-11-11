"""Which REST error codes the published contract defines."""

from __future__ import annotations

from google.protobuf.message import DecodeError, Message

from polyester.gen.alerts.v1 import price_alerts_pb2 as alerts_pb2
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2

_ENUM_CODES = frozenset(
    name
    for enum in (
        auth_pb2.AuthErrorCode,
        orders_pb2.ErrorCode,
        withdraw_pb2.ErrorCode,
        transfer_pb2.ErrorCode,
        ledger_read_pb2.ErrorCode,
    )
    for name in enum.DESCRIPTOR.values_by_name
)

# Contract REST codes that no generated error enum names.
_REST_ONLY_CODES = frozenset(
    {
        "API_KEY_ACTION_DENY",
        "API_KEY_POLICY_NOT_FOUND",
        "INVALID_BEFORE_TS_NS",
        "INVALID_DEPTH",
        "INVALID_END_TIME",
        "INVALID_LIMIT",
        "INVALID_OFFSET",
        "INVALID_ORDER_STATUS",
        "INVALID_PAGE_TOKEN",
        "INVALID_START_TIME",
        "INVALID_SYMBOL",
        "INVALID_TRIGGER_ID",
        "INVALID_TRIGGER_STATUS",
        "ORDER_ID_REQUIRED",
        "REQUEST_TOO_LARGE",
        "ROLE_ACTION_DENY",
        "ROLE_SPOT_TRADE_DENY",
        "SERVER_ERROR",
        "SUBACCOUNT_POLICY_DENY",
        "TRAILING_STOP_ORDER_TYPE_UNSUPPORTED",
        "TRIGGER_ID_REQUIRED",
    }
)


# An enum's zero value: "no code was provided", never a code of its own.
_PLACEHOLDER_CODES = frozenset({"UNSPECIFIED", "ERROR_CODE_UNSPECIFIED", "AUTH_UNSPECIFIED"})

_CODED_DETAILS: dict[str, type[Message]] = {
    "auth.v1.AuthErrorDetail": auth_pb2.AuthErrorDetail,
    "orders.v1.ErrorDetail": orders_pb2.ErrorDetail,
    "chain.withdraw.v1.ErrorDetail": withdraw_pb2.ErrorDetail,
    "transfer.v1.ErrorDetail": transfer_pb2.ErrorDetail,
    "ledger.read.v1.ErrorDetail": ledger_read_pb2.ErrorDetail,
    "alerts.v1.ErrorDetail": alerts_pb2.ErrorDetail,
    "polyester.ratelimit.v1.RateLimitDetail": ratelimit_pb2.RateLimitDetail,
}


def is_placeholder_code(code: object) -> bool:
    """Whether a code is an enum's zero value, which names nothing."""
    return isinstance(code, str) and code in _PLACEHOLDER_CODES


def is_placeholder_detail(detail: Message) -> bool:
    """Whether a decoded service detail says nothing: no code and no backoff."""
    name = detail.DESCRIPTOR.full_name
    if name not in _CODED_DETAILS:
        return False
    if name == "polyester.ratelimit.v1.RateLimitDetail":
        return detail.ByteSize() == 0
    if name == "orders.v1.ErrorDetail" and detail.rate_limit.ByteSize() > 0:
        return False
    return detail.code == 0


def has_future_code(detail: Message) -> bool:
    """Whether a decoded service detail has a code this SDK's enum can't name.

    Its type shows that a service sent it, not what the code means: it could be
    a future refusal or a future unknown outcome.
    """
    field = detail.DESCRIPTOR.fields_by_name.get("code")
    if detail.DESCRIPTOR.full_name not in _CODED_DETAILS or field is None:
        return False
    return detail.code != 0 and detail.code not in field.enum_type.values_by_number


def future_code_label(detail: Message) -> str:
    """The label a code from :func:`has_future_code` is reported under."""
    return f"UNKNOWN_ERROR_CODE({detail.code})"


def decode_coded_detail(detail_type: str, value: bytes) -> Message | None:
    """An encoded service detail, or ``None`` for another type or bad bytes."""
    message_type = _CODED_DETAILS.get(detail_type)
    if message_type is None:
        return None
    detail = message_type()
    try:
        detail.ParseFromString(value)
    except DecodeError:
        return None
    return detail


def carries_contract_code(detail_type: str, value: bytes) -> bool:
    """Whether an encoded detail is a service detail with a code this SDK can name."""
    detail = decode_coded_detail(detail_type, value)
    if detail is None:
        return False
    return not is_placeholder_detail(detail) and not has_future_code(detail)


def is_recognised_rest_code(code: str) -> bool:
    """Whether the contract defines this REST problem ``code``.

    A mutation's unknown outcome is recognised by its suffix, including one
    added to the contract after this SDK was generated.
    """
    if code in _PLACEHOLDER_CODES:
        return False
    return (
        code in _REST_ONLY_CODES
        or code in _ENUM_CODES
        or f"ERROR_CODE_{code}" in _ENUM_CODES
        or f"AUTH_{code}" in _ENUM_CODES
        or code.endswith("_OUTCOME_UNKNOWN")
    )
