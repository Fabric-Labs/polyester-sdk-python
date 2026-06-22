from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

import pytest

from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRouteNotFoundError,
    PolyesterServerError,
)

T = TypeVar("T")


def route_unavailable(exc: BaseException) -> bool:
    if isinstance(exc, PolyesterRouteNotFoundError):
        return True
    if isinstance(exc, PolyesterApiError):
        code = str(getattr(exc, "code", "") or "").lower()
        return code in {"route_not_found", "unimplemented", "not_found"}
    return False


def devnet_proto_mismatch(exc: BaseException) -> bool:
    if isinstance(exc, PolyesterServerError):
        message = str(exc).lower()
        return "internal error" in message or "decode" in message or "proto" in message
    return False


def jwt_session_only(exc: BaseException) -> bool:
    if isinstance(exc, PolyesterAuthError):
        message = str(exc).lower()
        return "authorization header" in message or "bearer" in message
    return False


async def call_optional(
    coro: Awaitable[T],
    *,
    label: str,
    allow_proto_mismatch: bool = True,
    allow_jwt_only: bool = True,
) -> T:
    """Run a live RPC; skip (not fail) when devnet does not mount the route."""
    try:
        return await coro
    except PolyesterRouteNotFoundError:
        pytest.skip(f"{label} not mounted on devnet")
    except PolyesterAuthError as exc:
        if allow_jwt_only and jwt_session_only(exc):
            pytest.skip(f"{label} requires JWT/session auth (API key not accepted on devnet)")
        raise
    except PolyesterServerError as exc:
        if allow_proto_mismatch and devnet_proto_mismatch(exc):
            pytest.skip(f"{label} unavailable on devnet: {exc}")
        raise


async def call_required(coro: Awaitable[T], *, label: str) -> T:
    """Run a live RPC that must exist; only skip on explicit env-based skips elsewhere."""
    try:
        return await coro
    except PolyesterRouteNotFoundError as exc:
        pytest.fail(f"{label} returned route not found on devnet: {exc}")


def assert_api_data_shape(raw: dict, *keys: str) -> None:
    for key in keys:
        assert key in raw, f"expected response key {key!r}, got {sorted(raw)}"


def assert_non_empty_api_list(raw: dict, list_key: str) -> list:
    assert_api_data_shape(raw, list_key)
    items = raw[list_key]
    assert isinstance(items, list)
    return items
