# TypeScript SDK Parity Tracker

Living ledger for `polyester-sdk` vs `packages/polyester-client`. Update when shipping slices.

Legend: **Done** · **Partial** · **Planned** · **Deferred** · **Omitted** · **Blocked**

## Client And Auth

| TypeScript | Python | Status | Notes |
| --- | --- | --- | --- |
| `PolyesterClient` | `AsyncPolyester` | Partial | Full service tree + realtime subscribe surface; orderbook book builder TBD. |
| `PolyesterServerClient` | `Polyester` | Partial | Sync facade over async client. |
| `PolyesterBrowserClient` | — | Omitted | API-key-only Python SDK. |
| JWT/session auth | — | Omitted | |
| API-key Ed25519 auth | API-key auth | Done | Signing + gzip-aware body hash. |

## Trading And Market Data

| Service | Status | Implemented | Missing |
| --- | --- | --- | --- |
| `market_data` / `candles` | Partial | spot config, trades, candles, `subscribe_trades`, `subscribe_candles` | Snapshot-then-stream market overview merge helper |
| `orderbook` | Partial | `get`, `subscribe_deltas` | Stateful local book (`createSubscription`) |
| `orders` | Partial | CRUD, batch, `subscribe` | |
| `trades` | Partial | `list`, `subscribe` | |
| `balances` | Partial | list/history/equity/holds, `subscribe` | Funding→trading on-chain only |
| `triggers` | Partial | CRUD, `subscribe`, `subscribe_events` | |
| `transfers` | Partial | `list`, `subscribe` | |
| `market_overview` | Partial | `list`, `subscribe` | TS snapshot-then-stream merge on subscribe |
| `heatmap` | Partial | `get`, `subscribe_live` | |
| `lifecycle` | Partial | list/get, `subscribe_open_flows`, `subscribe_flow_detail` | |
| `zipper` | Partial | config, `subscribe_zipped_asset_supply` | Typed catalog models |
| `chain_analytics` | Done | supply + unified balances RPCs | |
| `trading_withdraws` | Partial | signed intent withdraws | Wallet helper in API-key SDK |
| `ledger_write` | Partial | four transfer/reserve RPCs | Devnet route may be unmounted |
| `internal_transfers` | Partial | `create` | |
| `deposit` | Partial | `list_addresses`, `create_address` | |

## Realtime

| Area | Status | Notes |
| --- | --- | --- |
| API-key RT auth | Done | `/v1/rt/token` + `/v1/rt/subscribe` signed GET |
| Private trading streams | Partial | orders, balances, trades, transfers, triggers (+ events) |
| Private admin streams | Partial | api_keys, sub_accounts, policies, address_book invalidations |
| Public market streams | Partial | trades, candles, heatmap, market_overview, orderbook deltas |
| Public chain streams | Partial | lifecycle flows, zipper supply, identity updates |
| Orderbook local book | Planned | TS `createSubscription` snapshot+delta merge |
| Market overview merge | Planned | TS snapshot-then-stream on subscribe |

## Account And Admin

| Service | Status | Notes |
| --- | --- | --- |
| `accounts` / `resolve` | Done | `client.accounts` alias |
| `auth` / `profile` | Partial | `me`, profile CRUD, `subscribe_identity` |
| `api_keys` | Partial | CRUD, `generate_keypair`, `subscribe` |
| `sub_accounts` | Partial | CRUD, `subscribe`, `subscribe_api_keys` |
| `policies` | Partial | CRUD, `subscribe_subaccount_policies` |
| `address_book` | Partial | CRUD, `subscribe_view_invalidations` |
| `guard_signer` | Done | Wallet lifecycle + signing |
| `socialVerification` / `social_verification` | Done | `start`, `mark_ready`, `get` |
| `whiteboard` | Done | CRUD, ACL, archive, join token |
| `polychart` | Done | Layers, drawings, publish/share |
| `layout` | Done | Layouts, templates, subscriptions |
| `mfa` | Blocked | Unless API keys support step-up |

## Deferred Or Omitted

| Area | Status | Rationale |
| --- | --- | --- |
| `bridge` | Deferred | Product confirmation. |
| Browser/wallet/mock | Omitted | |

## Release And Repo

| Item | Status | Notes |
| --- | --- | --- |
| `polyester-python-proto` on PyPI | Partial | Pin `polyester-python-proto==X.Y.Z` with each SDK release. |
| Public GitHub repo | Done | Proprietary license; source visible, not OSS. |
| CI (pytest + ruff) | Done | `.github/workflows/ci.yml` |

## Current Blockers

- Orderbook stateful subscription (snapshot + gap recovery) not yet ported from TS.
- Market overview `subscribe` emits raw batches; TS merges into a live map with snapshot prefetch.
- MFA service blocked on API-key step-up.
