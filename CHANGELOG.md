# Changelog

## Unreleased

### SDK surface
- Orders: `batch_create`, `batch_cancel`, `cancel_all_after`
- API keys: `create`, `update`, `delete`
- Withdraw: `create_wallet_trading_withdraw`
- Address book: full CRUD, views, whitelist, counterparties
- New services: `policies`, `sub_accounts`, `guard_signer`

### Codecs
- Proto decode migration for balances history/equity/holds, triggers, transfers, deposit, withdraw, internal transfers, api keys, resolve, and public market services

### Testing
- Restructured `tests/unit`, `tests/integration`, `tests/e2e`, `tests/e2e/funded`
- Pytest markers: `integration`, `mutation`, `funded`, `treasury`, `optional`
- `scripts/smoke_test.py` delegates to pytest suite
- `docs/10-testing.md` — local devnet testing guide
- CI: `pytest tests/unit` with coverage on non-`gen/` code

## 0.1.0a0

- Initial alpha release with core trading and market data services.
