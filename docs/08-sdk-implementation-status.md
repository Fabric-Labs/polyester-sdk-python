# Python SDK implementation status

Living snapshot of what `polyester-sdk` exposes today.

## Client

| Surface | Status |
| --- | --- |
| `AsyncPolyester` / `Polyester` | Done |
| `from_env()` | Done |
| `format_ledger_u128` / `LEDGER_SCALE` | Done |
| API-key Ed25519 auth | Done |

## Services (bot-core)

| Service | Status | Notes |
| --- | --- | --- |
| `market_data` | Done | spot config, trades, candles, columns, `get_current_candle`, `subscribe_trades` |
| `market_overview` | Done | `list` |
| `orderbook` | Done | `get` |
| `heatmap` | Done | `get` |
| `zipper` | Done | `get_deposit_withdraw_config` |
| `lifecycle` | Done | `list_flows`, `get_flow`, `get_flow_by_tx`, `list_flows_by_tx` |
| `balances` | Done | list, history, equity, holds, `get_health` |
| `orders` | Done | CRUD, `cancel_all`, `batch_modify`, `batch_create`, `batch_cancel`, `cancel_all_after` |
| `trades` | Done | `list` |
| `triggers` | Done | Full CRUD + events |
| `transfers` | Done | `list` |
| `internal_transfers` | Done | `create` |
| `deposit` | Done | `list_addresses`, `create_address` |
| `withdraw` / `trading_withdraws` | Done | `create_to_funding`, `create_to_external_chain`, `create_wallet_trading_withdraw` |
| `ledger_write` | Done | `transfer_trading_to_trading`, `create_funding_user_transfer`, `reserve_trading_withdraw`, `release_trading_withdraw_reserve` |
| `api_keys` | Done | `list`, `get`, `create`, `update`, `delete`, `generate_keypair` |
| `resolve` | Done | `resolve_account` |
| `address_book` | Done | Full CRUD + views + transfer destinations |
| `policies` | Done | Subaccount + API key policy CRUD and assignment |
| `sub_accounts` | Done | List/create/members/invites + view service |
| `guard_signer` | Done | Wallet lifecycle + protected action signing |
| `auth` / `profile` | Done | `me`, `profile.get` / `update` / `get_username_history` |
| `chain_analytics` | Done | zipped supply, supply group, unified balances |
| `social_verification` | Done | `start`, `mark_ready`, `get` |
| `whiteboard` | Done | CRUD, ACL, archive, join token |
| `polychart` | Done | layers, drawings, publish/share/subscribe |
| `layout` | Done | layouts, templates, publish/share/subscriptions |

## Not in current gen / SDK

- Funding → trading bucket move — on-chain via TradingGateway deposit (UI / wallet), not an API-key RPC
- MFA service — session/step-up oriented; omit until API-key step-up is confirmed
- Realtime private channels — in progress (see Planned next)
- `echo` — no proto in `gen/`
- JWT / browser client flows — out of scope for API-key SDK
- `polychart`, `layout`, `whiteboard`, `mfa`, `profile`, `social_verification` — deferred (app-oriented)

## Testing

- CI: `pytest tests/unit` + ruff
- Local: integration + e2e against devnet — see `docs/10-testing.md`

## Planned next

- Private realtime (orders, balances, transfers)
- Default binary Connect wire
- `market_overview.subscribe`, `heatmap.subscribe_live`
