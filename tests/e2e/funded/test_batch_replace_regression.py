"""F-01/M1: BatchReplace admission, status polling, and idempotency. Live-gated."""
from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal

import pytest

from polyester.models import ClientOrderId
from tests.e2e.helpers import unique_client_order_id, wait_for_open_order
from tests.helpers import (
    FAR_BELOW_BUY_PRICE_HINTS,
    DevnetOrderNotIndexedError,
    devnet_order_skip_message,
    min_base_qty_for_pair,
)

pytestmark = [
    pytest.mark.account_wide_cleanup,
    pytest.mark.usefixtures("account_wide_cleanup_enabled"),
]


async def _wait_for_batch_replace_settlement(client, batch_request_id: str) -> object:
    last_error: Exception | None = None
    for _ in range(60):
        try:
            status = await client.orders.get_batch_replace_status(
                batch_request_id=batch_request_id
            )
        except Exception as exc:  # projection can lag the admission receipt
            if "not found" not in str(exc).lower():
                raise
            last_error = exc
            await asyncio.sleep(0.5)
            continue
        phases = {item.phase for item in status.items}
        if phases and phases <= {"working", "rejected", "terminal"}:
            return status
        await asyncio.sleep(0.5)
    if last_error is not None:
        raise AssertionError(
            f"batch replace {batch_request_id} status not available: {last_error}"
        ) from last_error
    raise AssertionError(f"batch replace {batch_request_id} did not leave admission")


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_batch_replace_admission_status_and_idempotency(
    live_client, trade_symbol, funded_enabled, mutation_enabled, require_trade_trading_balance
):
    spot = await live_client.market_data.get_spot_config()
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == trade_symbol), {})
    price = FAR_BELOW_BUY_PRICE_HINTS.get(trade_symbol, "100")
    qty = min_base_qty_for_pair(pair, price)
    cids: list[str] = []
    all_cids: set[str] = set()
    try:
        with contextlib.suppress(Exception):
            await live_client.orders.cancel_all(symbol=trade_symbol)
        for index in range(20):
            cid = unique_client_order_id(f"br-{index}")
            await live_client.orders.create(
                symbol=trade_symbol,
                side="buy",
                order_type="limit",
                tif="gtc",
                qty=qty,
                price=price,
                post_only=True,
                client_order_id=cid,
            )
            try:
                await wait_for_open_order(live_client, cid, timeout=15)
            except DevnetOrderNotIndexedError:
                pytest.skip(devnet_order_skip_message())
            cids.append(cid)
            all_cids.add(cid)

        for round_i in range(5):
            replacement_price = format(
                Decimal(price) * (Decimal("0.99") - Decimal(round_i) * Decimal("0.001")),
                "f",
            )
            new_cids = [unique_client_order_id(f"br-r{round_i}-{index}") for index in range(20)]
            items = [
                {
                    "key": ClientOrderId(cid),
                    "new_price": replacement_price,
                    "new_client_order_id": new_cid,
                }
                for cid, new_cid in zip(cids, new_cids, strict=True)
            ]
            request_id = unique_client_order_id(f"br-request-{round_i}")
            receipt = await live_client.orders.batch_replace(
                items=items, symbol=trade_symbol, request_id=request_id
            )
            assert receipt.batch_request_id
            assert receipt.status in {"admitted", "partially_admitted", "rejected"}
            assert receipt.accepted_count + receipt.rejected_count == len(receipt.results)

            status = await _wait_for_batch_replace_settlement(
                live_client, receipt.batch_request_id
            )
            assert status.batch_request_id == receipt.batch_request_id

            retry = await live_client.orders.batch_replace(
                items=items, symbol=trade_symbol, request_id=request_id
            )
            assert retry.batch_request_id == receipt.batch_request_id
            assert retry.status == receipt.status
            cids = new_cids
            all_cids.update(new_cids)
    finally:
        with contextlib.suppress(Exception):
            await live_client.orders.cancel_all(symbol=trade_symbol)
