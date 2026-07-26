"""F-01/M1: blocking BatchModify regression (5×40 + idempotent retry). Live-gated."""

from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal

import pytest

from tests.e2e.helpers import unique_client_order_id, wait_for_open_order
from tests.helpers import (
    FAR_BELOW_BUY_PRICE_HINTS,
    DevnetOrderNotIndexedError,
    batch_results_are_all_internal_error,
    devnet_order_skip_message,
    min_base_qty_for_pair,
)


def _assert_complete_batch_result(result, *, expected_cids: set[str], round_i: int) -> None:
    assert len(result.results) == 40, (
        f"round {round_i}: expected 40 result items, got {len(result.results)}"
    )
    if batch_results_are_all_internal_error(result.results):
        pytest.skip(devnet_order_skip_message())
    assert result.rejected_count == 0, (
        f"round {round_i}: expected no rejected, got {result.rejected_count}; "
        f"sample={[ (r.client_order_id, r.code) for r in result.results[:3] ]}"
    )
    assert result.amended_count + result.replaced_count == 40, (
        f"round {round_i}: amended+replaced="
        f"{result.amended_count}+{result.replaced_count} != 40"
    )
    seen = {item.client_order_id for item in result.results if item.client_order_id}
    missing = expected_cids - seen
    assert not missing, f"round {round_i}: missing client_order_ids in results: {sorted(missing)}"
    for item in result.results:
        assert item.status.lower() != "rejected", f"round {round_i}: rejected item {item}"


def _result_fingerprint(result) -> list[tuple[str, str, str]]:
    return sorted(
        (item.client_order_id, item.status, item.final_order_id) for item in result.results
    )


