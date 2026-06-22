from __future__ import annotations

import time
import uuid
from decimal import Decimal

from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.polyester.type.v1 import u128_pb2

DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS = 5 * 60


def str_to_u128_proto(value: str | int, *, scale: int = 18) -> u128_pb2.U128:
    amount = Decimal(str(value)) * (Decimal(10) ** scale)
    big = int(amount.to_integral_value())
    return u128_pb2.U128(hi=big >> 64, lo=big & ((1 << 64) - 1))


def _default_deadline_ts_sec() -> int:
    return int(time.time()) + DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS


def _default_nonce() -> int:
    nonce = time.time_ns()
    return nonce if nonce > 0 else 1


def trading_withdraw_payload_to_proto(
    *,
    action: str,
    asset_id: int,
    amount: str,
    idempotency_key: str,
    destination_chain_id: int = 0,
    deadline_ts_sec: int | None = None,
    nonce: str | int | None = None,
    destination_address: str = "",
    amount_scale: int = 18,
) -> withdraw_pb2.TradingWithdrawIntentPayload:
    action_aliases = {
        "to_funding": withdraw_pb2.TO_FUNDING,
        "to_external_chain": withdraw_pb2.TO_EXTERNAL_CHAIN,
    }
    action_key = action.lower().replace("-", "_")
    action_enum = action_aliases.get(action_key)
    if action_enum is None:
        enum_name = action_key.upper()
        if not enum_name.startswith("TO_"):
            enum_name = f"TO_{enum_name}"
        action_enum = getattr(withdraw_pb2, enum_name, withdraw_pb2.ACTION_UNSPECIFIED)
    resolved_deadline = deadline_ts_sec if deadline_ts_sec else _default_deadline_ts_sec()
    resolved_nonce = nonce if nonce is not None else _default_nonce()
    return withdraw_pb2.TradingWithdrawIntentPayload(
        action=action_enum,
        asset_id=asset_id,
        destination_chain_id=destination_chain_id,
        amount_e18=str_to_u128_proto(amount, scale=amount_scale),
        deadline_ts_sec=resolved_deadline,
        nonce=str_to_u128_proto(str(resolved_nonce), scale=0),
        destination_address=destination_address,
        idempotency_key=idempotency_key,
    )


def new_trading_withdraw_idempotency_key() -> str:
    return str(uuid.uuid4())
