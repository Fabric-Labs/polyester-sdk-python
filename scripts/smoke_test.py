#!/usr/bin/env python3
"""Live smoke test against Polyester devnet."""

from __future__ import annotations

import asyncio
import os
import traceback
import uuid

try:
    from dotenv import load_dotenv
except ImportError as exc:
    raise SystemExit('Install dev dependencies first: pip install -e ".[dev]"') from exc

try:
    from polyester import AsyncPolyester
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Cannot import polyester. Use: .venv/bin/python scripts/smoke_test.py"
    ) from exc

from decimal import Decimal

from polyester import format_ledger_u128
from polyester.auth import (
    ACCOUNT_ID_ENV,
    API_KEY_ID_ENV,
    API_PRIVATE_KEY_ENV,
    load_api_key_credentials,
)
from polyester.errors import PolyesterError, PolyesterRouteNotFoundError

OPTIONAL_STEPS = {
    "orderbook",
    "get_current_candle",
    "list_holds",
    "deposit_create_address",
    "withdraw_create_trading",
    "internal_transfer_create",
    "resolve_account",
    "api_keys_get",
}

TRANSFER_TYPE_NAMES: dict[int, str] = {
    1000: "deposit",
    1001: "withdraw",
    1030: "internal_transfer",
    1060: "fund_to_unified",
    1061: "unified_to_fund",
}


def _check_env() -> None:
    load_dotenv()
    print("Environment")
    print(f"  {API_KEY_ID_ENV}: {'set' if os.getenv(API_KEY_ID_ENV) else 'MISSING'}")
    print(f"  {API_PRIVATE_KEY_ENV}: {'set' if os.getenv(API_PRIVATE_KEY_ENV) else 'MISSING'}")
    acct = "set" if os.getenv(ACCOUNT_ID_ENV) else "not set"
    print(f"  {ACCOUNT_ID_ENV}: {acct}")
    print(f"  API URL: {os.getenv('POLYESTER_API_URL', 'https://api-devnet.polyester.ai')}")
    print()
    if load_api_key_credentials() is None:
        raise SystemExit(f"Set {API_KEY_ID_ENV} and {API_PRIVATE_KEY_ENV} in .env")
    print("Credentials loaded OK.")
    print()


