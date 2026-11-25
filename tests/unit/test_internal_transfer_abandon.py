"""Abandoning an internal transfer batch's idempotency key
(``AbandonInternalTransferBatch``) and the refusal of a batch under an
abandoned key."""

from __future__ import annotations

import base64
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from google.protobuf.message import Message

from polyester import (
    IDEMPOTENCY_KEY_ABANDONED,
    AsyncPolyester,
    PolyesterApiError,
    PolyesterResponseContractError,
    PolyesterValidationError,
    is_idempotency_key_abandoned,
)
from polyester.errors import is_retryable_error, mutation_outcome_unknown
from polyester.gen.transfer.v1 import internal_transfer_pb2 as it_pb2
from polyester.models import InternalTransferLeg
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()
Answer = Callable[[ParsedRequest], HttpScript]
_ABANDON_PATH = "/transfer.v1.InternalTransferService/AbandonInternalTransferBatch"


@asynccontextmanager
async def _client(answer: Answer):
    requests: list[ParsedRequest] = []

    async def handler(req: ParsedRequest) -> HttpScript:
        requests.append(req)
        return answer(req)

    http = await MockHttpServer.spawn(handler)
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=_CREDS.key_id,
        api_private_key=_CREDS.private_key,
        hydrate_catalogs=False,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


def _ok(message: Message) -> Answer:
    return lambda _req: connect_proto_response(message.SerializeToString())


def _transfer_error(connect_code: str, code: int, status: int) -> Answer:
    value = base64.b64encode(it_pb2.ErrorDetail(code=code).SerializeToString()).decode()
    body = {
        "code": connect_code,
        "message": it_pb2.ErrorCode.Name(code),
        "details": [{"type": "transfer.v1.ErrorDetail", "value": value}],
    }
    return lambda _req: HttpScript.json(status, body)


def _leg() -> InternalTransferLeg:
    return InternalTransferLeg(
        asset_id=1,
        quantity="1",
        quantity_scale=18,
        destination_smart_account_address="0x2222222222222222222222222222222222222222",
    )


async def test_abandon_batch_of_an_unused_key_answers_abandoned() -> None:
    reply = it_pb2.AbandonInternalTransferBatchResponse(status=it_pb2.BATCH_ABANDONED)
    async with _client(_ok(reply)) as (client, requests):
        batch = await client.internal_transfers.abandon_batch(idempotency_key="rebalance-1")
    (request,) = requests
    assert request.path == _ABANDON_PATH
    assert request.headers.get("x-api-signature")
    sent = it_pb2.AbandonInternalTransferBatchRequest.FromString(request.body)
    assert sent.idempotency_key == "rebalance-1"
    assert (batch.status, batch.request_id, batch.legs) == ("abandoned", "", [])


async def test_abandon_batch_answers_the_batch_submitted_under_the_key() -> None:
    reply = it_pb2.AbandonInternalTransferBatchResponse(
        request_id="1234",
        status=it_pb2.BATCH_ACCEPTED,
        legs=[
            it_pb2.InternalTransferBatchLegResult(
                leg_index=0,
                status=it_pb2.LEG_CREDITED,
                transfer_id="t0",
                flow_id="f0",
                credited_at_ts_ns=1,
            )
        ],
    )
    async with _client(_ok(reply)) as (client, _requests):
        batch = await client.internal_transfers.abandon_batch(idempotency_key="k")
    assert (batch.request_id, batch.status) == ("1234", "accepted")
    assert [(leg.status, leg.flow_id) for leg in batch.legs] == [("credited", "f0")]

    refused = it_pb2.AbandonInternalTransferBatchResponse(
        status=it_pb2.BATCH_REFUSED,
        legs=[
            it_pb2.InternalTransferBatchLegResult(
                leg_index=0,
                status=it_pb2.LEG_NOT_MOVED,
                error_code=it_pb2.ERROR_CODE_INSUFFICIENT_FUNDS,
            )
        ],
    )
    async with _client(_ok(refused)) as (client, _requests):
        batch = await client.internal_transfers.abandon_batch(idempotency_key="k")
    assert batch.status == "refused"
    assert batch.legs[0].error_code == "insufficient_funds"


@pytest.mark.parametrize("key", ["", "k" * 129, None, 12])
async def test_abandon_batch_refuses_a_key_the_contract_refuses(key: Any) -> None:
    reply = it_pb2.AbandonInternalTransferBatchResponse(status=it_pb2.BATCH_ABANDONED)
    async with _client(_ok(reply)) as (client, requests):
        with pytest.raises(PolyesterValidationError):
            await client.internal_transfers.abandon_batch(idempotency_key=key)
    assert requests == []


