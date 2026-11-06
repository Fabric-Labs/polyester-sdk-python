"""Contract catalog cases exercised through the public HTTP decode path."""

import base64
import json
from pathlib import Path

import pytest

from polyester import is_retryable_error, mutation_outcome_unknown
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from tests.unit.test_auth_error_codes import _rest_error

CATALOG = json.loads((Path(__file__).parents[1] / "fixtures/retry_contract.json").read_text())


@pytest.mark.parametrize(
    "case", CATALOG["bad_requests"], ids=lambda c: c["catalog"] + "/" + c["code"]
)
async def test_contract_bad_requests_are_definite_refusals(httpserver, case):
    error = await _rest_error(httpserver, 400, {"code": case["code"], "detail": "refused"})
    assert is_retryable_error(error) is case["retryable"]
    assert not mutation_outcome_unknown(error)


@pytest.mark.parametrize("shape", ["rest", "message", "detail", "hint"])
@pytest.mark.parametrize("case", CATALOG["resources"], ids=lambda c: c["code"])
async def test_contract_resource_codes(httpserver, case, shape):
    expected = "retry" in case["guidance"].lower() or case["code"] == "RATE_LIMIT_EXCEEDED"
    assert case["retryable"] is expected
    body = {"code": case["code"], "detail": "refused"}
    if shape != "rest":
        body = {"code": "resource_exhausted", "message": case["code"]}
    if shape in ("detail", "hint"):
        detail = orders_pb2.ErrorDetail(
            code=orders_pb2.ErrorCode.Value("ERROR_CODE_" + case["code"])
        )
        if shape == "hint":
            detail.rate_limit.retry_after_ms = 1250
        body["details"] = [
            {
                "type": "orders.v1.ErrorDetail",
                "value": base64.b64encode(detail.SerializeToString()).decode(),
            }
        ]
    error = await _rest_error(
        httpserver,
        case["status"],
        body,
        content_type="application/json",
        headers={"Retry-After": "1.25"},
    )
    assert is_retryable_error(error) is case["retryable"]
    assert not mutation_outcome_unknown(error)
    assert error.code == "ERROR_CODE_" + case["code"]
    if case["retryable"]:
        assert error.retry_after == 1.25


@pytest.mark.parametrize("case", CATALOG["unavailable"], ids=lambda c: c["code"])
@pytest.mark.parametrize("shape", ["rest", "message", "detail", "rest502"])
async def test_contract_unavailable_is_known_refusal(httpserver, case, shape):
    name = case["code"]
    body = {"code": name, "detail": "not admitted"}
    if shape == "message":
        body = {"code": "unavailable", "message": name, "details": []}
    if shape == "detail":
        detail = orders_pb2.ErrorDetail(code=orders_pb2.ErrorCode.Value("ERROR_CODE_" + name))
        body = {
            "code": "unavailable",
            "message": "not admitted",
            "details": [
                {
                    "type": "orders.v1.ErrorDetail",
                    "value": base64.b64encode(detail.SerializeToString()).decode(),
                }
            ],
        }
    error = await _rest_error(
        httpserver, 502 if shape == "rest502" else 503, body, content_type="application/json"
    )
    unknown = shape == "rest502" or (name == "UNAVAILABLE" and shape != "detail")
    assert is_retryable_error(error) is (case["retryable"] and not unknown)
    assert mutation_outcome_unknown(error) is unknown
    if not unknown:
        assert error.code == "ERROR_CODE_" + name


