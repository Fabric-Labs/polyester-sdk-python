# TypeScript SDK Parity Tracker

Living ledger for `polyester-sdk` vs `packages/polyester-client`. Update when shipping slices.

Legend: **Done** · **Partial** · **Planned** · **Deferred** · **Omitted** · **Blocked**

## Client And Auth

| TypeScript | Python | Status | Notes |
| --- | --- | --- | --- |
| `PolyesterClient` | `AsyncPolyester` | Done | Full service tree + maintained orderbook/market-overview streams. |
| `PolyesterServerClient` | `Polyester` | Done | Sync facade: `catalog`, nested services, `subscribe_sync` on all realtime surfaces. |
| `PolyesterBrowserClient` | — | Omitted | API-key-only Python SDK. |
| JWT/session auth | — | Omitted | |
| API-key Ed25519 auth | API-key auth | Done | Signing + gzip-aware body hash. |

## Trading And Market Data

| Service | Status | Implemented | Missing |
| --- | --- | --- | --- |
| `market_data` / `candles` | Done | spot config, trades, candles, `subscribe_trades`, `subscribe_candles`, sync variants | |
| `orderbook` | Done | `get`, `subscribe_deltas`, `create_subscription`, sync `set_bucket` | |
| `orders` | Done | CRUD, batch, `subscribe`, `account=` scope | |
| `trades` | Done | `list`, `subscribe`, `account=` scope | |
| `balances` | Done | list/history/equity/holds, `subscribe`, `account=` scope | Funding→trading on-chain only |
| `triggers` | Done | CRUD, `subscribe`, `subscribe_events`, `account=` scope | |
| `transfers` | Done | `list`, `subscribe`, `account=` scope | |
| `market_overview` | Done | `list`, `subscribe`, `create_subscription` (snapshot merge) | |
| `heatmap` | Done | `get`, `subscribe_live`, sync variant | |
| `lifecycle` | Done | list/get, flow subscribe + sync variants | |
| `zipper` | Done | typed config, enriched catalog, supply subscribe + catalog patch | |
| `chain_analytics` | Done | supply + unified balances RPCs | |
| `trading_withdraws` | Partial | signed intent withdraws, `account=` on wallet withdraw | Wallet helper in API-key SDK |
| `ledger_write` | Partial | four transfer/reserve RPCs | Devnet route may be unmounted; uses account_id not subaccount scope |
| `internal_transfers` | Done | `create`, `account=` scope | |
| `deposit` | Done | `list_addresses`, `create_address`, `account=` scope | |

## Realtime

| Area | Status | Notes |
| --- | --- | --- |
| API-key RT auth | Done | `/v1/rt/token` + `/v1/rt/subscribe` signed GET |
| Private trading streams | Done | orders, balances, trades, transfers, triggers (+ events) |
| Private admin streams | Done | api_keys, sub_accounts, policies, address_book invalidations, identity |
| Public market streams | Done | trades, candles, heatmap, market_overview, orderbook deltas |
| Public chain streams | Done | lifecycle flows, zipper supply |
| Orderbook local book | Done | `create_subscription` snapshot + seq-checked deltas + gap refresh |
| Market overview merge | Done | `create_subscription` snapshot-then-stream |
| Sync `subscribe_sync` | Done | All async subscribe surfaces mirrored on `Polyester` |

## Account And Admin

| Service | Status | Notes |
| --- | --- | --- |
| `accounts` / `resolve` | Done | `client.accounts` alias |
| `auth` / `profile` | Partial | `me`, profile CRUD, `subscribe_identity` (+ sync); profile JWT on devnet |
| `api_keys` | Done | CRUD, `generate_keypair`, `subscribe`, `account=` scope |
| `sub_accounts` | Done | CRUD, `subscribe`, `subscribe_api_keys`, `account=` scope |
| `policies` | Done | CRUD, `subscribe_subaccount_policies`, `account=` on subaccount policy ops |
| `address_book` | Done | CRUD, `subscribe_view_invalidations`, `account=` scope |
| `guard_signer` | Done | Wallet lifecycle + signing, `account=` scope |
| `socialVerification` / `social_verification` | Done | `start`, `mark_ready`, `get` |
| `whiteboard` | Done | CRUD, ACL, archive, join token |
| `polychart` | Done | Layers, drawings, publish/share |
| `layout` | Done | Layouts, templates, subscriptions |
| `mfa` | Blocked | Unless API keys support step-up |

## Deferred Or Omitted

| Area | Status | Rationale |
| --- | --- | --- |
| `bridge` | Deferred | Product confirmation. |
| `tradews/v1` | Deferred | Proto additive; assess wrapper need after merge. |
| Browser/wallet/mock | Omitted | |

## Release And Repo

| Item | Status | Notes |
| --- | --- | --- |
| `polyester-python-proto` on PyPI | Partial | Pin `polyester-python-proto==X.Y.Z` with each SDK release. |
| Public GitHub repo | Done | Proprietary license; source visible, not OSS. |
| CI (pytest + ruff) | Done | `.github/workflows/ci.yml` |

## Current Blockers (backend / devnet only)

- MFA service blocked on API-key step-up.
- Devnet OMS read path may not index accepted orders (order lifecycle e2e skips).
- `list_holds` unmounted on devnet gateway.
- JWT/session routes (profile, whiteboard, layout, polychart) on API-key devnet.
- Spot fill e2e needs liquidity/maker.
- Full devnet suite (typical account): **214 collected**, **~208 passed / ~16 skipped**.
