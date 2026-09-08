"""Live API-key coverage for POLY-4996 wrappers.

Read-only / dry-run plus targeted mutations (TWAP/ladder create+cancel,
impossible withdraw/transfer) that clean up their own rows.
"""

from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal, InvalidOperation

import pytest

from polyester.codecs.scalars import align_price_ticks, format_price_ticks, parse_price_ticks
from polyester.errors import (
    PolyesterApiError,
    PolyesterAuthError,
    PolyesterRouteNotFoundError,
)
from polyester.models import (
    CancelAllOrdersResult,
    CandlesResult,
    MarketOverviewList,
    SpotVolumeHistory,
    TriggersList,
)
from tests.e2e.helpers import unique_client_order_id
from tests.helpers import (
    is_devnet_order_internal_error,
    min_base_qty_for_pair,
    pair_for_symbol,
    pair_tick_size,
    quote_asset_id_for_symbol,
    resolve_far_below_buy_limit_price,
)
from tests.integration.support import call_optional, call_required

_DEAD_SMART_ACCOUNT = "0x000000000000000000000000000000000000dEaD"
_IMPOSSIBLE_WITHDRAW_QTY = "999999999"


def _assert_optional_scaled(value: str | None, *, label: str) -> None:
    if value is None or value == "":
        return
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise AssertionError(f"{label} is not a decimal string: {value!r}") from exc
    assert parsed >= 0, f"{label} must be non-negative: {value}"


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_spot_volume_history_by_symbol(live_client, smoke_symbol) -> None:
    result = await call_optional(
        live_client.market_overview.get_spot_volume_history(symbols=[smoke_symbol]),
        label="market_overview.get_spot_volume_history",
    )
    assert isinstance(result, SpotVolumeHistory)
    assert result.points >= 0
    assert result.start_ts_sec >= 0
    assert result.end_ts_sec >= result.start_ts_sec
    assert isinstance(result.pairs, list)
    assert isinstance(result.total_volume_usd_scaled, list)
    if result.points:
        assert len(result.total_volume_usd_scaled) == result.points
    for pair in result.pairs:
        assert pair.symbol_id > 0
        assert len(pair.volume_usd_scaled) == result.points
        symbol_id = live_client.catalogs.symbol_id_for_symbol(smoke_symbol)
        if symbol_id is not None:
            assert pair.symbol_id == symbol_id


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_spot_volume_history_by_symbol_id(live_client, smoke_symbol) -> None:
    symbol_id = live_client.catalogs.symbol_id_for_symbol(smoke_symbol)
    if symbol_id is None:
        pytest.skip(f"catalog missing symbol_id for {smoke_symbol}")
    result = await call_optional(
        live_client.market_overview.get_spot_volume_history(symbol_ids=[symbol_id]),
        label="market_overview.get_spot_volume_history(symbol_ids)",
    )
    assert isinstance(result, SpotVolumeHistory)
    for pair in result.pairs:
        assert pair.symbol_id == symbol_id


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_candles_preserve_quote_volume(live_client, smoke_symbol) -> None:
    result = await call_required(
        live_client.market_data.get_candles(symbol=smoke_symbol, limit=5),
        label="market_data.get_candles",
    )
    assert isinstance(result, CandlesResult)
    for candle in result.candles:
        assert isinstance(candle.quote_volume, str)
        _assert_optional_scaled(candle.quote_volume or None, label="candle.quote_volume")
        _assert_optional_scaled(candle.volume or None, label="candle.volume")


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_market_overview_optional_volume_fields(live_client) -> None:
    result = await call_required(
        live_client.market_overview.list(limit=10),
        label="market_overview.list",
    )
    assert isinstance(result, MarketOverviewList)
    for market in result.markets:
        assert market.symbol_id > 0
        _assert_optional_scaled(
            market.volume_24h_base_scaled, label="volume_24h_base_scaled"
        )
        _assert_optional_scaled(
            market.volume_24h_quote_scaled, label="volume_24h_quote_scaled"
        )
        _assert_optional_scaled(
            market.volume_24h_usd_scaled, label="volume_24h_usd_scaled"
        )


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_all_dry_run_symbols_and_symbol_ids(live_client, smoke_symbol) -> None:
    symbol_id = live_client.catalogs.symbol_id_for_symbol(smoke_symbol)
    if symbol_id is None:
        pytest.skip(f"catalog missing symbol_id for {smoke_symbol}")

    by_symbols = await call_required(
        live_client.orders.cancel_all(symbols=[smoke_symbol], dry_run=True),
        label="orders.cancel_all symbols dry-run",
    )
    assert isinstance(by_symbols, CancelAllOrdersResult)
    assert by_symbols.status
    assert by_symbols.matched_orders >= 0
    assert by_symbols.submitted_cancels == 0

    by_ids = await call_required(
        live_client.orders.cancel_all(symbol_ids=[symbol_id], dry_run=True),
        label="orders.cancel_all symbol_ids dry-run",
    )
    assert isinstance(by_ids, CancelAllOrdersResult)
    assert by_ids.status
    assert by_ids.submitted_cancels == 0


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_trigger_list_decodes_ladder_executed_fields(live_client) -> None:
    result = await call_required(
        live_client.triggers.list(limit=20),
        label="triggers.list",
    )
    assert isinstance(result, TriggersList)
    for trigger in result.triggers:
        details = trigger.details
        if details is None or details.case != "ladder" or details.ladder is None:
            continue
        assert details.ladder.executed_levels >= 0
        if details.ladder.executed_qty is not None:
            assert details.ladder.executed_qty.scaled >= 0


