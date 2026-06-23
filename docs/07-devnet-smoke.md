# Devnet smoke test

Living guide for live devnet validation. See [10-testing.md](10-testing.md) for the full testing guide.

## Run

```bash
cd polyester-sdk-python
cp .env.example .env
# POLYESTER_API_KEY_ID, POLYESTER_API_PRIVATE_KEY, POLYESTER_ACCOUNT_ID

pip install -e ".[dev,realtime]"

# Recommended: unit + live tiers
./scripts/test_all.sh

# Or explicit pytest
pytest tests/unit -q
pytest tests/integration tests/e2e -m "integration and not mutation and not funded" -v
```

Backwards-compatible wrapper:

```bash
python scripts/smoke_test.py
```

Mutation / funded (set flags in `.env` or export):

```bash
POLYESTER_TEST_MUTATION=1 POLYESTER_TEST_FUNDED=1 pytest tests/ -m integration -v
```

## Expected results

On a typical funded devnet API-key account (2026-06): **~198 passed, ~16 skipped, 0 failed**.

Skips are intentional — see [08-sdk-implementation-status.md](08-sdk-implementation-status.md#what-passes-vs-skips-on-devnet-typical-api-key-account).

## Environment

See `.env.example` and `docs/10-testing.md` for the full variable list.

Key pairs:

- `POLYESTER_TEST_SMOKE_SYMBOL` — read-only smoke (default `ETH-USDT`)
- `POLYESTER_TEST_TRADE_SYMBOL` — order/trigger mutation (e.g. `BTC-USDT`)

## Common devnet outcomes

- **Funding vs trading:** deposits show in `balances.list` under `funding`; spot orders need `trading` balance (USDT for USDT-quoted buys).
- **Order create vs read:** create may return `accepted` while read APIs return empty — known OMS indexing issue; e2e skips with a clear message.
- **Route not found:** SDK raises `PolyesterRouteNotFoundError` when the gateway returns HTTP 404.
- **Optional routes:** tests marked `@pytest.mark.optional` skip when unavailable or JWT-only.
