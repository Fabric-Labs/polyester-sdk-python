"""Enum numbers and names the SDK does not know yet degrade instead of raising.

The server adds error codes and enum values ahead of SDK releases. A newer
value must reach the caller as a labelled error or a default field, never as
a ``ValueError`` from the SDK's own error mapping or decoding.
"""

from __future__ import annotations

import pytest
from connectrpc.code import Code
from connectrpc.errors import ConnectError

from polyester._wire import map_connect_error
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRateLimitError,
)
from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.polyester.ratelimit.v1 import types_pb2 as ratelimit_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.transport import TransportConfig, codec_for_config

UNKNOWN = 999
API_URL = "https://api.example.test"


@pytest.mark.parametrize(
    "detail",
    [
        orders_pb2.ErrorDetail(code=UNKNOWN),
        auth_pb2.AuthErrorDetail(code=UNKNOWN),
        withdraw_pb2.ErrorDetail(code=UNKNOWN),
        transfer_pb2.ErrorDetail(code=UNKNOWN),
    ],
    ids=["orders", "auth", "withdraw", "transfer"],
)
def test_unknown_error_code_maps_to_a_labelled_api_error(detail: object) -> None:
    mapped = map_connect_error(
        ConnectError(Code.FAILED_PRECONDITION, "refused", details=[detail])  # type: ignore[list-item]
    )
    assert type(mapped) is PolyesterApiError
    assert mapped.code == f"UNKNOWN_ERROR_CODE({UNKNOWN})"
    assert str(mapped) == "refused"


def test_unknown_orders_code_with_rate_limit_detail_is_still_a_rate_limit() -> None:
    detail = orders_pb2.ErrorDetail(
        code=UNKNOWN,
        rate_limit=ratelimit_pb2.RateLimitDetail(retry_after_ms=1500),
    )
    mapped = map_connect_error(ConnectError(Code.RESOURCE_EXHAUSTED, "slow down", details=[detail]))
    assert isinstance(mapped, PolyesterRateLimitError)
    assert mapped.retry_after == 1.5


def test_known_error_codes_keep_their_names_and_classes() -> None:
    rate_limited = map_connect_error(
        ConnectError(
            Code.RESOURCE_EXHAUSTED,
            "slow down",
            details=[orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_RATE_LIMIT_EXCEEDED)],
        )
    )
    assert isinstance(rate_limited, PolyesterRateLimitError)

    terminal = map_connect_error(
        ConnectError(
            Code.FAILED_PRECONDITION,
            "done",
            details=[orders_pb2.ErrorDetail(code=orders_pb2.ERROR_CODE_ORDER_ALREADY_TERMINAL)],
        )
    )
    assert type(terminal) is PolyesterApiError
    assert terminal.code == "ERROR_CODE_ORDER_ALREADY_TERMINAL"

    withdraw = map_connect_error(
        ConnectError(
            Code.PERMISSION_DENIED,
            "denied",
            details=[withdraw_pb2.ErrorDetail(code=withdraw_pb2.ERROR_CODE_PERMISSION_DENIED)],
        )
    )
    assert isinstance(withdraw, PolyesterAuthError)


def test_json_wire_format_tolerates_unknown_enum_names_and_fields() -> None:
    codec = codec_for_config(TransportConfig(api_url=API_URL, wire_format="json"))
    payload = (
        b'{"triggerId": "5",'
        b' "failureReason": "TRIGGER_FAILURE_REASON_NOT_YET_IN_THIS_SDK",'
        b' "fieldNotYetInThisSdk": 1}'
    )
    trigger = codec.decode(payload, triggers_pb2.Trigger())
    assert trigger.trigger_id == 5
    # An enum name this SDK does not know reads as the unspecified value.
    assert trigger.failure_reason == 0
    # Unknown enum numbers are kept as numbers.
    numeric = codec.decode(b'{"failureReason": 241}', triggers_pb2.Trigger())
    assert numeric.failure_reason == 241


def test_json_wire_format_round_trips_requests() -> None:
    codec = codec_for_config(TransportConfig(api_url=API_URL, wire_format="json"))
    assert codec.name() == "json"
    message = triggers_pb2.Trigger(trigger_id=7, failure_reason=1)
    assert codec.decode(codec.encode(message), triggers_pb2.Trigger()) == message
