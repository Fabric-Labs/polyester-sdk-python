# Realtime

The TypeScript SDK uses Centrifugo over WebSocket with protobuf payloads. Python should mirror the channel model while exposing Python-native async iterators.

## Realtime Architecture

Components:

- `RealtimeClient`: owns the WebSocket connection, subscriptions, reconnection, and shared channel consumers.
- `AsyncSubscription[T]`: async iterator that yields decoded public models.
- Sync callback wrapper: runs a subscription on the sync client's background event loop/thread and returns an unsubscribe callable.
- Protobuf decoders: map raw publication bytes to generated protobuf messages, then to public `msgspec` models.

Public async shape:

```python
async for order in client.orders.subscribe(account_id):
    handle_order(order)
```

Optional explicit subscription object:

```python
sub = client.orders.subscribe(account_id)
async with sub:
    async for order in sub:
        ...
```

Sync shape:

```python
unsubscribe = client.orders.subscribe_callback(
    account_id,
    on_event=handle_order,
    on_open=lambda: print("open"),
    on_close=lambda: print("closed"),
    on_error=handle_error,
)
```

## Connection Lifecycle

Match the TypeScript shared-client behavior:

- Create the WebSocket connection when the first subscription starts.
- Reuse one connection across channels.
- Reference-count consumers per channel.
- Unsubscribe a channel when the final consumer closes.
- Disconnect the WebSocket when no channels remain.
- Reconnect after transient disconnects while subscriptions are active.
- Resubscribe active channels after reconnect.

Cancellation should be safe:

- Breaking from `async for` should unsubscribe the consumer.
- Exiting an async context manager should unsubscribe.
- Calling sync `unsubscribe()` should stop the callback subscription promptly.

## Auth and Private Channels

Channels beginning with `private:` require auth.

The TypeScript SDK obtains:

- connection token from `/v1/rt/token`
- private subscription token from `/v1/rt/subscribe?channel={encoded_channel}`

Python should use the same endpoints unless backend docs say otherwise.

Important difference:

- TypeScript currently sends JWT bearer auth for realtime token endpoints.
- Python must call these endpoints with API-key auth headers using the same Ed25519 signing contract as unary requests.

If token endpoints do not currently accept API-key auth, this is a backend requirement for the Python SDK. Document the SDK behavior as expected and fail with `PolyesterAuthError` if token acquisition returns 401/403.

## Channel Map

Use these channel names from `packages/polyester-client`.

| Python method | Channel | Payload |
| --- | --- | --- |
| `orders.subscribe(account_id)` | `private:spot:orders:{account_id}:proto` | order update |
| `trades.subscribe(account_id)` | `private:spot:trades:{account_id}:proto` | user trade |
| `balances.subscribe(account_id)` | `private:ledger:balances:{account_id}:proto` | ledger balance |
| `transfers.subscribe(account_id)` | `private:ledger:transfers:{account_id}:proto` | ledger transfer |
| `triggers.subscribe(account_id)` | `private:spot:triggers:{account_id}:proto` | trigger |
| `triggers.subscribe_events(account_id)` | `private:spot:triggers:events:{account_id}:proto` | trigger event |
| `api_keys.subscribe(account_id)` | `private:auth:api-keys:{account_id}:proto` | API key |
| `sub_accounts.subscribe(account_id)` | `private:auth:subaccounts:{account_id}:proto` | subaccount |
| `sub_accounts.subscribe_api_keys(account_id)` | `private:auth:api-keys:{account_id}:proto` | API key |
| `sub_accounts.subscribe_policies(account_id)` | `private:auth:subaccount-policies:{account_id}:proto` | subaccount policy |
| `policies.sub_account.subscribe_policies(account_id)` | `private:auth:subaccount-policies:{account_id}:proto` | subaccount policy |
| `market_data.subscribe_trades(symbol_or_id)` | `public:spot:market:trades:{symbol_id}:proto` | market trade |
| `orderbook.subscribe(symbol_or_id, depth)` | `public:spot:orderbook:deltas:depth:{depth}:{symbol_id}:proto` | orderbook delta |
| `candles.subscribe(symbol_or_id, timeframe)` | `public:spot:market:candles:{timeframe}:{symbol_id}:proto` | candle |
| `candles.subscribe_ints(symbol_or_id, timeframe)` | `public:spot:market:candles:{timeframe}:{symbol_id}:proto` | integer candle |
| `heatmap.subscribe_live(symbol_or_id, interval)` | `public:spot:market:heatmap:{interval}:{symbol_id}:proto` | heatmap |
| `market_overview.subscribe()` | `public:spot:market_overview:updates:proto` | market overview update |
| `lifecycle.subscribe_open_flows()` | `public:chain:lifecycle:flows:proto` | lifecycle flow |
| `lifecycle.subscribe_flow_detail(intent_id)` | `public:chain:lifecycle:flow:{intent_id}:proto` | lifecycle flow detail |
| `profile.subscribe_identity()` | `public:identity:updates:proto` | identity update |

Only expose `profile.subscribe_identity()` if profile/social identity services are included. Otherwise leave it out of the Python v1 service tree.

## Public vs Private Subscription Names

Keep method names Pythonic but close to TypeScript:

- `subscribe(...)`
- `subscribe_events(...)`
- `subscribe_api_keys(...)`
- `subscribe_policies(...)`
- `subscribe_open_flows(...)`
- `subscribe_flow_detail(...)`
- `subscribe_live(...)`

Public streams should not require credentials. Private streams should fail fast if no API key is configured.

## Backpressure

Async subscriptions should use a bounded queue.

Recommended defaults:

- `max_queue_size=1000`
- On overflow, default to raising `PolyesterRealtimeError` and closing the subscription.
- Optionally support `overflow="drop_oldest"` for market-data-only streams.

Do not silently drop private order/trade/balance events by default.

## Reconnect and Resubscribe

Default behavior:

- Reconnect automatically on transient network disconnect.
- Use exponential backoff with jitter.
- Reuse the same channel set after reconnect.
- Refresh connection and subscription tokens as needed.
- Call `on_close`/`on_open` or async lifecycle hooks around reconnects.

Bounded behavior:

- Allow `reconnect=True` default.
- Allow `max_reconnect_attempts=None` for indefinite bot operation.
- Allow users to set a finite reconnect attempt limit.

## Decoding

Every publication should be decoded as:

1. Raw Centrifugo publication data bytes.
2. Protobuf frame decode if the server wraps frames.
3. Generated protobuf message decode.
4. Public model conversion.
5. Yield/callback with public model.

If decoding fails:

- Public market stream: raise/log through subscription error path.
- Private stream: raise `PolyesterRealtimeError`; do not silently ignore malformed private events.

## Orderbook Maintainer

The TS `orderbook.createSubscription(...)` maintains local bid/ask maps from a snapshot plus deltas.

Python should mirror this as a high-level helper:

```python
async for book in client.orderbook.stream(symbol="BTC-USD", depth=50):
    best_bid = book.bids[0]
```

Implementation guidance:

- Fetch an initial snapshot with `orderbook.get(...)`.
- Subscribe to deltas for the same symbol/depth.
- Apply bid/ask deltas to local maps.
- Emit stable sorted levels.
- Provide a raw delta stream separately for users who want lower-level control.

## Sync Callback Wrapper

The sync client should not duplicate realtime internals.

Recommended implementation:

- Maintain a background event loop thread owned by `Polyester`.
- Start async subscriptions on that loop.
- Invoke callbacks from the background thread.
- Return an idempotent unsubscribe callable.
- On `client.close()`, cancel all active subscriptions and stop the loop.

Document that callbacks must be thread-safe.
