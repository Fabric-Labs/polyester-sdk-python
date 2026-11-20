"""Public contract 8894e54 (0.93.7): a refused batch replacement read through
``orders.get`` carries no order terms, the transfer reason filter,
``GetInternalTransferBatch``'s refusal of a key without
``READ_INTERNAL_TRANSFERS``, and ``AccountScopeType`` in its own file."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

import msgspec
import pytest
from google.protobuf import json_format

from polyester import AsyncPolyester
from polyester.codecs.decode.orders import get_order_from_proto
from polyester.codecs.scalars import format_id
from polyester.errors import (
    PolyesterAuthError,
    PolyesterValidationError,
    is_not_found,
    is_retryable_error,
)
from polyester.gen.auth.v1 import account_scope_pb2, address_book_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.ledger.v1 import catalog_pb2
from polyester.gen.orders.v1 import orders_read_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as it_pb2
from polyester.models import OrderId
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    connect_proto_response,
    make_test_credentials,
)

_CREDS = make_test_credentials()

Answer = Callable[[ParsedRequest], HttpScript]


@asynccontextmanager
async def _client(answer: Answer, *, wire_format: str = "binary"):
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
        wire_format=wire_format,  # type: ignore[arg-type]
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await http.aclose()


# --- a refused batch replacement read through orders.get -----------------------------------------

_SUCCESSOR_ID = 2001504781434687193
_BATCH_ID = 2001504781434687001

# GetOrder of a refused batch replacement's successor within 60 seconds of the
# batch's acceptance, as the API sends it: REJECTED at version 1 with its batch
# and its own lineage, no terminal time and no order terms (no symbol, side,
# type, time in force, self-trade prevention mode or fee asset), its quantities
# and prices 0 placeholders.
_REFUSED_REPLACEMENT_REPLY: dict[str, Any] = {
    "order": {
        "orderId": str(_SUCCESSOR_ID),
        "status": "REJECTED",
        "origQtyScaled": "0",
        "cumQtyScaled": "0",
        "inheritedCumQtyScaled": "0",
        "leavesQtyScaled": "0",
        "priceTicks": "0",
        "avgPriceTicks": "0",
        "createdTsNs": "1763600000123456789",
        "rejectReason": "ERROR_CODE_MODIFY_APPLY_EXPIRED",
        "version": 1,
        "batchRequestId": str(_BATCH_ID),
        "lineage": {"id": str(_SUCCESSOR_ID), "generation": 1},
    },
    "executionsComplete": True,
}

_TERMS = ("symbol_id", "side", "order_type", "tif", "self_trade_prevention_mode", "fee_asset")


def _refused_replacement_answer(req: ParsedRequest) -> HttpScript:
    assert req.path.endswith("/GetOrder")
    if req.body.lstrip().startswith(b"{"):
        return HttpScript.json(200, _REFUSED_REPLACEMENT_REPLY)
    message = json_format.ParseDict(_REFUSED_REPLACEMENT_REPLY, orders_read_pb2.GetOrderResponse())
    return connect_proto_response(message.SerializeToString())


@pytest.mark.parametrize("wire_format", ["binary", "json"])
async def test_get_order_decodes_a_refused_batch_replacement_without_terms(wire_format) -> None:
    order_id = format_id(_SUCCESSOR_ID)
    async with _client(_refused_replacement_answer, wire_format=wire_format) as (client, _):
        result = await client.orders.get(key=OrderId(order_id))
    order = result.order
    assert order is not None
    assert (order.order_id, order.status, order.reject_reason) == (
        order_id,
        "rejected",
        "modify_apply_expired",
    )
    assert (order.version, order.batch_request_id) == (1, format_id(_BATCH_ID))
    assert (order.created_ts_ns, order.terminal_ts_ns) == ("1763600000123456789", "")
    assert order.lineage is not None
    assert (order.lineage.id, order.lineage.generation) == (order_id, 1)
    assert all(getattr(order, name) is None for name in _TERMS), order
    for qty in (order.orig_qty, order.cum_qty, order.leaves_qty):
        assert qty is not None
        assert (qty.scaled, qty.scale, qty.symbol_id) == (0, None, None)
    assert order.price is None and order.avg_px is None
    encoded = json.loads(msgspec.json.encode(order))
    assert not set(_TERMS) & set(encoded), encoded


def test_a_refused_batch_replacement_looks_up_no_pair() -> None:
    looked_up: list[int] = []

    def scales(symbol_id: int) -> tuple[int | None, int | None]:
        looked_up.append(symbol_id)
        return 8, 6

    message = json_format.ParseDict(_REFUSED_REPLACEMENT_REPLY, orders_read_pb2.GetOrderResponse())
    order = get_order_from_proto(message, scales=scales).order
    assert order is not None and order.quote_quantity_scale is None
    assert looked_up == []


def test_an_order_with_its_terms_still_reads_them() -> None:
    message = json_format.ParseDict(
        {
            "orderId": "7",
            "symbolId": 1,
            "side": "BUY",
            "orderType": "LIMIT",
            "timeInForce": "GTC",
            "selfTradePreventionMode": "EXPIRE_TAKER",
            "feeAsset": "QUOTE",
        },
        orders_read_pb2.Order(),
    )
    order = get_order_from_proto(
        orders_read_pb2.GetOrderResponse(order=message), scales=lambda _id: (8, 6)
    ).order
    assert order is not None
    assert [getattr(order, name) for name in _TERMS] == [
        1,
        "buy",
        "limit",
        "gtc",
        "expire_taker",
        "quote",
    ]
    assert order.quote_quantity_scale == 6


# --- transfers.list(transfer_code=...) -----------------------------------------------------------


def _empty_transfers(req: ParsedRequest) -> HttpScript:
    if req.body.lstrip().startswith(b"{"):
        return HttpScript.json(200, {"nextPageToken": "next"})
    return connect_proto_response(
        ledger_read_pb2.ListTransfersResponse(next_page_token="next").SerializeToString()
    )


def _sent(req: ParsedRequest) -> ledger_read_pb2.ListTransfersRequest:
    if req.body.lstrip().startswith(b"{"):
        return json_format.Parse(req.body, ledger_read_pb2.ListTransfersRequest())
    return ledger_read_pb2.ListTransfersRequest.FromString(req.body)


@pytest.mark.parametrize("wire_format", ["binary", "json"])
async def test_transfers_list_sends_the_transfer_code_with_the_other_filters(wire_format) -> None:
    since = 1_700_000_000_000_000
    async with _client(_empty_transfers, wire_format=wire_format) as (client, requests):
        first = await client.transfers.list(
            limit=10, reversed=True, since=since, transfer_code=catalog_pb2.DEPOSIT
        )
        await client.transfers.list(
            limit=10,
            reversed=True,
            since=since,
            transfer_code=catalog_pb2.DEPOSIT,
            page_token=first.next_page_token,
        )
        await client.transfers.list(limit=10)
        await client.transfers.list(limit=10, transfer_code=0)
    filtered, continued, plain, every = (_sent(req) for req in requests)
    for request, token in ((filtered, ""), (continued, "next")):
        assert request.transfer_code == catalog_pb2.DEPOSIT == 1000
        assert (request.page_token, request.ts_min_us, request.reversed, request.limit) == (
            token,
            since,
            True,
            10,
        )
    assert plain.transfer_code == every.transfer_code == catalog_pb2.TRANSFER_CODE_UNSPECIFIED
    if wire_format == "json":
        assert "transferCode" in json.loads(requests[0].body)
        assert "transferCode" not in json.loads(requests[2].body)


@pytest.mark.parametrize("transfer_code", [-1, 2**31, True, 1.5, "DEPOSIT"])
async def test_transfers_list_refuses_an_invalid_transfer_code_before_sending(
    transfer_code,
) -> None:
    async with _client(_empty_transfers) as (client, requests):
        with pytest.raises(PolyesterValidationError, match="transfer_code"):
            await client.transfers.list(transfer_code=transfer_code)
    assert requests == []


# --- GetInternalTransferBatch refuses a key without READ_INTERNAL_TRANSFERS ----------------------


async def test_get_batch_refuses_a_key_without_the_read_grant_as_permission_denied() -> None:
    message = "API key policy does not grant READ_INTERNAL_TRANSFERS"
    detail = it_pb2.ErrorDetail(code=it_pb2.ERROR_CODE_PERMISSION_DENIED)
    body = {
        "code": "permission_denied",
        "message": message,
        "details": [
            {
                "type": "transfer.v1.ErrorDetail",
                "value": base64.b64encode(detail.SerializeToString()).decode(),
            }
        ],
    }
    async with _client(lambda _req: HttpScript.json(403, body)) as (client, requests):
        with pytest.raises(PolyesterAuthError) as raised:
            await client.internal_transfers.get_batch(request_id="12345")
    assert len(requests) == 1 and requests[0].path.endswith("/GetInternalTransferBatch")
    error = raised.value
    assert (error.code, str(error)) == ("ERROR_CODE_PERMISSION_DENIED", message)
    assert not is_not_found(error)
    assert not is_retryable_error(error)


# --- AccountScopeType moved to auth/v1/account_scope.proto ---------------------------------------


def test_account_scope_type_is_declared_in_its_own_file() -> None:
    from polyester.codecs.decode.address_book import account_scope_from_proto

    enum = account_scope_pb2.AccountScopeType
    assert enum.DESCRIPTOR.full_name == "auth.v1.AccountScopeType"
    assert enum.DESCRIPTOR.file.name == "auth/v1/account_scope.proto"
    assert not hasattr(address_book_pb2, "AccountScopeType")
    scope = account_scope_from_proto(
        address_book_pb2.AccountScopeRef(scope_type=account_scope_pb2.SCOPE_ROOT)
    )
    assert scope.scope_type == "root"
