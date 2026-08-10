# Changelog

## Unreleased

## 0.1.0a40

### Breaking
- Generated `TriggerEvent.fire_price_ticks` is now optional (absent for
  time-scheduled TWAP slice fires). Decoded `TriggerEvent.fire_price` is `None`
  when the wire field is unset.

### Added
- `orders.list_open(..., trigger_id=...)` and
  `orders.list_history(..., trigger_id=...)` filter child orders created by a
  standalone trigger (TWAP/ladder slice children and their execution prices).

## 0.1.0a39

### Breaking
- `lifecycle.get_flow_by_tx(...)` now returns `LifecycleFlowsList` instead of
  silently returning only the first match. Its default page size is now 50;
  use `list_flows_by_tx(...)` with `next_page_token` for complete pagination.

### Added
- Generated `polyester.ratelimit.v1` contracts expose structured quota
  rejection details used by order and trade WebSocket responses.

## 0.1.0a38

### Added
- `withdraw.validate_destination` wraps `ValidateWithdrawDestination` and maps
  validation codes to snake labels (`valid`, `invalid_address`,
  `denylisted_address`, …) for preflight checks before Trading → external
  withdraws.

## 0.1.0a37

### Added
- Lifecycle reason catalog maps trading-withdraw failure codes to snake labels:
  `trading_withdraw_policy_denied`, `trading_withdraw_contract_reverted`, and
  `trading_withdraw_execution_failed` .

## 0.1.0a36

### Fixed
- `ExportGuardSignerWalletResult.__repr__` redacts `private_key`.

### Docs
- README documents `UserTrade` fee e18 fields and `fee_is_rebate` polarity.
- README notes that the PyPI package excludes `tests/`; full pytest needs a git checkout.

## 0.1.0a35

### Breaking
- `UserTrade` fee fields move from asset-scaled integers to fixed 18-decimal
  magnitudes: `fee_scaled` → `fee_amount_e18`, `referral_share_scaled` →
  `referral_share_amount_e18` (decimal strings of wire `U128`). Convert to the
  fee asset's catalog scale before subtracting from BUY fill quantity.
- `UserTrade` adds sparse `fee_is_rebate`. When true, `fee_amount_e18` is a
  rebate credit rather than a fee debit (proto3 omits false).

## 0.1.0a34

### Docs
- PyPI Documentation URL points to the Python SDK docs on polyester.ai
  (`/docs/sdk/python/get-started/overview`).

## 0.1.0a33

### Fixed
- Attached `trailing_stop` encode rejects non-positive distance/max slippage and rejects
  `order_type` under `trailing_stop` (child is always market).
- Decode omits attached trailing legs that lack a positive distance (no fabricated
  zero-distance stop).

## 0.1.0a32

### Breaking
- Trigger snapshots no longer expose `child_order_ids`. Child-order history is
  authoritative on trigger events: use `triggers.list_events(..., event_type="fired")`
  and read `child_order_id` / `child_seq`.
- `TriggerEvent.fire_px` renamed to `fire_price`.

### Added
- `triggers.list_events(..., event_type=...)` optional filter
  (`fired` / `canceled` / `updated`).
- `TriggerEvent` thickens with `subaccount_id`, `child_seq`, and
  `child_order_id` (plus existing `symbol_id`, `trigger_type`, `fire_price`,
  `reason`, `ts_ns`).

## 0.1.0a31

### Breaking
- `PreviewOrderResult` no longer exposes fee/debit estimates
  (`estimated_quote_debit`, `estimated_fee`, `estimated_net_base_qty`,
  `fee_asset`, `fresh_at_ts_ns`) or `price_bound`. Wire/public result is now
  admissibility-focused: `admissible`, optional `rejection`
  (`OrderErrorDetail` with `code` + `violations`), `resolved_base_qty_scaled` /
  `resolved_base_qty`, `protected_price_bound` (renamed from `price_bound`;
  protective boundary, not expected fill), and `evaluated_at_ms`.
  Known Preview rejection codes use TypeScript-compatible labels such as
  `BAD_QTY`; unknown open-enum values use `UNKNOWN_ERROR_CODE(<n>)`.
- Lifecycle flow summaries expose `lifecycle_reason` (snake catalog label;
  unknown wire codes become `unknown_reason_{code}`) and optional
  `zipper_reason` (`ZipperReasonDetails`: numeric `code`, `reason_id`,
  `message`). Wire `FlowReason` / `reason_code` renamed to `LifecycleReason` /
  `lifecycle_reason`.

