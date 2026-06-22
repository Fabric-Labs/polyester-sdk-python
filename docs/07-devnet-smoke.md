# Devnet smoke test

Living guide for live devnet validation. See [10-testing.md](10-testing.md) for the full testing guide.

## Run

```bash
cd polyester-sdk-python
cp .env.example .env
# POLYESTER_API_KEY_ID, POLYESTER_API_PRIVATE_KEY

pip install -e ".[dev,realtime]"
pytest tests/integration tests/e2e -m "integration and not mutation and not funded" -v
```

Or use the backwards-compatible wrapper:

```bash
python scripts/smoke_test.py
```

For mutation tests (post-only order create + cancel):

```bash
POLYESTER_TEST_MUTATION=1 pytest tests/ -m integration -v
```

## Environment

See `.env.example` and `docs/10-testing.md` for the full variable list.

## Common devnet outcomes

- **Funding vs trading:** deposits show in `balances.list` under `funding`; spot orders need `trading` balance.
- **Route not found:** SDK raises `PolyesterRouteNotFoundError` when the gateway returns HTTP 404 for a Connect RPC.
- **Optional routes:** some tests are marked `@pytest.mark.optional` and skip when unavailable.
