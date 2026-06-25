# Polyester Python SDK

Official Python SDK for Polyester APIs, built for trading bots, backend jobs,
research notebooks, and automation.

**Status:** Alpha (`0.1.0a0`). The repo is **public** (visible on GitHub) under a
**proprietary** license — not open source. API-key-only; no browser or JWT flows.

Generated protobuf types and ConnectRPC clients live in `src/polyester/gen/` and are
updated automatically when public API protos change. Hand-written SDK code (client,
services, models, codecs) lives alongside them under `src/polyester/`.

## Install

Install the SDK from PyPI:

```bash
pip install "polyester-sdk[realtime]"
```

For local development from a checkout:

```bash
cd polyester-sdk-python
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,realtime]"
```

## Authentication

Pass credentials to the client from your app's config or secrets manager:

```python
from polyester import AsyncPolyester

client = AsyncPolyester(
    api_key_id="ak_...",
    api_private_key="...",  # 64-char hex Ed25519 secret or raw 32-byte key
)
```

If your app uses environment variables, read them in your application code and pass
them explicitly:

```python
import os

from polyester import AsyncPolyester

client = AsyncPolyester(
    api_key_id=os.environ["POLYESTER_API_KEY_ID"],
    api_private_key=os.environ["POLYESTER_API_PRIVATE_KEY"],
    default_account_id=os.getenv("POLYESTER_ACCOUNT_ID"),
)
```

For scripts and local tests, `AsyncPolyester.from_env()` and `Polyester.from_env()`
are convenience helpers that read `POLYESTER_*` from `os.environ`. The plain
constructor does not implicitly read environment variables.

## Quickstart

```python
from polyester import AsyncPolyester

async with AsyncPolyester(
    api_key_id="ak_...",
    api_private_key="...",
) as client:
    overview = await client.market_overview.list(limit=5)
    for market in overview.markets:
        print(market.symbol, market.last_price_ticks)

    open_orders = await client.orders.list_open()
    print(f"{len(open_orders.orders)} open orders")
```

## Create And Cancel

```python
from polyester import AsyncPolyester

async with AsyncPolyester(
    api_key_id="ak_...",
    api_private_key="...",
    default_sub_account_id="",
) as client:
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
(Funding → Unified Trading in the UI or on-chain via the funding wallet).

- **Funding → trading:** on-chain `TradingGateway.deposit` (not an API-key RPC).
- **Trading → funding:** `client.trading_withdraws.create_to_funding(...)` with a signed intent payload.
- **Trading → trading (another account):** `client.internal_transfers.create(...)` or `client.ledger_write.transfer_trading_to_trading(...)`.

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

Merged market overview stream (snapshot + live updates):

```python
sub = await client.market_overview.create_subscription()
async for markets in sub:
    print(len(markets), "rows")
    break
await sub.aclose()
```

## Testing

**CI (no network):** `pytest tests/unit -q`, plus ruff and package build.

**Full local suite:** devnet integration/e2e tests read `.env` in the test harness and pass credentials to the client as explicit constructor parameters.

```bash
cp .env.example .env
# POLYESTER_API_KEY_ID, POLYESTER_API_PRIVATE_KEY, POLYESTER_ACCOUNT_ID

pip install -e ".[dev,realtime]"

./scripts/test_all.sh          # unit + tiered live (reads .env flags)
# or
pytest tests/unit -q           # CI-equivalent
pytest tests/ -v               # full suite
python scripts/smoke_test.py   # backwards-compatible read/mutation wrapper
```

Useful markers include `smoke`, `mutation`, `funded`, `treasury`, `optional`, `realtime`, and `jwt_session`.

### Known devnet skips (not SDK failures)

| Skip reason | Tests affected |
|-------------|----------------|
| OMS read never indexes after `orders.create` | `test_order_round_trip`, `test_batch_create_and_cancel` |
| No open orders on book | `test_orders_get_round_trips_list_open` |
| `list_holds` unmounted | balance holds tests |
| JWT/session-only routes | profile, whiteboard, resolve, etc. |
| Guard signer not on account | `test_guard_signer_get_status` |
| No BTC-USDT asks / `POLYESTER_TEST_TRADE_E2E` | `test_spot_fill` |

Attach a **read/trade policy** to your API key. Spot orders need **USDT in unified trading** (not BTC).

Some RPCs return HTTP 404 on devnet. The SDK raises `PolyesterRouteNotFoundError` with a clearer message than `[unimplemented]: Not Found`.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Transport

Connect RPC over HTTP via generated clients in `src/polyester/gen/`. Wire format
defaults to **binary protobuf**; pass `wire_format="json"` for debugging.

