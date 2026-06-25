# Changelog

## Unreleased

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