async def test_abandon_batch_takes_a_key_of_the_longest_length() -> None:
    reply = it_pb2.AbandonInternalTransferBatchResponse(status=it_pb2.BATCH_ABANDONED)
    async with _client(_ok(reply)) as (client, requests):
        await client.internal_transfers.abandon_batch(idempotency_key="k" * 128)
    assert len(requests) == 1


_NOT_MOVED = it_pb2.InternalTransferBatchLegResult(leg_index=0, status=it_pb2.LEG_NOT_MOVED)


@pytest.mark.parametrize(
    "reply",
    [
        it_pb2.AbandonInternalTransferBatchResponse(status=it_pb2.BATCH_ABANDONED, request_id="1"),
        it_pb2.AbandonInternalTransferBatchResponse(
            status=it_pb2.BATCH_ABANDONED, legs=[_NOT_MOVED]
        ),
        it_pb2.AbandonInternalTransferBatchResponse(status=99, request_id="1", legs=[_NOT_MOVED]),
        it_pb2.AbandonInternalTransferBatchResponse(),
        it_pb2.AbandonInternalTransferBatchResponse(status=it_pb2.BATCH_ACCEPTED, request_id="1"),
    ],
    ids=[
        "abandoned-with-request-id",
        "abandoned-with-legs",
        "unknown-status",
        "unspecified-status",
        "accepted-without-legs",
    ],
)
async def test_abandon_batch_refuses_an_answer_that_breaks_the_contract(reply) -> None:
    async with _client(_ok(reply)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError) as raised:
            await client.internal_transfers.abandon_batch(idempotency_key="k")
    assert raised.value.context == "AbandonInternalTransferBatch"


async def test_abandon_batch_unknown_outcome_is_resolved_by_abandoning_again() -> None:
    answers = [
        _transfer_error("unavailable", it_pb2.ERROR_CODE_SERVICE_UNAVAILABLE, 503),
        _ok(it_pb2.AbandonInternalTransferBatchResponse(status=it_pb2.BATCH_ABANDONED)),
    ]

    def answer(req: ParsedRequest) -> HttpScript:
        return answers.pop(0)(req)

    async with _client(answer) as (client, requests):
        with pytest.raises(Exception) as raised:
            await client.internal_transfers.abandon_batch(idempotency_key="k")
        assert mutation_outcome_unknown(raised.value)
        batch = await client.internal_transfers.abandon_batch(idempotency_key="k")
    assert batch.status == "abandoned"
    assert len(requests) == 2


@pytest.mark.parametrize(
    "reply",
    [
        it_pb2.BatchCreateInternalTransfersResponse(status=it_pb2.BATCH_ABANDONED),
        it_pb2.GetInternalTransferBatchResponse(status=it_pb2.BATCH_ABANDONED),
    ],
    ids=["batch-create", "get-batch"],
)
async def test_only_abandon_batch_answers_an_abandoned_key(reply) -> None:
    async with _client(_ok(reply)) as (client, _requests):
        with pytest.raises(PolyesterResponseContractError):
            if isinstance(reply, it_pb2.BatchCreateInternalTransfersResponse):
                await client.internal_transfers.batch_create(legs=[_leg()], idempotency_key="k")
            else:
                await client.internal_transfers.get_batch(request_id="1")


async def test_batch_under_an_abandoned_key_is_final_and_not_retryable() -> None:
    answer = _transfer_error(
        "failed_precondition", it_pb2.ERROR_CODE_IDEMPOTENCY_KEY_ABANDONED, 400
    )
    async with _client(answer) as (client, _requests):
        with pytest.raises(PolyesterApiError) as raised:
            await client.internal_transfers.batch_create(legs=[_leg()], idempotency_key="k")
    err = raised.value
    assert err.code == IDEMPOTENCY_KEY_ABANDONED == "ERROR_CODE_IDEMPOTENCY_KEY_ABANDONED"
    assert is_idempotency_key_abandoned(err)
    assert not is_retryable_error(err) and not mutation_outcome_unknown(err)


async def test_rest_idempotency_key_abandoned_reads_the_same_code() -> None:
    body = {"code": "IDEMPOTENCY_KEY_ABANDONED", "status": 400, "detail": "abandoned"}
    async with _client(lambda _req: HttpScript.json(400, body)) as (client, _requests):
        with pytest.raises(PolyesterApiError) as raised:
            await client.internal_transfers.batch_create(legs=[_leg()], idempotency_key="k")
    assert is_idempotency_key_abandoned(raised.value)
    assert not is_retryable_error(raised.value)


async def test_an_idempotency_conflict_is_not_an_abandoned_key() -> None:
    answer = _transfer_error("already_exists", it_pb2.ERROR_CODE_IDEMPOTENCY_CONFLICT, 409)
    async with _client(answer) as (client, _requests):
        with pytest.raises(PolyesterApiError) as raised:
            await client.internal_transfers.batch_create(legs=[_leg()], idempotency_key="k")
    assert not is_idempotency_key_abandoned(raised.value)
