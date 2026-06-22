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

## Migrated services (proto decode)

- **orders** — full write/read including batch create/cancel/modify and cancel_all_after
- **trades** — list user trades
- **balances** — list, health, history, equity, holds
- **lifecycle** — list/get/get_by_tx
- **triggers** — full CRUD + events
- **transfers**, **internal_transfers**, **deposit**, **withdraw**
- **api_keys**, **resolve**
- **address_book**, **policies**, **sub_accounts**, **guard_signer**
- **market_data** — trades, candles (spot config still dict bridge for `SpotConfig.raw`)
- **market_overview**, **orderbook**, **heatmap**, **zipper**

## Still on legacy dict bridge

- `market_data.get_spot_config` — returns `SpotConfig(raw=dict)` escape hatch

## Rules

1. **Proto is source of truth** — use `src/polyester/gen` as wire contract.
2. Do not use `MessageToDict` as the hot path for migrated services.
3. Match TS client field naming in public models.
4. Order/trigger ids on the wire are uint64; public API exposes base58 via `format_uint64_id`.
