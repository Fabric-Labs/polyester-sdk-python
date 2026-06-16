# Models, Validation, and Codecs

The Python SDK should use `msgspec` as the primary public model layer and protobuf as the internal wire layer. The TypeScript SDK uses Zod schemas to validate user input, convert friendly values to protobuf values, and format protobuf responses. Python needs the same boundary, implemented with faster Python-native tools.

## Why msgspec

Use `msgspec` because the SDK is performance-sensitive and aimed at trading bots.

Compared with Pydantic v2:

- `msgspec` is typically faster and leaner for typed structs and JSON-like validation.
- It has fewer runtime features and less ecosystem gravity than Pydantic.
- It is a better default when CTO-level performance scrutiny matters.

DX tradeoff:

- Pydantic has richer validation ergonomics and more familiar error shapes.
- The SDK should compensate with small helper constructors and careful `PolyesterValidationError` wrapping.
- Do not build a second Pydantic model layer in v1; that doubles maintenance.

## Public Model Shape

Use `msgspec.Struct` for structured inputs and outputs:

```python
import msgspec

class CreateOrderRequest(msgspec.Struct, kw_only=True, omit_defaults=True):
    symbol: str | None = None
    symbol_id: int | None = None
    side: str
    order_type: str
    tif: str | None = None
    qty: str
    price: str | None = None
    sub_account_id: str | None = None
    client_order_id: str | None = None
```

Service methods may also accept keyword arguments for common operations:

```python
await client.orders.create(
    symbol="BTC-USD",
    side="buy",
    order_type="limit",
    tif="gtc",
    qty="0.1",
    price="50000",
)
```

Internally normalize both forms into the same request model, then convert to protobuf.

## Protobuf Boundary

Generated protobuf classes and generated Connect clients should live under `polyester._gen`, or be imported from backend-provided Buf generated Python packages and re-exported only internally.

Flow for requests:

1. Accept kwargs or a public `msgspec` request model.
2. Validate and normalize with SDK code.
3. Convert public values to protobuf field names and wire representations.
4. Omit unset optional fields.
5. Send protobuf through the generated Connect client for that service.

Flow for responses:

1. Decode protobuf response.
2. Convert wire enum integers and numeric fields into user-facing labels/values.
3. Return public `msgspec` response models.

Do not expose raw generated protobuf objects or generated Connect clients as the standard public API.

## Naming Policy

Python public API names use snake_case:

- `subAccountId` -> `sub_account_id`
- `clientOrderId` -> `client_order_id`
- `orderType` -> `order_type`
- `startTsNs` -> `start_ts_ns`
- `pageToken` -> `page_token`

Wire/protobuf field names remain whatever the generated code requires and are handled by codecs.

## Decimal and Integer Policy

Trading inputs must be exact.

Use strings for:

- order quantity: `qty`
- order price: `price`
- trigger prices
- quote amounts
- market max slippage quote amounts
- decimal filter bounds

Do not accept floats for trading quantities/prices in primary methods. Floats create silent precision loss and are inappropriate for bots.

Conversion rules from TypeScript:

- `parsePriceTicks(raw)` scales decimal price strings to 6 decimal places.
- `parseQtyScaled(raw, scale)` scales decimal quantity strings using symbol/base quantity scale.
- Required uint64 decimal fields must be non-empty positive integer strings.
- Optional uint64 filters may treat empty or invalid values as unset only where TypeScript does the same.

Recommended Python helpers:

```python
parse_price_ticks(raw: str, field_name: str) -> int
parse_qty_scaled(raw: str, scale: int, field_name: str) -> int
parse_required_uint64_decimal(raw: str, field_name: str) -> int
parse_optional_uint64_decimal(raw: str | None) -> int | None
```

Use Python `int` for arbitrary-size exact integers.

## ID Policy

The TypeScript SDK formats uint64 IDs as base58 display strings and accepts either decimal strings/numbers or base58 strings.

Python should mirror this:

- Public IDs are strings.
- Base58 strings are the preferred display format.
- Decimal strings are accepted for debugging/tooling.
- Convert public IDs to uint64 integers before protobuf requests.
- Convert uint64 response IDs to base58 strings before returning public models.

