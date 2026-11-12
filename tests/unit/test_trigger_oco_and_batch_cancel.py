"""``triggers.create_oco``, ``triggers.cancel_oco`` and ``triggers.batch_cancel``.

Each call is sent to a local server that records the request it decodes, so the
tests check the wire request, the decoded answer, and that a refused input
never reaches the server.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable
from typing import Any

import pytest
import pytest_asyncio
from google.protobuf.message import Message

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_id
from polyester.errors import (
    PolyesterApiError,
    PolyesterResponseContractError,
    PolyesterValidationError,
    mutation_outcome_unknown,
)
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2
from polyester.gen.triggers.v1 import triggers_pb2 as triggers
from polyester.models import (
    BatchCancelTriggerResultItem,
    BatchCancelTriggersResult,
    CancelOcoResult,
    CreateOcoResult,
    OrderFieldViolation,
    RiskLeg,
)
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

SERVICE = "/triggers.v1.TriggersService/"
SUB = 77
LIST_ID = (1 << 63) + 5
TP_ID = (1 << 63) + 6
SL_ID = (1 << 63) + 7

Answer = Callable[[Message], HttpScript]


def _ok(response: Message) -> Answer:
    return lambda _request: connect_proto_response(response.SerializeToString())


def _connect_error(status: int, code: str, detail: orders_pb2.ErrorDetail) -> HttpScript:
    value = base64.b64encode(detail.SerializeToString()).decode()
    return HttpScript.json(
        status,
        {
            "code": code,
            "message": "refused",
            "details": [{"type": "orders.v1.ErrorDetail", "value": value}],
        },
    )


class Server:
    """Answers each trigger RPC with the answer set for it and keeps every request."""

    REQUESTS: dict[str, type[Message]] = {
        "CreateOco": triggers.CreateOcoRequest,
        "CancelOco": triggers.CancelOcoRequest,
        "BatchCancelTriggers": triggers.BatchCancelTriggersRequest,
        "ListTriggers": triggers.ListTriggersRequest,
    }

    def __init__(self) -> None:
        self.answers: dict[str, Answer] = {}
        self.seen: list[tuple[str, Message]] = []

    async def handle(self, req: ParsedRequest) -> HttpScript:
        method = req.path.removeprefix(SERVICE)
        if req.method != "POST" or method not in self.answers:
            return HttpScript.not_found()
        request = self.REQUESTS[method].FromString(req.body)
        self.seen.append((method, request))
        return self.answers[method](request)

    def requests(self, method: str) -> list[Any]:
        return [request for name, request in self.seen if name == method]


@pytest_asyncio.fixture(loop_scope="function")
async def oco_client():
    server = Server()
    http = await MockHttpServer.spawn(server.handle)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    client.catalogs.hydrate_spot_config(
        {
            "pairs": [
                {
                    "symbol": "BTC-USDT",
                    "symbol_id": 1,
                    "base_quantity_scale": 8,
                    "quote_quantity_scale": 6,
                }
            ]
        }
    )
    yield client, server
    await client.aclose()
    await http.aclose()


def _created(request: triggers.CreateOcoRequest) -> HttpScript:
    response = triggers.CreateOcoResponse(
        order_list_id=LIST_ID,
        client_list_id=request.oco.client_list_id,
        take_profit_trigger_id=TP_ID,
        stop_loss_trigger_id=SL_ID,
        accepted_at_ts_ns=1,
    )
    return connect_proto_response(response.SerializeToString())


async def _create_oco(client: AsyncPolyester, **overrides: Any) -> CreateOcoResult:
    kwargs: dict[str, Any] = {
        "symbol": "BTC-USDT",
        "side": "sell",
        "qty": "0.5",
        "take_profit": {"trigger_price": "110000", "order_type": "limit", "limit_price": "109500"},
        "stop_loss": {"trigger_price": "90000"},
    }
    kwargs.update(overrides)
    return await client.triggers.create_oco(**kwargs)


# --- create_oco --------------------------------------------------------------


async def test_create_oco_sends_the_intent_and_reads_the_legs(oco_client) -> None:
    client, server = oco_client
    server.answers["CreateOco"] = _created
    result = await _create_oco(
        client,
        client_list_id="my-oco-1",
        self_trade_prevention_mode="expire_both",
        sub_account_id=format_id(SUB),
        stop_loss={
            "trigger_price": "90000",
            "order_type": "market",
            "trigger_price_source": "index",
        },
    )
    assert result == CreateOcoResult(
        order_list_id=format_id(LIST_ID),
        client_list_id="my-oco-1",
        take_profit_trigger_id=format_id(TP_ID),
        stop_loss_trigger_id=format_id(SL_ID),
    )
    [request] = server.requests("CreateOco")
    assert request.subaccount_id == SUB
    oco = request.oco
    assert oco.symbol_id == 1
    assert oco.side == orders_pb2.SELL
    assert oco.qty_scaled == 50_000_000
    assert oco.client_list_id == "my-oco-1"
    assert oco.self_trade_prevention_mode == orders_pb2.EXPIRE_BOTH
    assert oco.take_profit.trigger_price_ticks == 110_000 * 10**9
    assert oco.take_profit.child.WhichOneof("execution") == "limit_gtc"
    assert oco.take_profit.child.limit_gtc.price_ticks == 109_500 * 10**9
    assert oco.take_profit.trigger_price_source == orders_pb2.TRIGGER_PRICE_SOURCE_UNSPECIFIED
    assert oco.stop_loss.trigger_price_ticks == 90_000 * 10**9
    assert oco.stop_loss.child.WhichOneof("execution") == "market_ioc"
    assert oco.stop_loss.trigger_price_source == orders_pb2.INDEX_PRICE


async def test_create_oco_takes_risk_leg_models(oco_client) -> None:
    client, server = oco_client
    server.answers["CreateOco"] = _created
    await _create_oco(
        client,
        side="buy",
        take_profit=RiskLeg(trigger_price="90000"),  # type: ignore[arg-type]
        stop_loss=RiskLeg(
            trigger_price="110000",  # type: ignore[arg-type]
            order_type="limit",
            limit_price="110500",  # type: ignore[arg-type]
        ),
    )
    [request] = server.requests("CreateOco")
    assert request.oco.side == orders_pb2.BUY
    assert request.oco.take_profit.child.WhichOneof("execution") == "market_ioc"
    assert request.oco.stop_loss.child.limit_gtc.price_ticks == 110_500 * 10**9
    assert not request.HasField("subaccount_id")


@pytest.mark.parametrize("kwargs", [{}, {"client_list_id": None}, {"client_list_id": ""}])
async def test_create_oco_without_an_id_sends_a_generated_one(oco_client, kwargs) -> None:
    client, server = oco_client
    server.answers["CreateOco"] = _created
    first = await _create_oco(client, **kwargs)
    await _create_oco(client, **kwargs)
    ids = [request.oco.client_list_id for request in server.requests("CreateOco")]
    assert all(re.fullmatch(r"oco-[0-9a-f]{12}", value) for value in ids), ids
    assert ids[0] != ids[1]
    assert first.client_list_id == ids[0]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"client_list_id": "   "}, "client_list_id"),
        ({"client_list_id": "x" * 37}, "client_list_id"),
        ({"side": "short"}, "side must be buy or sell"),
        ({"self_trade_prevention_mode": "decrement"}, "self_trade_prevention_mode"),
        ({"take_profit": {"trigger_price": "110000", "order_type": "limit"}}, "limit_price"),
        ({"stop_loss": {"order_type": "market"}}, "stop_loss requires trigger_price"),
        ({"stop_loss": {"trigger_price": "90000", "tif": "ioc"}}, "unsupported fields"),
        (
            {"stop_loss": {"trigger_price": "90000", "trigger_price_source": "mark"}},
            "mark is not supported",
        ),
        ({"symbol": "DOGE-USDT"}, "DOGE-USDT"),
    ],
)
async def test_create_oco_refuses_bad_input_before_sending(oco_client, overrides, message) -> None:
    client, server = oco_client
    server.answers["CreateOco"] = _created
    with pytest.raises(PolyesterValidationError, match=message):
        await _create_oco(client, **overrides)
    assert server.seen == []


async def test_create_oco_unconfirmed_outcome_is_raised_once_and_not_resent(oco_client) -> None:
    client, server = oco_client
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_TRIGGER_CREATE_OUTCOME_UNKNOWN)
    server.answers["CreateOco"] = lambda _request: _connect_error(504, "deadline_exceeded", detail)
    with pytest.raises(PolyesterApiError) as caught:
        await _create_oco(client, client_list_id="my-oco-1")
    assert caught.value.code == "ERROR_CODE_TRIGGER_CREATE_OUTCOME_UNKNOWN"
    assert mutation_outcome_unknown(caught.value)
    assert len(server.requests("CreateOco")) == 1


# --- cancel_oco --------------------------------------------------------------


async def test_cancel_oco_sends_the_id_and_reads_the_status(oco_client) -> None:
    client, server = oco_client
    server.answers["CancelOco"] = _ok(
        triggers.CancelOcoResponse(order_list_id=LIST_ID, status=triggers.STATUS_CANCELED, ts_ns=1)
    )
    result = await client.triggers.cancel_oco(
        order_list_id=format_id(LIST_ID), sub_account_id=format_id(SUB)
    )
    assert result == CancelOcoResult(order_list_id=format_id(LIST_ID), status="canceled")
    [request] = server.requests("CancelOco")
    assert request.order_list_id == LIST_ID
    assert request.subaccount_id == SUB


async def test_cancel_oco_takes_a_decimal_id_and_the_main_account(oco_client) -> None:
    client, server = oco_client
    server.answers["CancelOco"] = _ok(
        triggers.CancelOcoResponse(order_list_id=LIST_ID, status=triggers.STATUS_CANCELED)
    )
    await client.triggers.cancel_oco(order_list_id=str(LIST_ID))
    [request] = server.requests("CancelOco")
    assert request.order_list_id == LIST_ID
    assert not request.HasField("subaccount_id")


async def test_cancel_oco_of_a_trigger_id_keeps_the_refusal_code(oco_client) -> None:
    client, server = oco_client
    detail = orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_TRIGGER_NOT_FOUND)
    server.answers["CancelOco"] = lambda _request: _connect_error(404, "not_found", detail)
    with pytest.raises(PolyesterApiError) as caught:
        await client.triggers.cancel_oco(order_list_id=TP_ID)
    assert caught.value.code == "ERROR_CODE_TRIGGER_NOT_FOUND"
    assert not mutation_outcome_unknown(caught.value)


# --- batch_cancel ------------------------------------------------------------


def _batch_answer(request: triggers.BatchCancelTriggersRequest) -> HttpScript:
    accepted, rejected = request.trigger_ids
    rate_limit = types_pb2.RateLimitDetail(retry_after_ms=250)
    response = triggers.BatchCancelTriggersResponse(
        results=[
            triggers.BatchCancelTriggersResultItem(
                status=triggers.BatchCancelTriggersResultItem.ACCEPTED, trigger_id=accepted
            ),
            triggers.BatchCancelTriggersResultItem(
                status=triggers.BatchCancelTriggersResultItem.REJECTED,
                trigger_id=rejected,
                code="RATE_LIMIT_EXCEEDED",
                error=orders_pb2.ErrorDetail(
                    code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED,
                    rate_limit=rate_limit,
                    violations=[
                        orders_pb2.FieldViolation(
                            field_path="trigger_ids[1]", rule_id="rate", message="slow down"
                        )
                    ],
                ),
            ),
        ],
        accepted_count=1,
        rejected_count=1,
        ts_ns=1,
    )
    return connect_proto_response(response.SerializeToString())


async def test_batch_cancel_sends_the_ids_in_order_and_reads_each_result(oco_client) -> None:
    client, server = oco_client
    server.answers["BatchCancelTriggers"] = _batch_answer
    result = await client.triggers.batch_cancel(
        trigger_ids=[format_id(TP_ID), str(SL_ID)],
        request_id="tpsl-cancel-all-7f3a",
        sub_account_id=format_id(SUB),
    )
    [request] = server.requests("BatchCancelTriggers")
    assert list(request.trigger_ids) == [TP_ID, SL_ID]
    assert request.request_id == "tpsl-cancel-all-7f3a"
    assert request.subaccount_id == SUB
    assert isinstance(result, BatchCancelTriggersResult)
    assert result.accepted_count == 1
    assert result.rejected_count == 1
    accepted, rejected = result.results
    assert accepted == BatchCancelTriggerResultItem(status="accepted", trigger_id=format_id(TP_ID))
    assert rejected.status == "rejected"
    assert rejected.trigger_id == format_id(SL_ID)
    assert rejected.code == "RATE_LIMIT_EXCEEDED"
    assert rejected.rate_limit is not None
    assert rejected.rate_limit.retry_after_ms == 250
    assert rejected.violations == [
        OrderFieldViolation(field_path="trigger_ids[1]", rule_id="rate", message="slow down")
    ]


@pytest.mark.parametrize("request_id", [None, "", "  "])
async def test_batch_cancel_without_a_request_id_sends_a_generated_one(
    oco_client, request_id
) -> None:
    client, server = oco_client
    server.answers["BatchCancelTriggers"] = _batch_answer
    for _ in range(2):
        await client.triggers.batch_cancel(trigger_ids=[TP_ID, SL_ID], request_id=request_id)
    ids = [request.request_id for request in server.requests("BatchCancelTriggers")]
    assert all(re.fullmatch(r"trg-cancel-[0-9a-f]{12}", value) for value in ids), ids
    assert ids[0] != ids[1]
    assert not server.requests("BatchCancelTriggers")[0].HasField("subaccount_id")


async def test_batch_cancel_takes_fifty_ids(oco_client) -> None:
    client, server = oco_client
    server.answers["BatchCancelTriggers"] = _ok(triggers.BatchCancelTriggersResponse())
    result = await client.triggers.batch_cancel(trigger_ids=list(range(1, 51)))
    assert result == BatchCancelTriggersResult(results=[])
    [request] = server.requests("BatchCancelTriggers")
    assert list(request.trigger_ids) == list(range(1, 51))


@pytest.mark.parametrize(
    ("trigger_ids", "request_id", "message"),
    [
        ([], None, "at least one trigger ID"),
        (list(range(1, 52)), None, "at most 50 trigger IDs; received 51"),
        ([TP_ID, format_id(TP_ID)], None, r"trigger_ids\[1\] repeats"),
        ([TP_ID, 0], None, r"trigger_ids\[1\] must be a non-zero"),
        (["1"], None, r"trigger_ids\[0\] must be a non-zero"),
        (["not base58!"], None, r"trigger_ids\[0\] must be base58 or decimal"),
        (str(TP_ID), None, "trigger_ids must be a list"),
        ([TP_ID], "bad id", "request_id contains invalid characters"),
        ([TP_ID], "x" * 65, "request_id must be 1 to 64 characters"),
    ],
)
async def test_batch_cancel_refuses_bad_input_before_sending(
    oco_client, trigger_ids, request_id, message
) -> None:
    client, server = oco_client
    server.answers["BatchCancelTriggers"] = _batch_answer
    with pytest.raises(PolyesterValidationError, match=message):
        await client.triggers.batch_cancel(trigger_ids=trigger_ids, request_id=request_id)
    assert server.seen == []


@pytest.mark.parametrize(
    "response",
    [
        triggers.BatchCancelTriggersResponse(
            results=[triggers.BatchCancelTriggersResultItem(trigger_id=TP_ID)],
            rejected_count=1,
        ),
        triggers.BatchCancelTriggersResponse(
            results=[
                triggers.BatchCancelTriggersResultItem(
                    status=triggers.BatchCancelTriggersResultItem.ACCEPTED, trigger_id=TP_ID
                )
            ],
            accepted_count=2,
        ),
    ],
    ids=["unknown status", "counts disagree"],
)
async def test_batch_cancel_refuses_an_inconsistent_answer(oco_client, response) -> None:
    client, server = oco_client
    server.answers["BatchCancelTriggers"] = _ok(response)
    with pytest.raises(PolyesterResponseContractError, match="BatchCancelTriggers"):
        await client.triggers.batch_cancel(trigger_ids=[TP_ID])


# --- list by OCO -------------------------------------------------------------


async def test_list_filters_by_oco(oco_client) -> None:
    client, server = oco_client
    server.answers["ListTriggers"] = _ok(triggers.ListTriggersResponse())
    await client.triggers.list(order_list_id=format_id(LIST_ID))
    await client.triggers.list(client_list_id="my-oco-1")
    await client.triggers.list()
    by_id, by_client_id, unfiltered = server.requests("ListTriggers")
    assert by_id.order_list_id == LIST_ID
    assert not by_id.HasField("client_list_id")
    assert by_client_id.client_list_id == "my-oco-1"
    assert not by_client_id.HasField("order_list_id")
    assert not unfiltered.HasField("order_list_id")
    assert not unfiltered.HasField("client_list_id")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"order_list_id": 0}, "order_list_id must be a non-zero"),
        ({"order_list_id": "1"}, "order_list_id must be a non-zero"),
        ({"client_list_id": " "}, "client_list_id"),
    ],
)
async def test_list_refuses_a_bad_oco_filter_before_sending(oco_client, kwargs, message) -> None:
    client, server = oco_client
    server.answers["ListTriggers"] = _ok(triggers.ListTriggersResponse())
    with pytest.raises(PolyesterValidationError, match=message):
        await client.triggers.list(**kwargs)
    assert server.seen == []
