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
from polyester.codecs.scalars import format_id
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterResponseContractError,
    is_trigger_already_ended,
)
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.services.orders import AsyncOrdersService
from polyester.services.triggers import AsyncTriggersService
from polyester.transport import TransportConfig, TransportFactory

LIST_PATH = "/triggers.v1.TriggersService/ListTriggers"
CANCEL_TRIGGER_PATH = "/triggers.v1.TriggersService/CancelTrigger"
CANCEL_OCO_PATH = "/triggers.v1.TriggersService/CancelOco"
CANCEL_ALL_PATH = "/orders.v1.OrdersService/CancelAllOrders"


def _proto(message) -> Response:
    return Response(message.SerializeToString(), content_type="application/proto")


def _refusal(code: str, status: int) -> Response:
    return Response(
        json.dumps({"code": code, "message": "refused"}),
        status=status,
        content_type="application/json",
    )


def _coded_refusal(detail_code: int) -> Response:
    detail = orders_pb2.ErrorDetail(code=detail_code)
    body = {
        "code": "failed_precondition",
        "message": "refused",
        "details": [
            {
                "type": "orders.v1.ErrorDetail",
                "value": base64.b64encode(detail.SerializeToString()).decode().rstrip("="),
            }
        ],
    }
    return Response(json.dumps(body), status=400, content_type="application/json")