@pytest.mark.integration
@pytest.mark.mutation
@pytest.mark.asyncio(loop_scope="session")
async def test_create_ladder_decodes_executed_fields(
    live_client, trade_symbol, mutation_enabled
) -> None:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = pair_for_symbol(spot.raw, trade_symbol) or {}
    far_below = await resolve_far_below_buy_limit_price(live_client, trade_symbol, pair)
    tick_size = pair_tick_size(pair)
    max_ticks = align_price_ticks(parse_price_ticks(far_below), tick_size)
    min_ticks = align_price_ticks(int(max_ticks * Decimal("0.8")), tick_size)
    if min_ticks <= 0 or min_ticks >= max_ticks:
        pytest.skip("could not form a valid far-below ladder range")
    ladder_price_max = format_price_ticks(max_ticks)
    ladder_price_min = format_price_ticks(min_ticks)
    levels = 2
    per_level_qty = Decimal(min_base_qty_for_pair(pair, ladder_price_min))
    total_qty = format(per_level_qty * levels, "f")
    trigger_id: str | None = None
    try:
        created = await live_client.triggers.create(
            symbol=trade_symbol,
            trigger_type="ladder",
            side="buy",
            qty=total_qty,
            order_type="limit",
            limit_price=ladder_price_max,
            ladder_price_min=ladder_price_min,
            ladder_price_max=ladder_price_max,
            ladder_levels=levels,
            ladder_distribution="linear",
            client_trigger_id=unique_client_order_id("trg-ladder-exec"),
        )
        assert created.trigger_id
        assert created.status == "accepted"
        trigger_id = created.trigger_id
        fetched = await _wait_for_trigger(live_client, trigger_id)
        assert fetched is not None, "triggers.get returned no row for the created ladder"
        details = fetched.details
        assert details is not None and details.case == "ladder" and details.ladder is not None
        assert details.ladder.executed_levels >= 0
        if details.ladder.executed_qty is not None:
            assert details.ladder.executed_qty.scaled >= 0
    except (PolyesterApiError, AssertionError) as exc:
        _skip_on_devnet_quirk(exc)
        raise
    finally:
        if trigger_id:
            with contextlib.suppress(PolyesterApiError):
                await live_client.triggers.cancel(trigger_id=trigger_id)


def _skip_on_devnet_quirk(exc: BaseException) -> None:
    if is_devnet_order_internal_error(exc):
        pytest.skip(f"devnet trigger placement unavailable: {exc}")
    if isinstance(exc, PolyesterApiError):
        code = str(getattr(exc, "code", "") or "").lower()
        if code in {"route_not_found", "unimplemented", "not_found"}:
            pytest.skip(f"trigger route unavailable on devnet: {exc}")
        message = str(exc).lower()
        for token in ("notional", "not supported", "insufficient", "balance"):
            if token in message:
                pytest.skip(f"devnet/product limitation for this trigger config: {exc}")


async def _wait_for_trigger(client, trigger_id: str, *, timeout: float = 10):
    last_error: Exception | None = None
    for _ in range(max(1, int(timeout / 0.5))):
        try:
            trigger = await client.triggers.get(trigger_id=trigger_id)
            if trigger is not None:
                return trigger
        except PolyesterApiError as exc:
            if str(exc.code or "").lower() != "not_found":
                raise
            last_error = exc
        await asyncio.sleep(0.5)
    raise AssertionError(
        f"Trigger {trigger_id} was not readable within {timeout}s"
    ) from last_error


async def _create_twap_then_cancel(client, symbol: str, **create_kwargs):
    created = await client.triggers.create(symbol=symbol, **create_kwargs)
    assert created.trigger_id
    assert created.status == "accepted"
    with contextlib.suppress(PolyesterApiError):
        await client.triggers.cancel(trigger_id=created.trigger_id)
    return created