async def _wait_zero_open_test_orders(client, cids: set[str], *, timeout: float = 30) -> None:
    attempts = max(1, int(timeout / 0.5))
    for _ in range(attempts):
        open_orders = await client.orders.list_open(limit=100)
        remaining = {o.client_order_id for o in open_orders.orders if o.client_order_id in cids}
        if not remaining:
            return
        await asyncio.sleep(0.5)
    open_orders = await client.orders.list_open(limit=100)
    remaining = {o.client_order_id for o in open_orders.orders if o.client_order_id in cids}
    raise AssertionError(f"open test orders remain after cleanup: {sorted(remaining)}")


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_batch_modify_five_rounds_of_forty(
    live_client, trade_symbol, funded_enabled, mutation_enabled, require_trade_trading_balance
):
    print(f"trade_symbol={trade_symbol}", flush=True)
    # Far-below static post-only price — market-aware best-bid-1tick gets drained
    # by live book activity before a 40-order batch can settle.
    spot = await live_client.market_data.get_spot_config()
    pair = next((p for p in spot.raw.get("pairs") or [] if p.get("symbol") == trade_symbol), {})
    price = FAR_BELOW_BUY_PRICE_HINTS.get(trade_symbol, "100")
    qty = min_base_qty_for_pair(pair, price)
    # Active client-order ids (updated when replace assigns new_client_order_id).
    cids: list[str] = []
    # All ids ever used by this fixture (for cleanup / open-set checks).
    all_cids: set[str] = set()
    try:
        with contextlib.suppress(Exception):
            await live_client.orders.cancel_all(symbol=trade_symbol)
        for i in range(40):
            cid = unique_client_order_id(f"bm-{i}")
            try:
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
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "internal" in msg or "unavailable" in msg or "notional" in msg:
                    pytest.skip(devnet_order_skip_message())
                raise
            cids.append(cid)
            all_cids.add(cid)
            try:
                await wait_for_open_order(live_client, cid, timeout=15)
            except DevnetOrderNotIndexedError:
                pytest.skip(devnet_order_skip_message())
            except AssertionError as exc:
                msg = str(exc).lower()
                if "terminal status" in msg and "filled" in msg:
                    pytest.skip(
                        f"post-only resting order filled by book activity before batch: {exc}"
                    )
                raise

        for round_i in range(5):
            # Distinct price each round; new_client_order_id avoids CONFLICT on replace.
            modify_price = format(
                Decimal(price) * (Decimal("0.99") - Decimal(round_i) * Decimal("0.001")),
                "f",
            )
            new_cids = [unique_client_order_id(f"bm-r{round_i}-{i}") for i in range(40)]
            items = [
                {
                    "client_order_id": cid,
                    "new_price": modify_price,
                    "new_client_order_id": new_cid,
                }
                for cid, new_cid in zip(cids, new_cids, strict=True)
            ]
            request_id = unique_client_order_id(f"bm-req-{round_i}")
            requested = set(cids)
            all_cids.update(new_cids)

            # Snapshot open state before attempt (timeout retry reconciles per docs).
            before_ids: dict[str, str] = {}
            for _ in range(20):
                before_open = await live_client.orders.list_open(limit=100)
                before_ids = {
                    o.client_order_id: o.order_id
                    for o in before_open.orders
                    if o.client_order_id in requested
                }
                if len(before_ids) == 40:
                    break
                await asyncio.sleep(0.5)
            if len(before_ids) != 40:
                pytest.skip(
                    f"round {round_i}: only {len(before_ids)}/40 test orders still open "
                    "(book activity drained resting post-only bids)"
                )

            try:
                result = await live_client.orders.batch_modify(
                    items=items,
                    symbol=trade_symbol,
                    request_id=request_id,
                    allow_partial=True,
                )
            except Exception as exc:  # noqa: BLE001
                # Timeout / ambiguous commit: same request_id retry after reconcile.
                after_open = await live_client.orders.list_open(limit=100)
                after_ids = {
                    o.client_order_id: o.order_id
                    for o in after_open.orders
                    if o.client_order_id in all_cids
                }
                assert len(after_ids) == 40, (
                    f"round {round_i}: open set changed during failed attempt "
                    f"({len(after_ids)}); first={exc}"
                )
                await asyncio.sleep(0.2)
                try:
                    result = await live_client.orders.batch_modify(
                        items=items,
                        symbol=trade_symbol,
                        request_id=request_id,
                        allow_partial=True,
                    )
                except Exception as retry_exc:  # noqa: BLE001
                    pytest.fail(f"batch_modify round {round_i}: {retry_exc} (first={exc})")

            _assert_complete_batch_result(result, expected_cids=requested, round_i=round_i)
            fingerprint = _result_fingerprint(result)

            # Intentional identical request_id retry after success — no double-apply.
            retry_ok = await live_client.orders.batch_modify(
                items=items,
                symbol=trade_symbol,
                request_id=request_id,
                allow_partial=True,
            )
            _assert_complete_batch_result(retry_ok, expected_cids=requested, round_i=round_i)
            assert _result_fingerprint(retry_ok) == fingerprint, (
                f"round {round_i}: idempotent retry changed action/final ids"
            )

            # Resolve the live key for each item: prefer new_cid when it is open.
            next_cids: list[str] = []
            for old_cid, new_cid in zip(cids, new_cids, strict=True):
                chosen = None
                for candidate in (new_cid, old_cid):
                    try:
                        await wait_for_open_order(live_client, candidate, timeout=3)
                        chosen = candidate
                        break
                    except (AssertionError, DevnetOrderNotIndexedError):
                        continue
                if chosen is None:
                    pytest.fail(
                        f"round {round_i}: neither {old_cid!r} nor {new_cid!r} open after modify"
                    )
                next_cids.append(chosen)
            cids = next_cids
            open_after = await live_client.orders.list_open(limit=100)
            open_count = sum(1 for o in open_after.orders if o.client_order_id in set(cids))
            assert open_count == 40, (
                f"round {round_i}: expected 40 open test orders after idempotent retry, "
                f"got {open_count}"
            )
    finally:
        with contextlib.suppress(Exception):
            await live_client.orders.cancel_all(symbol=trade_symbol)
        if all_cids:
            await _wait_zero_open_test_orders(live_client, all_cids)