async def _run_step(name: str, coro, *, optional: bool = False) -> bool:
    tag = " (optional)" if optional else ""
    print(f"→ {name}{tag}")
    try:
        result = await coro
        summary = str(result)
        if "\n" in summary:
            print("  OK:")
            for line in summary.splitlines():
                print(f"    {line}")
        else:
            print(f"  OK: {summary}")
        print()
        return True
    except PolyesterError as exc:
        print(f"  SDK error: {_format_sdk_error(exc)}")
        print()
        return False
    except Exception as exc:
        print(f"  Failed: {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)
        print()
        return False


async def main() -> int:
    _check_env()
    api_url = os.getenv("POLYESTER_API_URL", "https://api-devnet.polyester.ai")
    smoke_chain_id = os.getenv("POLYESTER_SMOKE_CHAIN_ID")
    resolve_query = os.getenv("POLYESTER_SMOKE_RESOLVE_QUERY")
    run_mutation = os.getenv("POLYESTER_SMOKE_MUTATION", "").lower() in ("1", "true", "yes")
    run_realtime = os.getenv("POLYESTER_SMOKE_REALTIME", "").lower() in ("1", "true", "yes")
    async with AsyncPolyester.from_env(api_url=api_url, hydrate_catalogs=False) as client:
        spot = await client.market_data.get_spot_config()
        client.catalogs.hydrate_spot_config(spot.raw)
        zipper = await client.zipper.get_deposit_withdraw_config()
        asset_labels = _asset_labels(spot.raw, zipper.raw)
        smoke_symbol = _resolve_smoke_symbol(spot.raw, os.getenv("POLYESTER_SMOKE_SYMBOL"))
        deposit_chain_id = _deposit_chain_id(zipper.raw, smoke_chain_id)
        symbol_id = _symbol_id_for(spot.raw, smoke_symbol)
        smoke_pair = _pair_for(spot.raw, smoke_symbol)
        print(f"Smoke symbol: {smoke_symbol} (symbol_id={symbol_id})")
        if deposit_chain_id is not None:
            print(f"Deposit chain_id: {deposit_chain_id}")
        print()
        results: list[bool] = []
        required: list[bool] = []

        required.append(
            await _run_step("market_data.get_spot_config", _return_value(_spot_summary(spot)))
        )
        required.append(
            await _run_step(
                "zipper.get_deposit_withdraw_config",
                _return_value(_zipper_summary(zipper)),
            )
        )
        required.append(
            await _run_step(
                "market_overview.list",
                _summarize_overview(client.market_overview.list(limit=5), smoke_symbol),
            )
        )
        if symbol_id is not None:
            required.append(
                await _run_step(
                    f"market_data.get_trades {smoke_symbol}",
                    _summarize_trades(client.market_data.get_trades(symbol_id=symbol_id, limit=5)),
                )
            )
            required.append(
                await _run_step(
                    f"market_data.get_candles {smoke_symbol}",
                    _summarize_candles(
                        client.market_data.get_candles(symbol_id=symbol_id, timeframe="1m", limit=5)
                    ),
                )
            )
            required.append(
                await _run_step(
                    f"market_data.get_candles_columns {smoke_symbol}",
                    _summarize_candles(
                        client.market_data.get_candles_columns(
                            symbol_id=symbol_id, timeframe="1m", limit=5
                        )
                    ),
                )
            )
            results.append(
                await _run_step(
                    f"market_data.get_current_candle {smoke_symbol}",
                    _summarize_current_candle(
                        client.market_data.get_current_candle(
                            symbol_id=symbol_id, timeframe="1m"
                        )
                    ),
                    optional=True,
                )
            )
            required.append(
                await _run_step(
                    f"heatmap.get {smoke_symbol}",
                    _summarize_heatmap(client.heatmap.get(symbol_id=symbol_id, limit=5)),
                )
            )
            if run_realtime:
                results.append(
                    await _run_step(
                        f"market_data.subscribe_trades {smoke_symbol}",
                        _summarize_realtime(client, symbol_id),
                        optional=True,
                    )
                )
        results.append(
            await _run_step(
                f"orderbook.get {smoke_symbol}",
                _summarize_orderbook(client.orderbook.get(symbol=smoke_symbol, depth=10)),
                optional=True,
            )
        )

        flows = await client.lifecycle.list_flows(limit=5)
        flow_count = len(flows.flows)
        required.append(
            await _run_step("lifecycle.list_flows", _return_value(f"flows={flow_count}"))
        )
        intent_id = next((f.intent_id for f in flows.flows if f.intent_id), None)
        if intent_id:
            required.append(
                await _run_step(
                    "lifecycle.get_flow",
                    _summarize_flow(client.lifecycle.get_flow(intent_id=intent_id)),
                )
            )
        tx_hash = os.getenv("POLYESTER_SMOKE_TX_HASH")
        if tx_hash:
            results.append(
                await _run_step(
                    "lifecycle.get_flow_by_tx",
                    _summarize_flow(
                        client.lifecycle.get_flow_by_tx(tx_hash=tx_hash)
                    ),
                    optional=True,
                )
            )

        required.append(
            await _run_step(
                "balances.get_health (authenticated)",
                _summarize_health(client.balances.get_health()),
            )
        )

        open_orders = await client.orders.list_open()
        read_ok = await _run_step(
            "orders.list_open (authenticated)",
            _return_value(_summarize_orders(open_orders)),
        )
        if open_orders.orders:
            first = open_orders.orders[0]
            required.append(
                await _run_step(
                    "orders.get (authenticated)",
                    _summarize_get_order(
                        client.orders.get(
                            order_id=first.order_id or None,
                            client_order_id=first.client_order_id or None,
                        )
                    ),
                )
            )
        balances_result = await client.balances.list()
        required.append(
            await _run_step(
                "balances.list (authenticated)",
                _return_value(_summarize_balances(balances_result, asset_labels)),
            )
        )
        if deposit_chain_id is not None:
            required.append(
                await _run_step(
                    f"deposit.list_addresses chain={deposit_chain_id}",
                    _summarize_deposit_addresses(
                        client.deposit.list_addresses(chain_id=deposit_chain_id)
                    ),
                )
            )
            results.append(
                await _run_step(
                    f"deposit.create_address chain={deposit_chain_id}",
                    _summarize_deposit_address(
                        client.deposit.create_address(chain_id=deposit_chain_id)
                    ),
                    optional=True,
                )
            )
        history = await client.orders.list_history(limit=5)
        required.append(
            await _run_step(
                "orders.list_history (authenticated)",
                _return_value(_summarize_orders(history)),
            )
        )
        if symbol_id is not None:
            required.append(
                await _run_step(
                    f"trades.list (authenticated) {smoke_symbol}",
                    _summarize_user_trades(
                        client.trades.list(symbol_id=symbol_id, limit=5)
                    ),
                )
            )
        triggers_list = await client.triggers.list(limit=5)
        required.append(
            await _run_step(
                "triggers.list (authenticated)",
                _return_value(
                    f"triggers={len(triggers_list.triggers)} total={triggers_list.total}"
                ),
            )
        )
        if triggers_list.triggers:
            first_trigger_id = triggers_list.triggers[0].trigger_id
            required.append(
                await _run_step(
                    "triggers.list_events (authenticated)",
                    _summarize_trigger_events(
                        client.triggers.list_events(trigger_id=first_trigger_id, limit=5)
                    ),
                )
            )
        required.append(
            await _run_step(
                "transfers.list (authenticated)",
                _summarize_transfers(client.transfers.list(limit=5), asset_labels),
            )
        )
        required.append(
            await _run_step(
                "balances.get_balance_history (authenticated)",
                _summarize_balance_history(client.balances.get_balance_history(range="7d")),
            )
        )
        required.append(
            await _run_step(
                "balances.get_equity_history (authenticated)",
                _summarize_equity_history(client.balances.get_equity_history(range="7d")),
            )
        )
        results.append(
            await _run_step(
                "balances.list_holds (authenticated)",
                _summarize_holds(client.balances.list_holds(limit=5)),
                optional=True,
            )
        )
        api_keys = await client.api_keys.list()
        required.append(
            await _run_step(
                "api_keys.list (authenticated)",
                _return_value(_summarize_api_keys_list(api_keys)),
            )
        )
        if api_keys.api_keys:
            sample_key_id = api_keys.api_keys[0].key_id
            results.append(
                await _run_step(
                    "api_keys.get (authenticated)",
                    _summarize_api_key(client.api_keys.get(key_id=sample_key_id)),
                    optional=True,
                )
            )
        if resolve_query:
            results.append(
                await _run_step(
                    "resolve.resolve_account",
                    _summarize_resolve(client.resolve.resolve_account(query=resolve_query)),
                    optional=True,
                )
            )
        results.append(
            await _run_step(
                "address_book.list_transfer_destinations",
                _summarize_transfer_destinations(
                    client.address_book.list_transfer_destinations()
                ),
                optional=True,
            )
        )
        if read_ok:
            required.append(
                await _run_step(
                    "orders.cancel_all dry_run (authenticated)",
                    _summarize_cancel_all(
                        client.orders.cancel_all(dry_run=True, symbol=smoke_symbol)
                    ),
                )
            )

        if run_mutation or read_ok:
            results.append(
                await _run_step(
                    "orders.create + cancel (authenticated)",
                    _mutation_round_trip(client, smoke_symbol, smoke_pair),
                    optional=True,
                )
            )

    passed_required = sum(required)
    total_required = len(required)
    optional_passed = sum(results)
    optional_total = len(results)
    print(f"Smoke summary: {passed_required}/{total_required} required steps succeeded.")
    if optional_total:
        print(f"Optional: {optional_passed}/{optional_total} succeeded.")
    print()
    if passed_required == 0:
        return 1
    if passed_required < total_required:
        if read_ok:
            print(
                "Some required steps failed (API-key policies look OK for reads). "
                "Check mutation sizing, symbol choice, or lifecycle data. "
                "Optional: orderbook/get_current_candle may be absent on devnet."
            )
        else:
            print(
                "Some required steps failed. Attach API-key policies in the UI for authenticated "
                "calls. Optional: orderbook/get_current_candle may be absent on devnet."
            )
        return 1
    return 0


def _format_sdk_error(exc: PolyesterError) -> str:
    message = str(exc).strip() or "(no message from server)"
    code = getattr(exc, "code", None)
    if isinstance(exc, PolyesterRouteNotFoundError):
        return f"{type(exc).__name__} [{code}]: {message}"
    if code:
        return f"{type(exc).__name__} [{code}]: {message}"
    return f"{type(exc).__name__}: {message}"


def _asset_labels(spot_raw: dict, zipper_raw: dict) -> dict[int, str]:
    labels: dict[int, str] = {}
    for assets_key in ("assets", "Assets"):
        for source in (zipper_raw, spot_raw):
            for item in source.get(assets_key) or []:
                if not isinstance(item, dict):
                    continue
                ledger_id = item.get("ledgerId") or item.get("ledger_id") or item.get("id")
                symbol = item.get("symbol") or item.get("ticker") or item.get("name")
                if ledger_id is not None:
                    labels[int(ledger_id)] = str(symbol or ledger_id)
    return labels


def _asset_name(labels: dict[int, str], asset_id: int) -> str:
    return labels.get(asset_id, f"asset_{asset_id}")


def _transfer_type_name(code: int) -> str:
    return TRANSFER_TYPE_NAMES.get(code, f"type_{code}")


def _zipper_summary(config) -> str:
    assets = config.raw.get("assets") or []
    usdt = _find_usdt_asset(assets)
    parts = [f"assets={len(assets)}"]
    if usdt:
        parts.append(
            f"USDT ledger_id={usdt['ledger_id']} scale={usdt.get('quantity_scale', '?')}"
        )
    return " ".join(parts)


def _find_usdt_asset(assets: list) -> dict | None:
    for item in assets:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or item.get("ticker") or "").upper()
        name = str(item.get("name") or "").upper()
        is_usdt = symbol == "USDT" or "USDT" in name or "TETHER" in name
        if not is_usdt:
            continue
        ledger_id = item.get("ledgerId") or item.get("ledger_id")
        scale = item.get("quantityScale") or item.get("quantity_scale")
        if ledger_id is not None:
            return {"ledger_id": int(ledger_id), "quantity_scale": scale}
    return None


