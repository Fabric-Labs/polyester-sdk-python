# Codec boundary (Python SDK)

## Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| Public API | `polyester.services.*`, `polyester.models` | Stable msgspec types and method signatures |
| Encode | `polyester.codecs.orders`, `ledger`, … | kwargs / models → protobuf requests |
| Transport | `polyester.services._generated` | Connect unary; returns protobuf `Message` |
| Decode (preferred) | `polyester.codecs.decode.*` | protobuf `Message` → public models |
| Decode (legacy) | `polyester.codecs.wire_decode` | JSON-ish dict → public models via `MessageToDict` |

## Preferred path

```
Service method
  → build protobuf request (codecs/* encode helpers)
  → unary_auth_message / unary_public_message
  → decoder(response Message) in codecs/decode/*
  → msgspec model returned to caller
```

Helpers:

- `unary_auth_decoded` / `unary_public_decoded` — pass a `Callable[[TResponse], R]` decoder.
- `proto_helpers` — uint64 base58 ids, u128 strings, enum name normalization.

## Migrated services (proto decode)

- **orders** — list/get/create/cancel/modify/cancel_all/batch_modify
- **trades** — list user trades
- **balances** — `list`, `get_health` (history/equity/holds still use `wire_decode`)
- **lifecycle** — list/get/get_by_tx

## Still on legacy dict bridge

All other services use `unary_auth` / `unary_public` → `protobuf_to_public_dict` → `wire_decode`.

Migrate when touching a service: add `codecs/decode/<domain>.py`, switch the service to `unary_*_decoded`, add unit tests building protobuf messages directly.

## Rules

1. **Proto is source of truth** — no RPCs or fields not in `polyester-python-proto`.
2. Do not use `MessageToDict` as the hot path for migrated services.
3. Match TS client field naming in public models (camelCase in JSON wire is already normalized in models).
4. Order/trigger ids on the wire are uint64; public API exposes base58 via `format_id` / `format_uint64_id`.
