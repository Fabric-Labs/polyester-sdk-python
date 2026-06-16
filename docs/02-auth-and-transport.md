# Auth and Transport

The Python SDK should match the TypeScript SDK transport contract: Connect RPC over HTTP with binary protobuf bodies by default, plus Ed25519 API-key request signing.

## Transport Model

Assume the backend/API team provides generated Python protobuf modules and generated Connect RPC client stubs through Buf. The SDK should use those generated clients internally instead of constructing service names and method names as strings.

Required behavior:

- Binary protobuf wire format is the default.
- JSON wire format is optional and should be documented as debug/playground-only.
- Public API methods accept Python primitives or `msgspec` request models.
- Service methods convert public inputs into protobuf request messages.
- Responses are protobuf-decoded and converted into `msgspec` response models.
- Generated protobuf modules and Connect clients live under `polyester._gen` and are internal by default.

Suggested implementation libraries:

- `connectrpc` Python runtime for generated Connect clients.
- Generated `*_pb2.py`, `*_pb2.pyi`, and Connect client modules from Buf.
- HTTP runtime used by `connectrpc`; do not duplicate request dispatch if generated clients already own it.
- `cryptography` for Ed25519 signatures.
- `msgspec` for public model validation and serialization.

The TypeScript SDK maintains separate public and authenticated transports. Python should preserve the same idea:

- Public transport: no auth headers for public market data.
- Auth transport: API-key signing applied to every authenticated request.

## Client Configuration

Recommended constructors:

```python
class AsyncPolyester:
    def __init__(
        self,
        *,
        api_key_id: str | None = None,
        api_private_key: str | bytes | None = None,
        api_url: str = "https://api-devnet.polyester.ai",
        ws_url: str = "wss://api-devnet.polyester.ai",
        default_sub_account_id: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        wire_format: Literal["binary", "json"] = "binary",
    ): ...

    @classmethod
    def from_env(cls, **overrides) -> "AsyncPolyester": ...
```

Sync client:

```python
class Polyester:
    def __init__(self, **config): ...

    @classmethod
    def from_env(cls, **overrides) -> "Polyester": ...
```

Environment variables:

- `POLYESTER_API_KEY_ID`
- `POLYESTER_API_PRIVATE_KEY`

`from_env()` reads the process environment only. It does not load `.env` files.
For local development in this repository, use `scripts/smoke_test.py` (which
loads `.env` via `python-dotenv`) or `set -a && source .env && set +a` before
running examples.

Credential rules:

- Explicit constructor values win over environment variables.
- Missing credentials are allowed only for public-only use.
- Authenticated calls without credentials raise `PolyesterAuthError`.
- `api_private_key` accepts raw bytes or hex string.
- Hex strings should allow optional whitespace trimming but should not allow malformed length/content.

## API-Key Signing Contract

Authenticated requests use these headers:

- `X-API-KEY-ID`: API key ID
- `X-API-TIMESTAMP`: current Unix timestamp in milliseconds as a decimal string
- `X-API-SIGNATURE`: hex-encoded Ed25519 signature

The canonical string must match TypeScript:

```text
{timestamp}
{method}
{pathname}
{canonical_query}
{body_sha256_hex}
```

Where:

- `timestamp` is `str(int(time.time() * 1000))`.
- `method` is the HTTP request method used by Connect, usually `POST`.
- `pathname` is the URL path only, not scheme, host, query, or fragment.
- `canonical_query` is the request query string sorted by encoded key/value pairs.
- `body_sha256_hex` is the SHA-256 hex digest of the exact request body bytes.

Canonical query construction:

1. Read all query parameters from the final request URL.
2. Percent-encode each key and value.
3. Format each pair as `{key}={value}`.
4. Sort all pairs lexicographically.
5. Join with `&`.

Body bytes:

- Unary binary requests: protobuf binary serialization of the request message.
- Unary JSON requests: protobuf JSON serialization encoded as UTF-8.
- Streaming requests, if any are added later: sign an empty byte string unless the backend defines a different contract.

Signing:

```python
canonical = f"{timestamp}\n{method}\n{pathname}\n{canonical_query}\n{body_hash}"
signature = ed25519_private_key.sign(canonical.encode("utf-8")).hex()
```

The signing code must be deterministic and easy to compare against TypeScript golden examples.

## Generated Connect Client Details

The Python SDK should call generated Connect clients directly. Service wrappers should not call a generic stringly typed method like:

