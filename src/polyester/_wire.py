from __future__ import annotations

import re
from typing import Any

from connectrpc.errors import ConnectError
from google.protobuf.any_pb2 import Any as AnyMessage
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError, Message

from polyester._contract_codes import (
    future_code_label,
    has_future_code,
    is_placeholder_code,
    is_placeholder_detail,
)
from polyester.codecs.decode.ratelimit import (
    rate_limit_detail_from_proto,
    retry_after_seconds_from_detail,
)
from polyester.codecs.proto_helpers import error_code_name, format_uint64_id
from polyester.errors import (
    API_KEY_AUTH_ERROR_CODES,
    AUTH_SESSION_KIND_NOT_ALLOWED,
    AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED,
    AUTH_TIMESTAMP_SKEW,
    TIMESTAMP_SKEW,
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterNotImplementedError,
    PolyesterRateLimitError,
    PolyesterRouteNotFoundError,
    PolyesterServerError,
    PolyesterSessionRequiredError,
    PolyesterSubaccountOwnerRoleLockedError,
    PolyesterTimeoutError,
    PolyesterTimestampSkewError,
    PolyesterTransportError,
    _is_known_admission_refusal,
    auth_error_code_from_rest,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from polyester.models.trading import OrderFieldViolation
from polyester.transport import (
    AMBIGUOUS_CONNECT_CODES,
    ROUTE_NOT_FOUND_MESSAGES,
    GatewayProblemError,
)
from polyester.user_agent import cloudflare_1010_message, is_cloudflare_browser_ban

_EMPTY_ERROR_MESSAGE = "request failed without server error details"
_SERVER_FAILURE_CODES = AMBIGUOUS_CONNECT_CODES | {"internal", "unavailable", "deadline_exceeded"}
_SERVICE_ERROR_ENUMS = {
    "orders.v1.ErrorDetail": orders_pb2.ErrorCode,
    "chain.withdraw.v1.ErrorDetail": withdraw_pb2.ErrorCode,
    "transfer.v1.ErrorDetail": transfer_pb2.ErrorCode,
    "ledger.read.v1.ErrorDetail": ledger_read_pb2.ErrorCode,
}


def protobuf_to_public_dict(message: Message) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        always_print_fields_with_no_presence=True,
    )


_DETAIL_MESSAGES: tuple[type[Message], ...] = (
    auth_pb2.AuthErrorDetail,
    orders_pb2.ErrorDetail,
    withdraw_pb2.ErrorDetail,
    transfer_pb2.ErrorDetail,
    ledger_read_pb2.ErrorDetail,
    ratelimit_pb2.RateLimitDetail,
)


def _unpack_error_detail(detail: Message) -> Message | None:
    if isinstance(detail, AnyMessage) or detail.DESCRIPTOR.full_name == "google.protobuf.Any":
        for message_type in _DETAIL_MESSAGES:
            if detail.Is(message_type.DESCRIPTOR):
                unpacked = message_type()
                try:
                    detail.Unpack(unpacked)
                except DecodeError:
                    # Undecodable bytes prove nothing; the Connect code still stands.
                    return None
                return unpacked
        return None
    return detail


_FINAL_RESOURCE_CODES = frozenset(
    [
        "ERROR_CODE_ORDER_SEQUENCE_EXHAUSTED",
        "ERROR_CODE_TRIGGER_FIRE_LIMIT_REACHED",
        "ERROR_CODE_QUICKSWAP_CAPACITY_REACHED",
        "ERROR_CODE_ACCOUNT_RESERVATION_LIMIT_REACHED",
        "ERROR_CODE_TRIGGER_LIMIT_EXCEEDED",
    ]
)


_RETRYABLE_RESOURCE_CODES = frozenset(
    [
        "ERROR_CODE_OVERLOADED",
        "ERROR_CODE_SYSTEM_RATE_LIMITED",
        "ERROR_CODE_RATE_LIMIT_EXCEEDED",
        "ERROR_CODE_PRICE_LEVELS_EXHAUSTED",
        "ERROR_CODE_CLIENT_ORDER_IDS_EXHAUSTED",
        "ERROR_CODE_CLIENT_ORDER_ID_CAPACITY_REACHED",
        "ERROR_CODE_MARKET_LADDER_LIMIT_EXCEEDED",
        "ERROR_CODE_MARKET_TRIGGER_LIMIT_EXCEEDED",
        "ERROR_CODE_MARKET_TWAP_LIMIT_EXCEEDED",
        "ERROR_CODE_NEW_ACCOUNT_CAPACITY_REACHED",
        "ERROR_CODE_REQUEST_RECEIPTS_EXHAUSTED",
        "ERROR_CODE_RESERVATION_CAPACITY_REACHED",
        "ERROR_CODE_TRIGGER_CAPACITY_REACHED",
        "ERROR_CODE_TRIGGER_CONTROL_SHARE_EXHAUSTED",
        "ERROR_CODE_TWAP_CAPACITY_REACHED",
    ]
)


