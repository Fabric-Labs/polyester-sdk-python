from __future__ import annotations

import secrets
import time
import uuid
from decimal import Decimal

from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.types.money import (
    AssetAmount,
    QuantityDomain,
    resolve_asset_amount_scaled,
)

DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS = 5 * 60


def str_to_u128_proto(value: str | Decimal | AssetAmount, *, scale: int = 18) -> u128_pb2.U128:
    domain = QuantityDomain.LEDGER_E18 if scale == 18 else QuantityDomain.ASSET
    big = resolve_asset_amount_scaled(value, scale, "amount", domain=domain)
    return u128_pb2.U128(hi=big >> 64, lo=big & ((1 << 64) - 1))


def _nonce_to_u128(value: str | int) -> u128_pb2.U128:
    big = int(value)
    if big <= 0:
        raise PolyesterValidationError("nonce must be non-zero")
    if big >= 1 << 128:
        raise PolyesterValidationError("nonce exceeds uint128 range")
    return u128_pb2.U128(hi=big >> 64, lo=big & ((1 << 64) - 1))


def _default_deadline_ts_sec() -> int:
    now = int(time.time())
    if now < 0:
        raise PolyesterValidationError("system clock is before UNIX_EPOCH")
    return now + DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS


def trading_withdraw_payload_to_proto(
    *,
    action: str,
    asset_id: int,
    amount: str | Decimal | AssetAmount,
    idempotency_key: str,
    destination_chain_id: int = 0,
    deadline_ts_sec: int | None = None,
    nonce: str | int,
    destination_address: str = "",
    amount_scale: int = 18,
) -> withdraw_pb2.TradingWithdrawIntentPayload:
    if not idempotency_key.strip():
        raise PolyesterValidationError("idempotency_key is required")
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
    return withdraw_pb2.TradingWithdrawIntentPayload(
        action=action_enum,
        asset_id=asset_id,
        destination_chain_id=destination_chain_id,
        amount_e18=str_to_u128_proto(amount, scale=amount_scale),
        deadline_ts_sec=resolved_deadline,
        nonce=_nonce_to_u128(nonce),
        destination_address=destination_address,
        idempotency_key=idempotency_key,
    )


def new_trading_withdraw_idempotency_key() -> str:
    return str(uuid.uuid4())


def new_trading_withdraw_nonce() -> int:
    """Return a cryptographically random, non-zero uint128 nonce."""
    while True:
        nonce = secrets.randbits(128)
        if nonce:
            return nonce
