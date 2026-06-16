# Python SDK implementation status

Living snapshot of what `polyester-sdk` exposes today. For the original TypeScript parity plan, see `06-typescript-parity.md` (read-only).

## Client

| Surface | Status |
| --- | --- |
| `AsyncPolyester` / `Polyester` | Done |
| `from_env()` | Done |
| `format_ledger_u128` / `LEDGER_SCALE` | Done |
| API-key Ed25519 auth | Done |

## Services (high level)

| Service | Status | Notes |
| --- | --- | --- |
| `market_data` | Partial | `get_spot_config`, trades, candles, columns, `get_current_candle`, `subscribe_trades` |
| `market_overview` | Partial | `list` |
| `orderbook` | Partial | `get` |
| `heatmap` | Partial | `get` |
| `zipper` | Partial | `get_deposit_withdraw_config` |
| `lifecycle` | Partial | `list_flows`, `get_flow`, `get_flow_by_tx` |
| `echo` | Partial | Devnet may 404 |
| `balances` | Partial | `list`, history, equity, holds, `get_health` |
| `orders` | Partial | CRUD, `cancel_all`, `batch_modify`, attached-risk flags |
| `trades` | Partial | `list` |
| `triggers` | Partial | Full CRUD + events |
| `transfers` | Partial | `list` |
| `internal_transfers` | Partial | `create` |
| `deposit` | Partial | `list_addresses`, `create_address` |
| `api_keys` | Partial | `list`, `get` |
| `resolve` | Partial | `resolve_account` |
| `address_book` | Partial | `list_transfer_destinations` |
| `withdraw` | Partial | `create_trading_withdraw` |

## Not in current proto / SDK

- `transfer_funding_to_unified` — no `TransferFundToUnified` in generated `ledger_write` at this revision
- JWT / browser client flows — out of scope for API-key SDK

## Planned next (SDK-only)

- `auth.policies`, `auth.sub_accounts`, `chain.guard_signer`
- Private realtime (orders, balances, transfers)
- Default binary Connect wire
- `market_overview.subscribe`, `heatmap.subscribe_live`

## Blockers outside SDK

- Devnet routes not mounted (`echo`, `get_current_candle`, some ledger writes)
- Trading balance required for order/trigger mutations after funding-only deposits
