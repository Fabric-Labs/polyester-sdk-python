from __future__ import annotations

from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.models import WithdrawIntentResult


def withdraw_intent_from_proto(
    msg: withdraw_pb2.CreateTradingWithdrawResponse
    | withdraw_pb2.CreateWalletTradingWithdrawResponse,
) -> WithdrawIntentResult:
    return WithdrawIntentResult(intent_id=msg.intent_id)
