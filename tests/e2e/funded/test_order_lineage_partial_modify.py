"""POLY-4708: predecessor fills survive ModifyOrder on a partially filled limit."""

from __future__ import annotations

import asyncio
import contextlib
import os
from decimal import Decimal

import pytest

from polyester import AsyncPolyester
from polyester.codecs.scalars import format_price_ticks, parse_price_ticks
from polyester.errors import PolyesterServerError
from polyester.models import ClientOrderId, OrderId
from tests.e2e.helpers import unique_client_order_id, wait_for_no_open_order
from tests.helpers import (
    is_devnet_order_internal_error,
    min_base_qty_for_pair,
    pair_tick_size,
)


def _trade_e2e_enabled() -> bool:
    return os.getenv("POLYESTER_TEST_TRADE_E2E", "").lower() in {"1", "true", "yes"}


def _second_client_credentials() -> tuple[str, str] | None:
    primary = os.getenv("POLYESTER_API_KEY_ID")
    for key_env, priv_env in (
        ("POLYESTER_TEST_MAKER_API_KEY_ID", "POLYESTER_TEST_MAKER_API_PRIVATE_KEY"),
        ("POLYESTER_SUBACCOUNT_API_KEY_ID", "POLYESTER_SUBACCOUNT_API_PRIVATE_KEY"),
    ):
        key_id = os.getenv(key_env)
        private_key = os.getenv(priv_env)
        if key_id and private_key and key_id != primary:
            return key_id, private_key
    return None


def _self_trade(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "self-trade" in text or "self_trade" in text or "stp" in text


def _skippable_order_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        is_devnet_order_internal_error(exc)
        or _self_trade(exc)
        or "notional" in text
        or "insufficient" in text
    )


async def _wait_listed_open(client, client_order_id: str, *, timeout: float = 15):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        listed = await client.orders.list_open(limit=50)
        for order in listed.orders:
            if order.client_order_id == client_order_id:
                return order
        try:
            detail = await _state_only(client, ClientOrderId(client_order_id))
        except Exception:
            detail = None
        if detail is not None and detail.order is not None:
            if detail.order.status in {"pending", "working", "pending_cancel"}:
                return detail.order
            if detail.order.status == "filled":
                return None
        await asyncio.sleep(0.5)
    return None


async def _state_only(client, key):
    return await client.orders.get(key=key, include_execution_history=False)


async def _history(
    client, key, *, limit: int = 5, page_token: str | None = None, retries: int = 3
):
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            return await client.orders.get(
                key=key,
                include_execution_history=True,
                limit=limit,
                page_token=page_token,
            )
        except PolyesterServerError as exc:
            last_error = exc
            if "timeout" not in str(exc).lower() and "query aborted" not in str(exc).lower():
                raise
            await asyncio.sleep(1)
    raise AssertionError(
        "GetOrder execution history timed out; lineage predecessor fills cannot be confirmed"
    ) from last_error


async def _wait_partial(client, client_order_id: str, *, timeout: float = 20):
    deadline = asyncio.get_event_loop().time() + timeout
    last = None
    while asyncio.get_event_loop().time() < deadline:
        last = await _state_only(client, ClientOrderId(client_order_id))
        order = last.order
        if order is None:
            await asyncio.sleep(0.5)
            continue
        cum = order.cum_qty.scaled if order.cum_qty is not None else 0
        leaves = order.leaves_qty.scaled if order.leaves_qty is not None else 0
        if cum > 0 and leaves > 0:
            return last
        if order.status == "filled" or (cum > 0 and leaves == 0):
            return None
        await asyncio.sleep(0.5)
    raise AssertionError(f"order {client_order_id} never partially filled: {last}")