### Added
- `OrderErrorDetail`, `OrderFieldViolation`, and `ZipperReasonDetails` public
  models for Preview rejection and lifecycle Zipper failure detail.

## 0.1.0a30

### Breaking
- `PreviewOrderResult` now exposes typed `estimated_quote_debit` and
  `estimated_fee` (`Quantity`) instead of bare `estimated_quote_debit_scaled` /
  `estimated_fee_scaled` strings. Quote estimates carry `QuantityDomain.ORDER_QUOTE`
  and the pair's catalog quote scale; fee estimates use `ORDER_BASE` or
  `ORDER_QUOTE` according to `fee_asset`.
- Quote-budget encoding (`max_quote_debit`) always resolves the catalog
  `quote_quantity_scale` and rejects typed `Quantity` values that omit scale or
  mismatch the catalog. Prefer `Quantity.from_quote_scaled` /
  `from_quote_decimal` / `from_quote_decimal_str` with
  `QuantityDomain.ORDER_QUOTE`.
- Wire break: `PreviewOrderRequest` now wraps an `OrderIntent`
  (`subaccount_id` + `order`), matching create. The public
  `orders.preview_order(...)` kwargs stay the same create shape.
- Wire break: `TrailingStopTrigger` carries `side`. Standalone trailing create
  still validates sell-only, but encode always populates the wire field.
  Trigger decode surfaces type/side/`parent_order_id` for attached trailing
  stops (side is no longer hardcoded to sell).

### Added
- `QuantityDomain.ORDER_QUOTE` and `Quantity.from_quote_*` constructors.
- Local validation rejects create, cancel, and replace batches above 20 items.

### Fixed
- Transfer/withdraw `AssetAmount` encoding fails closed when neither the value
  nor request parameters provide a source scale (no silent e18 assumption).

### Clarified
- Preview is not deployed on every API host; handle unimplemented/not-found and
  do not make Preview a prerequisite for order submission.
