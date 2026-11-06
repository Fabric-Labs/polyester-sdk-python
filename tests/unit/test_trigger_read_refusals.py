"""Trigger reads return a definite REST refusal at once and retry real unavailability."""

from __future__ import annotations

import json

import pytest

from polyester import AsyncPolyester
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRateLimitError,
    PolyesterServerError,
)
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

READS = {
    "get": (
        "/triggers.v1.TriggersService/GetTrigger",
        lambda client: client.triggers.get(trigger_id="9"),
        triggers.GetTriggerResponse(trigger=triggers.Trigger(trigger_id=9)),
    ),
    "list": (
        "/triggers.v1.TriggersService/ListTriggers",
        lambda client: client.triggers.list(),
        triggers.ListTriggersResponse(),
    ),
    "list_events": (
        "/triggers.v1.TriggersService/ListTriggerEvents",
        lambda client: client.triggers.list_events(trigger_id="9"),
        triggers.ListTriggerEventsResponse(),
    ),
}


async def _read(name: str, status: int, body: object, fail_for: int) -> tuple[object, int]:
    """Answer ``fail_for`` requests with the failure, then succeed."""
    path, call, ok = READS[name]
    calls = 0

    async def handler(req: ParsedRequest) -> HttpScript:
        nonlocal calls
        if req.method != "POST" or req.path != path:
            return HttpScript.not_found()
        calls += 1
        if calls <= fail_for:
            return HttpScript.json(status, json.dumps(body).encode())
        return connect_proto_response(ok.SerializeToString())

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        try:
            return await call(client), calls
        except Exception as exc:  # noqa: BLE001 - the test asserts on the type
            return exc, calls
    finally:
        await client.aclose()
        await http.aclose()


@pytest.mark.parametrize("read", sorted(READS))
@pytest.mark.parametrize(
    ("status", "body", "expected", "code"),
    [
        (401, {"code": "IP_NOT_ALLOWED", "detail": "x"}, PolyesterAuthError, None),
        (403, {"code": "PERMISSION_DENIED", "detail": "x"}, PolyesterAuthError, None),
        (400, {"code": "BAD_PRICE", "detail": "x"}, PolyesterApiError, "ERROR_CODE_BAD_PRICE"),
        (
            429,
            {"code": "RATE_LIMIT_EXCEEDED", "detail": "x"},
            PolyesterRateLimitError,
            "ERROR_CODE_RATE_LIMIT_EXCEEDED",
        ),
        (
            503,
            {"code": "ACCOUNT_ROUTING_INVALID", "detail": "x"},
            PolyesterApiError,
            "ERROR_CODE_ACCOUNT_ROUTING_INVALID",
        ),
    ],
    ids=["401", "403", "400", "429", "503-routing"],
)
async def test_definite_refusal_makes_one_request(read, status, body, expected, code) -> None:
    error, calls = await _read(read, status, body, fail_for=1 << 30)
    assert calls == 1
    assert type(error) is expected
    if code is not None:
        assert error.code == code


@pytest.mark.parametrize("read", sorted(READS))
@pytest.mark.parametrize(
    ("status", "body"),
    [
        (503, {"code": "unavailable", "message": "catching up"}),
        (503, {"code": "UNAVAILABLE", "detail": "catching up"}),
        (502, {"code": "BAD_GATEWAY", "detail": "upstream"}),
        (504, {"code": "GATEWAY_TIMEOUT", "detail": "upstream"}),
    ],
    ids=["connect-503", "problem-503", "problem-502", "problem-504"],
)
async def test_real_unavailability_still_retries(read, status, body) -> None:
    result, calls = await _read(read, status, body, fail_for=2)
    assert not isinstance(result, Exception), result
    assert calls == 3


async def test_retry_of_real_unavailability_stays_bounded() -> None:
    error, calls = await _read(
        "get", 503, {"code": "UNAVAILABLE", "detail": "catching up"}, fail_for=1 << 30
    )
    assert type(error) is PolyesterServerError
    assert 2 <= calls <= 12
