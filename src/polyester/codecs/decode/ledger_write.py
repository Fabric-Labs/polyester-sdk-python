from __future__ import annotations

from polyester.codecs.ledger_write import ledger_write_transfer_from_proto
from polyester.gen.ledger.write.v1 import ledger_write_pb2
from polyester.models import LedgerWriteTransferResult


def ledger_write_transfer_result_from_proto(
    msg: ledger_write_pb2.TransferTradingToTradingResponse
    | ledger_write_pb2.CreateFundingUserTransferResponse
    | ledger_write_pb2.ReserveTradingWithdrawResponse
    | ledger_write_pb2.ReleaseTradingWithdrawReserveResponse,
) -> LedgerWriteTransferResult:
    transfer_id, timestamp = ledger_write_transfer_from_proto(msg)
    return LedgerWriteTransferResult(transfer_id=transfer_id, timestamp=timestamp)
