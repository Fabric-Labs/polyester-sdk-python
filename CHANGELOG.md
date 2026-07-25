# Changelog

## Unreleased

### Fixed
- Realtime now negotiates the `centrifuge-protobuf` WebSocket subprotocol and uses binary, length-delimited Centrifugo commands, replies, pings, and publications. Previous releases selected `:proto` channels while speaking the JSON client protocol, so subscriptions could handshake but receive no binary publications.
- Concurrent authenticated calls now receive distinct monotonic signing timestamps, preventing identical same-millisecond requests from colliding with replay protection.
- BUY trailing-stop requests are rejected locally because the wire strategy is SELL-only; they are no longer silently encoded as SELL.
- Authentication failures without server detail now carry a non-empty fallback message.
- `ApiKeyCredentials` / `Ed25519Keypair` repr output redacts private key material.
- Realtime subscription-token HTTP exchange rejects response bodies larger than 64 KiB.
- Public ID parsing prefers canonical base58 when an all-digit string round-trips via `format_id`.
- Quantity scale resolution no longer silently defaults to 8 when catalogs/symbol are missing for decimal qty.
- WebSocket read timeout is treated as connection death (reconnect / error), not a silent continue.
- Subscriptions expose `resubscribed` / `take_resubscribed()` after reconnect gaps.
- Candle subscriptions normalize aliases (`MIN_1` / `min1`) to the live channel label (`1m`).

## 0.1.0a15

### Breaking
- `TriggerEventsList.next_before_ts_ns` renamed to `next_page_token` (opaque API cursor; no longer timestamp-shaped)
- `triggers.list_events(..., before_ts_ns=...)` renamed to `page_token=...` and now sets the proto `page_token` field

### Fixed
- `TriggersList` and `TriggerEventsList` expose `next_page_token` from the API so trigger list/event pagination can continue
- JSON wire decode for trigger events maps `fire_price_ticks` onto `fire_px` (was a broken `fire_px_ticks` kwarg)

## 0.1.0a14

### Breaking
- Stable MFA auth error codes (POLY-2919): `AUTH_API_KEY_MFA_REQUIRED` is removed; use `AUTH_MFA_NOT_ENROLLED`, `AUTH_STEP_UP_REQUIRED`, `AUTH_MFA_ELEVATION_REQUIRED`, and `AUTH_MFA_LAST_FACTOR_REQUIRED` from `AuthErrorDetail`
- Removed JWT/session-only account-admin RPCs from the API-key SDK surface. Use the TypeScript browser client for interactive account administration.
  - Policies: unary create/update/delete/list/get/set removed; keep `subscribe_subaccount_policies` / `subscribe_api_policies`
  - API keys: `create` / `update` / `delete` removed; keep `list` / `get` / `subscribe` / `generate_keypair`
  - Subaccounts: create/update/delete and member/invite mutations removed; keep reads + `subscribe` / `subscribe_api_keys`
  - Address book: entry/tag mutations removed; keep list/get/view/subscribe
  - Profile: `get` / `update` / `get_username_history` removed; keep `subscribe_identity`
  - Account resolve (`client.resolve` / `client.accounts`) removed entirely

### Features
- `is_mfa_enrollment_required` / `is_step_up_required` / `is_mfa_elevation_required` / `is_mfa_last_factor_required` classify MFA control flow from structured auth codes only (no message heuristics)
- Public method options expose `polyester.api.MFARequirement` documentation metadata
- POLY-3739: `policies.subscribe_api_policies` typed subscribe for `private:auth:api-policies:{account_id}:proto` (sync: `subscribe_api_policies_sync`)

### Testing
- Unit coverage for MFA auth-code mapping and predicates
- Unit coverage for API/subaccount policy realtime protobuf decode
- Live trigger create asserts `status == "accepted"` (POLY-3701 synthesized admission status)

### Changed
- CI no longer auto-commits `sdk-capabilities.json` / README on pull requests. Capability refresh + optional bot commit runs only on merge to `main`.
- README capability matrix labels clarify API-key-safe account surfaces (reads/subscribe vs session-only admin)
- Realtime subscribe waits for the Centrifugo handshake (including private token fetch) before returning; initial auth failures are returned immediately

## 0.1.0a13

