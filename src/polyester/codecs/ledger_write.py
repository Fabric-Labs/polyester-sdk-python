from __future__ import annotations

import uuid

from polyester.codecs.ledger_amounts import LEDGER_SCALE
from polyester.codecs.scalars import id_to_int
from polyester.codecs.withdraw import str_to_u128_proto
from polyester.errors import PolyesterValidationError
from polyester.gen.ledger.write.v1 import ledger_write_pb2


def decimal_to_amount_units_proto(
    amount: str,
    *,
    scale: int = LEDGER_SCALE,
) -> ledger_write_pb2.U128:
    units = str_to_u128_proto(amount, scale=scale)
    return ledger_write_pb2.U128(hi=units.hi, lo=units.lo)


def ledger_write_transfer_from_proto(
    msg: ledger_write_pb2.TransferTradingToTradingResponse
    | ledger_write_pb2.CreateFundingUserTransferResponse
    | ledger_write_pb2.ReserveTradingWithdrawResponse
    | ledger_write_pb2.ReleaseTradingWithdrawReserveResponse,
) -> tuple[str, int]:
    return msg.transfer_id, int(msg.timestamp)


def transfer_trading_to_trading_to_proto(
    *,
    from_account_id: str | int,
    to_account_id: str | int,
    ledger_id: int,
    quantity: str,
    request_id: str | None = None,
    quantity_scale: int = LEDGER_SCALE,
) -> ledger_write_pb2.TransferTradingToTradingRequest:
    if ledger_id <= 0:
        raise PolyesterValidationError("ledger_id must be positive")
    return ledger_write_pb2.TransferTradingToTradingRequest(
        request_id=request_id or str(uuid.uuid4()),
        from_account_id=id_to_int(from_account_id, "from_account_id"),
        to_account_id=id_to_int(to_account_id, "to_account_id"),
        ledger=ledger_id,
        amount_units=decimal_to_amount_units_proto(quantity, scale=quantity_scale),
    )


def create_funding_user_transfer_to_proto(
    *,
    from_account_id: str | int,
    to_account_id: str | int,
    ledger_id: int,
    quantity: str,
    intent_id: str | None = None,
    quantity_scale: int = LEDGER_SCALE,
) -> ledger_write_pb2.CreateFundingUserTransferRequest:
    if ledger_id <= 0:
        raise PolyesterValidationError("ledger_id must be positive")
    return ledger_write_pb2.CreateFundingUserTransferRequest(
        intent_id=intent_id or str(uuid.uuid4()),
        from_account_id=id_to_int(from_account_id, "from_account_id"),
        to_account_id=id_to_int(to_account_id, "to_account_id"),
        ledger=ledger_id,
        amount_units=decimal_to_amount_units_proto(quantity, scale=quantity_scale),
    )


def reserve_trading_withdraw_to_proto(
    *,
    account_id: str | int,
    ledger_id: int,
    quantity: str,
    intent_id: str | None = None,
    quantity_scale: int = LEDGER_SCALE,
) -> ledger_write_pb2.ReserveTradingWithdrawRequest:
    if ledger_id <= 0:
        raise PolyesterValidationError("ledger_id must be positive")
    return ledger_write_pb2.ReserveTradingWithdrawRequest(
        intent_id=intent_id or str(uuid.uuid4()),
        account_id=id_to_int(account_id, "account_id"),
        ledger=ledger_id,
        amount_units=decimal_to_amount_units_proto(quantity, scale=quantity_scale),
    )


def release_trading_withdraw_reserve_to_proto(
    *,
    account_id: str | int,
    ledger_id: int,
    intent_id: str,
    close_scope: str = "",
) -> ledger_write_pb2.ReleaseTradingWithdrawReserveRequest:
    if ledger_id <= 0:
        raise PolyesterValidationError("ledger_id must be positive")
    if not intent_id:
        raise PolyesterValidationError("intent_id is required")
    return ledger_write_pb2.ReleaseTradingWithdrawReserveRequest(
        intent_id=intent_id,
        account_id=id_to_int(account_id, "account_id"),
        ledger=ledger_id,
        close_scope=close_scope,
    )