@pytest.mark.parametrize(
    "status,body", [(504, {"code": "deadline_exceeded"}), (503, {"code": "unavailable"}), (502, {})]
)
async def test_ambiguous_errors_never_retry(httpserver, status, body):
    error = await _rest_error(httpserver, status, body, content_type="application/json")
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize("operation", ["trigger", "wait", "snapshot"])
@pytest.mark.parametrize(
    "status,kind,body",
    [
        (502, "text/plain", ""),
        (503, "text/html", "<html>Unavailable</html>"),
        (504, "application/json", '{"code":"deadline_exceeded"}'),
        (503, "application/json", '{"code":"unavailable"}'),
    ],
)
async def test_ambiguous_read_recovery(httpserver, operation, status, kind, body):
    import asyncio

    from tests.unit.test_trigger_read_retry import GET_PATH, _service, _trigger_response
    from tests.unit.test_wait_batch_replace import (
        BATCH_ID,
        STATUS_PATH,
        _orders_service,
        _respond,
        _status,
        _working,
    )

    path = GET_PATH if operation == "trigger" else STATUS_PATH
    httpserver.expect_oneshot_request(path, method="POST").respond_with_data(
        body, status=status, content_type=kind
    )
    if operation == "trigger":
        httpserver.expect_oneshot_request(path, method="POST").respond_with_data(
            _trigger_response(), content_type="application/proto"
        )
        service, transport = _service(httpserver)
        try:
            await service.get(trigger_id="9")
        finally:
            await transport.aclose()
    else:
        _respond(httpserver, _status(_working(), accepted=1))
        service, transport = _orders_service(httpserver)
        try:
            if operation == "wait":
                await service.wait_batch_replace(batch_request_id=str(BATCH_ID))
            else:
                from polyester.realtime import AsyncRealtimeClient
                from polyester.realtime.snapshot_then_stream import (
                    AsyncSnapshotThenStreamSubscription,
                )

                realtime = AsyncRealtimeClient("ws://example.invalid")
                sub = AsyncSnapshotThenStreamSubscription(
                    realtime=realtime,
                    channel="public:test",
                    decode=lambda b: b,
                    fetch_snapshot=lambda: service.get_batch_replace_status(
                        batch_request_id=str(BATCH_ID)
                    ),
                    read_publication=lambda p: [p],
                    apply_snapshot=lambda s, p: None,
                    apply_live_publications=lambda p: None,
                )
                try:
                    sub.request_refresh()
                    async with asyncio.timeout(2):
                        while not sub.is_ready() and not sub.is_disposed():
                            await asyncio.sleep(0.001)
                    assert sub.is_ready()
                finally:
                    await sub.aclose()
                    await realtime.aclose()
        finally:
            await transport.aclose()
    assert len(httpserver.log) == 2


async def test_client_timeout_unknown_and_no_create_replay(httpserver):
    import time

    from werkzeug.wrappers import Response

    from polyester import AsyncPolyester, Quantity

    calls = []

    def stall(request):
        calls.append(request.path)
        time.sleep(0.2)
        return Response(b"", content_type="application/proto")

    path = "/orders.v1.OrdersService/CreateOrder"
    httpserver.expect_request(path, method="POST").respond_with_handler(stall)
    client = AsyncPolyester(
        api_url=httpserver.url_for("").rstrip("/"),
        api_key_id="ak_test",
        api_private_key="01" * 32,
        hydrate_catalogs=False,
        timeout=0.05,
    )
    client.catalogs.hydrate_spot_config(
        {"pairs": [{"symbol": "BTC-USDT", "symbol_id": 1, "base_quantity_scale": 8}]}
    )
    try:
        with pytest.raises(Exception) as caught:
            await client.orders.create(
                symbol="BTC-USDT",
                side="buy",
                order_type="market",
                qty=Quantity.from_scaled(1, scale=8),
            )
        assert mutation_outcome_unknown(caught.value)
        assert not is_retryable_error(caught.value)
        assert calls == [path]
    finally:
        await client.aclose()


async def test_connect_message_is_not_a_structured_admission_refusal(httpserver):
    error = await _rest_error(
        httpserver,
        503,
        {"code": "unavailable", "message": "UNAVAILABLE"},
        content_type="application/json",
    )
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)


async def test_unknown_outcome_takes_precedence_over_backoff(httpserver):
    from polyester.gen.polyester.ratelimit.v1 import types_pb2

    detail = orders_pb2.ErrorDetail(
        code=orders_pb2.ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN,
        rate_limit=types_pb2.RateLimitDetail(retry_after_ms=1250),
    )
    body = {
        "code": "unavailable",
        "message": "read back",
        "details": [
            {
                "type": "orders.v1.ErrorDetail",
                "value": base64.b64encode(detail.SerializeToString()).decode(),
            }
        ],
    }
    error = await _rest_error(httpserver, 503, body, content_type="application/json")
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)


