from __future__ import annotations

from polyester.codecs.decode.balances import u128_from_proto
from polyester.gen.ledger.read.v1 import ledger_read_pb2
from polyester.models import LedgerTransfer, TransfersList


def ledger_transfer_from_proto(msg: ledger_read_pb2.TransferRow) -> LedgerTransfer:
    return LedgerTransfer(
        asset_id=int(msg.asset_id),
        amount=u128_from_proto(msg.amount_e18),
        transfer_type=int(msg.transfer_code),
        account_code=int(msg.account_code),
        timestamp=int(msg.ts_us),
        pending=False,
        tx_id=msg.flow_id,
        is_debit=bool(msg.is_debit),
    )


def transfers_list_from_proto(msg: ledger_read_pb2.ListTransfersResponse) -> TransfersList:
    transfers = [ledger_transfer_from_proto(item) for item in msg.transfers]
    next_cursor: int | None = None
    if msg.next_page_token:
        try:
            parsed = int(msg.next_page_token)
            if parsed != 0:
                next_cursor = parsed
        except ValueError:
            next_cursor = None
    return TransfersList(transfers=transfers, next_cursor=next_cursor)