### Breaking
- POLY-3701 wire break: order and trigger creation now target explicit execution variants. The flat `order_type`/`tif`/`post_only`/`price` inputs are still accepted on `CreateOrderRequest` but are mapped onto the new `OrderIntent` execution oneof (`market_ioc`/`limit_gtc`/`limit_ioc`/`limit_fok`); `post_only` is only valid for limit-GTC and is rejected otherwise
- `CreateOrderRequest` now wraps an `OrderIntent` (`subaccount_id` + `order`); batch create items are `OrderIntent`s and the removed `allow_partial` argument is accepted but ignored
- `triggers.create` maps flat params onto the new `TriggerIntent` strategy oneof (`stop_loss`/`take_profit` conditional, `trailing_stop`, `twap`, `ladder`); trailing stops are always SELL market-IOC, ladder distribution only accepts `linear`, and `trigger_price_source` is dropped from the wire
- `CreateOrderResponse` / `CreateTriggerResponse` no longer carry a `status` field; admitted mutations synthesize `status="accepted"`
- Batch-create result items now use an `accepted`/`rejected` oneof, projected back onto the flat `status`/`order_id`/`code` result model
- `Trigger` read model now exposes full proto fields (order params, timestamps, detail blocks, `post_only`, `parent_order_id`, child order ids)
- `Order` read model adds `post_only` and `attached_risk`
- `triggers.list` accepts validated `status` filter labels (`created`/`armed`/`running`/`completed`/`cancelled`/`failed`/`paused`)

### Fixed
- Order/trigger decode reads the POLY-3701 shapes: attached-risk legs derive `order_type`/`limit_price` from their `RiskExecution` child, and the thick `Trigger` projection is rebuilt from the configuration oneof + runtime detail blocks
- `orders.get` / list with `include_attached_risk=True` now returns policy data on `Order.attached_risk`

## 0.1.0a12

### Fixed
- `CreateSubaccountResult.revision` is returned from create so clients can pass `expected_revision` on the next mutation without a follow-up read

## 0.1.0a11

### Breaking
- Durable auth PATCH contract: subaccount, API key, subaccount/API policy, and address-book entry updates require nested mutable specs, a non-empty FieldMask, and a positive `expected_revision` from a prior read
- Policy creates nest fields under `policy` (optional `sub_account_id` / `assign_to_key_id` remain on the outer request)
- Soft-delete subaccount requires `expected_revision`; update APIs are presence-aware via omitted kwargs / `UNSET` so `""`, `[]`, `false`, `0`, and null timestamp clears survive
- Address-book entry updates no longer accept `new_tags` (mutable paths: `label`, `note`, `tag_ids`); tag updates remain optional `name` / `color` without revision/mask
- Durable resource models expose `revision`; Connect `AuthErrorDetail` maps `AUTH_REVISION_CONFLICT` onto `PolyesterApiError.code`

### Testing
- Live funded UserOp tests: Funding → Trading (`TradingGateway.deposit`) and Funding → external (`withdrawToChain`), gated by `POLYESTER_TEST_CHAIN_USEROP=1`
- Unit coverage for nested FieldMask request construction, presence/clear semantics, revision decode, and revision-conflict error mapping

### Changed
- Realtime (`websockets`) and on-chain Funding helpers (`eth-abi` / friends) are required dependencies, not optional extras. Empty `[realtime]` / `[chain]` extras remain for install compatibility.

## 0.1.0a10

### Features
- Optional `[chain]` smart-account path: CREATE2 Safe prediction, ERC-4337 UserOp submit (bundler + paymaster), Funding → external / Funding → Trading calldata, Zipper fee quote, and full FundingAccount / GuardRegistry whitelist encoders
- Realtime delivery is fail-closed on queue overflow (`PolyesterRealtimeOverflowError`); managed snapshot-then-stream subscriptions refresh Connect snapshots on reconnect and expose recovery hooks

### Changed
- Connect RPC coverage gate no longer commits dashboard reports under `docs/`; CI fails on unexpected gaps only (`sdk-coverage.toml` + `scripts/check_sdk_coverage.py`)

### Docs
- README `Supported surface` table is generated from `sdk-capabilities.json` (`--write-capabilities`); links to the public [SDK capability matrix](https://polyester.ai/docs/developer-docs/getting-started/sdk-capability-matrix)
- CI auto-commits refreshed `sdk-capabilities.json` + README capability table when they drift (same-repo)
- README documents on-chain Funding UserOps (caller-supplied owner EOA → derive Polyester Safe) vs Trading withdraw RPCs; realtime overflow / reconnect recovery contract

### Testing
- Live smokes on Polyester testnet: Funding → Trading UserOp (`TradingGateway.deposit`) and Funding → BSC USDT withdraw (`withdrawToChain`) via owner-key smart account

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
