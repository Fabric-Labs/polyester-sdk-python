"""Classification of the order error codes 86-94 (trigger and leg refusals)."""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.codecs.decode.orders import order_from_proto
from polyester.errors import (
    PolyesterApiError,
    PolyesterRateLimitError,
    is_retryable_error,
    mutation_outcome_unknown,
)
from polyester.gen.orders.v1 import orders_pb2, orders_read_pb2

# These refusals change nothing. TWAP capacity explicitly permits retrying later.
_NEW_CODES = [
    orders_pb2.ERROR_CODE_ATTACHED_LEGS_EXCEEDED,
    orders_pb2.ERROR_CODE_FEE_ASSET_INVALID,
    orders_pb2.ERROR_CODE_FEE_CEILING_INVALID,
    orders_pb2.ERROR_CODE_UNSUPPORTED_FIELD_SET,
    orders_pb2.ERROR_CODE_TRIGGER_FIRE_LIMIT_REACHED,
    orders_pb2.ERROR_CODE_CONDITION_FLAGS_INVALID,
    orders_pb2.ERROR_CODE_CONDITION_PARAMETER_SET,
    orders_pb2.ERROR_CODE_TWAP_CAPACITY_REACHED,
    orders_pb2.ERROR_CODE_CHILD_ORDER_INCONSISTENT,
]


def test_new_codes_are_86_to_94() -> None:
    assert sorted(_NEW_CODES) == list(range(86, 95))


@pytest.mark.parametrize(
    "connect_code",
    [Code.INVALID_ARGUMENT, Code.FAILED_PRECONDITION, Code.RESOURCE_EXHAUSTED],
    ids=lambda code: code.value,
)
@pytest.mark.parametrize("code", _NEW_CODES, ids=orders_pb2.ErrorCode.Name)
def test_new_codes_follow_contract_retry_guidance(code: int, connect_code: Code) -> None:
    mapped = map_connect_error(
        ConnectError(connect_code, "refused", details=[orders_pb2.ErrorDetail(code=code)])
    )
    retryable = code == orders_pb2.ERROR_CODE_TWAP_CAPACITY_REACHED
    assert type(mapped) is (PolyesterRateLimitError if retryable else PolyesterApiError)
    assert mapped.code == orders_pb2.ErrorCode.Name(code)
    assert is_retryable_error(mapped) is retryable
    assert not mutation_outcome_unknown(mapped)


@pytest.mark.parametrize(
    ("code", "label"),
    [
        (orders_pb2.ERROR_CODE_ATTACHED_LEGS_EXCEEDED, "ATTACHED_LEGS_EXCEEDED"),
        (orders_pb2.ERROR_CODE_TWAP_CAPACITY_REACHED, "TWAP_CAPACITY_REACHED"),
        (orders_pb2.ERROR_CODE_CHILD_ORDER_INCONSISTENT, "CHILD_ORDER_INCONSISTENT"),
        (orders_pb2.ERROR_CODE_TRIGGER_FIRE_LIMIT_REACHED, "TRIGGER_FIRE_LIMIT_REACHED"),
    ],
)
def test_rejected_order_names_a_new_code(code: int, label: str) -> None:
    order = order_from_proto(
        orders_read_pb2.Order(
            order_id=1, symbol_id=101, status=orders_read_pb2.REJECTED, reject_reason=code
        )
    )
    assert order.reject_reason == label
