# Python SDK implementation status

Living snapshot of what `polyester-sdk` exposes today. Last full devnet run: **198 passed, 16 skipped, 0 failed** (214 collected).

## Client

| Surface | Status |
| --- | --- |
| `AsyncPolyester` / `Polyester` | Done |
| `from_env()` | Done |
| `format_ledger_u128` / `LEDGER_SCALE` | Done |
| API-key Ed25519 auth | Done |
| Binary Connect wire (default) | Done |
| `realtime` Centrifugo client | Done |

## Services (bot-core)

| Service | Status | Notes |
| --- | --- | --- |
| `market_data` | Done | spot config, trades, candles, columns, `get_current_candle`, `subscribe_trades`, `subscribe_candles` |
| `market_overview` | Done | `list`, raw `subscribe`, `create_subscription` (snapshot merge) |
| `orderbook` | Done | `get`, `subscribe_deltas`, `create_subscription` (snapshot + delta merge) |
| `heatmap` | Done | `get`, `subscribe_live` |
| `zipper` | Partial | `get_deposit_withdraw_config`, `subscribe_zipped_asset_supply`; raw dict catalog |
| `lifecycle` | Done | list/get + `subscribe_open_flows`, `subscribe_flow_detail` |
| `balances` | Done | list, history, equity, holds, `get_health`, `subscribe` |
| `orders` | Done | CRUD, batch, `cancel(symbol=…)`, `subscribe` |
| `trades` | Done | `list`, `subscribe` |
| `triggers` | Done | Full CRUD + events + subscribe |
| `transfers` | Done | `list`, `subscribe` |
| `internal_transfers` | Done | `create` |
| `deposit` | Done | `list_addresses`, `create_address` |
| `withdraw` / `trading_withdraws` | Done | `create_to_funding`, `create_to_external_chain`, `create_wallet_trading_withdraw` |
| `ledger_write` | Done | transfer/reserve RPCs (devnet route may be unmounted) |
| `api_keys` | Done | CRUD, `generate_keypair`, `subscribe` |
| `resolve` | Done | `resolve_account` |
| `address_book` | Done | Full CRUD + `subscribe_view_invalidations` |
| `policies` | Done | CRUD + `subscribe_subaccount_policies` |
| `sub_accounts` | Done | CRUD/members/invites + subscribe |
| `guard_signer` | Done | Wallet lifecycle + protected action signing |
| `auth` / `profile` | Done | `me`, profile CRUD, `subscribe_identity` (profile JWT on devnet) |
| `chain_analytics` | Done | zipped supply, supply group, unified balances |
| `social_verification` | Done | `start`, `mark_ready`, `get` |
| `whiteboard` | Done | CRUD, ACL, archive, join token |
| `polychart` | Done | layers, drawings, publish/share/subscribe |
| `layout` | Done | layouts, templates, publish/share/subscriptions |

## Not in current gen / SDK

- Funding → trading bucket move — on-chain via TradingGateway deposit (UI / wallet), not an API-key RPC
- MFA service — session/step-up oriented; omit until API-key step-up is confirmed
- `echo` — no proto in `gen/`
- JWT / browser client flows — out of scope for API-key SDK

## Testing

| Tier | Count | Role |
| --- | --- | --- |
| Unit (`tests/unit`) | 161 | CI gate; codecs, auth, service wiring |
| Integration + e2e (live) | 53 | Real devnet RPCs and multi-step flows |
| **Full suite** | 214 collected | 198 pass + 16 skip on typical devnet account |

Commands: `docs/10-testing.md`, `./scripts/test_all.sh`, `pytest tests/unit -q` (CI).

### What passes vs skips on devnet (typical API-key account)

**Passes (meaningful):** api_keys round-trip, auth.me, balances, market data, triggers lifecycle, internal transfer, policies/sub_accounts reads, address book, realtime orders subscribe wiring, cancel_all dry_run, deposit addresses.

**Skips (honest, documented):**

| Reason | Tests |
| --- | --- |
| Devnet OMS read index lag after create | order round-trip, batch orders |
| No open orders on book | `test_orders_get_round_trips_list_open` |
| `list_holds` unmounted | holds integration + e2e |
| JWT/session routes | profile, whiteboard, resolve, some e2e identity |
| Routes not on devnet gateway | layout, polychart layers |
| Account not configured | guard signer wallet |
| Env not set | ledger_write smoke, spot fill (no asks / no maker) |

**Smoke vs proof:** `@pytest.mark.smoke` tests pass with empty lists (shape-only). Proof tests (e.g. api_keys get round-trip, trigger lifecycle, internal transfer balance check) assert real data when preconditions are met.

## What's left

### Blocked on backend / devnet

1. **Order read-after-create** — `orders.create` returns `accepted` but `get` / `list_open` empty for 15s+ (Yvan/OMS).
2. **`list_holds`** — mount on devnet gateway.
3. **Spot fill e2e** — needs visible asks or second maker account + liquidity.

### SDK parity (not blocked)

1. **Zipper typed catalog models** — replace raw `zipper_config` dict hydration.
2. **`Polyester` sync facade** — broader coverage / ergonomics vs `AsyncPolyester`.
3. **Orderbook bucket UX** — polish only; core snapshot+delta done.

### Deferred

- MFA (API-key step-up TBD)
- `bridge` service
- PyPI publish + pin `polyester-python-proto` per release