def _error_detail_priority(detail: Message) -> int:
    full_name = detail.DESCRIPTOR.full_name
    if full_name not in _SERVICE_ERROR_ENUMS:
        return 2
    code = error_code_name(_SERVICE_ERROR_ENUMS[full_name], detail.code)
    if code.endswith("_OUTCOME_UNKNOWN"):
        return 0
    if full_name == "orders.v1.ErrorDetail" and code in _FINAL_RESOURCE_CODES:
        return 1
    return 2


def _rate_limit_error(
    message: str, *, proto_detail=None, code: str | None = None
) -> PolyesterRateLimitError:
    detail = rate_limit_detail_from_proto(proto_detail)
    return PolyesterRateLimitError(
        message,
        retry_after=retry_after_seconds_from_detail(detail),
        detail=detail,
        code=code,
    )


def _order_error_code_from_rest(code: str) -> str:
    """``QTY_STEP_SIZE`` -> ``ERROR_CODE_QTY_STEP_SIZE``; unknown codes stay as sent."""
    prefixed = code if code.startswith("ERROR_CODE_") else f"ERROR_CODE_{code}"
    return prefixed if prefixed in orders_pb2.ErrorCode.DESCRIPTOR.values_by_name else code


def _rest_violations(items: list[dict[str, object]]) -> list[OrderFieldViolation]:
    return [
        OrderFieldViolation(
            field_path=str(item.get("fieldPath") or item.get("field_path") or ""),
            rule_id=str(item.get("ruleId") or item.get("rule_id") or ""),
            message=str(item.get("message") or ""),
        )
        for item in items
    ]


def _map_gateway_problem(exc: GatewayProblemError):
    """Map a REST problem body the gateway answered instead of a Connect error."""
    code = exc.code.value
    message = exc.detail or exc.problem_code
    if exc.problem_code.endswith("_OUTCOME_UNKNOWN"):
        # The business outcome takes precedence over the HTTP failure code.
        return PolyesterApiError(
            message,
            code=_order_error_code_from_rest(exc.problem_code),
            violations=_rest_violations(exc.violations),
        )
    order_code = _order_error_code_from_rest(exc.problem_code)
    if order_code in _RETRYABLE_RESOURCE_CODES:
        return PolyesterRateLimitError(message, retry_after=exc.retry_after, code=order_code)
    if exc.http_status == 429:
        return PolyesterApiError(message, code=order_code)
    if exc.http_status == 504:
        return PolyesterServerError(
            message or "Gateway Timeout", code=exc.problem_code or None, status_code=504
        )
    if code == "unimplemented" and exc.http_status == 501:
        return PolyesterNotImplementedError(message, code=order_code)
    if exc.problem_code == AUTH_SESSION_KIND_NOT_ALLOWED:
        return PolyesterSessionRequiredError(
            exc.detail or "interactive session required", status_code=exc.http_status
        )
    if code in ("unauthenticated", "permission_denied"):
        # The detail names what to fix, for example the API-key policy
        # action to grant ("api key policy does not allow READ_AUTO_WITHDRAW").
        return PolyesterAuthError(
            message,
            status_code=exc.http_status,
            code=auth_error_code_from_rest(exc.problem_code) or exc.problem_code or code,
        )
    if exc.http_status == 503 and order_code == "ERROR_CODE_ACCOUNT_ROUTING_INVALID":
        return PolyesterApiError(message, code=order_code)
    if code in ("unavailable", "internal"):
        return PolyesterServerError(
            message,
            code=_order_error_code_from_rest(exc.problem_code) or None,
            status_code=exc.http_status,
        )
    if code in ("resource_exhausted", "unknown"):
        return None
    return PolyesterApiError(
        message,
        code=_order_error_code_from_rest(exc.problem_code),
        violations=_rest_violations(exc.violations),
    )


def map_connect_error(exc: ConnectError):
    mapped = _map_connect_error(exc)
    if isinstance(mapped, PolyesterRateLimitError) and mapped.retry_after is None:
        mapped.retry_after = getattr(exc, "retry_after", None)
    if isinstance(exc, GatewayProblemError):
        mapped.problem = exc.problem
    return mapped


def _auth_status(exc: ConnectError) -> int | None:
    return {"unauthenticated": 401, "permission_denied": 403}.get(exc.code.value)