@pytest.mark.parametrize("operation", ["trigger", "wait", "snapshot"])
async def test_client_timeout_read_recovery(operation):
    import asyncio
    import time

    from werkzeug.wrappers import Response

    from tests.hardening_support import ProbeFreeHTTPServer
    from tests.unit.test_trigger_read_retry import GET_PATH, _service, _trigger_response
    from tests.unit.test_wait_batch_replace import (
        BATCH_ID,
        STATUS_PATH,
        _orders_service,
        _respond,
        _status,
        _working,
    )

    server = ProbeFreeHTTPServer(host="127.0.0.1", threaded=True)
    server.start()
    path = GET_PATH if operation == "trigger" else STATUS_PATH

    def stall(_request):
        time.sleep(0.2)
        return Response(b"", content_type="application/proto")

    server.expect_oneshot_request(path, method="POST").respond_with_handler(stall)
    if operation == "trigger":
        server.expect_oneshot_request(path, method="POST").respond_with_data(
            _trigger_response(), content_type="application/proto"
        )
        service, transport = _service(server)
    else:
        _respond(server, _status(_working(), accepted=1))
        service, transport = _orders_service(server)
    from dataclasses import replace

    transport.config = replace(transport.config, timeout=0.05)
    try:
        if operation == "trigger":
            await service.get(trigger_id="9")
        elif operation == "wait":
            await service.wait_batch_replace(batch_request_id=str(BATCH_ID))
        else:
            from polyester.realtime import AsyncRealtimeClient
            from polyester.realtime.snapshot_then_stream import AsyncSnapshotThenStreamSubscription

            realtime = AsyncRealtimeClient("ws://example.invalid")
            sub = AsyncSnapshotThenStreamSubscription(
                realtime=realtime,
                channel="public:test",
                decode=lambda b: b,
                fetch_snapshot=lambda: service.get_batch_replace_status(
                    batch_request_id=str(BATCH_ID)
                ),
                read_publication=lambda p: [p],
                apply_snapshot=lambda s, p: None,
                apply_live_publications=lambda p: None,
            )
            try:
                sub.request_refresh()
                async with asyncio.timeout(2):
                    while not sub.is_ready() and not sub.is_disposed():
                        await asyncio.sleep(0.001)
                assert sub.is_ready()
            finally:
                await sub.aclose()
                await realtime.aclose()
        await asyncio.sleep(0.2)
        assert len(server.log) == 2
    finally:
        await transport.aclose()
        server.stop()


async def test_future_resource_code_is_not_blindly_retryable(httpserver):
    error = await _rest_error(
        httpserver,
        429,
        {"code": "resource_exhausted", "message": "FUTURE_PERMANENT_CAPACITY"},
        content_type="application/json",
    )
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)
    assert error.code == "FUTURE_PERMANENT_CAPACITY"


@pytest.mark.parametrize("code", ["FUTURE_CAPACITY", "TOO_MANY_REQUESTS", "RESOURCE_EXHAUSTED"])
async def test_future_rest_resource_code_is_known_refusal(httpserver, code):
    error = await _rest_error(httpserver, 429, {"code": code, "detail": "refused"})
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)
    assert error.code == code


@pytest.mark.parametrize("first", [True, False])
async def test_standalone_backoff_never_hides_unknown_outcome(httpserver, first):
    details = [
        {
            "type": "polyester.ratelimit.v1.RateLimitDetail",
            "value": base64.b64encode(
                ratelimit_pb2.RateLimitDetail(retry_after_ms=1250).SerializeToString()
            ).decode(),
        },
        {
            "type": "orders.v1.ErrorDetail",
            "value": base64.b64encode(
                orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_ORDER_CREATE_OUTCOME_UNKNOWN
                ).SerializeToString()
            ).decode(),
        },
    ]
    if not first:
        details.reverse()
    error = await _rest_error(
        httpserver,
        503,
        {"code": "unavailable", "message": "read back", "details": details},
        content_type="application/json",
    )
    assert not is_retryable_error(error)
    assert mutation_outcome_unknown(error)


async def test_code_only_unknown_precedes_standalone_backoff(httpserver):
    rate = ratelimit_pb2.RateLimitDetail(retry_after_ms=1250)
    error = await _rest_error(
        httpserver,
        503,
        {
            "code": "unavailable",
            "message": "ORDER_CREATE_OUTCOME_UNKNOWN",
            "details": [
                {
                    "type": "polyester.ratelimit.v1.RateLimitDetail",
                    "value": base64.b64encode(rate.SerializeToString()).decode(),
                }
            ],
        },
        content_type="application/json",
    )
    assert mutation_outcome_unknown(error)
    assert not is_retryable_error(error)
