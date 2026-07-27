from __future__ import annotations

from polyester.errors import PolyesterResponseContractError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.models import WithdrawIntentResult


def withdraw_intent_from_proto(
    msg: withdraw_pb2.CreateTradingWithdrawResponse
    | withdraw_pb2.CreateWalletTradingWithdrawResponse,
) -> WithdrawIntentResult:
    if not msg.intent_id.strip():
        raise PolyesterResponseContractError(
            type(msg).__name__, "missing intent_id"
        )
    return WithdrawIntentResult(intent_id=msg.intent_id)
