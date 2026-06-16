# Devnet smoke test

Living guide for `scripts/smoke_test.py`. Does not replace the original SDK planning docs.

## Run

```bash
cd polyester-python
cp .env.example .env
# POLYESTER_API_KEY_ID, POLYESTER_API_PRIVATE_KEY

.venv/bin/python scripts/smoke_test.py
```

## Environment

| Variable | Purpose |
| --- | --- |
| `POLYESTER_API_KEY_ID` | Required |
| `POLYESTER_API_PRIVATE_KEY` | Required (64-char hex Ed25519 secret) |
| `POLYESTER_ACCOUNT_ID` | Profile base58 id (optional for most reads) |
| `POLYESTER_API_URL` | Default `https://api-devnet.polyester.ai` |
| `POLYESTER_SMOKE_SYMBOL` | Override pair; otherwise auto-picks `BNB-USDT`, then `SOL-USDT`, etc. |
| `POLYESTER_SMOKE_CHAIN_ID` | Override deposit chain; otherwise first chain from zipper config |
| `POLYESTER_SMOKE_TX_HASH` | Optional `lifecycle.get_flow_by_tx` |
| `POLYESTER_SMOKE_RESOLVE_QUERY` | Optional `resolve.resolve_account` |
| `POLYESTER_SMOKE_MUTATION` | `1` to run far-from-market limit create + cancel |
| `POLYESTER_SMOKE_REALTIME` | `1` to test `subscribe_trades` |

## Required vs optional steps

**Required** exercises authenticated reads, public market data for the smoke symbol, lifecycle list, ledger health, and deposit address list (when zipper returns a chain).

**Optional** steps are expected to fail on some devnet builds:

- `echo`, `orderbook`, `get_current_candle`, `list_holds`
- `deposit.create_address`, `orders.create` (needs trading balance)
- `resolve`, `api_keys.get` (policy-dependent)

Exit code is **0** only when all required steps pass.

## Common devnet outcomes

- **Funding vs trading:** deposits show in `balances.list` under `funding`; spot orders need `trading` balance.
- **Route not found:** SDK raises `PolyesterRouteNotFoundError` when the gateway returns plain HTTP 404 for a Connect RPC.
- **Orderbook not found:** symbol may exist in spot config but not on the orderbook service; smoke uses BNB-USDT by default to reduce this.
