# Build Roadmap

This is a suggested implementation sequence for the Python engineer.

## 1. Repository and Package Skeleton

Create a standalone repository for the Python SDK.

Package defaults:

- PyPI distribution: `polyester-sdk`
- Import package: `polyester`
- Python version: choose a modern baseline such as Python 3.11+ unless product support requires 3.10.
- Package manager/build backend: use a current `pyproject.toml` flow.

Initial module layout:

```text
polyester/
  __init__.py
  client.py
  auth.py
  transport.py
  realtime.py
  errors.py
  models/
  codecs/
  services/
  catalogs/
  _gen/
```

Export only stable public classes from `polyester.__init__`:

```python
from polyester import AsyncPolyester, Polyester
```

## 2. Generated Protobuf and Connect Inputs

Assume the backend/API team provides generated Python protobuf modules and generated Connect RPC clients through Buf. The Python SDK should consume those generated artifacts before writing service wrappers.

Requirements:

- Use the same protobuf source/descriptors as `packages/polyester-client/src/gen`.
- Generate or consume Python modules under `polyester._gen`, or consume backend-published Buf generated Python packages as dependencies.
- Include protobuf message generation, type stubs, and Connect client generation:

```yaml
version: v2
plugins:
  - remote: buf.build/protocolbuffers/python
    out: polyester/_gen
  - remote: buf.build/protocolbuffers/pyi
    out: polyester/_gen
  - remote: buf.build/connectrpc/python
    out: polyester/_gen
```

- Treat generated modules as internal implementation details.
- Document the command/process that refreshes generated code when APIs change.

Do not hand-write protobuf message classes or Connect service clients.

## 3. Auth and Transport

Build the shared foundation first:

- Credential loading from explicit args and env vars.
- Hex/bytes Ed25519 private key normalization.
- API-key signing with the exact TypeScript canonical string.
- Generated Connect client configuration with binary protobuf by default.
- Public/authenticated transport separation.
- Stable SDK exception hierarchy.
- Context manager and close lifecycle.

This phase should produce enough infrastructure for one public unary call and one authenticated unary call.

## 4. Core Codecs and Models

Implement shared model/codecs before broad service work:

- `msgspec.Struct` conventions.
- Enum codecs.
- Base58 uint64 ID parsing/formatting.
- Decimal string to scaled integer helpers.
- Timestamp helpers.
- u128 helpers.
- Optional field omission helpers.
- Catalog manager and best-effort hydration hooks.

Keep conversion functions small and explicit. The TypeScript SDK has service-specific schemas for a reason; avoid a giant generic mapper that hides edge cases.

## 5. First Service Slice

Implement a vertical slice that proves the architecture:

- Public: `market_data.get_spot_config`, `orderbook.get`, or `candles.list`.
- Authenticated: `orders.list_open` and `balances.list`.
- Mutation: `orders.create` or `orders.cancel`.

Use this slice to settle method naming, model shape, error wrapping, and transport ergonomics before copying the rest of the service tree.

Each service wrapper should call typed generated clients internally rather than string service/method descriptors. For example, `orders.create(...)` should convert a public request into the generated `CreateOrderRequest`, call the generated `OrdersServiceClient.create_order(...)`, and convert the generated response back into a public model.

## 6. Trading Services

Prioritize the bot-critical services:

- `orders`
- `triggers`
- `trades`
- `balances`
- `transfers`
- `deposit`
- `market_data`
- `market_overview`
- `orderbook`
- `candles`
- `heatmap`
- `lifecycle`
- `zipper`

These services define the value of the SDK for trading bots and should land before lower-priority account-management or app-oriented services.

## 7. Account and Admin Services

Add the API-key-compatible account/admin surfaces:

- `accounts`
- `api_keys`
- `policies.api_key`
- `policies.sub_account`
- `sub_accounts`
- `address_book`
- `guard_signer`
- `mfa`, if API-key step-up flows are supported

Document permission requirements clearly. If a method cannot work with API-key auth, either omit it or raise a clear unsupported/auth error instead of pretending it works.

## 8. Realtime

After unary service models are stable, implement realtime:

- Shared `RealtimeClient`.
- Public channel subscriptions.
- Private channel token flow with API-key auth.
- Async iterator subscriptions.
- Sync callback wrappers.
- Orderbook maintained stream.

Use the channel map in `04-realtime.md` as the source of truth.

## 9. Deferred Services

Evaluate these after trading and account services:

- `social_verification`
- `whiteboard`
- `profile.subscribe_identity`
- `bridge`

Default stance:

- Defer social/whiteboard/profile identity because they are not trading-bot core.
- Defer bridge until the product confirms Python bridge workflows and auth requirements.

## 10. Examples and User Docs

Once the API shape is stable, write examples aimed at bot builders:

- Install and configure API keys.
- Fetch market config and orderbook.
- Place/cancel a limit order.
- Place a market order with explicit slippage controls.
- Listen to private order/trade/balance streams.
- Maintain a local orderbook.
- Use subaccount defaults and overrides.
- Handle rate limits and API errors.

Examples should use exact decimal strings and avoid floats for order inputs.

## Implementation Principles

- Keep async as the source of truth; keep sync thin.
- Keep generated protobuf and generated Connect clients internal.
- Keep public models fast and typed with `msgspec`.
- Delete browser/session/wallet concepts rather than porting them.
- Prefer explicit service-specific codecs over clever generic conversion.
- Make unsupported API-key flows fail loudly with actionable errors.
