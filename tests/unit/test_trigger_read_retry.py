"""Trigger reads resend the same request while the server answers unavailable."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pytest_httpserver import HTTPServer

from polyester import PolyesterApiError, PolyesterServerError
from polyester.auth import ApiKeyCredentials
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services import _retry
from polyester.services.triggers import AsyncTriggersService
from polyester.transport import TransportConfig, TransportFactory

GET_PATH = "/triggers.v1.TriggersService/GetTrigger"
LIST_PATH = "/triggers.v1.TriggersService/ListTriggers"
TRIGGER_ID = 1234567890123456789
CATCHING_UP = "Triggers are catching up with recent activity; retry the request."


def _service(httpserver: HTTPServer) -> tuple[AsyncTriggersService, TransportFactory]:
    private = Ed25519PrivateKey.generate()
    transport = TransportFactory(
        TransportConfig(api_url=httpserver.url_for("").rstrip("/")),
        credentials=ApiKeyCredentials(key_id="ak_test", private_key=private.private_bytes_raw()),
    )
    return AsyncTriggersService(transport, None, None), transport  # type: ignore[arg-type]


def _unavailable(httpserver: HTTPServer, path: str, *, rest: bool = False) -> None:
    if rest:
        # The REST problem shape a gateway may answer instead of a Connect error.
        httpserver.expect_oneshot_request(path, method="POST").respond_with_json(
            {"status": 503, "code": "UNAVAILABLE", "detail": CATCHING_UP},
            status=503,
            content_type="application/problem+json",
        )
        return
    httpserver.expect_oneshot_request(path, method="POST").respond_with_json(
        {"code": "unavailable", "message": CATCHING_UP}, status=503
    )


def _trigger_response() -> bytes:
    return triggers_pb2.GetTriggerResponse(
        trigger=triggers_pb2.Trigger(trigger_id=TRIGGER_ID, symbol_id=1)
    ).SerializeToString()


@pytest.mark.asyncio
@pytest.mark.parametrize("rest", [False, True], ids=["connect", "rest-problem"])
async def test_get_trigger_retries_unavailable_with_the_same_request(
    httpserver: HTTPServer, rest: bool
) -> None:
    _unavailable(httpserver, GET_PATH, rest=rest)
    _unavailable(httpserver, GET_PATH, rest=rest)
    httpserver.expect_oneshot_request(GET_PATH, method="POST").respond_with_data(
        _trigger_response(), content_type="application/proto"
    )
    triggers, transport = _service(httpserver)
    try:
        trigger = await triggers.get(trigger_id=str(TRIGGER_ID))
    finally:
        await transport.aclose()

    assert trigger is not None
    assert len(httpserver.log) == 3
    assert {request.data for request, _ in httpserver.log} == {
        triggers_pb2.GetTriggerRequest(trigger_id=TRIGGER_ID).SerializeToString()
    }


@pytest.mark.asyncio
async def test_list_triggers_retries_unavailable(httpserver: HTTPServer) -> None:
    _unavailable(httpserver, LIST_PATH)
    httpserver.expect_oneshot_request(LIST_PATH, method="POST").respond_with_data(
        triggers_pb2.ListTriggersResponse(
            triggers=[triggers_pb2.Trigger(trigger_id=TRIGGER_ID, symbol_id=1)]
        ).SerializeToString(),
        content_type="application/proto",
    )
    triggers, transport = _service(httpserver)
    try:
        listed = await triggers.list()
    finally:
        await transport.aclose()

    assert len(listed.triggers) == 1
    assert len(httpserver.log) == 2


@pytest.mark.asyncio
async def test_trigger_reads_give_up_after_about_two_seconds(
    httpserver: HTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = {"now": 0.0}
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        clock["now"] += delay

    monkeypatch.setattr(_retry, "_sleep", fake_sleep)
    monkeypatch.setattr(_retry, "_monotonic", lambda: clock["now"])
    httpserver.expect_request(GET_PATH, method="POST").respond_with_json(
        {"code": "unavailable", "message": CATCHING_UP}, status=503
    )
    triggers, transport = _service(httpserver)
    try:
        with pytest.raises(PolyesterServerError, match="catching up"):
            await triggers.get(trigger_id=str(TRIGGER_ID))
    finally:
        await transport.aclose()

    assert sleeps == [0.025, 0.05, 0.1, 0.2, 0.4, 0.5, 0.5]
    assert sum(sleeps) <= 2.0
    assert len(httpserver.log) == len(sleeps) + 1


@pytest.mark.asyncio
async def test_trigger_reads_do_not_retry_other_errors(httpserver: HTTPServer) -> None:
    httpserver.expect_request(GET_PATH, method="POST").respond_with_json(
        {"code": "not_found", "message": "trigger not found"}, status=404
    )
    triggers, transport = _service(httpserver)
    try:
        with pytest.raises(PolyesterApiError):
            await triggers.get(trigger_id=str(TRIGGER_ID))
    finally:
        await transport.aclose()

    assert len(httpserver.log) == 1


@pytest.mark.parametrize("rest", [False, True], ids=["connect", "rest-problem"])
async def test_trigger_events_retry_and_keep_request(httpserver: HTTPServer, rest: bool) -> None:
    path = "/triggers.v1.TriggersService/ListTriggerEvents"
    _unavailable(httpserver, path, rest=rest)
    _unavailable(httpserver, path, rest=rest)
    httpserver.expect_oneshot_request(path, method="POST").respond_with_data(
        triggers_pb2.ListTriggerEventsResponse().SerializeToString(),
        content_type="application/proto",
    )
    triggers, transport = _service(httpserver)
    try:
        result = await triggers.list_events(
            trigger_id=str(TRIGGER_ID), sub_account_id="12", limit=17,
            event_type="fired", page_token="next-page",
        )
    finally:
        await transport.aclose()
    assert result.events == []
    assert len(httpserver.log) == 3
    assert {request.data for request, _ in httpserver.log} == {
        triggers_pb2.ListTriggerEventsRequest(
            trigger_id=TRIGGER_ID, subaccount_id=12, limit=17,
            event_type=triggers_pb2.EVENT_FIRED, page_token="next-page",
        ).SerializeToString()
    }


async def test_trigger_events_not_found_matches_get(httpserver: HTTPServer) -> None:
    path = "/triggers.v1.TriggersService/ListTriggerEvents"
    for route in (GET_PATH, path):
        httpserver.expect_oneshot_request(route, method="POST").respond_with_json(
            {"code": "not_found", "message": "NOT_FOUND"}, status=404,
        )
    triggers, transport = _service(httpserver)
    try:
        with pytest.raises(PolyesterApiError) as get_error:
            await triggers.get(trigger_id=str(TRIGGER_ID))
        with pytest.raises(type(get_error.value)) as events_error:
            await triggers.list_events(trigger_id=str(TRIGGER_ID))
        assert events_error.value.code == get_error.value.code
    finally:
        await transport.aclose()
    assert len(httpserver.log) == 2
