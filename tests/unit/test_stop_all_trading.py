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
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterResponseContractError,
)
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


def _refusal(code: str, status: int) -> Response:
    return Response(
        json.dumps({"code": code, "message": "refused"}),
        status=status,
        content_type="application/json",
    )


class _Exchange:
    """Answers the three RPCs and records them in call order."""

    def __init__(
        self,
        *,
        ended: set[int] | None = None,
        failing: set[int] | None = None,
        list_refused: bool = False,
        repeat_token: bool = False,
        cancel_all_refused: bool = False,
        tokens: list[str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, object]] = []
        self.ended = ended or set()
        self.failing = failing or set()
        self.list_refused = list_refused
        self.repeat_token = repeat_token
        self.cancel_all_refused = cancel_all_refused
        # When set, the next page token of each successive listing; the
        # fixture refuses a twelfth listing so a missed cycle cannot hang.
        self.tokens = tokens

    def __call__(self, request: Request) -> Response:
        if request.path == LIST_PATH:
            req = triggers_pb2.ListTriggersRequest.FromString(request.get_data())
            self.calls.append(("list", (list(req.status), req.limit, req.page_token)))
            if self.list_refused:
                return _refusal("permission_denied", 403)
            if self.tokens is not None:
                listed = sum(1 for call in self.calls if call[0] == "list")
                if listed > 11:
                    return _refusal("aborted", 409)
                token = self.tokens[listed - 1] if listed <= len(self.tokens) else ""
                return _proto(
                    triggers_pb2.ListTriggersResponse(
                        triggers=[
                            triggers_pb2.Trigger(
                                trigger_id=100 + listed, status=triggers_pb2.STATUS_ARMED
                            )
                        ],
                        next_page_token=token,
                    )
                )
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
                    ],
                    next_page_token="page-2" if self.repeat_token else "",
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
            if self.cancel_all_refused:
                return _refusal("permission_denied", 403)
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
    assert result.trigger_failures == []
    assert result.cancel_all is not None and result.cancel_all.total_cancelled == 2


async def _run(httpserver: HTTPServer, exchange: _Exchange):
    for path in (LIST_PATH, CANCEL_TRIGGER_PATH, CANCEL_ALL_PATH):
        httpserver.expect_request(path, method="POST").respond_with_handler(exchange)
    orders, transport = _services(httpserver)
    try:
        return await orders.stop_all_trading()
    finally:
        await transport.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exchange",
    [_Exchange(ended={12}), _Exchange(failing={12})],
    ids=["already-ended", "other-refusal"],
)
async def test_a_failed_trigger_cancel_is_recorded_and_orders_are_still_canceled(
    httpserver: HTTPServer, exchange: _Exchange
) -> None:
    result = await _run(httpserver, exchange)

    # The trigger after the failed one is still canceled, then the orders.
    assert [c for c in exchange.calls if c[0] != "list"] == [
        ("cancel_trigger", 11),
        ("cancel_trigger", 12),
        ("cancel_trigger", 13),
        ("cancel_all", None),
    ]
    assert len(result.canceled_trigger_ids) == 2
    [failure] = result.trigger_failures
    assert failure.trigger_id not in result.canceled_trigger_ids
    assert isinstance(failure.error, PolyesterApiError)
    assert result.cancel_all is not None


@pytest.mark.asyncio
async def test_a_listing_error_is_raised_before_anything_is_canceled(
    httpserver: HTTPServer,
) -> None:
    exchange = _Exchange(list_refused=True)
    with pytest.raises(PolyesterAuthError):
        await _run(httpserver, exchange)

    assert [c[0] for c in exchange.calls] == ["list"]


@pytest.mark.asyncio
async def test_a_repeated_page_token_is_raised_before_anything_is_canceled(
    httpserver: HTTPServer,
) -> None:
    exchange = _Exchange(repeat_token=True)
    with pytest.raises(PolyesterResponseContractError, match="repeats"):
        await _run(httpserver, exchange)

    assert [c[0] for c in exchange.calls] == ["list", "list"]


@pytest.mark.asyncio
async def test_a_cancel_all_error_is_raised(httpserver: HTTPServer) -> None:
    exchange = _Exchange(cancel_all_refused=True)
    with pytest.raises(PolyesterAuthError):
        await _run(httpserver, exchange)

    assert exchange.calls[-1] == ("cancel_all", None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tokens",
    [["A", "B"] * 8, ["A", "B", "C"] * 6, ["A", "B", "C", "D"] + ["B", "C", "D"] * 5],
    ids=["A,B,A", "A,B,C,A", "A,B,C,D,B"],
)
async def test_a_page_token_cycle_is_raised_before_anything_is_canceled(
    httpserver: HTTPServer, tokens: list[str]
) -> None:
    exchange = _Exchange(tokens=tokens)
    with pytest.raises(PolyesterResponseContractError, match="repeats an earlier page"):
        await _run(httpserver, exchange)

    first_repeat = next(i for i, token in enumerate(tokens) if token in tokens[:i])
    assert [c[0] for c in exchange.calls] == ["list"] * (first_repeat + 1)


@pytest.mark.asyncio
async def test_a_finite_listing_cancels_everything_once(httpserver: HTTPServer) -> None:
    exchange = _Exchange(tokens=["A", "B"])
    result = await _run(httpserver, exchange)

    assert [c[0] for c in exchange.calls] == ["list"] * 3 + ["cancel_trigger"] * 3 + ["cancel_all"]
    assert len(result.canceled_trigger_ids) == 3