_ALREADY_ENDED = orders_pb2.ERROR_CODE_TRIGGER_STATUS_INVALID
_NOT_FOUND = orders_pb2.ERROR_CODE_TRIGGER_NOT_FOUND
_PERMISSION_DENIED = -1


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
        live: list[tuple[int, int]] | None = None,
        refusals: dict[int, int] | None = None,
        oco_refusals: dict[int, int] | None = None,
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
        # When set, the one page listed: (trigger ID, OCO ID or 0). As on the
        # server, canceling one leg of an OCO ends both, and a cancel of a
        # trigger or OCO that has ended is refused as already ended.
        # ``ended`` then names triggers that ended after the listing.
        self.live = live
        # A scripted refusal per trigger or OCO ID: an error detail code, or
        # _PERMISSION_DENIED.
        self.refusals = refusals or {}
        self.oco_refusals = oco_refusals or {}

    def _end(self, trigger_id: int, order_list_id: int) -> bool:
        """End a trigger and its OCO sibling; False when both had ended."""
        live = False
        for listed_id, listed_oco in self.live or []:
            matches = listed_id == trigger_id or (order_list_id and listed_oco == order_list_id)
            if matches and listed_id not in self.ended:
                self.ended.add(listed_id)
                live = True
        return live

    @staticmethod
    def _scripted(refusal: int) -> Response:
        if refusal == _PERMISSION_DENIED:
            return _refusal("permission_denied", 403)
        return _coded_refusal(refusal)

    def __call__(self, request: Request) -> Response:
        if request.path == LIST_PATH:
            req = triggers_pb2.ListTriggersRequest.FromString(request.get_data())
            self.calls.append(("list", (list(req.status), req.limit, req.page_token)))
            if self.list_refused:
                return _refusal("permission_denied", 403)
            if self.live is not None:
                return _proto(
                    triggers_pb2.ListTriggersResponse(
                        triggers=[
                            triggers_pb2.Trigger(
                                trigger_id=trigger_id,
                                status=triggers_pb2.STATUS_ARMED,
                                **({"order_list_id": oco} if oco else {}),
                            )
                            for trigger_id, oco in self.live
                        ]
                    )
                )
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
            if req.trigger_id in self.refusals:
                return self._scripted(self.refusals[req.trigger_id])
            if self.live is not None:
                oco = dict(self.live).get(req.trigger_id, 0)
                if not self._end(req.trigger_id, oco):
                    return _coded_refusal(_ALREADY_ENDED)
            elif req.trigger_id in self.ended or req.trigger_id in self.failing:
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
        if request.path == CANCEL_OCO_PATH:
            req = triggers_pb2.CancelOcoRequest.FromString(request.get_data())
            self.calls.append(("cancel_oco", req.order_list_id))
            if req.order_list_id in self.oco_refusals:
                return self._scripted(self.oco_refusals[req.order_list_id])
            if not self._end(0, req.order_list_id):
                return _coded_refusal(_ALREADY_ENDED)
            return _proto(
                triggers_pb2.CancelOcoResponse(
                    order_list_id=req.order_list_id, status=triggers_pb2.STATUS_CANCELED
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
    for path in (LIST_PATH, CANCEL_TRIGGER_PATH, CANCEL_OCO_PATH, CANCEL_ALL_PATH):
        httpserver.expect_request(path, method="POST").respond_with_handler(exchange)
    orders, transport = _services(httpserver)
    try:
        return await orders.stop_all_trading()
    finally:
        await transport.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exchange", "error_type"),
    [
        (_Exchange(failing={12}), PolyesterApiError),
        (_Exchange(refusals={12: _PERMISSION_DENIED}), PolyesterAuthError),
    ],
    ids=["busy", "permission-denied"],
)
async def test_a_failed_trigger_cancel_is_recorded_and_orders_are_still_canceled(
    httpserver: HTTPServer, exchange: _Exchange, error_type: type[Exception]
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
    assert isinstance(failure.error, error_type)
    assert not is_trigger_already_ended(failure.error)
    assert result.cancel_all is not None


@pytest.mark.asyncio
async def test_an_oco_is_canceled_once_by_its_oco_id(httpserver: HTTPServer) -> None:
    # Canceling one leg of an OCO ends the other: the second leg is never
    # canceled on its own, so the stop reports no failure.
    exchange = _Exchange(live=[(21, 90), (11, 0), (22, 90)])
    result = await _run(httpserver, exchange)

    assert [c for c in exchange.calls if c[0] != "list"] == [
        ("cancel_oco", 90),
        ("cancel_trigger", 11),
        ("cancel_all", None),
    ]
    assert result.trigger_failures == []
    assert result.canceled_trigger_ids == [format_id(21), format_id(22), format_id(11)]
    assert result.cancel_all is not None


@pytest.mark.asyncio
async def test_a_trigger_or_oco_that_already_ended_is_stopped_not_failed(
    httpserver: HTTPServer,
) -> None:
    # 12 and OCO 90 ended (filled or expired) after the listing; 13 and OCO 91
    # are refused not found.
    exchange = _Exchange(
        live=[(11, 0), (12, 0), (13, 0), (21, 90), (22, 90), (31, 91), (32, 91)],
        ended={12, 21, 22},
        refusals={13: _NOT_FOUND},
        oco_refusals={91: _NOT_FOUND},
    )
    result = await _run(httpserver, exchange)

    assert [c for c in exchange.calls if c[0] != "list"] == [
        ("cancel_trigger", 11),
        ("cancel_trigger", 12),
        ("cancel_trigger", 13),
        ("cancel_oco", 90),
        ("cancel_oco", 91),
        ("cancel_all", None),
    ]
    assert result.trigger_failures == []
    assert result.canceled_trigger_ids == [format_id(11)]
    assert result.cancel_all is not None


@pytest.mark.asyncio
async def test_a_refused_oco_cancel_is_recorded_for_each_leg(httpserver: HTTPServer) -> None:
    exchange = _Exchange(live=[(21, 90), (22, 90), (11, 0)], oco_refusals={90: _PERMISSION_DENIED})
    result = await _run(httpserver, exchange)

    assert [c for c in exchange.calls if c[0] != "list"] == [
        ("cancel_oco", 90),
        ("cancel_trigger", 11),
        ("cancel_all", None),
    ]
    assert [f.trigger_id for f in result.trigger_failures] == [format_id(21), format_id(22)]
    for failure in result.trigger_failures:
        assert isinstance(failure.error, PolyesterAuthError)
    assert result.canceled_trigger_ids == [format_id(11)]
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
