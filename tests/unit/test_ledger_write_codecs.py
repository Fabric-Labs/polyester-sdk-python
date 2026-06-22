import time

import pytest

from polyester.codecs.decode.ledger_write import ledger_write_transfer_result_from_proto
from polyester.codecs.ledger_write import (
    create_funding_user_transfer_to_proto,
    ledger_write_transfer_from_proto,
    release_trading_withdraw_reserve_to_proto,
    reserve_trading_withdraw_to_proto,
    transfer_trading_to_trading_to_proto,
)
from polyester.codecs.withdraw import (
    DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS,
    new_trading_withdraw_idempotency_key,
    trading_withdraw_payload_to_proto,
)
from polyester.errors import PolyesterValidationError
from polyester.gen.chain.withdraw.v1 import withdraw_pb2
from polyester.gen.ledger.write.v1 import ledger_write_pb2


def test_transfer_trading_to_trading_to_proto_scales_amount() -> None:
    req = transfer_trading_to_trading_to_proto(
        from_account_id="1",
        to_account_id="2",
        ledger_id=42,
        quantity="1.5",
    )
    assert req.from_account_id == 1
    assert req.to_account_id == 2
    assert req.ledger == 42
    assert req.amount_units.lo == 1_500_000_000_000_000_000


def test_transfer_trading_to_trading_rejects_invalid_ledger() -> None:
    with pytest.raises(PolyesterValidationError):
        transfer_trading_to_trading_to_proto(
            from_account_id=1,
            to_account_id=2,
            ledger_id=0,
            quantity="1",
        )


def test_create_funding_user_transfer_to_proto() -> None:
    req = create_funding_user_transfer_to_proto(
        from_account_id=10,
        to_account_id=20,
        ledger_id=7,
        quantity="0.01",
        intent_id="intent-abc",
    )
    assert req.intent_id == "intent-abc"
    assert req.from_account_id == 10
    assert req.ledger == 7


def test_reserve_and_release_trading_withdraw_to_proto() -> None:
    reserve = reserve_trading_withdraw_to_proto(
        account_id=99,
        ledger_id=3,
        quantity="5",
        intent_id="reserve-1",
    )
    assert reserve.intent_id == "reserve-1"
    assert reserve.account_id == 99

    release = release_trading_withdraw_reserve_to_proto(
        account_id=99,
        ledger_id=3,
        intent_id="reserve-1",
        close_scope="test",
    )
    assert release.intent_id == "reserve-1"
    assert release.close_scope == "test"


def test_ledger_write_transfer_from_proto() -> None:
    msg = ledger_write_pb2.TransferTradingToTradingResponse(
        transfer_id="xfer-1",
        timestamp=123,
    )
    assert ledger_write_transfer_from_proto(msg) == ("xfer-1", 123)
    result = ledger_write_transfer_result_from_proto(msg)
    assert result.transfer_id == "xfer-1"
    assert result.timestamp == 123


def test_trading_withdraw_payload_defaults_deadline_and_nonce() -> None:
    before = int(time.time())
    payload = trading_withdraw_payload_to_proto(
        action="to_funding",
        asset_id=1,
        amount="10",
        idempotency_key=new_trading_withdraw_idempotency_key(),
    )
    after = int(time.time())
    assert payload.action == withdraw_pb2.TO_FUNDING
    assert before + DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS <= payload.deadline_ts_sec <= (
        after + DEFAULT_TRADING_WITHDRAW_DEADLINE_SECONDS
    )
    assert payload.nonce.lo > 0