def _map_connect_error(exc: ConnectError):
    if (exc.message or "").strip() == TIMESTAMP_SKEW:
        return PolyesterTimestampSkewError(
            status_code=401 if exc.code.value == "unauthenticated" else None
        )
    if (exc.message or "").strip() == AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED:
        # A REST problem body (HTTP 412) the gateway answered instead of a
        # Connect error; see transport._raise_for_gateway_rejection.
        return PolyesterSubaccountOwnerRoleLockedError(
            status_code=412 if exc.code.value == "failed_precondition" else None
        )
    if isinstance(exc, GatewayProblemError):
        mapped = _map_gateway_problem(exc)
        if mapped is not None:
            return mapped
    error_message = exc.message or _EMPTY_ERROR_MESSAGE
    # A detail with no code says nothing about the outcome, but its field
    # violations still name what to fix on a recognised Connect code.
    placeholder_violations: list[OrderFieldViolation] = []
    future_code: str | None = None
    if exc.details:
        decoded_details = [
            d for detail in exc.details if (d := _unpack_error_detail(detail)) is not None
        ]
        # A code this SDK can't name stands only behind a recognised refusal.
        server_failure = exc.code.value in _SERVER_FAILURE_CODES
        unpacked_details = [
            d
            for d in decoded_details
            if not is_placeholder_detail(d) and not (server_failure and has_future_code(d))
        ]
        if server_failure:
            future_code = next(
                (future_code_label(d) for d in decoded_details if has_future_code(d)), None
            )
        placeholder_violations = [
            OrderFieldViolation(
                field_path=item.field_path, rule_id=item.rule_id, message=item.message
            )
            for d in decoded_details
            if is_placeholder_detail(d) and d.DESCRIPTOR.full_name == "orders.v1.ErrorDetail"
            for item in d.violations
        ]
        unpacked_details.sort(key=_error_detail_priority)
        if error_message.strip().endswith("_OUTCOME_UNKNOWN") and (
            not unpacked_details or _error_detail_priority(unpacked_details[0]) != 0
        ):
            return PolyesterApiError(
                error_message, code=_order_error_code_from_rest(error_message.strip())
            )
        for unpacked in unpacked_details:
            full_name = unpacked.DESCRIPTOR.full_name
            if full_name in _SERVICE_ERROR_ENUMS:
                code_name = error_code_name(_SERVICE_ERROR_ENUMS[full_name], unpacked.code)
                rate_limit = (
                    unpacked.rate_limit
                    if full_name == "orders.v1.ErrorDetail" and unpacked.HasField("rate_limit")
                    else None
                )
                # Preserve backoff hints and unknown mutation outcomes before
                # applying the transport's temporary-failure classification.
                if (
                    not code_name.endswith("_OUTCOME_UNKNOWN")
                    and code_name not in _FINAL_RESOURCE_CODES
                    and (rate_limit is not None or code_name in _RETRYABLE_RESOURCE_CODES)
                ):
                    return _rate_limit_error(error_message, proto_detail=rate_limit, code=code_name)
                if (
                    exc.code.value == "unavailable"
                    and not code_name.endswith("_OUTCOME_UNKNOWN")
                    and code_name != "ERROR_CODE_ACCOUNT_ROUTING_INVALID"
                    and code_name not in _FINAL_RESOURCE_CODES
                ):
                    return PolyesterServerError(
                        error_message, code=code_name, status_code=503, raw=unpacked
                    )
            if full_name == "auth.v1.AuthErrorDetail":
                code_name = error_code_name(auth_pb2.AuthErrorCode, unpacked.code)
                message = unpacked.message or error_message
                if code_name == AUTH_SUBACCOUNT_OWNER_ROLE_LOCKED:
                    return PolyesterSubaccountOwnerRoleLockedError(
                        message,
                        status_code=412 if exc.code.value == "failed_precondition" else None,
                        raw=unpacked,
                    )
                if code_name == AUTH_TIMESTAMP_SKEW:
                    # Same error as the gateway's TIMESTAMP_SKEW: re-sign and retry.
                    return PolyesterTimestampSkewError(
                        message,
                        status_code=401 if exc.code.value == "unauthenticated" else None,
                    )
                if code_name == AUTH_SESSION_KIND_NOT_ALLOWED:
                    return PolyesterSessionRequiredError(
                        message,
                        status_code=403 if exc.code.value == "permission_denied" else None,
                        raw=unpacked,
                    )
                if code_name in API_KEY_AUTH_ERROR_CODES:
                    return PolyesterAuthError(
                        message,
                        status_code=_auth_status(exc),
                        code=code_name,
                    )
                return PolyesterApiError(message, code=code_name, raw=unpacked)
            if full_name == "polyester.ratelimit.v1.RateLimitDetail":
                return _rate_limit_error(error_message, proto_detail=unpacked)
            if full_name == "orders.v1.ErrorDetail":
                code_name = error_code_name(orders_pb2.ErrorCode, unpacked.code)
                if (
                    "POLICY" in code_name
                    or "UNAUTHENTICATED" in code_name
                    or "PERMISSION" in code_name
                ):
                    return PolyesterAuthError(
                        error_message,
                        code=code_name,
                        status_code=403
                        if exc.code.value == "permission_denied"
                        else (401 if exc.code.value == "unauthenticated" else None),
                    )
                return PolyesterApiError(
                    error_message,
                    code=code_name,
                    raw=unpacked,
                    existing_order_id=(
                        format_uint64_id(unpacked.existing_order_id)
                        if unpacked.existing_order_id
                        else None
                    ),
                    violations=[
                        OrderFieldViolation(
                            field_path=item.field_path,
                            rule_id=item.rule_id,
                            message=item.message,
                        )
                        for item in unpacked.violations
                    ],
                )
            if full_name == "chain.withdraw.v1.ErrorDetail":
                code_name = error_code_name(withdraw_pb2.ErrorCode, unpacked.code)
                if (
                    "UNAUTHENTICATED" in code_name
                    or "PERMISSION" in code_name
                    or "API_KEY" in code_name
                    or "WALLET_BINDING" in code_name
                ):
                    return PolyesterAuthError(
                        error_message, code=code_name, status_code=_auth_status(exc)
                    )
                return PolyesterApiError(error_message, code=code_name)
            if full_name == "transfer.v1.ErrorDetail":
                code_name = error_code_name(transfer_pb2.ErrorCode, unpacked.code)
                if (
                    "UNAUTHENTICATED" in code_name
                    or "PERMISSION" in code_name
                    or "POLICY" in code_name
                ):
                    return PolyesterAuthError(
                        error_message, code=code_name, status_code=_auth_status(exc)
                    )
                return PolyesterApiError(error_message, code=code_name)
            if full_name == "ledger.read.v1.ErrorDetail":
                code_name = error_code_name(ledger_read_pb2.ErrorCode, unpacked.code)
                if "UNAUTHENTICATED" in code_name or "PERMISSION" in code_name:
                    return PolyesterAuthError(
                        error_message, code=code_name, status_code=_auth_status(exc)
                    )
                return PolyesterApiError(error_message, code=code_name)
    code = exc.code.value
    message_code = (exc.message or "").strip()
    if is_placeholder_code(message_code):
        message_code = ""
    if message_code.endswith("_OUTCOME_UNKNOWN"):
        return PolyesterApiError(error_message, code=_order_error_code_from_rest(message_code))
    order_code = _order_error_code_from_rest(message_code)
    if code == "unavailable" and order_code == "ERROR_CODE_ACCOUNT_ROUTING_INVALID":
        return PolyesterApiError(error_message, code=order_code)
    if code == "unavailable" and _is_known_admission_refusal(order_code):
        return PolyesterServerError(error_message, code=order_code, status_code=503)
    if code == "resource_exhausted":
        if order_code in _RETRYABLE_RESOURCE_CODES:
            return PolyesterRateLimitError(
                error_message, code=order_code, retry_after=getattr(exc, "retry_after", None)
            )
        if order_code in orders_pb2.ErrorCode.DESCRIPTOR.values_by_name or re.fullmatch(
            r"[A-Z][A-Z0-9_]*", message_code
        ):
            return PolyesterApiError(error_message, code=order_code)
    if is_cloudflare_browser_ban(error_message):
        return PolyesterTransportError(cloudflare_1010_message())
    if code in ("unauthenticated", "permission_denied"):
        return PolyesterAuthError(
            error_message,
            code=auth_error_code_from_rest((exc.message or "").strip()) or code,
            status_code=_auth_status(exc),
        )
    if code in ("unavailable", "internal"):
        return PolyesterServerError(error_message, code=future_code)
    if code == "resource_exhausted":
        # A structured detail supplies the delay first; response headers
        # provide its fallback in map_connect_error.
        order_code = _order_error_code_from_rest(message_code)
        service_code = (
            order_code if order_code in orders_pb2.ErrorCode.DESCRIPTOR.values_by_name else None
        )
        return PolyesterRateLimitError(error_message, code=service_code)
    if code == "deadline_exceeded":
        return PolyesterTimeoutError(error_message)
    message = (exc.message or "").strip().lower()
    if code == "unimplemented" and message in ROUTE_NOT_FOUND_MESSAGES:
        return PolyesterRouteNotFoundError()
    if code == "unimplemented":
        return PolyesterNotImplementedError(error_message)
    if code in AMBIGUOUS_CONNECT_CODES:
        return PolyesterServerError(error_message, code=future_code)
    return PolyesterApiError(error_message, code=code, violations=placeholder_violations)