Implement equivalents of:

- `id_to_int(input, label="id") -> int`
- `format_id(input) -> str`

Validation:

- IDs must be `0 <= id <= 2**64 - 1`.
- Invalid base58 characters raise `PolyesterValidationError`.

## Timestamp Policy

The TS SDK uses a mix of protobuf `Timestamp`, millisecond display values, ISO strings, and nanosecond integer filters.

Python policy:

- Public response timestamps should use timezone-aware `datetime` for human-facing fields where practical.
- Keep exact wire/filter timestamps as integer fields when they are naturally nanoseconds or seconds.
- Accept ISO 8601 strings or `datetime` for fields like `expires_at`.
- Accept decimal strings or integers for nanosecond filters like `start_ts_ns` and `end_ts_ns`.

Helpers:

```python
timestamp_pb_to_datetime(pb) -> datetime | None
datetime_to_timestamp_pb(value: datetime) -> Timestamp
ns_to_datetime(value: int) -> datetime
```

Never use naive datetimes internally; normalize to UTC.

## u128 Policy

The TypeScript SDK has `u128` helpers for ledger/order values. Python can represent these as plain `int`.

Rules:

- Decode protobuf u128 structures into Python `int`.
- Validate bounds where the wire type requires them.
- Provide display helpers for catalog-scaled asset amounts.
- Keep exact integer fields available if precision matters.

## Enum Policy

Public enum-like inputs should use stable strings, not protobuf integers.

Examples from TypeScript:

- order side: `"buy"`, `"sell"`
- order type: `"limit"`, `"market"`
- TIF: `"gtc"`, `"ioc"`, `"fok"`
- fee source: `"quote"`, `"received"`
- STP mode: `"expire_taker"`, `"expire_maker"`, `"expire_both"`
- trigger price source: `"last"`, `"index"`, `"mark"`

Python should accept only documented string values by default. Avoid accepting random protobuf enum names and integers in public methods because that weakens validation and editor help.

Each codec should be explicit:

```python
ORDER_SIDE_TO_PROTO = {
    "buy": Side.BUY,
    "sell": Side.SELL,
}
```

Response codecs should map protobuf enums back to stable string labels. Unknown/unspecified wire values should map to `"unknown"` only where TypeScript does; otherwise raise an SDK API/codec error so drift is visible.

## Optional Field Omission

TypeScript calls `removeUndefined(...)` before protobuf requests. Python needs the same behavior.

Rules:

- `None` means unset for optional request fields.
- Do not serialize optional `None` as empty strings, zeroes, or empty nested messages unless the TS schema intentionally does that.
- Empty string has special meaning for `sub_account_id`: force main account by omitting the protobuf subaccount field.
- Empty lists are preserved only when the API distinguishes empty list from omitted list.

For `msgspec.Struct`, use `omit_defaults=True` where appropriate, but keep explicit conversion code for protobuf to avoid accidental semantic changes.

## Catalog-Backed Formatting

The TS SDK enriches responses with labels and display strings using catalogs:

- market data catalog for symbols/assets/scales
- order catalog for order labels and formatting
- ledger catalog for asset/account-code display
- zipper catalog for chain/asset metadata

Python should include a catalog module that supports:

- `get_pair(symbol)` / `get_pair_by_symbol_id(symbol_id)`
- `symbol_id_for_symbol(symbol)`
- `symbol_for_symbol_id(symbol_id)`
- `base_quantity_scale_for_symbol(symbol)`
- `get_asset(...)`
- amount and price display helpers

Catalog hydration should be best-effort and should not block basic SDK usage if the network request fails.

## Validation Error DX

Raw `msgspec.ValidationError` messages are useful but can be terse. Wrap them:

```python
try:
    request = msgspec.convert(data, type=CreateOrderRequest)
except msgspec.ValidationError as exc:
    raise PolyesterValidationError("Invalid orders.create request", cause=exc) from exc
```

Include:

- service/method name
- field path when available
- expected type/value set
- original cause

The goal is Pydantic-like clarity without Pydantic as a dependency.
