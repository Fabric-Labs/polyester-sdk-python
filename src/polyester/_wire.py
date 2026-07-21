from __future__ import annotations

from typing import Any

from connectrpc.errors import ConnectError
from google.protobuf.any_pb2 import Any as AnyMessage
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRouteNotFoundError,
    PolyesterServerError,
    PolyesterTransportError,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.orders.v1 import orders_pb2

_ROUTE_NOT_FOUND_MESSAGES = frozenset({"not found", "404 page not found", "404 not found"})


def protobuf_to_public_dict(message: Message) -> dict[str, Any]:
    return MessageToDict(
        message,
        preserving_proto_field_name=False,
        always_print_fields_with_no_presence=True,
    )


def _unpack_error_detail(detail: Message) -> Message | None:
    if isinstance(detail, AnyMessage) or detail.DESCRIPTOR.full_name == "google.protobuf.Any":
        if detail.Is(auth_pb2.AuthErrorDetail.DESCRIPTOR):
            auth_detail = auth_pb2.AuthErrorDetail()
            detail.Unpack(auth_detail)
            return auth_detail
        if detail.Is(orders_pb2.ErrorDetail.DESCRIPTOR):
            order_detail = orders_pb2.ErrorDetail()
            detail.Unpack(order_detail)
            return order_detail
        return None
    return detail


def map_connect_error(exc: ConnectError):
    if exc.details:
        for detail in exc.details:
            unpacked = _unpack_error_detail(detail)
            if unpacked is None:
                continue
            full_name = unpacked.DESCRIPTOR.full_name
            if full_name == "auth.v1.AuthErrorDetail":
                code_name = auth_pb2.AuthErrorCode.Name(unpacked.code)
                message = unpacked.message or exc.message
                return PolyesterApiError(message, code=code_name, raw=unpacked)
            if full_name.endswith("ErrorDetail") and hasattr(unpacked, "code"):
                code_name = orders_pb2.ErrorCode.Name(unpacked.code)
                if (
                    "POLICY" in code_name
                    or "UNAUTHENTICATED" in code_name
                    or "PERMISSION" in code_name
                ):
                    return PolyesterAuthError(exc.message)
                if code_name.startswith("ERROR_CODE_"):
                    return PolyesterApiError(exc.message, code=code_name)
    code = exc.code.value
    if code in ("unauthenticated", "permission_denied"):
        return PolyesterAuthError(exc.message)
    if code in ("unavailable", "internal"):
        return PolyesterServerError(exc.message)
    if code == "deadline_exceeded":
        return PolyesterTransportError(exc.message)
    message = (exc.message or "").strip().lower()
    if code == "unimplemented" and message in _ROUTE_NOT_FOUND_MESSAGES:
        return PolyesterRouteNotFoundError()
    return PolyesterApiError(exc.message, code=code)
