"""``orders.stop_all_trading`` cancels every live trigger before it cancels the
open orders (contract note 0320Z)."""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response

from polyester.auth import ApiKeyCredentials
from polyester.codecs.decode.triggers import trigger_status_from_label
from polyester.errors import PolyesterApiError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.orders import AsyncOrdersService
from polyester.services.triggers import AsyncTriggersService
from polyester.transport import TransportConfig, TransportFactory

LIST_PATH = "/triggers.v1.TriggersService/ListTriggers"
CANCEL_TRIGGER_PATH = "/triggers.v1.TriggersService/CancelTrigger"
CANCEL_ALL_PATH = "/orders.v1.OrdersService/CancelAllOrders"


def _proto(message) -> Response:
    return Response(message.SerializeToString(), content_type="application/proto")


class _Exchange:
    """Answers the three RPCs and records them in call order."""

    def __init__(self, *, ended: set[int] | None = None, failing: set[int] | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.ended = ended or set()
        self.failing = failing or set()

    def __call__(self, request: Request) -> Response:
        if request.path == LIST_PATH:
            req = triggers_pb2.ListTriggersRequest.FromString(request.get_data())
            self.calls.append(("list", (list(req.status), req.limit, req.page_token)))
            if not req.page_token:
                return _proto(
                    triggers_pb2.ListTriggersResponse(
                        triggers=[
                            triggers_pb2.Trigger(trigger_id=11, status=triggers_pb2.STATUS_ARMED),
                            triggers_pb2.Trigger(trigger_id=12, status=triggers_pb2.STATUS_PAUSED),
                        ],
                        next_page_token="page-2",
                    )
                )
            return _proto(
                triggers_pb2.ListTriggersResponse(
                    triggers=[
                        triggers_pb2.Trigger(trigger_id=13, status=triggers_pb2.STATUS_RUNNING)
                    ]
                )
            )
        if request.path == CANCEL_TRIGGER_PATH:
            req = triggers_pb2.CancelTriggerRequest.FromString(request.get_data())
            self.calls.append(("cancel_trigger", req.trigger_id))
            if req.trigger_id in self.ended or req.trigger_id in self.failing:
                detail_code = (
                    orders_pb2.ERROR_CODE_TRIGGER_NOT_FOUND
                    if req.trigger_id in self.ended
                    else orders_pb2.ERROR_CODE_TRIGGER_CONTROLS_BUSY
                )
                detail = orders_pb2.ErrorDetail(code=detail_code)
                body = {
                    "code": "failed_precondition",
                    "message": "refused",
                    "details": [
                        {
                            "type": "orders.v1.ErrorDetail",
                            "value": base64.b64encode(detail.SerializeToString())
                            .decode()
                            .rstrip("="),
                        }
                    ],
                }
                return Response(json.dumps(body), status=400, content_type="application/json")
            return _proto(
                triggers_pb2.CancelTriggerResponse(
                    trigger_id=req.trigger_id, status=triggers_pb2.STATUS_CANCELED
                )
            )
        if request.path == CANCEL_ALL_PATH:
            self.calls.append(("cancel_all", None))
            return _proto(
                orders_pb2.CancelAllOrdersResponse(
                    status=orders_pb2.CancelAllOrdersResponse.SUBMITTED,
                    matched_orders=2,
                    submitted_cancels=2,
                    total_cancelled=2,
                    ts_ns=1_700_000_000_000_000_000,
                )
            )
        return Response("unexpected", status=500)


def _services(httpserver: HTTPServer):
    private = Ed25519PrivateKey.generate()
    transport = TransportFactory(
        TransportConfig(api_url=httpserver.url_for("").rstrip("/")),
        credentials=ApiKeyCredentials(key_id="ak_test", private_key=private.private_bytes_raw()),
    )
    triggers = AsyncTriggersService(transport, None, None)  # type: ignore[arg-type]
    orders = AsyncOrdersService(transport, None, None, triggers=triggers)  # type: ignore[arg-type]
    return orders, transport


@pytest.mark.asyncio
async def test_cancels_every_live_trigger_then_all_orders(httpserver: HTTPServer) -> None:
    exchange = _Exchange()
    for path in (LIST_PATH, CANCEL_TRIGGER_PATH, CANCEL_ALL_PATH):
        httpserver.expect_request(path, method="POST").respond_with_handler(exchange)
    orders, transport = _services(httpserver)
    try:
        result = await orders.stop_all_trading()
    finally:
        await transport.aclose()

    live = [trigger_status_from_label(s) for s in ("created", "armed", "running", "paused")]
    assert exchange.calls == [
        ("list", (live, 1000, "")),
        ("list", (live, 1000, "page-2")),
        ("cancel_trigger", 11),
        ("cancel_trigger", 12),
        ("cancel_trigger", 13),
        ("cancel_all", None),
    ]
    assert len(result.canceled_trigger_ids) == 3
    assert result.ended_trigger_ids == []
    assert result.cancel_all is not None and result.cancel_all.total_cancelled == 2


@pytest.mark.asyncio
async def test_a_trigger_that_already_ended_does_not_stop_the_order_cancel(
    httpserver: HTTPServer,
) -> None:
    exchange = _Exchange(ended={12})
    for path in (LIST_PATH, CANCEL_TRIGGER_PATH, CANCEL_ALL_PATH):
        httpserver.expect_request(path, method="POST").respond_with_handler(exchange)
    orders, transport = _services(httpserver)
    try:
        result = await orders.stop_all_trading()
    finally:
        await transport.aclose()

    assert len(result.canceled_trigger_ids) == 2
    assert len(result.ended_trigger_ids) == 1
    assert exchange.calls[-1] == ("cancel_all", None)


@pytest.mark.asyncio
async def test_another_cancel_refusal_is_raised_before_the_order_cancel(
    httpserver: HTTPServer,
) -> None:
    exchange = _Exchange(failing={12})
    for path in (LIST_PATH, CANCEL_TRIGGER_PATH, CANCEL_ALL_PATH):
        httpserver.expect_request(path, method="POST").respond_with_handler(exchange)
    orders, transport = _services(httpserver)
    try:
        with pytest.raises(PolyesterApiError):
            await orders.stop_all_trading()
    finally:
        await transport.aclose()

    assert ("cancel_all", None) not in exchange.calls
