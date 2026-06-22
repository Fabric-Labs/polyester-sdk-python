# Testing guide

The Python SDK uses a three-tier test pyramid. **CI runs unit tests only.** Integration and e2e tests hit **real devnet** with your API key from `.env` — no HTTP mocking.

## Setup

```bash
cd polyester-sdk-python
cp .env.example .env
# Set POLYESTER_API_KEY_ID and POLYESTER_API_PRIVATE_KEY
pip install -e ".[dev,realtime]"
```

## Test tiers

| Tier | Marker | Env flag | Touches balances? |
|------|--------|----------|-------------------|
| Read | `@pytest.mark.integration` | (none) | No |
| Mutation-safe | `@pytest.mark.mutation` | `POLYESTER_TEST_MUTATION=1` | Holds only (post-only limit, then cancel) |
| Funded | `@pytest.mark.funded` | `POLYESTER_TEST_FUNDED=1` | Yes (batch orders, holds, internal transfer) |
| Treasury | `@pytest.mark.treasury` | `POLYESTER_TEST_TREASURY=1` | Withdraw, guard wallet ops |

### Account prerequisites

Devnet deposits land in **funding** balance; spot orders need **trading** balance. Default smoke pair is **ETH-USDT** with **USDT** quote-balance checks (typical devnet funding: USDT on Ethereum → unified trading).

Mutation/funded **buy** limit orders and **buy stop** triggers reserve USDT. Sell-side triggers need base-asset (ETH) balance and are not the default path.

Order mutation tests skip with a clear message when devnet OMS returns `INTERNAL_ERROR` (known devnet issue as of this writing).

Mutation and funded order tests skip with a clear message when trading balance is below `POLYESTER_TEST_MIN_TRADING_QUOTE` (default `10`).

Funding → trading is **not** automatable via the API-key SDK: it is an on-chain `TradingGateway.deposit` from the funding wallet. Move USDT into trading manually in the devnet UI before running mutation/funded suites (or set `POLYESTER_TEST_SKIP_FUNDING_CHECK=1` to bypass the preflight only).

Trading → funding uses `client.trading_withdraws.create_to_funding(...)` with a signed `TradingWithdrawIntentPayload` (treasury tests, `POLYESTER_TEST_TREASURY=1`).

### Trade/fill e2e

Single-account self-match is not a valid fill test because spot matching enforces self-trade prevention. The fill e2e is therefore gated behind `POLYESTER_TEST_TRADE_E2E=1`. Without maker credentials it attempts a passive taker buy against the best visible devnet ask. If no ask is visible, it skips before placing an order.

Set `POLYESTER_TEST_TRADE_SYMBOL=BTC-USDT` to test USDT → BTC. The passive flow buys at the current best ask, then verifies `orders.get(...).trades`, `trades.list(...)`, and taker balance direction. For deterministic coverage, also set `POLYESTER_TEST_MAKER_API_KEY_ID` and `POLYESTER_TEST_MAKER_API_PRIVATE_KEY`; then the test posts a maker sell from the second account and verifies both sides. It will still skip while devnet OMS returns the known order-create `INTERNAL_ERROR`.

## Commands

```bash
# CI (no network)
pytest tests/unit -q

# Read-only live validation
pytest tests/integration tests/e2e -m "integration and not mutation and not funded" -v

# Safe mutations (post-only orders)
POLYESTER_TEST_MUTATION=1 pytest tests/ -m mutation -v

# Full funded validation
POLYESTER_TEST_MUTATION=1 POLYESTER_TEST_FUNDED=1 pytest tests/e2e/funded tests/integration -m "integration or funded" -v

# Backwards-compatible smoke entrypoint
python scripts/smoke_test.py
```

## Environment variables

