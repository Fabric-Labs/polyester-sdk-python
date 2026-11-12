"""Encode OCO (one-cancels-the-other) creates for ``triggers.v1.TriggersService``."""

from __future__ import annotations

import uuid
from typing import Any

from polyester.codecs.correlation_id import required_client_id
from polyester.codecs.orders import _risk_leg_from_dict, _risk_leg_model_to_dict
from polyester.codecs.scalars import parse_account_id
from polyester.codecs.triggers import self_trade_prevention_mode_to_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.orders.v1 import orders_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.trading import RiskLeg
from polyester.types.money import resolve_qty_scaled


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

    ``client_list_id`` is the create's idempotency key; left out or empty, one
    is generated. A blank one raises ``PolyesterValidationError``.
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
        # The contract requires an ID. A blank one is a caller's mistake:
        # replacing it would hide that a retry can no longer find its first
        # attempt.
        client_list_id=(
            required_client_id(client_list_id, "client_list_id")
            if client_list_id
            else f"oco-{uuid.uuid4().hex[:12]}"
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
