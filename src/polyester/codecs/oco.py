"""Encode OCO (one-cancels-the-other) creates for ``triggers.v1.TriggersService``."""

from __future__ import annotations

import uuid
from typing import Any

from polyester.codecs.orders import _risk_leg_from_dict, _risk_leg_model_to_dict
from polyester.codecs.scalars import parse_account_id
from polyester.codecs.triggers import self_trade_prevention_mode_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.trading import RiskLeg
from polyester.types.money import resolve_qty_scaled


def _contract_client_list_id_max_bytes() -> int:
    """The ``client_list_id`` byte limit the public contract sets."""
    field = triggers_pb2.OcoIntent.DESCRIPTOR.fields_by_name["client_list_id"]
    return int(field.GetOptions().Extensions[validate_pb2.field].string.max_bytes)


CLIENT_LIST_ID_MAX_BYTES = _contract_client_list_id_max_bytes()


def validate_client_list_id(value: object, field_name: str = "client_list_id") -> str:
    """Check a client list ID as the contract does: 1 to 36 bytes in UTF-8.

    Any characters are allowed. The ID is returned, and sent, exactly as given:
    it is not stripped or normalized.
    """
    if not isinstance(value, str):
        raise PolyesterValidationError(f"{field_name} must be a string")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise PolyesterValidationError(f"{field_name} must be valid UTF-8 text") from exc
    if size == 0 or size > CLIENT_LIST_ID_MAX_BYTES:
        raise PolyesterValidationError(
            f"{field_name} must be 1 to {CLIENT_LIST_ID_MAX_BYTES} bytes in UTF-8; got {size}"
        )
    return value


def _oco_leg(leg: RiskLeg | dict[str, Any], *, field_name: str, symbol: str) -> triggers_pb2.OcoLeg:
    """Encode one leg as an attached take-profit or stop-loss leg is encoded.

    A leg takes ``trigger_price``, ``order_type`` (``market``, the default, or
    ``limit``), ``limit_price`` for a limit exit and ``trigger_price_source``,
    or the proto-JSON ``trigger_price_ticks`` and ``child``.
    """
    if isinstance(leg, RiskLeg):
        leg = _risk_leg_model_to_dict(leg)
    policy = _risk_leg_from_dict(leg, field_name=field_name, symbol=symbol, risk_field="oco")
    return triggers_pb2.OcoLeg(
        trigger_price_ticks=policy.trigger_price_ticks,
        child=policy.child,
        trigger_price_source=policy.trigger_price_source,
    )


def create_oco_to_proto(
    *,
    symbol: str,
    symbol_id: int,
    side: str,
    qty: object,
    take_profit: RiskLeg | dict[str, Any],
    stop_loss: RiskLeg | dict[str, Any],
    quantity_scale: int,
    client_list_id: str | None = None,
    self_trade_prevention_mode: str | None = None,
    sub_account_id: str | int | None = None,
) -> triggers_pb2.CreateOcoRequest:
    """Encode an OCO over ``qty`` of ``symbol`` that both legs trade on ``side``.

    ``client_list_id`` is the create's idempotency key; left out (``None``),
    one is generated. Given, it must be 1 to 36 bytes in UTF-8, any
    characters, and is sent unchanged; otherwise ``PolyesterValidationError``.
    """
    if symbol_id <= 0:
        raise PolyesterValidationError("create OCO requires a resolved symbol_id")
    side_key = side.lower() if isinstance(side, str) else ""
    if side_key not in ("buy", "sell"):
        raise PolyesterValidationError("side must be buy or sell")
    intent = triggers_pb2.OcoIntent(
        symbol_id=symbol_id,
        side=orders_pb2.BUY if side_key == "buy" else orders_pb2.SELL,
        qty_scaled=resolve_qty_scaled(
            qty,  # type: ignore[arg-type]
            quantity_scale,
            "qty",
            symbol=symbol,
            symbol_id=symbol_id,
        ),
        # The contract requires an ID. An empty one is a caller's mistake:
        # replacing it would hide that a retry can no longer find its first
        # attempt.
        client_list_id=(
            f"oco-{uuid.uuid4().hex[:12]}"
            if client_list_id is None
            else validate_client_list_id(client_list_id)
        ),
    )
    if self_trade_prevention_mode is not None:
        intent.self_trade_prevention_mode = self_trade_prevention_mode_to_proto(
            self_trade_prevention_mode
        )
    intent.take_profit.CopyFrom(_oco_leg(take_profit, field_name="take_profit", symbol=symbol))
    intent.stop_loss.CopyFrom(_oco_leg(stop_loss, field_name="stop_loss", symbol=symbol))
    proto = triggers_pb2.CreateOcoRequest(oco=intent)
    if sub_account_id is not None:
        proto.subaccount_id = parse_account_id(sub_account_id, "sub_account_id")
    return proto