```python
await transport.unary(
    service="orders.v1.OrdersService",
    method="CreateOrder",
    ...
)
```

Instead, generated modules should be imported internally and used as typed clients:

```python
from polyester._gen.orders.v1.orders_pb2 import CreateOrderRequest
from polyester._gen.orders.v1.orders_connect import OrdersServiceClient


class AsyncOrdersService:
    def __init__(self, client: OrdersServiceClient, codecs: OrderCodecs):
        self._client = client
        self._codecs = codecs

    async def create(self, **kwargs):
        public_request = self._codecs.create_order_request(kwargs)
        pb_request = self._codecs.create_order_to_pb(public_request)
        pb_response = await self._client.create_order(pb_request)
        return self._codecs.create_order_result_from_pb(pb_response)
```

The exact generated import names may differ by generator version and proto package layout. The important rule is that service wrappers depend on generated Python clients/types, not string service descriptors.

The SDK's `transport` module should focus on cross-cutting configuration for those generated clients:

- Base URL and wire format.
- Auth interceptor/middleware that can sign the final request.
- Timeout configuration.
- Retry policy where safe.
- Error mapping into SDK exceptions.
- Shared public/authenticated generated client factories.

The generated Connect runtime should own endpoint construction, content-type details, protobuf request serialization, and protobuf response decoding wherever it supports those concerns.

Keep this layer small. Avoid rebuilding a Connect client manually unless the generated client/runtime cannot support a required auth-signing hook.

## Generated Code Contract

The backend/API team should provide or document Buf generation that produces:

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

Expected outputs:

- Protobuf message modules, typically `*_pb2.py`.
- Type stub modules, typically `*_pb2.pyi`.
- Connect client modules generated by `buf.build/connectrpc/python`.

The SDK should not hand-write protobuf classes or service clients. It should wrap generated clients with:

- Pythonic method names.
- `msgspec` public models.
- Polyester enum/decimal/ID/timestamp codecs.
- API-key auth configuration.
- SDK exceptions.

If the backend team publishes generated Python SDK packages through Buf Schema Registry instead of checking code into the Python SDK repo, the wrapper package can depend on those packages. The public Polyester SDK should still hide generated package details behind its stable service tree.

## Timeouts

Defaults should be conservative for bots:

- Default request timeout: 10 seconds.
- Allow per-client and per-call timeout overrides.
- Separate connect/read/write timeouts may be exposed later, but a single float is enough for v1 docs.

Do not hide long hangs behind infinite defaults.

## Retries

Retry only where safe:

- Public GET-like/unary reads: retry transient network errors, 408, 429 with retry-after, and 5xx.
- Authenticated reads: same as public reads.
- Mutations such as create order, cancel, modify, trigger creation, API-key mutations: do not retry by default unless the request has an idempotency key or the backend explicitly documents safety.

For order creation, preserve or generate a client request ID when the API supports it. If the TS SDK generates `requestId` for modify when missing, Python should do the same.

Retry policy fields:

- `max_retries`
- exponential backoff with jitter
- respect `Retry-After` when present
- expose the final response/error after retries are exhausted

## Errors

Expose a small stable exception hierarchy:

```python
PolyesterError
PolyesterAuthError
PolyesterValidationError
PolyesterTransportError
PolyesterRateLimitError
PolyesterServerError
PolyesterApiError
PolyesterRealtimeError
```

Error mapping guidance:

- Local model/codec failures -> `PolyesterValidationError`
- Missing credentials -> `PolyesterAuthError`
- Network failures/timeouts -> `PolyesterTransportError`
- 401/403 -> `PolyesterAuthError`
- 429 -> `PolyesterRateLimitError`
- 5xx -> `PolyesterServerError`
- Connect/protobuf error responses -> `PolyesterApiError` with code, message, metadata, and raw details where available

The SDK should not return `None` for failed network/API calls. Use exceptions.

## Rate Limits

Rate-limit behavior should be explicit:

- Raise `PolyesterRateLimitError` on 429.
- Include retry-after seconds if the server provides it.
- Do not auto-sleep indefinitely.
- Optional retry-on-429 should be bounded by `max_retries`.

## Resource Lifecycle

Both clients should support context managers:

```python
async with AsyncPolyester.from_env() as client:
    ...

with Polyester.from_env() as client:
    ...
```

Also expose explicit close methods:

```python
await async_client.aclose()
client.close()
```

Closing should stop HTTP clients and realtime connections.