| Variable | Purpose |
|----------|---------|
| `POLYESTER_API_KEY_ID` | Required for live tests |
| `POLYESTER_API_PRIVATE_KEY` | Required for live tests |
| `POLYESTER_TEST_MUTATION=1` | Enable mutation tests |
| `POLYESTER_TEST_FUNDED=1` | Enable funded e2e |
| `POLYESTER_TEST_TREASURY=1` | Enable withdraw/guard wallet tests |
| `POLYESTER_TEST_SMOKE_SYMBOL` | Override trading pair |
| `POLYESTER_TEST_MIN_TRADING_QUOTE` | Min trading balance for order tests |
| `POLYESTER_TEST_INTERNAL_TRANSFER_DEST` | Destination account for internal transfer e2e |
| `POLYESTER_TEST_SKIP_FUNDING_CHECK=1` | Skip trading balance preflight |
| `POLYESTER_TEST_TRADE_E2E=1` | Enable two-account spot fill e2e |
| `POLYESTER_TEST_TRADE_SYMBOL` | Spot pair for fill e2e, for example `BTC-USDT` |
| `POLYESTER_TEST_MAKER_API_KEY_ID` | Optional maker account API key for deterministic spot fill e2e |
| `POLYESTER_TEST_MAKER_API_PRIVATE_KEY` | Optional maker account private key for deterministic spot fill e2e |
| `POLYESTER_TEST_TRADE_PRICE` | Optional cross price override when using maker credentials |
| `POLYESTER_TEST_TRADE_QTY` | Optional base quantity override for spot fill e2e |
| `POLYESTER_ACCOUNT_ID` | Base58 account id for resolve integration tests |
| `POLYESTER_TEST_LEDGER_WRITE_SMOKE=1` | Opt-in ledger_write mutation smoke |

## What each tier validates

| Tier | Purpose | Fails when |
|------|---------|------------|
| **Unit** (`tests/unit`) | Proto codecs, request builders, client wiring, mocked unary calls | Decode regressions, wrong enum mapping, broken service request shape |
| **Integration** (`tests/integration`) | One real devnet RPC per test with field-level assertions | Auth, routing, proto drift, API contract changes |
| **E2E** (`tests/e2e`) | Multi-step flows across services | Cross-service identity/balance inconsistencies |

`@pytest.mark.optional` skips when a route is not mounted on devnet. Tests **without** `optional` fail loudly if the route 404s — use that for services that must work on devnet (auth, balances, api keys).

### Coverage map (integration files)

| File | Services / focus |
|------|------------------|
| `test_auth_and_analytics.py` | `auth.me`, `profile`, username history |
| `test_account_services.py` | `resolve`, `api_keys`, `deposit` |
| `test_app_services.py` | `whiteboard`, `layout`, `social_verification`, `polychart` |
| `test_market_public.py` | `market_overview`, `heatmap`, `zipper`, `chain_analytics` |
| `test_balances.py` | balances, history, holds |
| `test_market_data.py` | spot config, trades, candles |
| `test_orders.py`, `test_trades.py`, `test_triggers.py` | trading reads |
| `test_sub_accounts.py`, `test_policies.py`, `test_address_book.py` | account admin |
| `test_ledger_write.py` | ledger write (opt-in mutation) |
| `test_lifecycle.py`, `test_guard_signer.py`, `test_transfers.py` | chain / treasury reads |

E2E: `test_account_identity.py` cross-checks `auth.me`, profile, api keys, and balances in one flow.

## Adding a test for a new RPC

1. Add a unit test in `tests/unit/` building protobuf messages directly (preferred decode path).
2. Add `@pytest.mark.integration` test in `tests/integration/test_<service>.py` calling one SDK method.
3. For writes, use `@pytest.mark.mutation` or `@pytest.mark.funded` and gate with env flags.
4. Use `@pytest.mark.optional` when devnet may not mount the route; skip on `PolyesterRouteNotFoundError`.

### Unit coverage expectations

Every service should have at least one unit test that asserts the **protobuf request shape** sent to `unary_*_decoded` (see `tests/unit/test_services_unary.py`, `test_ledger_write_service.py`, `test_withdraw_service.py`, `test_polychart_layout_services.py`). Codec-only paths belong in dedicated codec tests; service-layer tests catch wiring regressions when method signatures or field names change.

## Layout

```
tests/
  unit/           # CI, no network
  integration/    # one RPC per test, real devnet
  e2e/            # multi-step flows
  e2e/funded/     # balance-changing scenarios
```
