import os

import pytest

from polyester.models import LedgerWriteTransferResult
from tests.integration.support import call_optional


@pytest.mark.integration
@pytest.mark.optional
async def test_ledger_write_transfer_trading_to_trading_route(live_client) -> None:
    """Smoke only: verifies route/auth; does not execute a real transfer without explicit env."""
    if not os.getenv("POLYESTER_TEST_LEDGER_WRITE_SMOKE"):
        pytest.skip("Set POLYESTER_TEST_LEDGER_WRITE_SMOKE=1 to probe ledger_write mutations")
    to_account = os.getenv("POLYESTER_TEST_INTERNAL_TRANSFER_DEST")
    if not to_account:
        pytest.skip("POLYESTER_TEST_INTERNAL_TRANSFER_DEST required for ledger_write smoke")
    zipper = await live_client.zipper.get_deposit_withdraw_config()
    assets = zipper.raw.get("assets") or []
    if not assets:
        pytest.skip("zipper config missing assets")
    ledger_id = int(assets[0].get("ledgerId") or assets[0].get("ledger_id") or 0)
    if ledger_id <= 0:
        pytest.skip("cannot resolve ledger id")
    result = await call_optional(
        live_client.ledger_write.transfer_trading_to_trading(
            to_account_id=to_account,
            ledger_id=ledger_id,
            quantity="0.00000001",
        ),
        label="ledger_write.transfer_trading_to_trading",
    )
    assert isinstance(result, LedgerWriteTransferResult)
    assert result.transfer_id
