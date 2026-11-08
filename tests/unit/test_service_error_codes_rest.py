"""A refusal reads the same ``ERROR_CODE_`` code over REST and ConnectRPC.

The REST problem body names the code without its prefix (``SAME_SOURCE_DESTINATION``);
the typed ConnectRPC detail carries the service's enum value. Transfer,
withdraw and ledger codes read like order codes either way.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

from polyester.errors import PolyesterApiError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from tests.unit.test_auth_error_codes import _rest_error

REFUSALS = [
    pytest.param(transfer_pb2, "transfer.v1.ErrorDetail", "SAME_SOURCE_DESTINATION", id="transfer"),
    pytest.param(
        transfer_pb2, "transfer.v1.ErrorDetail", "INSUFFICIENT_FUNDS", id="transfer_funds"
    ),
    pytest.param(
        withdraw_pb2, "chain.withdraw.v1.ErrorDetail", "AMOUNT_BELOW_MINIMUM", id="withdraw"
    ),
    pytest.param(
        ledger_read_pb2, "ledger.read.v1.ErrorDetail", "INVALID_SUBACCOUNT_ID", id="ledger"
    ),
    pytest.param(orders_pb2, "orders.v1.ErrorDetail", "QTY_STEP_SIZE", id="orders"),
]


async def _typed_error(httpserver: Any, module: Any, detail_type: str, name: str) -> BaseException:
    detail = module.ErrorDetail(code=module.ErrorCode.Value("ERROR_CODE_" + name))
    body = {
        "code": "invalid_argument",
        "message": "refused",
        "details": [
            {
                "type": detail_type,
                "value": base64.b64encode(detail.SerializeToString()).decode(),
            }
        ],
    }
    return await _rest_error(httpserver, 400, body, content_type="application/json")


@pytest.mark.parametrize(("module", "detail_type", "name"), REFUSALS)
async def test_refusal_code_is_the_same_over_rest_and_connect(
    httpserver: Any, module: Any, detail_type: str, name: str
) -> None:
    typed = await _typed_error(httpserver, module, detail_type, name)
    httpserver.clear()
    rest = await _rest_error(httpserver, 400, {"code": name, "detail": "refused"})
    assert isinstance(typed, PolyesterApiError)
    assert isinstance(rest, PolyesterApiError)
    assert typed.code == "ERROR_CODE_" + name
    assert rest.code == "ERROR_CODE_" + name
