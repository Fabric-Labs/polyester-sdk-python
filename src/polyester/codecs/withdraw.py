from __future__ import annotations

import secrets
import time
import uuid
from decimal import Decimal

from polyester.codecs.scalars import UINT32_MAX, UINT64_MAX, exact_integer
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.polyester.type.v1 import u128_pb2
from polyester.types.money import (
    AssetAmount,
    resolve_asset_amount_scaled_with_input_scale,
)

DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS = 5 * 60
UINT128_MAX = 2**128 - 1


def str_to_u128_proto(
    value: str | Decimal | AssetAmount,
    *,
    scale: int | None = None,
    asset_id: int | None = None,
) -> u128_pb2.U128:
    """Encode an amount declared at ``scale`` into exact ledger scale-18 units."""
    big = resolve_asset_amount_scaled_with_input_scale(
        value,
        scale if isinstance(value, AssetAmount) or scale is not None else 18,
        18,
        "amount",
        asset_id=asset_id,
    )
    return u128_pb2.U128(hi=big >> 64, lo=big & ((1 << 64) - 1))


def _nonce_to_u128(value: str | int) -> u128_pb2.U128:
    big = exact_integer(value, "nonce", min_value=1, max_value=UINT128_MAX, allow_str=True)
    return u128_pb2.U128(hi=big >> 64, lo=big & ((1 << 64) - 1))


def trading_withdraw_deadline(value: str | int) -> int:
    """A caller's ``deadline_ts_sec``: an integer or decimal-integer string, 1 to 2**64 - 1."""
    return exact_integer(
        value, "deadline_ts_sec", min_value=1, max_value=UINT64_MAX, allow_str=True
    )


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
    deadline_ts_sec: str | int | None = None,
    nonce: str | int,
    destination_address: str = "",
    amount_scale: int | None = None,
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
        raise PolyesterValidationError(f"unknown trading withdraw action: {action}")
    # Every integer the payload signs is exactly the caller's: never truncated
    # or cast (nonce 1.5 must not sign as nonce 1).
    resolved_asset_id = exact_integer(asset_id, "asset_id", min_value=1, max_value=UINT32_MAX)
    resolved_chain_id = exact_integer(
        destination_chain_id, "destination_chain_id", min_value=0, max_value=UINT64_MAX
    )
    resolved_deadline = (
        _default_deadline_ts_sec()
        if deadline_ts_sec is None
        else trading_withdraw_deadline(deadline_ts_sec)
    )
    resolved_nonce = _nonce_to_u128(nonce)
    return withdraw_pb2.TradingWithdrawIntentPayload(
        action=action_enum,
        asset_id=resolved_asset_id,
        destination_chain_id=resolved_chain_id,
        amount_e18=str_to_u128_proto(amount, scale=amount_scale, asset_id=resolved_asset_id),
        deadline_ts_sec=resolved_deadline,
        nonce=resolved_nonce,
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