- Market orders enforce slippage-derived price protection; see
  [Market Order Price Protection](https://polyester.ai/developer-docs/shared-concepts/market-order-price-protection).

## 0.1.0a29

### Changed
- README install pin catches up to the current alpha tag. No API changes from `0.1.0a28`.

## 0.1.0a28

### Breaking
- Replaced `fee_source` with `fee_asset` (`quote` or `base`) on trigger and trade models. The backend no longer emits the prior received-asset enum.

### Features
- Orders support explicit base-quantity or quote-budget (`max_quote_debit`) sizing. Create and preview results expose resolved base quantity, quote debit, fee asset, and estimates where returned by the API.
- Added `orders.preview_order(...)` and `is_batch_replace_settled(...)`.

### Fixed
- Batch-replace status decoding now rejects aggregate counts that do not reconcile with item phases.

### Clarified
- Batch-replace admission is not finality: predecessor IDs may be stale after admission, while status returns successor IDs and phases. Poll status for reconciliation, reuse the same `request_id` on retry, and do not treat `is_batch_replace_settled` as finality.

## 0.1.0a27

### Breaking
- Replaced `orders.batch_modify` with `orders.batch_replace`. The new write returns an admission receipt (`batch_request_id`, admission outcomes, and accepted/rejected counts), without behavior or partial-execution options. Poll `orders.get_batch_replace_status(batch_request_id=...)` for execution phases.

## 0.1.0a26

### Breaking
- Order lookup/mutation APIs take a typed `OrderKey` (`OrderId` | `ClientOrderId`) instead of dual optional `order_id` / `client_order_id` kwargs. Affects `orders.get`, `orders.cancel`, `orders.modify`, `wait_for_order_trades_complete`, and batch cancel/modify item dicts (`key=` instead of `order_id`/`client_order_id` fields).

### Fixed
- Reject market creates that also supply a limit `price`.
- Decimal price parsing stays exact (no float intermediate).
- TWAP trigger projection coverage for proto decode paths.

## 0.1.0a25

### Breaking
- `get_current_candle` returns `None` when no candle rows exist, matching Rust `Option<Candle>` instead of a synthetic empty `Candle`.

### Fixed
- Outbound HTTP/Connect/JSON-RPC requests send an explicit `User-Agent: polyester-sdk-python/<version>` instead of the default `python-httpx/*` / library identity, so edge WAF rules that ban browser signatures (Cloudflare error 1010) do not block the SDK before authentication.
- Cloudflare error 1010 responses are mapped to `PolyesterTransportError` with an explicit WAF message instead of being misclassified as `PolyesterAuthError`.
- Orderbook snapshots reject missing or invalid levels, and managed books reject malformed levels and invalid sequence ranges atomically without advancing.
- Regression coverage preserves the protocol's exact depth `1` and `1000` mappings.
- Singular cancel and lookup by client-order-id validate the documented identifier constraints before contacting the transport.
- API-key trading withdraws can be prepared, signed over exact deterministic protobuf bytes, persisted, restored, and submitted unchanged.
- Withdraw and internal-transfer amounts rescale exactly from their declared input scale to `amount_e18`.
- Mutation response-contract violations fail closed with `PolyesterResponseContractError`.
- Snapshot recovery drains post-snapshot publications atomically and coalesces orderbook gap refreshes into a bounded single-flight worker.

## 0.1.0a24

### Fixed
- Local orderbook bucketing rounds asks up and rejects negative prices/quantities instead of emitting corrupted levels.
- `cancel_all` / `cancel_all_after` response decoding rejects empty or unknown statuses (`submitted`/`dry_run`, `armed`/`disabled`) instead of returning success for ambiguous payloads. Cancel-all now also surfaces `failed_cancels`.
- Client order/trigger IDs and caller-supplied request IDs are trimmed and validated locally for documented length and ASCII-character constraints before a request is sent.

### Testing
- Decoder coverage asserts empty/unknown cancel-all and cancel-all-after statuses fail closed.
- Orderbook unit coverage asserts negative levels are rejected and ask buckets round up.

## 0.1.0a23

### Fixed
- Concurrent identical requests receive unique authentication timestamps with a five-second future-skew ceiling. Async Connect/realtime signing uses bounded cooperative backpressure; the synchronous low-level signer returns an immediate retryable capacity error instead of sleeping the caller's thread.

### Clarified
- Document that `client_order_id` on order create is API-optional; set a stable value when retrying after ambiguous mutation failures.

### Testing
- A 10,000-identical-request hardening probe verifies unique bounded authentication tuples while an independent event-loop timer continues to run.

## 0.1.0a22

### Fixed
- Batch-modify and batch-cancel decoding reconcile aggregate counts against per-item outcomes and reject unknown/ambiguous result states.
- Columnar candles reject misaligned OHLCV arrays instead of emitting empty fields.
- Deposit-address creation and singular lifecycle lookups reject missing required entities instead of returning placeholder models.
- User trades expose fee source and referral share, so received-asset fees can be distinguished from quote fees and BUY net quantity can be calculated correctly.
- Concurrent identical requests receive unique authentication timestamps with a five-second future-skew ceiling and bounded backpressure.

### Testing
- Public-service Connect fault injection covers inconsistent batch counts and misaligned candle columns in addition to decoder-level boundary tests.
- The funded BUY-to-SELL acceptance test waits for complete fill projection and sells net received base quantity after received-asset fees.

## 0.1.0a21

### Breaking
- Trading withdrawals require explicit non-empty `idempotency_key` and non-zero `nonce` values.
- Scale-dependent market data, orderbook, and Zipper supply paths require hydrated catalog scales instead of guessing.
- Low-level trigger, candle, realtime-candle, and local-orderbook codecs require an explicit quantity scale.

### Features
- `AsyncSubscription.set_on_error` exposes background transport and terminal feed errors.
- Retry classifiers and cryptographically random withdrawal key/nonce helpers are exported.

### Fixed
- Batch-create decoding rejects missing outcomes and inconsistent aggregate counts; unknown rejection enum values retain their numeric code.
- Realtime reconnects use capped exponential backoff with per-subscription jitter.
- Signing timestamps stay on wall clock during large concurrent bursts and malformed absolute URLs fail before send.
- Catalog hydration rejects conflicting symbol/asset identities atomically, preserves the previous valid snapshot after a rejected refresh, and accepts valid scale `0`; REST and realtime public trades carry catalog quantity-scale metadata.

## 0.1.0a20

### Breaking
- Removed the unused `max_retries` constructor/transport option. The SDK never performed automatic unary retries; applications must retry eligible transport/rate-limit failures with stable idempotency keys and reconcile mutation outcomes.

### Fixed
- ConnectRPC responses are capped at 4 MiB explicitly, including catalog hydration.
- The funded market roundtrip can use external order-book liquidity when dedicated maker credentials are unavailable, carries partial BUY fills into cleanup, and cancels only its own client order IDs.
- Live market reference-price helpers format typed `Price` values before decimal sizing.
- Removed an unused legacy JSON unary bridge that referenced a nonexistent authenticated transport method; all service calls remain generated binary ConnectRPC.
- Corrected kw-only `ApiData` construction in heatmap and zipped-supply realtime decoders.

### Testing
- Hardening coverage now injects corrupt and oversized protobuf catalog responses.
- Whole-source `mypy` is now a required CI gate for the advertised typed package.
- Tests that use non-dry-run `cancel_all` require an explicit dedicated-account cleanup gate.

## 0.1.0a19

### Fixed
- Realtime HTTP 401/403 errors now expose `code`, `context`, and `endpoint` in addition to the existing status/label/body fields.
- Snapshot reconnect retries retain buffered publications across failed attempts and close the replacement WebSocket when cancellation interrupts refresh.
- Oversized WebSocket messages fail closed instead of entering a reconnect loop.
- Every live-test and smoke path now uses `POLYESTER_TEST_TRADE_SYMBOL`; legacy smoke-symbol variables are no longer consulted.

### Testing
- Added oversized-message and combined reconnect/retry/cancellation fault-injection regressions.

## 0.1.0a18

### Breaking
- `wait_for_catalogs()` now raises when catalog hydration fails (HTTP errors, empty/malformed spot or zipper, out-of-range scales/ids). Previously returned successfully after a best-effort failure. Use `catalogs_last_error` to inspect the failure.
- `format_qty_scaled` / `format_ledger_u128` / `Quantity.format` / `AssetAmount.format` raise `PolyesterValidationError` when `scale > MAX_PROTOCOL_SCALE` (36) instead of allocating pathological padding.
- Realtime token HTTP 403 maps to `PolyesterAuthError` with `status_code`, `label`, and truncated `body` (not opaque `PolyesterRealtimeError("… HTTP 403")`).

### Features
- `MAX_PROTOCOL_SCALE = 36` exported; catalog hydrate rejects `u64→u32` truncation and scales above the protocol max.
- `CatalogManager.hydrate_zipper_config_typed` accepts typed `DepositWithdrawConfig` without a consumer JSON round-trip.
- `wait_for_order_trades_complete` / `orders.wait_for_order_trades_complete` poll until sum(trade qtys) equals order `cum_qty` or timeout.
- JSON-RPC client enforces a 1 MiB response body cap and validates `jsonrpc=="2.0"`, matching `id`, and exactly one of `result`|`error`.
- `AsyncSnapshotThenStreamSubscription.last_error` / `err()` surfaces snapshot refresh failures; one bounded reconnect retry then fail-closed.
- `AsyncRealtimeClient.aclose` cancels tracked subscriptions; WebSocket inbound frames bounded by `WS_MAX_MESSAGE_BYTES`.

### Fixed
- Realtime token fetch and JSON-RPC request/arequest now enforce one absolute wall-clock deadline across headers + bounded body collect (slow-drip safe). Sync JSON-RPC uses a deadline closer that aborts the client without leaking worker threads.
- Realtime token exchange streams and size-caps the body under the HTTP client timeout.
- `TransportFactory` / `TransportConfig` `__repr__` redacts credentials (parity with credential repr).

### Testing
- Local public-API hardening L2 suite (`tests/hardening/`) for token stall/403, JSON-RPC, catalogs, snapshot, and scale.
- Live harness: STRICT_LIVE fail-on-skip + executed/skipped/failed counts; `POLYESTER_TEST_TRADE_SYMBOL`; market BUY→SELL roundtrip carries filled qty; BatchModify 5×40 regression (gated).

## 0.1.0a17

### Breaking
- `AssetBalance` drops `trading_updated_at_ns` / `funding_updated_at_ns` / `reserved_updated_at_ns`. Use `trading_revision` (orders trading/reserved/available) and `funding_revision` (orders funding independently) instead.
- `CatalogManager.base_quantity_scale_for_symbol` / `_id` return `None` when unknown/unhydrated instead of inventing scale `8`. Decode-only paths (orderbook/market data) keep an explicit `or 8` fallback.

### Fixed
- Order/trigger write paths auto-await `wait_for_catalogs` before resolving pair quantity scale, preventing first-order false `INSUFFICIENT_FUNDS` when ETH-USDT (scale 6) was encoded at invented scale 8.

## 0.1.0a16

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
- Stable MFA auth error codes: `AUTH_API_KEY_MFA_REQUIRED` is removed; use `AUTH_MFA_NOT_ENROLLED`, `AUTH_STEP_UP_REQUIRED`, `AUTH_MFA_ELEVATION_REQUIRED`, and `AUTH_MFA_LAST_FACTOR_REQUIRED` from `AuthErrorDetail`
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
- `policies.subscribe_api_policies` typed subscribe for `private:auth:api-policies:{account_id}:proto` (sync: `subscribe_api_policies_sync`)

### Testing
- Unit coverage for MFA auth-code mapping and predicates
- Unit coverage for API/subaccount policy realtime protobuf decode
- Live trigger create asserts `status == "accepted"`

### Changed
- CI no longer auto-commits `sdk-capabilities.json` / README on pull requests. Capability refresh + optional bot commit runs only on merge to `main`.
- README capability matrix labels clarify API-key-safe account surfaces (reads/subscribe vs session-only admin)
- Realtime subscribe waits for the Centrifugo handshake (including private token fetch) before returning; initial auth failures are returned immediately

## 0.1.0a13

### Breaking
- wire break: order and trigger creation now target explicit execution variants. The flat `order_type`/`tif`/`post_only`/`price` inputs are still accepted on `CreateOrderRequest` but are mapped onto the new `OrderIntent` execution oneof (`market_ioc`/`limit_gtc`/`limit_ioc`/`limit_fok`); `post_only` is only valid for limit-GTC and is rejected otherwise
- `CreateOrderRequest` now wraps an `OrderIntent` (`subaccount_id` + `order`); batch create items are `OrderIntent`s and the removed `allow_partial` argument is accepted but ignored
- `triggers.create` maps flat params onto the new `TriggerIntent` strategy oneof (`stop_loss`/`take_profit` conditional, `trailing_stop`, `twap`, `ladder`); trailing stops are always SELL market-IOC, ladder distribution only accepts `linear`, and `trigger_price_source` is dropped from the wire
- `CreateOrderResponse` / `CreateTriggerResponse` no longer carry a `status` field; admitted mutations synthesize `status="accepted"`
- Batch-create result items now use an `accepted`/`rejected` oneof, projected back onto the flat `status`/`order_id`/`code` result model
- `Trigger` read model now exposes full proto fields (order params, timestamps, detail blocks, `post_only`, `parent_order_id`, child order ids)
- `Order` read model adds `post_only` and `attached_risk`
- `triggers.list` accepts validated `status` filter labels (`created`/`armed`/`running`/`completed`/`cancelled`/`failed`/`paused`)

### Fixed
- Order/trigger decode reads the shapes: attached-risk legs derive `order_type`/`limit_price` from their `RiskExecution` child, and the thick `Trigger` projection is rebuilt from the configuration oneof + runtime detail blocks
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
- `triggers.create()` exposes the full `CreateTriggerRequest` surface, unblocking `TRAILING_STOP`, `TWAP`, and `LADDER` creation via the SDK: `fee_asset`, `self_trade_prevention_mode`, `trailing_distance_ticks`/`trailing_distance_bps`, `activation_price`, `max_slippage_ticks`/`max_slippage_bps`, `twap_duration_ms`/`twap_slice_interval_ms`, `ladder_price_min`/`ladder_price_max`, `ladder_levels`, and `ladder_distribution`
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
- `market_overview.create_subscription()`: snapshot-then-stream merge (TS parity)

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
- `test_orders_get_round_trips_list_open`: proof-style when open orders exist
- `scripts/test_all.sh` and `scripts/smoke_test.py` (pytest wrapper)
- `scripts/smoke_realtime.sh`: unit realtime tests + live Centrifugo heartbeat (~35s)
- Unit tests for Centrifugo ping/pong and batched frames
- Integration test holds a public trades subscription past Centrifugo heartbeat interval
- CI: `pytest tests/unit` with coverage on non-`gen/` code
- Full devnet suite documents honest skips for OMS read lag, JWT routes, optional mounts, and account-specific prerequisites

## 0.1.0a0

- Initial alpha release with core trading and market data services.
