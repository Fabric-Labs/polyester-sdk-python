# Python SDK Overview

This document set is the reference for building a standalone Python SDK for Polyester. It translates the existing TypeScript SDK in `packages/polyester-client` into a Python package shape suitable for trading bots, backend services, research notebooks, and automation jobs.

The Python SDK should be lean, fast, API-key-only, and pleasant to use from both async trading systems and simple scripts.

## Package Identity

- PyPI distribution: `polyester-sdk`
- Import package: `polyester`
- Primary client: `AsyncPolyester`
- Sync wrapper: `Polyester`
- Default API URL: `https://api-devnet.polyester.ai`, matching the current TypeScript SDK default
- Default WebSocket URL: `wss://api-devnet.polyester.ai`, matching the current TypeScript SDK default

Example target DX:

```python
from polyester import AsyncPolyester

async with AsyncPolyester.from_env() as client:
    book = await client.orderbook.get(symbol_id=1, depth=50)
    result = await client.orders.create(
        symbol="BTC-USD",
        side="buy",
        order_type="limit",
        tif="gtc",
        qty="0.1",
        price="50000",
    )
```

Sync users should get the same service tree without learning `asyncio`:

```python
from polyester import Polyester

with Polyester.from_env() as client:
    balances = client.balances.list()
```

## Target Users

The primary users are Python engineers building trading bots and backend automations. Their priorities are:

- Low request construction and serialization overhead
- Safe handling of prices, quantities, IDs, timestamps, and enum values
- Strong type hints and editor completion
- Clear validation errors for malformed order requests
- Async-first realtime streams for orders, trades, balances, market data, and lifecycle updates
- A sync path for scripts, cron jobs, notebooks, and simpler bots

The SDK should feel closer to an exchange trading SDK than an app/browser SDK.

## Architecture Defaults

Use the same conceptual layering as `packages/polyester-client`:

- `polyester.client`: `AsyncPolyester`, `Polyester`, client config, lifecycle
- `polyester.auth`: API-key credential loading, Ed25519 signing, auth header injection
- `polyester.transport`: auth/retry/error wrappers around generated Connect clients
- `polyester.realtime`: Centrifugo/protobuf subscriptions
- `polyester.models`: public `msgspec.Struct` request/response models
- `polyester.codecs`: enum, ID, decimal, timestamp, and protobuf conversion helpers
- `polyester.services`: service wrappers mirroring the TypeScript client service tree
- `polyester._gen`: generated Python protobuf modules and Connect client stubs, treated as internal

`AsyncPolyester` owns the real implementation. `Polyester` should be a thin blocking facade over the async client, sharing models, codecs, service names, method names, and error types.

## Auth Boundary

The Python SDK only accepts API keys. It should not implement or expose:

- Cookie parsing
- JWT auth
- Browser login
- Wallet login
- Smart-account creation
- Session restore or refresh
- Svelte/browser state helpers
- Local mock mode

Credential sources:

- Explicit constructor args: `api_key_id`, `api_private_key`
- Environment fallback: `POLYESTER_API_KEY_ID`, `POLYESTER_API_PRIVATE_KEY`
- `api_private_key` accepts hex string or raw bytes and is normalized internally

## Transport Boundary

The TypeScript SDK uses Connect RPC with binary protobuf by default. Python should do the same, but the Python SDK should assume the backend/API team provides generated Python protobuf modules and Connect client stubs through Buf generation.

- Binary protobuf is the default and production path.
- JSON wire format can be exposed only as a debugging/playground option.
- Generated protobuf messages and generated Connect clients are internal transport details.
- Public inputs and outputs should use SDK-owned `msgspec` models and Python primitives.

The SDK may expose a raw low-level escape hatch, but it should be deliberately named, for example `client.raw`, and documented as unstable.

## Model Boundary

Use `msgspec` as the primary public model layer because performance is a first-order requirement. This avoids Pydantic overhead while still giving typed structures, validation, and fast serialization.

Guidelines:

- Use `msgspec.Struct` for request and response models.
- Prefer plain Python primitives in method signatures for common calls.
- Accept strings for decimal trading inputs such as `qty`, `price`, `trigger_price`, and quote amounts.
- Do not accept floats for order quantities or prices unless the method name clearly says it is approximate/debug-only.
- Convert public models to protobuf messages at the service boundary.
- Convert protobuf responses back into public models before returning to users.

## Client Surface

The Python SDK should expose a service tree similar to TypeScript:

```python
client.orders
client.triggers
client.trades
client.balances
client.transfers
client.deposit
client.market_data
client.market_overview
client.orderbook
client.candles
client.heatmap
client.lifecycle
client.accounts
client.api_keys
client.policies.api_key
client.policies.sub_account
client.sub_accounts
client.address_book
client.guard_signer
client.mfa
client.social_verification
client.whiteboard
client.zipper
```

Service names should be Pythonic snake_case while staying recognizably mapped to the TypeScript SDK.

## Realtime Surface

Realtime should be native to async Python:

```python
async for order in client.orders.subscribe(account_id):
    handle_order(order)
```

The sync client can expose callback wrappers:

```python
unsubscribe = client.orders.subscribe_callback(account_id, on_event=handle_order)
```

Realtime subscriptions should decode protobuf payloads into the same public models as unary responses where possible.

## Non-Goals

Do not include browser functionality:

- No cookie-based session parsing
- No `PolyesterBrowserClient`
- No `PolyesterServerClient` cookie helpers
- No wallet interface
- No Safe/smart-account helpers
- No app-local auth state
- No local mock runtime

Do not turn generated protobuf classes or generated Connect clients into the public SDK API. They are allowed as an advanced escape hatch only.
