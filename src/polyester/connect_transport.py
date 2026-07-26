from __future__ import annotations

import json
from typing import Any, Literal

import httpx

from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRateLimitError,
    PolyesterRouteNotFoundError,
    PolyesterServerError,
    PolyesterValidationError,
)

WireFormat = Literal["binary", "json"]

CONNECT_PROTOCOL_VERSION = "1"
CONNECT_JSON_CONTENT_TYPE = "application/json"
CONNECT_PROTO_CONTENT_TYPE = "application/connect+proto"


def _retry_after_seconds(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def connect_content_type(wire_format: WireFormat) -> str:
    if wire_format == "json":
        return CONNECT_JSON_CONTENT_TYPE
    return CONNECT_PROTO_CONTENT_TYPE


def connect_headers(*, wire_format: WireFormat) -> dict[str, str]:
    return {
        "Content-Type": connect_content_type(wire_format),
        "Connect-Protocol-Version": CONNECT_PROTOCOL_VERSION,
    }


def encode_connect_body(request: dict[str, Any] | None, *, wire_format: WireFormat) -> bytes:
    if wire_format != "json":
        raise PolyesterValidationError(
            "Binary Connect/protobuf requests require generated clients under polyester._gen"
        )
    return json.dumps(request or {}, separators=(",", ":")).encode("utf-8")


def raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    message = response.text or "API error"
    if response.status_code in (401, 403):
        raise PolyesterAuthError(message)
    if response.status_code == 429:
        retry_after = response.headers.get("retry-after")
        raise PolyesterRateLimitError(
            message,
            retry_after=_retry_after_seconds(retry_after),
        )
    if response.status_code >= 500:
        raise PolyesterServerError(message)
    if response.status_code == 404:
        raise PolyesterRouteNotFoundError()
    raise PolyesterApiError(message, code=str(response.status_code))


def parse_connect_json_response(response: httpx.Response) -> Any:
    raise_for_status(response)
    if not response.content:
        return {}
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise PolyesterApiError(
            "Connect response was not valid JSON",
            raw=response.text,
        ) from exc
    if isinstance(payload, dict) and "code" in payload and "message" in payload:
        code = str(payload.get("code", ""))
        message = str(payload.get("message", "API error"))
        if code in ("unauthenticated", "permission_denied"):
            raise PolyesterAuthError(message)
        raise PolyesterApiError(message, code=code, raw=payload)
    return payload


def normalize_procedure(procedure: str) -> str:
    return procedure if procedure.startswith("/") else f"/{procedure}"
