# Polyester Python SDK

Official Python SDK for Polyester APIs, built for trading bots, backend jobs,
research notebooks, and automation.

**Status:** Alpha (`0.1.0a0`). The repo is **public** (visible on GitHub) under a
**proprietary** license — not open source. API-key-only; no browser or JWT flows.

Generated protobuf types and ConnectRPC clients live in `src/polyester/gen/` and are
updated automatically when public API protos change. Hand-written SDK code (client,
services, models, codecs) lives alongside them under `src/polyester/`.

## Install

Package publishing is not enabled yet. Until the first release, consume this
repository from GitHub or a local checkout:

```bash
cd polyester-sdk-python
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,realtime]"
```

## Authentication

Set in the process environment (never commit keys):

```bash
export POLYESTER_API_KEY_ID="..."
export POLYESTER_API_PRIVATE_KEY="..."   # 64-char hex Ed25519 secret
```

`AsyncPolyester.from_env()` reads `os.environ` only (no `.env` inside the library).

## Quickstart

```python
from polyester import AsyncPolyester

async with AsyncPolyester.from_env() as client:
    overview = await client.market_overview.list(limit=5)
    for market in overview.markets:
        print(market.symbol, market.last_price_ticks)

    open_orders = await client.orders.list_open()
    print(f"{len(open_orders.orders)} open orders")
```

## Create And Cancel

```python
from polyester import AsyncPolyester

async with AsyncPolyester.from_env(default_sub_account_id="") as client:
    result = await client.orders.create(
        symbol="BNB-USDT",
        side="buy",
        order_type="limit",
        tif="gtc",
        qty="0.01",
        price="100",
        post_only=True,
        client_order_id="my-bot-001",
    )
    print(result.status, result.order_id)

    await client.orders.cancel(client_order_id="my-bot-001")
```

Use **decimal strings** for `qty` and `price`. Do not pass floats.

## Balances: funding vs trading

Ledger balances expose separate **funding** and **trading** buckets per asset. Spot
orders spend **trading** balance. Deposits land in **funding** until you move them
(Funding → Unified Trading in the UI). There is no funding→trading RPC in the
current generated ledger write proto; use the dashboard until it is added back.

Format u128 wire amounts with the public helper (18-decimal scale):

```python
from polyester import format_ledger_u128

print(format_ledger_u128(balance.funding), format_ledger_u128(balance.trading))
```

Set `POLYESTER_ACCOUNT_ID` to your profile base58 id (not a raw decimal uint64) for
bucket transfers.

## Public Market Data

```python
candles = await client.market_data.get_candles(symbol="BTC-USDT", timeframe="1m", limit=50)
current = await client.market_data.get_current_candle(symbol="BTC-USDT", timeframe="1m")
trades = await client.market_data.get_trades(symbol="BTC-USDT", limit=20)
health = await client.balances.get_health()

async with client.market_data.subscribe_trades(symbol="BNB-USDT") as sub:
    async for trade in sub:
        print(trade.price_ticks, trade.qty_scaled)
        break
```

Realtime requires `pip install polyester-sdk[realtime]` (websockets).

## Testing

### Unit tests (CI)

```bash
pytest tests -q
ruff check src tests scripts
```

### Live smoke (devnet)

```bash
cp .env.example .env
# POLYESTER_API_KEY_ID, POLYESTER_API_PRIVATE_KEY

.venv/bin/python scripts/smoke_test.py
```

Optional authenticated mutation check (far-from-market limit + cancel):

```bash
export POLYESTER_SMOKE_MUTATION=1
export POLYESTER_SMOKE_SYMBOL=BTC-USDT
export POLYESTER_SMOKE_CHAIN_ID=1          # optional: deposit.list_addresses
export POLYESTER_SMOKE_TX_HASH=0x...       # optional: lifecycle.get_flow_by_tx
export POLYESTER_SMOKE_RESOLVE_QUERY=alice # optional: resolve.resolve_account
.venv/bin/python scripts/smoke_test.py
```

Attach a **read/trade policy** to your API key in the Polyester UI if authenticated steps fail.

Some RPCs return plain HTTP 404 on devnet (not mounted on the gateway). The SDK raises
`PolyesterRouteNotFoundError` with a clearer message than `[unimplemented]: Not Found`.
Examples: `orderbook`, `balances.list_holds`.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Transport

Connect RPC over HTTP via generated clients in `src/polyester/gen/`. Wire format
defaults to JSON for debugging; binary protobuf is the production target.
