# Dependencies And Release Workflow

## Runtime Dependencies

| Package | Role |
| --- | --- |
| `polyester-python-proto` | Generated protobuf + Connect clients (internal wire contract). |
| `connectrpc` | Connect runtime for generated clients. |
| `protobuf` | Message runtime (must match generated code, currently `>=7.34.1`). |
| `msgspec` | Public SDK structs. |
| `cryptography` | Ed25519 API-key signing. |
| `httpx` | HTTP substrate. |
| `base58` | uint64 ID encoding compatible with TypeScript. |

Optional **`[realtime]`**: `websockets` for Centrifugo subscriptions.

## Proto Package Coupling

Each `polyester-sdk` release must pin a compatible `polyester-python-proto` version:

```toml
# pyproject.toml
dependencies = [
  "polyester-python-proto==0.1.0",  # bump in lockstep when protos change
]
```

Release process:

1. Regenerate / publish `polyester-python-proto` when Buf protos change.
2. Bump the pin in `polyester-sdk` and run full tests + smoke against devnet.
3. Tag both packages (or monorepo paths) with aligned versions in CHANGELOG.

Monorepo dev install:

```bash
pip install -e ../polyester-python-proto
pip install -e ".[dev,realtime]"
```

## Public Repository (Not Open Source)

- Source may be visible on GitHub for Fabric customers and integrators.
- License remains **proprietary** — no OSS redistribution rights unless granted separately.
- Do not commit `.env`, API keys, or customer data.
- CI runs on every PR: `ruff` + `pytest` (see `.github/workflows/ci.yml`).

## PyPI Publishing

- Distribution: `polyester-sdk`
- Import: `polyester`
- Start with alpha versions until trading + realtime slices stabilize.

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

Publish `polyester-python-proto` to PyPI first when wire contracts change, then the SDK.

## Credentials

`POLYESTER_API_KEY_ID` and `POLYESTER_API_PRIVATE_KEY` only. `python-dotenv` is dev-only
(`scripts/smoke_test.py`), not a runtime dependency.
