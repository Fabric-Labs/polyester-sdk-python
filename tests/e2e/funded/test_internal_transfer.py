import asyncio
import os
import uuid
from decimal import Decimal

import pytest

from polyester.codecs.ledger_amounts import LEDGER_SCALE
from tests.helpers import (
    quote_asset_id_for_symbol,
    trading_balance_decimal,
)


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_internal_transfer_tiny(
    live_client,
    trade_symbol,
    funded_enabled,
    mutation_enabled,
    require_trade_trading_balance,
):
    dest = os.getenv("POLYESTER_TEST_INTERNAL_TRANSFER_DEST")
    if not dest:
        pytest.skip("Set POLYESTER_TEST_INTERNAL_TRANSFER_DEST for internal transfer e2e")

    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    if not live_client.catalogs.zipper:
        zipper = await live_client.zipper.get_deposit_withdraw_config()
        live_client.catalogs.hydrate_zipper_config(zipper)

    asset_id = quote_asset_id_for_symbol(
        spot.raw,
        trade_symbol,
        zipper_raw=live_client.catalogs.zipper_config,
    )
    if asset_id is None:
        pytest.skip(f"Cannot resolve quote asset for internal transfer on {trade_symbol}")

    quantity = os.getenv("POLYESTER_TEST_INTERNAL_TRANSFER_QTY", "1")
    qty = Decimal(quantity)

    before = await live_client.balances.list()
    trading_before = trading_balance_decimal(before, asset_id)
    if trading_before < qty:
        pytest.skip(
            f"Trading balance {trading_before} below transfer quantity {qty} for asset {asset_id}"
        )

    result = await live_client.internal_transfers.create(
        asset_id=asset_id,
        quantity=str(quantity),
        destination_account_id=dest,
        idempotency_key=f"e2e-xfer-{uuid.uuid4().hex[:12]}",
        quantity_scale=LEDGER_SCALE,
    )
    assert result.request_id or result.transfer_id
    assert result.quantity is not None
    assert result.quantity.scaled == int(qty * Decimal(10**LEDGER_SCALE))

    expected_after = trading_before - qty
    trading_after = trading_before
    for _ in range(20):
        await asyncio.sleep(0.5)
        after = await live_client.balances.list()
        trading_after = trading_balance_decimal(after, asset_id)
        if trading_after == expected_after:
            break
    assert trading_after == expected_after