async def _mutation_round_trip(client, symbol: str, pair: dict | None) -> str:
    from decimal import ROUND_UP

    from polyester.codecs.scalars import align_price_ticks, format_price_ticks, parse_price_ticks

    client_order_id = f"smoke-{uuid.uuid4().hex[:12]}"
    symbol_id = client.catalogs.symbol_id_for_symbol(symbol)
    tick_size = str((pair or {}).get("tickSize") or (pair or {}).get("tick_size") or "0.01")
    step_size = Decimal((pair or {}).get("stepSize") or (pair or {}).get("step_size") or "0.001")
    min_qty_base = Decimal(
        (pair or {}).get("minQtyBase") or (pair or {}).get("min_qty_base") or step_size
    )
    min_notional = Decimal(
        (pair or {}).get("minNotionalQuote")
        or (pair or {}).get("min_notional_quote")
        or "10"
    )
    price = os.getenv("POLYESTER_SMOKE_PRICE")
    if price is None:
        overview = await client.market_overview.list(limit=50)
        for row in overview.markets:
            if row.symbol != symbol and row.symbol_id != symbol_id:
                continue
            if not row.last_price_ticks:
                continue
            last_ticks = int(row.last_price_ticks)
            # Far below market so post-only limit buy should not fill.
            limit_ticks = align_price_ticks(max(1, last_ticks // 10), tick_size)
            price = format_price_ticks(limit_ticks)
            break
        else:
            price = format_price_ticks(align_price_ticks(parse_price_ticks("1"), tick_size))
    qty = os.getenv("POLYESTER_SMOKE_QTY")
    if qty is None:
        limit_price = Decimal(price)
        if limit_price > 0:
            qty_units = (min_notional / limit_price / step_size).to_integral_value(
                rounding=ROUND_UP
            )
        else:
            qty_units = Decimal(1)
        min_qty_units = (min_qty_base / step_size).to_integral_value(rounding=ROUND_UP)
        qty = format(max(qty_units, min_qty_units, Decimal(1)) * step_size, "f")
    created = await client.orders.create(
        symbol=symbol,
        side="buy",
        order_type="limit",
        tif="gtc",
        qty=qty,
        price=price,
        post_only=True,
        client_order_id=client_order_id,
    )
    cancelled = await client.orders.cancel(
        client_order_id=client_order_id,
        symbol_id=symbol_id,
    )
    return f"create={created.status!r} cancel={cancelled.status!r} cid={client_order_id}"


def _pair_for(spot_raw: dict, symbol: str) -> dict | None:
    for pair in spot_raw.get("pairs") or []:
        if pair.get("symbol") == symbol:
            return pair
    return None


def _symbol_id_for(spot_raw: dict, symbol: str) -> int | None:
    pair = _pair_for(spot_raw, symbol)
    if pair is None:
        return None
    value = pair.get("symbolId") or pair.get("symbol_id")
    return int(value) if value is not None else None


def _resolve_smoke_symbol(spot_raw: dict, env_symbol: str | None) -> str:
    if env_symbol and _symbol_id_for(spot_raw, env_symbol) is not None:
        return env_symbol
    for preferred in ("BNB-USDT", "SOL-USDT", "ETH-USDT", "BTC-USDT"):
        if _symbol_id_for(spot_raw, preferred) is not None:
            return preferred
    for pair in spot_raw.get("pairs") or []:
        symbol = pair.get("symbol")
        if not symbol or not isinstance(symbol, str):
            continue
        upper = symbol.upper()
        if "DISABLED" in upper or "LISTSOON" in upper:
            continue
        return symbol
    return env_symbol or "BNB-USDT"


def _deposit_chain_id(zipper_raw: dict, env_chain_id: str | None) -> int | None:
    if env_chain_id:
        return int(env_chain_id)
    chains = zipper_raw.get("chains") or []
    if chains and isinstance(chains[0], dict):
        chain_id = chains[0].get("chainId") or chains[0].get("chain_id")
        if chain_id is not None:
            return int(chain_id)
    polyester_chain_id = zipper_raw.get("polyesterChainId") or zipper_raw.get(
        "polyester_chain_id"
    )
    if polyester_chain_id is not None:
        return int(polyester_chain_id)
    return None


def _spot_summary(config) -> str:
    return f"pairs={len(config.raw.get('pairs') or [])}"


async def _return_value(value: str) -> str:
    return value


async def _summarize_overview(coro, smoke_symbol: str) -> str:
    result = await coro
    symbols = [m.symbol for m in result.markets[:5]]
    smoke_row = next((m for m in result.markets if m.symbol == smoke_symbol), None)
    extra = ""
    if smoke_row and smoke_row.last_price_ticks:
        extra = f" {smoke_symbol} last_ticks={smoke_row.last_price_ticks}"
    return f"markets={len(result.markets)} total={result.total} sample={symbols!r}{extra}"


async def _summarize_trades(coro) -> str:
    result = await coro
    return f"trades={len(result.trades)}"


async def _summarize_candles(coro) -> str:
    result = await coro
    return f"candles={len(result.candles)} tf={result.timeframe!r}"


async def _summarize_current_candle(coro) -> str:
    candle = await coro
    return f"ts_sec={candle.ts_sec} close={candle.close!r} closed={candle.is_closed}"


async def _summarize_health(coro) -> str:
    health = await coro
    return f"ok={health.ok} version={health.version!r}"


async def _summarize_deposit_addresses(coro) -> str:
    result = await coro
    return f"addresses={len(result.addresses)}"


async def _summarize_deposit_address(coro) -> str:
    addr = await coro
    return f"chain_id={addr.chain_id} address={addr.deposit_address!r}"


async def _summarize_get_order(coro) -> str:
    result = await coro
    if result.order is None:
        return "order=None"
    order = result.order
    return f"order_id={order.order_id!r} status={order.status!r} trades={len(result.trades)}"


def _summarize_api_keys_list(result) -> str:
    if not result.api_keys:
        return "api_keys=0"
    first = result.api_keys[0]
    return f"api_keys={len(result.api_keys)} sample={first.key_id!r} status={first.status!r}"


async def _summarize_api_key(coro) -> str:
    key = await coro
    return f"key_id={key.key_id!r} label={key.label!r} status={key.status!r}"


async def _summarize_resolve(coro) -> str:
    result = await coro
    if not result.matches:
        return "matches=0"
    first = result.matches[0]
    return f"matches={len(result.matches)} sample_account={first.account_id!r}"


async def _summarize_transfer_destinations(coro) -> str:
    result = await coro
    return f"destinations={len(result.destinations)}"


async def _summarize_heatmap(coro) -> str:
    result = await coro
    return f"keys={list(result.raw.keys())[:4]}" if hasattr(result, "raw") else "ok"


async def _summarize_orderbook(coro) -> str:
    book = await coro
    return f"bids={len(book.bids)} asks={len(book.asks)}"


async def _summarize_flow(coro) -> str:
    flow = await coro
    return f"intent={flow.intent_id!r} step={flow.latest_step!r}"


def _summarize_orders(result) -> str:
    if not result.orders:
        return "orders=0"
    first = result.orders[0]
    return (
        f"orders={len(result.orders)} "
        f"sample cid={first.client_order_id!r} status={first.status!r} side={first.side!r}"
    )


def _summarize_balances(result, asset_labels: dict[int, str]) -> str:
    nonzero: list[tuple[str, str, str]] = []
    for balance in result.balances:
        funding = format_ledger_u128(balance.funding)
        trading = format_ledger_u128(balance.trading)
        if funding == "0" and trading == "0":
            continue
        name = _asset_name(asset_labels, balance.asset_id)
        nonzero.append((name, funding, trading))
    nonzero.sort(key=lambda row: (row[1] == "0" and row[2] == "0", row[0]))
    lines = [f"balances={len(result.balances)} nonzero={len(nonzero)}"]
    for name, funding, trading in nonzero[:6]:
        lines.append(f"  {name}: funding={funding} trading={trading}")
    if len(nonzero) > 6:
        lines.append(f"  ... +{len(nonzero) - 6} more")
    if not nonzero:
        lines.append("  (all buckets zero — deposit may be pending or on another key)")
    return "\n  ".join(lines)


async def _summarize_user_trades(coro) -> str:
    result = await coro
    if not result.trades:
        return "trades=0"
    first = result.trades[0]
    return f"trades={len(result.trades)} sample side={first.side!r} qty_scaled={first.qty_scaled!r}"


async def _summarize_trigger_events(coro) -> str:
    result = await coro
    return f"events={len(result.events)}"


async def _summarize_transfers(coro, asset_labels: dict[int, str]) -> str:
    result = await coro
    lines = [f"transfers={len(result.transfers)}"]
    for transfer in result.transfers[:4]:
        name = _asset_name(asset_labels, transfer.asset_id)
        amount = format_ledger_u128(transfer.amount)
        kind = _transfer_type_name(transfer.transfer_type)
        pending = " pending" if transfer.pending else ""
        lines.append(f"  {kind} {name} amt={amount}{pending}")
    return "\n  ".join(lines)


async def _summarize_cancel_all(coro) -> str:
    result = await coro
    return (
        f"status={result.status!r} matched={result.matched_orders} "
        f"submitted={result.submitted_cancels}"
    )


async def _summarize_balance_history(coro) -> str:
    result = await coro
    return f"range={result.range!r} points={result.points} series={len(result.series)}"


async def _summarize_equity_history(coro) -> str:
    result = await coro
    return f"range={result.range!r} points={result.points} series={len(result.series)}"


async def _summarize_holds(coro) -> str:
    result = await coro
    return f"holds={len(result.holds)}"


async def _summarize_realtime(client, symbol_id: int) -> str:
    sub = client.market_data.subscribe_trades(symbol_id=symbol_id)
    try:
        trade = await asyncio.wait_for(sub.__anext__(), timeout=5.0)
        return f"trade price_ticks={trade.price_ticks}"
    except TimeoutError:
        return "connected (no trade within 5s)"
    finally:
        await sub.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
