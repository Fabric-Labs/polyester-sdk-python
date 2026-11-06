"""Ledger refusals keep their ``ledger.read.v1.ErrorDetail`` code."""

from __future__ import annotations

import base64
import json

import pytest

from polyester import AsyncPolyester
from polyester.errors import (
    PolyesterApiError,
    PolyesterServerError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.ledger.read.v1 import ledger_read_pb2 as ledger_read
from tests.hardening_support import (
    HttpScript,
    MockHttpServer,
    ParsedRequest,
    make_test_credentials,
)

SERVICE_PREFIX = "/ledger.read.v1.LedgerReadService/"


def _body(code: int, connect_code: str) -> bytes:
    value = base64.b64encode(ledger_read.ErrorDetail(code=code).SerializeToString()).decode()
    return json.dumps(
        {
            "code": connect_code,
            "message": "refused",
            "details": [{"type": "ledger.read.v1.ErrorDetail", "value": value}],
        }
    ).encode()


async def _balances_error(status: int, body: bytes) -> tuple[BaseException, int]:
    calls = 0

    async def handler(req: ParsedRequest) -> HttpScript:
        nonlocal calls
        if req.method != "POST" or not req.path.startswith(SERVICE_PREFIX):
            return HttpScript.not_found()
        calls += 1
        return HttpScript.json(status, body)

    http = await MockHttpServer.spawn(handler)
    creds = make_test_credentials()
    client = AsyncPolyester(
        api_url=http.base_url,
        api_key_id=creds.key_id,
        api_private_key=creds.private_key,
        hydrate_catalogs=False,
    )
    try:
        with pytest.raises(BaseException) as raised:
            await client.balances.list()
        return raised.value, calls
    finally:
        await client.aclose()
        await http.aclose()


async def test_invalid_subaccount_code_reaches_the_caller() -> None:
    assert ledger_read.ERROR_CODE_INVALID_SUBACCOUNT_ID == 11
    error, calls = await _balances_error(
        400, _body(ledger_read.ERROR_CODE_INVALID_SUBACCOUNT_ID, "invalid_argument")
    )
    assert calls == 1
    assert type(error) is PolyesterApiError
    assert error.code == "ERROR_CODE_INVALID_SUBACCOUNT_ID"
    assert not is_retryable_error(error)
    assert not mutation_outcome_unknown(error)


async def test_unavailable_ledger_detail_stays_a_server_failure() -> None:
    error, calls = await _balances_error(
        503, _body(ledger_read.ERROR_CODE_UPSTREAM_ERROR, "unavailable")
    )
    assert calls == 1
    assert type(error) is PolyesterServerError
    assert error.code == "ERROR_CODE_UPSTREAM_ERROR"
