# Changelog

## Unreleased

- Authenticated services: `orders.modify`, `orders.cancel_all`, `triggers` (list/get/create/cancel/modify/pause/resume/list_events), `transfers.list`, `internal_transfers.create`, `deposit.list_addresses` / `create_address`, `balances.get_balance_history` / `get_equity_history` / `list_holds`, `balances.transfer_funding_to_unified` (Funding → Unified via `TransferFundToUnified` in proto).
- Typed `msgspec` models for orders, balances, user/market trades, candles, and market overview.
- `orders.list_history`, `orders.get`, `trades.list`, and `market_data.subscribe_trades` (minimal public realtime).
- GitHub Actions CI (pytest + ruff) and release notes for `polyester-python-proto` version coupling.
- Smoke-test authenticated create/cancel when `POLYESTER_SMOKE_MUTATION=1` or read policy succeeds.

## 0.1.0a0

- Use Connect RPC over HTTP (POST, `Connect-Protocol-Version`, JSON body) instead of plain GET.
- Default wire format is JSON until generated protobuf clients land under `polyester._gen`.
- API key env/args use `POLYESTER_API_PRIVATE_KEY` / `api_private_key` to match
  Polyester UI naming.
- Scaffolded PyPI-ready `polyester-sdk` package with `polyester` import package.
- Added API-key-only auth helpers and Ed25519 request signing contract.
- Added initial async/sync client shape, public models, scalar codecs, and service wrappers.
- Added first vertical slice placeholders for market data, orderbook, and orders.
- Documented dependency choices, release workflow, and TypeScript parity tracking.
