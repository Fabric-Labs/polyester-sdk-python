# TypeScript SDK Parity Tracker

Living ledger for `polyester-sdk` vs `packages/polyester-client`. Update when shipping slices.

Legend: **Done** · **Partial** · **Planned** · **Deferred** · **Omitted** · **Blocked**

## Client And Auth

| TypeScript | Python | Status | Notes |
| --- | --- | --- | --- |
| `PolyesterClient` | `AsyncPolyester` | Partial | Service tree + generated Connect clients; realtime v0 (public trades). |
| `PolyesterServerClient` | `Polyester` | Partial | Sync facade over async client. |
| `PolyesterBrowserClient` | — | Omitted | API-key-only Python SDK. |
| JWT/session auth | — | Omitted | |
| API-key Ed25519 auth | API-key auth | Done | Signing + gzip-aware body hash. |

## Trading And Market Data

| Service | Status | Implemented | Missing |
| --- | --- | --- | --- |
| `marketData` / `market_data` | Partial | `get_spot_config`, `get_trades`, `get_candles`, `get_candles_columns`, `subscribe_trades` | Private streams, maintained catalog models. |
| `candles` (TS service) | Partial | Methods on `market_data` | Separate `client.candles` alias optional. |
| `orderbook` | Partial | `get` (generated) | Delta stream, local book. |
| `orders` | Partial | `list_open`, `list_history`, `get`, `create`, `cancel`, `modify`, `cancel_all` | Streams, batch modify. |
| `trades` | Partial | `list` (user trades) | Private trade stream. |
| `balances` | Partial | `list`, `get_balance_history`, `get_equity_history`, `list_holds`, `transfer_funding_to_unified` | Unified→funding not in proto yet; private stream. |
| `triggers` | Partial | `list`, `get`, `create`, `cancel`, `modify`, `pause`, `resume`, `list_events` | Streams. |
| `transfers` | Partial | `list` (ledger transfers) | Private stream. |
| `internal_transfers` | Partial | `create` | |
| `deposit` | Partial | `list_addresses`, `create_address` | Withdraw service. |
| `marketOverview` / `market_overview` | Partial | `list` (typed) | `subscribe` stream. |
| `heatmap` | Partial | `get` | `subscribe_live`. |
| `lifecycle` | Partial | `list_flows`, `get_flow`, `get_flow_by_tx` | Public lifecycle streams. |
| `zipper` | Partial | `get_deposit_withdraw_config` | Typed asset/chain models. |
| `echo` | Partial | `echo` | Devnet may not mount service. |

## Realtime

| Area | Status | Notes |
| --- | --- | --- |
| Public market trades | Partial | `market_data.subscribe_trades` via Centrifugo JSON + protobuf decode. |
| Private orders/balances | Planned | Needs API-key RT token endpoints confirmed. |
| Orderbook deltas | Planned | |

## Account And Admin

| Service | Status | Notes |
| --- | --- | --- |
| `accounts` | Planned | Confirm API-key access. |
| `api_keys` | Planned | May need step-up. |
| `policies.*` | Planned | |
| `sub_accounts` | Planned | |
| `address_book` | Planned | |
| `guard_signer` | Planned | |
| `mfa` | Blocked | Unless API keys support step-up. |

## Deferred Or Omitted

| Area | Status | Rationale |
| --- | --- | --- |
| `socialVerification`, `whiteboard`, `profile` | Deferred | Not bot-core. |
| `bridge` | Deferred | Product confirmation. |
| Browser/wallet/mock | Omitted | |

## Release And Repo

| Item | Status | Notes |
| --- | --- | --- |
| `polyester-python-proto` on PyPI | Partial | Pin `polyester-python-proto==X.Y.Z` with each SDK release. |
| Public GitHub repo | Done | Proprietary license; source visible, not OSS. |
| CI (pytest + ruff) | Done | `.github/workflows/ci.yml` |

## Current Blockers

- Default wire format is still JSON; flip to binary protobuf for production parity with TS.
- Expand smoke coverage as new authenticated services land.
- Orderbook snapshot availability per symbol on devnet.
- Realtime private channels need API-key token endpoint confirmation.