def _assert_typed_money_error(exc: BaseException, *, label: str) -> None:
    if isinstance(exc, PolyesterApiError):
        assert exc.code, f"{label} missing ErrorDetail code: {exc}"
        assert str(exc.code).startswith("ERROR_CODE_") or str(exc.code).startswith(
            "UNKNOWN_ERROR_CODE"
        ), f"{label} unexpected code={exc.code!r}"
        return
    if isinstance(exc, PolyesterAuthError):
        # Withdraw/transfer permission and MFA codes unpack to AuthError.
        return
    raise AssertionError(f"{label} did not raise a mapped SDK error: {type(exc)}: {exc}")


@pytest.mark.integration
@pytest.mark.mutation
@pytest.mark.asyncio(loop_scope="session")
async def test_twap_market_ioc_accepts_slippage(
    live_client, trade_symbol, mutation_enabled
) -> None:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    pair = pair_for_symbol(spot.raw, trade_symbol) or {}
    far_below = await resolve_far_below_buy_limit_price(live_client, trade_symbol, pair)
    qty = min_base_qty_for_pair(pair, far_below)
    try:
        created_bps = await _create_twap_then_cancel(
            live_client,
            symbol=trade_symbol,
            trigger_type="twap",
            side="buy",
            qty=qty,
            order_type="market",
            twap_duration_ms=600_000,
            twap_slice_interval_ms=300_000,
            max_slippage_bps=25,
            client_trigger_id=unique_client_order_id("trg-twap-bps"),
        )
        created_ticks = await _create_twap_then_cancel(
            live_client,
            symbol=trade_symbol,
            trigger_type="twap",
            side="buy",
            qty=qty,
            order_type="market",
            twap_duration_ms=600_000,
            twap_slice_interval_ms=300_000,
            max_slippage_ticks=1,
            client_trigger_id=unique_client_order_id("trg-twap-ticks"),
        )
    except (PolyesterApiError, AssertionError) as exc:
        _skip_on_devnet_quirk(exc)
        raise
    assert created_bps.trigger_id
    assert created_ticks.trigger_id


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="session")
async def test_social_verification_discord_without_handle(live_client) -> None:
    result = await call_optional(
        live_client.social_verification.start(provider="discord"),
        label="social_verification.start(discord)",
    )
    assert result is not None
    listed = await call_optional(
        live_client.social_verification.get(provider="discord"),
        label="social_verification.get(discord)",
    )
    assert listed is not None


@pytest.mark.integration
@pytest.mark.mutation
@pytest.mark.asyncio(loop_scope="session")
async def test_withdraw_error_detail_from_impossible_funding_move(
    live_client, trade_symbol, mutation_enabled
) -> None:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    if live_client.catalogs.zipper is None:
        zipper = await live_client.zipper.get_deposit_withdraw_config()
        live_client.catalogs.hydrate_zipper_config(zipper)
    asset_id = quote_asset_id_for_symbol(
        spot.raw,
        trade_symbol,
        zipper_raw=live_client.catalogs.zipper_config,
    )
    if asset_id is None:
        pytest.skip(f"cannot resolve quote asset for {trade_symbol}")
    try:
        await live_client.withdraw.create_api_key_to_funding(
            asset_id=asset_id,
            quantity=_IMPOSSIBLE_WITHDRAW_QTY,
            idempotency_key=unique_client_order_id("poly4996-wd"),
        )
    except (PolyesterApiError, PolyesterAuthError) as exc:
        _assert_typed_money_error(exc, label="withdraw.create_api_key_to_funding")
        return
    except PolyesterRouteNotFoundError:
        pytest.skip("withdraw.create_api_key_to_funding not mounted on devnet")
    pytest.fail("expected withdraw ErrorDetail for an impossible funding amount")


@pytest.mark.integration
@pytest.mark.mutation
@pytest.mark.asyncio(loop_scope="session")
async def test_transfer_error_detail_from_unknown_destination(
    live_client, trade_symbol, mutation_enabled
) -> None:
    spot = await live_client.market_data.get_spot_config()
    live_client.catalogs.hydrate_spot_config(spot.raw)
    if live_client.catalogs.zipper is None:
        zipper = await live_client.zipper.get_deposit_withdraw_config()
        live_client.catalogs.hydrate_zipper_config(zipper)
    asset_id = quote_asset_id_for_symbol(
        spot.raw,
        trade_symbol,
        zipper_raw=live_client.catalogs.zipper_config,
    )
    if asset_id is None:
        pytest.skip(f"cannot resolve quote asset for {trade_symbol}")
    try:
        await live_client.internal_transfers.create(
            asset_id=asset_id,
            quantity="0.000001",
            destination_smart_account_address=_DEAD_SMART_ACCOUNT,
            idempotency_key=unique_client_order_id("poly4996-xfer"),
        )
    except (PolyesterApiError, PolyesterAuthError) as exc:
        _assert_typed_money_error(exc, label="internal_transfers.create")
        return
    except PolyesterRouteNotFoundError:
        pytest.skip("internal_transfers.create not mounted on devnet")
    pytest.fail("expected transfer ErrorDetail for an unknown destination")
