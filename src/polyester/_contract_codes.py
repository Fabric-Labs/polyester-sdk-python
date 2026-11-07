"""Which REST error codes the published contract defines."""

from __future__ import annotations

from polyester.gen.auth.v1 import auth_pb2
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.transfer.v1 import internal_transfer_pb2 as transfer_pb2

_ENUM_CODES = frozenset(
    name
    for enum in (
        auth_pb2.AuthErrorCode,
        orders_pb2.ErrorCode,
        withdraw_pb2.ErrorCode,
        transfer_pb2.ErrorCode,
        ledger_read_pb2.ErrorCode,
    )
    for name in enum.DESCRIPTOR.values_by_name
)

# Contract REST codes that no generated error enum names.
_REST_ONLY_CODES = frozenset(
    {
        "API_KEY_ACTION_DENY",
        "API_KEY_POLICY_NOT_FOUND",
        "INVALID_BEFORE_TS_NS",
        "INVALID_DEPTH",
        "INVALID_END_TIME",
        "INVALID_LIMIT",
        "INVALID_OFFSET",
        "INVALID_ORDER_STATUS",
        "INVALID_PAGE_TOKEN",
        "INVALID_START_TIME",
        "INVALID_SYMBOL",
        "INVALID_TRIGGER_ID",
        "INVALID_TRIGGER_STATUS",
        "ORDER_ID_REQUIRED",
        "REQUEST_TOO_LARGE",
        "ROLE_ACTION_DENY",
        "ROLE_SPOT_TRADE_DENY",
        "SERVER_ERROR",
        "SUBACCOUNT_POLICY_DENY",
        "TRAILING_STOP_ORDER_TYPE_UNSUPPORTED",
        "TRIGGER_ID_REQUIRED",
    }
)


def is_recognised_rest_code(code: str) -> bool:
    """Whether the contract defines this REST problem ``code``.

    A mutation's unknown outcome is recognised by its suffix, including one
    added to the contract after this SDK was generated.
    """
    return (
        code in _REST_ONLY_CODES
        or code in _ENUM_CODES
        or f"ERROR_CODE_{code}" in _ENUM_CODES
        or f"AUTH_{code}" in _ENUM_CODES
        or code.endswith("_OUTCOME_UNKNOWN")
    )
