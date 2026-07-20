# Changelog

## Unreleased

### Changed
- Connect RPC coverage gate no longer commits dashboard reports under `docs/`; CI fails on unexpected gaps only (`sdk-coverage.toml` + `scripts/check_sdk_coverage.py`)

### Docs
- README `Supported surface` table is generated from `sdk-capabilities.json` (`--write-capabilities`); links to the public [SDK capability matrix](https://polyester.ai/docs/developer-docs/getting-started/sdk-capability-matrix)
- CI auto-commits refreshed `sdk-capabilities.json` + README capability table when they drift (same-repo)

## 0.1.0a9

### Features
- Realtime, orderbook, and market-overview subscriptions support `async with` for automatic cleanup
- Connect RPC wrapper coverage gate: `scripts/check_sdk_coverage.py` + `sdk-coverage.toml`

### Docs
- README realtime examples use `async with` instead of manual `try` / `finally` / `aclose()`

## 0.1.0a8

### Breaking
- Authoritative freshness: `Order.state_revision` → `Order.version`; balance `trading_version` / `funding_version` / `reserved_version` → `trading_updated_at_ns` / `funding_updated_at_ns` / `reserved_updated_at_ns`; subaccount and API-key `updated_at` are configuration timestamps; API-key `last_used_at` stays independent activity time

### Features
- Generated reconciliation and policy types exposed in the public SDK surface
- Internal transfer amounts use U128 wire types end-to-end

## 0.1.0a7

### Breaking
- Dual-path qty/price scalars: reads expose typed `price` / `qty` domain values (`.ticks` / `.scaled`) instead of primary digit-string `price_ticks` / `qty_scaled` fields
- Order, trigger, transfer, and withdraw writes accept human decimals (`str` / `Decimal`) or bot scaled inputs (`Price` / `Quantity` / `AssetAmount`); excess precision is rejected (no silent `ROUND_DOWN`)

### Money types
- New `Price`, `Quantity`, and `AssetAmount` helpers for human decimal and scaled/tick paths, with compatibility checks when reusing read values on writes

### Docs / examples
- README documents human vs bot dual-path usage

### Testing
- Unit coverage for money conversion, bounds, and mismatch rejection
- Funded/integration asserts updated for typed price/qty reads
- Skip transfer-to-user smoke on Connect `"Request timed out"` as a devnet unavailable signal

## 0.1.0a6

### Breaking
- Removed private `ledger.write.v1` / `client.ledger_write` from the public SDK (not in `public.files.txt`)

## 0.1.0a5

### Triggers
- `triggers.create()` exposes the full `CreateTriggerRequest` surface, unblocking `TRAILING_STOP`, `TWAP`, and `LADDER` creation via the SDK: `fee_source`, `self_trade_prevention_mode`, `trailing_distance_ticks`/`trailing_distance_bps`, `activation_price`, `max_slippage_ticks`/`max_slippage_bps`, `twap_duration_ms`/`twap_slice_interval_ms`, `ladder_price_min`/`ladder_price_max`, `ladder_levels`, and `ladder_distribution`
- `trigger_price` is now optional on `create()` (not required for trailing/TWAP/ladder types)

### Testing
- Unit tests for advanced trigger param mapping (`tests/unit/test_triggers_codecs.py`)
- Devnet mutation e2e proving trailing stop, TWAP, and ladder creation through the SDK (`tests/e2e/test_advanced_trigger_creation.py`)

## 0.1.0a4

### Breaking
- `orders.cancel_all()` no longer accepts `max_orders`; the field was removed from the public proto and server no longer honors it

### Orders
- Market orders: pass `market_client_ref_price` on `create()` when the orderbook may be empty (required for IOC market buys on devnet)
- Proto gen bump (2026-07-03 bundle) aligned with server contract

### Realtime
- Auto-reconnect on Centrifugo disconnect with 30s read timeout (matches Go SDK behavior)

### Testing
- Market order mutation e2e (single-account IOC buy/sell on devnet)
- Market order fill e2e and spot fill e2e with optional maker credentials (`POLYESTER_TEST_MAKER_*`)
- Realtime reconnect unit test; integration batch excludes duplicate realtime runs
- `test_balances_get_health` marked optional when route is not mounted

## 0.1.0a3

### Codecs
- Decode candle OHLC from wire price ticks (1e6) to decimal strings, matching the TypeScript SDK surface
- Decode candle volume using the pair's `base_quantity_scale` from spot config when catalogs are loaded

## 0.1.0a2

### Documentation
- README: remove stale hardcoded alpha version from PyPI project description
- Align `polyester.__version__` with package metadata

## 0.1.0a1

### SDK surface
- Orders: `batch_create`, `batch_cancel`, `cancel_all_after`; `cancel(symbol=…)` resolves `symbol_id`
- API keys: `create`, `update`, `delete`
- Withdraw: `create_wallet_trading_withdraw`
- Address book: full CRUD, views, whitelist, counterparties
- New services: `policies`, `sub_accounts`, `guard_signer`
- `market_overview.create_subscription()` — snapshot-then-stream merge (TS parity)

### Codecs
- Proto decode migration for balances history/equity/holds, triggers, transfers, deposit, withdraw, internal transfers, api keys, resolve, and public market services
- `order_mutation_from_proto` handles `CancelOrderResponse` (no `client_order_id` field)

### Realtime
- Centrifugo heartbeat: reply to `{}` ping frames with `{}` pong (fixes websocket `3012 no pong` disconnects)
- Graceful stream teardown without unhandled background task exceptions

### Dependencies
- Pin `connectrpc<0.11` (protobuf stub compatibility)

### Testing
- Restructured `tests/unit`, `tests/integration`, `tests/e2e`, `tests/e2e/funded`
- Pytest markers: `integration`, `smoke`, `mutation`, `funded`, `treasury`, `optional`, `realtime`
- `POLYESTER_TEST_TRADE_SYMBOL` for order/trigger mutation (separate from `POLYESTER_TEST_SMOKE_SYMBOL`)
- Dynamic mutation pricing from `market_overview` (~2% of last trade)
- `test_orders_get_round_trips_list_open` — proof-style when open orders exist
- `scripts/test_all.sh` and `scripts/smoke_test.py` (pytest wrapper)
- `scripts/smoke_realtime.sh` — unit realtime tests + live Centrifugo heartbeat (~35s)
- Unit tests for Centrifugo ping/pong and batched frames
- Integration test holds a public trades subscription past Centrifugo heartbeat interval
- CI: `pytest tests/unit` with coverage on non-`gen/` code
- Full devnet suite documents honest skips for OMS read lag, JWT routes, optional mounts, and account-specific prerequisites

## 0.1.0a0

- Initial alpha release with core trading and market data services.
