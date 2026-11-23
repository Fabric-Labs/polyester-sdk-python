"""Encode OCO (one-cancels-the-other) creates for ``triggers.v1.TriggersService``.

The rules are ``polyester.pure``'s; this module converts the SDK's models,
generates a missing ``client_list_id`` and fills the generated message.
"""

from __future__ import annotations

import uuid
from typing import Any

from polyester.codecs.orders import _risk_leg_model_to_dict
from polyester.codecs.pure_bridge import call, message, pure
from polyester.gen.buf.validate import validate_pb2
from polyester.gen.triggers.v1 import triggers_pb2
from polyester.models.trading import RiskLeg


def _contract_client_list_id_max_len() -> int:
    """The ``client_list_id`` length limit the public contract sets."""
    field = triggers_pb2.OcoIntent.DESCRIPTOR.fields_by_name["client_list_id"]
    return int(field.GetOptions().Extensions[validate_pb2.field].string.max_len)


# Read from the contract; polyester.pure holds the same limit, tested equal.
CLIENT_LIST_ID_MAX_LEN = _contract_client_list_id_max_len()


def validate_client_list_id(value: object, field_name: str = "client_list_id") -> str:
    """Check a client list ID as the contract does, with the client order ID
    rule: 1 to 36 ASCII letters, digits, ``.``, ``_``, ``:``, ``/`` or ``-``.

    The ID is returned, and sent, exactly as given: it is not stripped or
    normalized, so an ID with outer spaces is refused. A refusal carries
    ``ERROR_CODE_CLIENT_LIST_ID_INVALID``, the code the API answers.
    """
    return call(pure._client_list_id, value, field_name)


def _leg_input(leg: RiskLeg | dict[str, Any]) -> object:
    return _risk_leg_model_to_dict(leg) if isinstance(leg, RiskLeg) else leg


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
    one is generated. ``self_trade_prevention_mode`` ``decrement`` and a leg's
    ``trigger_price_source`` ``mark``, which the contract does not support on an
    OCO, raise ``PolyesterValidationError``. A given ``client_list_id`` must follow
    the client order ID rule (1 to 36 ASCII letters, digits, ``.``, ``_``, ``:``,
    ``/`` or ``-``) and is sent unchanged; otherwise ``PolyesterValidationError``.
    Each leg is encoded as an order's attached take-profit or stop-loss leg; a
    refused trigger price answers ``TRIGGER_PRICE_INVALID`` and a refused limit
    price ``BAD_PRICE``, as the API answers them for an OCO.
    """
    built = call(
        pure._oco_request,
        symbol,
        symbol_id,
        side,
        qty,
        _leg_input(take_profit),
        _leg_input(stop_loss),
        quantity_scale,
        client_list_id,
        self_trade_prevention_mode,
        sub_account_id,
    )
    # The contract requires an ID; one left out is generated, never an empty one.
    built["oco"].setdefault("clientListId", f"oco-{uuid.uuid4().hex[:12]}")
    return message(built, triggers_pb2.CreateOcoRequest())