@pytest.mark.integration
@pytest.mark.funded
@pytest.mark.mutation
async def test_partial_fill_modify_keeps_predecessor_execution_history(
    live_client,
    trade_symbol,
    mutation_enabled,
    funded_enabled,
    require_trade_trading_balance,
):
    if not _trade_e2e_enabled():
        pytest.skip("Set POLYESTER_TEST_TRADE_E2E=1 to spend against the live book")

    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = next(
        (item for item in spot.raw.get("pairs") or [] if item.get("symbol") == trade_symbol),
        {},
    )
    if not pair:
        pytest.skip(f"{trade_symbol} is not in spot config")

    book = await live_client.orderbook.get(symbol=trade_symbol, depth=5)
    if not book.asks or book.asks[0].price is None:
        pytest.skip(f"no visible asks on {trade_symbol}")

    ask_price = book.asks[0].price.format()
    step = parse_price_ticks(pair_tick_size(pair), "tick_size")
    original_cid = unique_client_order_id("pfill")
    replacement_cid = unique_client_order_id("pfillr")
    created_order_id = ""
    final_order_id = ""
    maker = None
    maker_cid = unique_client_order_id("pfillm")

    try:
        second = _second_client_credentials()
        if second is not None and book.bids and book.bids[0].price is not None:
            maker_ticks = book.bids[0].price.ticks + step
            if maker_ticks >= book.asks[0].price.ticks:
                pytest.skip("spread is too tight for an inside-spread maker")
            maker_price = format_price_ticks(maker_ticks)
            min_qty = Decimal(min_base_qty_for_pair(pair, maker_price))
            qty = format(min_qty * 2, "f")
            maker_qty = format(min_qty, "f")
            maker = AsyncPolyester(
                api_key_id=second[0],
                api_private_key=second[1],
                api_url=live_client.api_url,
                hydrate_catalogs=True,
            )
        else:
            min_qty = Decimal(min_base_qty_for_pair(pair, ask_price))
            maker_price = None
            qty = format(min_qty * 2, "f")
            maker_qty = None

        if maker is not None:
            spot_maker = await maker.market_data.get_spot_config()
            maker.catalogs.hydrate_spot_config(spot_maker.raw)
            maker_opened = None
            for attempt in range(2):
                if attempt:
                    maker_cid = unique_client_order_id("pfillm")
                try:
                    await maker.orders.create(
                        symbol=trade_symbol,
                        side="sell",
                        order_type="limit",
                        tif="gtc",
                        qty=maker_qty,
                        price=maker_price,
                        post_only=True,
                        client_order_id=maker_cid,
                    )
                except Exception as exc:
                    if _skippable_order_error(exc):
                        pytest.skip(str(exc))
                    raise
                maker_opened = await _wait_listed_open(maker, maker_cid, timeout=12)
                if maker_opened is not None:
                    break
                with contextlib.suppress(Exception):
                    await maker.orders.cancel(key=ClientOrderId(maker_cid), symbol=trade_symbol)
            if maker_opened is None:
                pytest.skip("maker sell was not visible as open")
            create_price = maker_price
        else:
            scale = live_client.catalogs.base_quantity_scale_for_symbol(trade_symbol)
            if book.asks[0].qty is None or scale is None:
                pytest.skip(f"best ask quantity unavailable on {trade_symbol}")
            ask_qty = book.asks[0].qty.as_decimal(scale)
            if ask_qty < min_qty:
                pytest.skip(f"best ask {ask_qty} is below min qty {min_qty}")
            target = ask_qty + (min_qty * 2)
            notional = target * Decimal(ask_price)
            if notional > Decimal("800"):
                pytest.skip(
                    f"no second key for a cheap partial fill, and sweeping the ask "
                    f"would spend {notional} quote"
                )
            qty = format(target, "f")
            create_price = ask_price

        try:
            created = await live_client.orders.create(
                symbol=trade_symbol,
                side="buy",
                order_type="limit",
                tif="gtc",
                qty=qty,
                price=create_price,
                post_only=False,
                client_order_id=original_cid,
            )
        except Exception as exc:
            if _skippable_order_error(exc):
                pytest.skip(str(exc))
            raise
        created_order_id = created.order_id

        partial = await _wait_partial(live_client, original_cid)
        if partial is None:
            pytest.skip(
                "buy at best ask fully filled; book too deep to rest a remainder for ModifyOrder"
            )
        assert partial.order is not None
        first_fill_qty = partial.order.cum_qty.scaled if partial.order.cum_qty is not None else 0
        assert first_fill_qty > 0
        first_lineage_id = (
            partial.order.lineage.id if partial.order.lineage is not None else created.order_id
        )
        first_generation = (
            partial.order.lineage.generation if partial.order.lineage is not None else 1
        )
        first_match_ids: set[str] = set()
        for _ in range(8):
            try:
                snapshot = await _history(
                    live_client, OrderId(created.order_id), limit=5, retries=1
                )
                first_match_ids = {trade.match_id for trade in snapshot.trades if trade.match_id}
            except AssertionError:
                snapshot = None
            if first_match_ids:
                break
            try:
                listed = await live_client.trades.list(order_id=created.order_id, limit=10)
                first_match_ids = {trade.match_id for trade in listed.trades if trade.match_id}
            except PolyesterServerError as exc:
                if "timeout" not in str(exc).lower() and "query aborted" not in str(exc).lower():
                    raise
            if first_match_ids:
                break
            await asyncio.sleep(0.5)

        step = parse_price_ticks(pair_tick_size(pair), "tick_size")
        rest_ticks = max(partial.order.price.ticks - step, step) if partial.order.price else step
        if book.bids and book.bids[0].price is not None:
            rest_ticks = min(rest_ticks, max(book.bids[0].price.ticks - step, step))
        rest_price = format_price_ticks(rest_ticks)

        modified = await live_client.orders.modify(
            key=OrderId(partial.order.order_id),
            symbol=trade_symbol,
            new_price=rest_price,
            behavior="replace_only",
            new_client_order_id=replacement_cid,
        )
        assert modified.old_order_id == created.order_id
        assert modified.final_order_id
        final_order_id = modified.final_order_id
        opened = await _wait_listed_open(live_client, replacement_cid)
        if opened is None:
            pytest.skip("replacement was not visible as open after modify")
        assert opened.order_id == modified.final_order_id

        history = await _history(live_client, OrderId(modified.final_order_id), limit=5)
        assert history.order is not None
        assert history.order.lineage is not None
        assert history.order.lineage.id == first_lineage_id
        assert history.order.lineage.generation == first_generation + 1
        assert history.order.cum_qty is not None
        assert history.order.cum_qty.scaled >= first_fill_qty
        history_match_ids = {trade.match_id for trade in history.trades if trade.match_id}
        assert history.trades, (
            "POLY-4708: GetOrder history is empty after replacing a partially filled order"
        )
        if first_match_ids:
            assert first_match_ids <= history_match_ids, (
                f"predecessor fills missing after replace: before={first_match_ids} "
                f"after={history_match_ids}"
            )
        for trade in history.trades:
            if trade.lineage is not None:
                assert trade.lineage.id == first_lineage_id
                assert trade.lineage.generation <= history.order.lineage.generation

        page = await _history(live_client, OrderId(modified.final_order_id), limit=1)
        assert page.order is not None
        if page.next_page_token:
            page_two = await _history(
                live_client,
                OrderId(modified.final_order_id),
                limit=1,
                page_token=page.next_page_token,
            )
            assert page_two.order is not None
            assert page_two.order.order_id == modified.final_order_id

        last_trade_error: Exception | None = None
        scoped = None
        for _ in range(3):
            try:
                scoped = await live_client.trades.list(
                    lineage_id=first_lineage_id,
                    through_generation=history.order.lineage.generation,
                    include_transfers=True,
                    limit=5,
                )
                break
            except PolyesterServerError as exc:
                last_trade_error = exc
                if "timeout" not in str(exc).lower() and "query aborted" not in str(exc).lower():
                    raise
                await asyncio.sleep(1)
        if scoped is None:
            raise AssertionError(
                "GetUserTrades lineage_id+transfers timed out after a real replacement"
            ) from last_trade_error
        scoped_matches = {trade.match_id for trade in scoped.trades if trade.match_id}
        assert first_match_ids <= scoped_matches
        assert isinstance(scoped.transfers, list)
        seen_tx: set[str] = set()
        for transfer in scoped.transfers:
            if transfer.tx_id:
                assert transfer.tx_id not in seen_tx
                seen_tx.add(transfer.tx_id)
    finally:
        for cid in (replacement_cid, original_cid):
            with contextlib.suppress(Exception):
                await live_client.orders.cancel(key=ClientOrderId(cid), symbol=trade_symbol)
                await wait_for_no_open_order(live_client, cid, timeout=8)
        for order_id in (final_order_id, created_order_id):
            if not order_id:
                continue
            with contextlib.suppress(Exception):
                await live_client.orders.cancel(key=OrderId(order_id), symbol=trade_symbol)
        if maker is not None:
            with contextlib.suppress(Exception):
                await maker.orders.cancel(key=ClientOrderId(maker_cid), symbol=trade_symbol)
            with contextlib.suppress(Exception):
                await maker.aclose()
