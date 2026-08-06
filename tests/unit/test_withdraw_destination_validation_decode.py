from __future__ import annotations

import pytest

from polyester.codecs.decode.withdraw import (
    withdraw_destination_validation_code_label,
    withdraw_destination_validation_from_proto,
)
from polyester.gen.chain.withdraw.v1 import withdraw_pb2


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (withdraw_pb2.RESULT_UNSPECIFIED, "unspecified"),
        (withdraw_pb2.VALID, "valid"),
        (withdraw_pb2.INVALID_ADDRESS, "invalid_address"),
        (withdraw_pb2.UNSUPPORTED_CHAIN, "unsupported_chain"),
        (withdraw_pb2.POLYESTER_SMART_ACCOUNT, "polyester_smart_account"),
        (withdraw_pb2.TOKEN_CONTRACT, "token_contract"),
        (withdraw_pb2.DENYLISTED_ADDRESS, "denylisted_address"),
        (99, "unknown_code_99"),
    ],
)
def test_withdraw_destination_validation_code_labels(code: int, expected: str) -> None:
    assert withdraw_destination_validation_code_label(code) == expected


def test_withdraw_destination_validation_from_proto() -> None:
    result = withdraw_destination_validation_from_proto(
        withdraw_pb2.ValidateWithdrawDestinationResponse(
            valid=False,
            code=withdraw_pb2.DENYLISTED_ADDRESS,
            message="blocked",
        )
    )
    assert result.valid is False
    assert result.code == "denylisted_address"
    assert result.message == "blocked"
    assert result.canonical_destination_address == ""
